import anthropic
import asyncio
import os
import dotenv
import sys # For loguru configuration

from tool_executor import ToolExecutor
# Import tool classes from the tools package
from tools import (
    CalculatorTool,
    PercentageTool,
    TemperatureConversionTool,
    TimeConversionTool,
    # Enums are not strictly needed here for registration but good for clarity if used directly
    # TemperatureUnit, 
    # TimeUnit
)

# Import rich and loguru
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from loguru import logger

# --- Loguru Configuration ---
logger.remove() # Remove default handler
logger.add(sys.stderr, level="INFO") # Default level for console
logger.add("calc_agent.log", rotation="10 MB", level="DEBUG") # Log file
# ---

# --- Rich Console Initialization ---
console = Console()
# ---

dotenv.load_dotenv()

client = anthropic.Anthropic(
    api_key=os.getenv("CLAUDE_API_KEY"),
)

# Initialize ToolExecutor
tool_executor = ToolExecutor()

# Instantiate and register tools
tool_executor.register_tool(CalculatorTool())
tool_executor.register_tool(PercentageTool())
tool_executor.register_tool(TemperatureConversionTool())
tool_executor.register_tool(TimeConversionTool())

async def query(query_string: str):
    console.print(Panel(query_string, title="[bold blue]User Query[/bold blue]"))
    logger.info(f"User Query: {query_string}")
    messages = [{"role": "user", "content": query_string}]
    
    MAX_TURNS = 5 # Define max turns to avoid overly long conversations

    for turn in range(MAX_TURNS):
        logger.debug(f"Conversation turn {turn + 1}. Messages so far: {messages}")
        response = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=2048,
            tools=tool_executor.get_all_tool_schemas(),
            messages=messages,
        )
        logger.debug(f"Claude raw response: {response}")

        assistant_response_content = []
        has_text_response = False

        for content_block in response.content:
            if content_block.type == "text":
                console.print(Panel(content_block.text, title="[bold green]Claude[/bold green]"))
                logger.info(f"Claude says: {content_block.text}")
                assistant_response_content.append({"type": "text", "text": content_block.text})
                has_text_response = True
            elif content_block.type == "tool_use":
                logger.info(f"Claude requests tool: {content_block.name} with input: {content_block.input}")
                # Pretty print tool use request with rich.syntax if possible (for JSON-like input)
                try:
                    tool_input_str = Syntax(str(content_block.input), "json", theme="native", line_numbers=True)
                    console.print(Panel(tool_input_str, title=f"[bold yellow]Tool Call Requested: {content_block.name}[/bold yellow]"))
                except Exception:
                    console.print(Panel(str(content_block.input), title=f"[bold yellow]Tool Call Requested: {content_block.name}[/bold yellow]"))
                
                assistant_response_content.append({"type": "tool_use", "id": content_block.id, "name": content_block.name, "input": content_block.input})

        messages.append({"role": "assistant", "content": assistant_response_content})

        if response.stop_reason == "tool_use":
            tool_results_content = []
            for content_block in response.content:
                if content_block.type == "tool_use":
                    tool_name = content_block.name
                    tool_input = content_block.input 
                    tool_use_id = content_block.id
                    
                    logger.info(f"Executing tool: {tool_name} with input: {tool_input}")
                    
                    result = tool_executor.execute_tool(tool_name, **tool_input)
                    logger.info(f"Tool '{tool_name}' result: {result}")
                    console.print(Panel(str(result), title=f"[bold magenta]Tool Result: {tool_name}[/bold magenta]"))
                    
                    tool_results_content.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": str(result), 
                    })
            
            if tool_results_content:
                 messages.append({
                    "role": "user",
                    "content": tool_results_content
                })
                 logger.debug(f"Appended tool results to messages: {tool_results_content}")
            else:
                logger.warning("Tool use indicated by stop_reason, but no tool_use blocks found in content.")
        
        elif has_text_response and response.stop_reason in ["end_turn", "max_tokens"]:
            final_answer = ""
            for block in assistant_response_content:
                if block["type"] == "text":
                    final_answer += block["text"] + " "
            logger.success(f"Final answer from Claude: {final_answer.strip()}")
            return final_answer.strip()
        
        elif not has_text_response and response.stop_reason in ["end_turn", "max_tokens"]:
            if not any(block.get("type") == "tool_use" for block in assistant_response_content):
                 logger.warning("Claude returned an empty or unexpected response (no text, no tool_use). Ending conversation.")
                 console.print(Panel("Claude returned an empty response.", title="[bold red]System Message[/bold red]"))
                 return "Sorry, I couldn't process that."
            else:
                logger.debug("Response has tool_use but no text, continuing loop for tool execution.")

    # If loop finishes due to MAX_TURNS
    logger.warning(f"Reached max conversation turns ({MAX_TURNS}). Ending.")
    console.print(Panel(f"Reached max conversation turns ({MAX_TURNS}).", title="[bold red]System Message[/bold red]"))
    # Attempt to return any partial text response if available
    final_answer = ""
    for block in assistant_response_content:
        if block.get("type") == "text":
            final_answer += block["text"] + " "
    if final_answer.strip():
        logger.info(f"Returning partial answer after max turns: {final_answer.strip()}")
        return final_answer.strip()
    return "Sorry, I couldn't resolve that in a few steps."


if __name__ == "__main__":
    async def main():
        queries = [
            "What's 17% of 420?",
            "Convert 100°F to Celsius.",
            "How many seconds are there in 3.5 days?",
            "Calculate 10 + 5",
            "What is the capital of France?",
            "Calculate 10 / 0" # Test error handling in tool
        ]

        for q in queries:
            try:
                result = await query(q)
                # Final answer is already printed by rich within query function if successful
                # console.print(Panel(result, title="[bold cyan]Final Answer[/bold cyan]"))
            except Exception as e:
                logger.error(f"Unhandled error processing query '{q}': {e}", exc_info=True)
                console.print(Panel(f"An unexpected error occurred: {e}", title="[bold red]System Error[/bold red]"))
            console.print("-" * 40)

    asyncio.run(main())