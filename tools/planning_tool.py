import os
import anthropic # For the sub-Claude call
from pydantic import BaseModel, Field
from typing import Any, Optional
from .tool_base import ToolBase
from loguru import logger

# Ensure API key is available for the sub-client
SUB_CLIENT_API_KEY = os.getenv("CLAUDE_API_KEY")

class GeneratePlanInput(BaseModel):
    prompt_for_plan: str = Field(..., description="A detailed prompt describing the task or problem for which a thinking plan is needed. E.g., 'I need to write a blog post about the benefits of remote work. Give me a plan.'")
    output_file_path: Optional[str] = Field(None, description="Optional. If provided, the generated plan will be saved to this file path. E.g., 'output/my_plan.txt'.")

class PlanningTool(ToolBase):
    name = "create_thinking_plan"
    description = "Generates a thinking plan or a list of steps to address a complex prompt. This tool will call another AI to generate the plan."
    input_schema = GeneratePlanInput

    def _get_sub_client(self):
        if not SUB_CLIENT_API_KEY:
            logger.error("CLAUDE_API_KEY not found for PlanningTool's sub-client.")
            return None
        return anthropic.Anthropic(api_key=SUB_CLIENT_API_KEY)

    def execute(self, prompt_for_plan: str, output_file_path: Optional[str] = None, **kwargs: Any) -> str:
        logger.info(f"PlanningTool: Received request for plan with prompt: '{prompt_for_plan[:50]}...'")
        sub_client = self._get_sub_client()
        if not sub_client:
            return "Error: Sub-client for plan generation could not be initialized due to missing API key."

        plan_generation_prompt = f"""
        Please generate a clear, actionable, step-by-step thinking plan or strategy to address the following request.
        The plan should be easy to follow. Use bullet points or numbered lists for clarity.
        Only output the plan itself, with no other explanatory text or preamble unless it's part of the plan's introduction.
        Request: {prompt_for_plan}
        """

        try:
            logger.debug("Calling sub-Claude for plan generation.")
            # Using a model suitable for structured text generation.
            # User's latest preference was claude-3-5-haiku-20241022, let's try that here.
            response = sub_client.messages.create(
                model="claude-3-haiku-20240307", # Or user specified: "claude-3-5-haiku-20241022"
                max_tokens=2048, 
                messages=[{"role": "user", "content": plan_generation_prompt}]
            )
            logger.debug(f"Sub-Claude plan generation response object: {response}")

            generated_plan = ""
            if response.content and isinstance(response.content, list) and len(response.content) > 0:
                if response.content[0].type == "text":
                    generated_plan = response.content[0].text.strip()
                else:
                    logger.warning("Sub-Claude plan generation did not return a text block as expected.")
                    return "Error: Sub-AI did not return plan in the expected format."
            else:
                logger.warning("Sub-Claude plan generation returned no content.")
                return "Error: Sub-AI returned no content for plan generation."

            if not generated_plan:
                logger.warning("Generated plan is empty after processing.")
                return "Error: Generated plan was empty."

            if output_file_path:
                # Create directory for output_file_path if it doesn't exist
                dir_name = os.path.dirname(output_file_path)
                if dir_name:
                    os.makedirs(dir_name, exist_ok=True)
                with open(output_file_path, "w", encoding="utf-8") as f:
                    f.write(generated_plan)
                logger.success(f"Successfully generated plan and saved to {output_file_path}")
                return f"Successfully generated plan and saved to {output_file_path}. Plan:\n{generated_plan}"
            else:
                logger.success(f"Successfully generated plan.")
                return f"Generated Plan:\n{generated_plan}"

        except anthropic.APIError as e:
            logger.error(f"Sub-Claude API error during plan generation: {e}")
            return f"Error during plan generation (API Error): {e}"
        except Exception as e:
            logger.error(f"Failed to generate or save plan. Error: {e}")
            return f"Failed to generate or save plan. Error: {e}" 