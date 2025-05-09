import os
import anthropic # For the sub-Claude call
from pydantic import BaseModel, Field
from typing import Any
from .tool_base import ToolBase
from loguru import logger

# Ensure API key is available for the sub-client
SUB_CLIENT_API_KEY = os.getenv("CLAUDE_API_KEY")

class GenerateHTMLInput(BaseModel):
    file_path: str = Field(..., description="The full path where the HTML file should be saved, e.g., 'output/my_page.html'.")
    prompt_for_html: str = Field(..., description="A detailed prompt describing the HTML content to be generated. E.g., 'Create a simple landing page for a bakery with a header, a short description, and a contact button.'")

class HTMLGeneratorTool(ToolBase):
    name = "create_html_file"
    description = "Generates an HTML file based on a user prompt and saves it to the specified path. This tool will call another AI to generate the HTML content."
    input_schema = GenerateHTMLInput

    def _get_sub_client(self):
        if not SUB_CLIENT_API_KEY:
            logger.error("CLAUDE_API_KEY not found for HTMLGeneratorTool's sub-client.")
            return None
        return anthropic.Anthropic(api_key=SUB_CLIENT_API_KEY)

    def execute(self, file_path: str, prompt_for_html: str, **kwargs: Any) -> str:
        logger.info(f"HTMLGeneratorTool: Received request to create {file_path} with prompt: '{prompt_for_html[:50]}...'")
        sub_client = self._get_sub_client()
        if not sub_client:
            return "Error: Sub-client for HTML generation could not be initialized due to missing API key."

        html_generation_prompt = f"""
        Please generate complete, well-formed HTML code based on the following request. 
        Only output the HTML code itself, with no other explanatory text, preamble, or markdown code fences. 
        Ensure all tags are properly closed and the structure is valid.
        Include CSS within <style> tags in the <head> if styling is requested or implied by the prompt.
        If JavaScript is needed for simple interactivity as per the prompt, include it within <script> tags at the end of the <body>.
        Request: {prompt_for_html}
        """

        try:
            logger.debug("Calling sub-Claude for HTML generation.")
            # Using a simpler model for potentially faster/cheaper generation if desired, user can tune
            # For now, using the same model family as main agent for consistency, but Haiku is good for this.
            # User's latest preference was claude-3-5-haiku-20241022, let's try that here. If not available, they can change.
            response = sub_client.messages.create(
                model="claude-3-haiku-20240307", # Or user specified: "claude-3-5-haiku-20241022"
                max_tokens=4000, # Allow ample space for HTML
                messages=[{"role": "user", "content": html_generation_prompt}]
            )
            logger.debug(f"Sub-Claude HTML generation response object: {response}")

            generated_html = ""
            if response.content and isinstance(response.content, list) and len(response.content) > 0:
                # Expecting a single text block with the HTML
                if response.content[0].type == "text":
                    generated_html = response.content[0].text
                    # Sometimes Claude might still wrap in ```html ... ``` despite instructions
                    if generated_html.startswith("```html\n"):
                        generated_html = generated_html[len("```html\n"):]
                    if generated_html.endswith("\n```"):
                        generated_html = generated_html[:-len("\n```")]
                    generated_html = generated_html.strip()
                else:
                    logger.warning("Sub-Claude HTML generation did not return a text block as expected.")
                    return "Error: Sub-AI did not return HTML in the expected format."
            else:
                logger.warning("Sub-Claude HTML generation returned no content.")
                return "Error: Sub-AI returned no content for HTML generation."

            if not generated_html:
                logger.warning("Generated HTML content is empty after processing.")
                return "Error: Generated HTML content was empty."

            # Create directory for file_path if it doesn't exist
            dir_name = os.path.dirname(file_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(generated_html)
            
            logger.success(f"Successfully generated and saved HTML to {file_path}")
            return f"Successfully generated HTML and saved to {file_path}. Content length: {len(generated_html)} bytes."

        except anthropic.APIError as e:
            logger.error(f"Sub-Claude API error during HTML generation: {e}")
            return f"Error during HTML generation (API Error): {e}"
        except Exception as e:
            logger.error(f"Failed to generate or save HTML file {file_path}. Error: {e}")
            return f"Failed to generate or save HTML file {file_path}. Error: {e}" 