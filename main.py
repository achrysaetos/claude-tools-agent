import anthropic
import asyncio
import os
import dotenv
import sys 
import typing

from tool_executor import ToolExecutor
# Import tool classes from the tools package
from tools import (
    CalculatorTool,
    PercentageTool,
    TemperatureConversionTool,
    TimeConversionTool,
    CreateDirectoryTool,
    HTMLGeneratorTool,
    PlanningTool,
    # Enums are not strictly needed here for registration but good for clarity if used directly
    # TemperatureUnit, 
    # TimeUnit
)

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.live import Live
from rich.spinner import Spinner
from loguru import logger

# --- Loguru Configuration ---
logger.remove() 
logger.add(sys.stderr, level="ERROR") # Only errors and critical to console
logger.add("calc_agent.log", rotation="10 MB", level="DEBUG") 
# ---

# --- Rich Console Initialization ---
console = Console()
# ---

dotenv.load_dotenv()

# --- Anthropic Client Initialization ---
# It's good practice to check if the API key exists
api_key = os.getenv("CLAUDE_API_KEY")
if not api_key:
    logger.critical("CLAUDE_API_KEY not found in environment variables.")
    console.print("[bold red]Error: CLAUDE_API_KEY not found. Please set it in your .env file.[/bold red]")
    sys.exit(1)
client = anthropic.Anthropic(api_key=api_key)
# ---

# --- ToolExecutor Initialization and Tool Registration ---
tool_executor = ToolExecutor()
tool_executor.register_tool(CalculatorTool())
tool_executor.register_tool(PercentageTool())
tool_executor.register_tool(TemperatureConversionTool())
tool_executor.register_tool(TimeConversionTool())
tool_executor.register_tool(CreateDirectoryTool())
tool_executor.register_tool(HTMLGeneratorTool())
tool_executor.register_tool(PlanningTool())
# ---

MAX_TOOL_ITERATIONS_PER_TURN = 5 # Max tool uses before forcing a text response or ending turn

async def execute_conversation_turn(messages_for_api: list, system_prompt: typing.Optional[str] = None) -> list:
    """Processes a single turn, appends assistant's response to messages_for_api and returns it."""
    logger.debug(f"Executing turn. Current messages for API depth: {len(messages_for_api)}")
    logger.debug(f"Messages before API call: {messages_for_api}")
    if system_prompt:
        logger.debug(f"Using system prompt for this turn: {system_prompt}")

    for _ in range(MAX_TOOL_ITERATIONS_PER_TURN):
        assistant_response_content_blocks = []
        full_claude_response_obj = None
        text_generated_this_iteration = False
        tool_calls_made_this_iteration = False

        with Live(Spinner("dots", text="Claude is thinking..."), console=console, transient=True, refresh_per_second=10):
            try:
                api_params = {
                    "model": "claude-3-haiku-20240307", # Reverted to a known good model for now, user can change back
                    "max_tokens": 2048, # Reverted for now
                    "tools": tool_executor.get_all_tool_schemas(),
                    "messages": messages_for_api, # Use the passed list directly for the API call
                }
                if system_prompt:
                    api_params["system"] = system_prompt
                
                full_claude_response_obj = client.messages.create(**api_params)
                logger.debug(f"Claude raw response object: {full_claude_response_obj}")
            except anthropic.APIError as e:
                logger.error(f"Anthropic API Error: {e}")
                console.print(Panel(f"[bold red]API Error:[/bold red] {e}", title="[bold red]Error[/bold red]"))
                messages_for_api.append({"role": "assistant", "content": [{"type": "text", "text": f"I encountered an API error: {e}"}]})
                return messages_for_api 
        
        if not full_claude_response_obj or not full_claude_response_obj.content:
            logger.warning("Received empty or no content from Claude.")
            console.print(Panel("Claude returned an empty response.", title="[bold red]System Message[/bold red]"))
            messages_for_api.append({"role": "assistant", "content": [{"type": "text", "text": "I received an empty response from the model."}]})
            return messages_for_api

        for content_block in full_claude_response_obj.content:
            if content_block.type == "text":
                console.print(Panel(content_block.text, title="[bold green]Claude[/bold green]"))
                logger.info(f"Claude says: {content_block.text}")
                assistant_response_content_blocks.append({"type": "text", "text": content_block.text})
                text_generated_this_iteration = True
            elif content_block.type == "tool_use":
                tool_calls_made_this_iteration = True
                logger.info(f"Claude requests tool: {content_block.name} with input: {content_block.input}")
                try:
                    tool_input_str = Syntax(str(content_block.input), "json", theme="paraiso-dark", line_numbers=True, background_color="#2b2b2b")
                    console.print(Panel(tool_input_str, title=f"[bold yellow]Tool Call Requested: {content_block.name}[/bold yellow]"))
                except Exception:
                    console.print(Panel(str(content_block.input), title=f"[bold yellow]Tool Call Requested: {content_block.name}[/bold yellow]"))
                assistant_response_content_blocks.append({"type": "tool_use", "id": content_block.id, "name": content_block.name, "input": content_block.input})
        
        if assistant_response_content_blocks:
            messages_for_api.append({"role": "assistant", "content": assistant_response_content_blocks})
            logger.debug(f"Appended assistant response to messages_for_api: {assistant_response_content_blocks}")

        if full_claude_response_obj.stop_reason == "tool_use":
            tool_results_for_next_iteration = []
            actual_tool_use_found = False
            # Iterate over the assistant message we *just added* to messages_for_api
            last_assistant_message_content = messages_for_api[-1]["content"]
            for block in last_assistant_message_content:
                if block["type"] == "tool_use":
                    actual_tool_use_found = True
                    tool_name = block["name"]
                    tool_input = block["input"]
                    tool_use_id = block["id"]
                    
                    logger.info(f"Executing tool: {tool_name} with input: {tool_input}")
                    result = tool_executor.execute_tool(tool_name, **tool_input)
                    logger.info(f"Tool '{tool_name}' result: {result}")
                    console.print(Panel(str(result), title=f"[bold magenta]Tool Result: {tool_name}[/bold magenta]"))
                    
                    tool_results_for_next_iteration.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": str(result), 
                    })
            
            if actual_tool_use_found and tool_results_for_next_iteration:
                messages_for_api.append({"role": "user", "content": tool_results_for_next_iteration})
                logger.debug(f"Appended tool results for next API call: {tool_results_for_next_iteration}")
                # Continue loop for Claude to process tool results
            else: # No tool use found, or no results generated. Stop this turn.
                logger.warning("Tool use indicated by stop_reason, but no valid tool calls/results processed. Ending turn.")
                return messages_for_api 
        
        elif full_claude_response_obj.stop_reason in ["end_turn", "max_tokens"]:
            if not text_generated_this_iteration and not tool_calls_made_this_iteration:
                 logger.warning(f"Claude returned no text and no tool calls. Stop reason: {full_claude_response_obj.stop_reason}")
                 # Ensure assistant says something if it truly produced nothing textual after stop_reason=end_turn
                 # Check if the last message was already an empty one from us
                 if not (messages_for_api and messages_for_api[-1]["role"] == "assistant" and 
                         any(c.get("text") == "I received an empty response from the model." or c.get("text") == "I didn't produce a textual response for that." for c in messages_for_api[-1]["content"])):
                    no_text_msg = "I didn't produce a textual response for that."
                    messages_for_api.append({"role": "assistant", "content": [{"type": "text", "text": no_text_msg}]})
            logger.success(f"Turn ended. Stop reason: {full_claude_response_obj.stop_reason}")
            return messages_for_api 
        else:
            logger.error(f"Unhandled stop reason: {full_claude_response_obj.stop_reason}")
            console.print(Panel(f"Unhandled stop reason: {full_claude_response_obj.stop_reason}", title="[bold red]System Error[/bold red]"))
            return messages_for_api 

    logger.warning(f"Reached max tool iterations ({MAX_TOOL_ITERATIONS_PER_TURN}) for this turn.")
    console.print(Panel(f"Reached max tool iterations ({MAX_TOOL_ITERATIONS_PER_TURN}).", title="[bold orange]System Warning[/bold orange]"))
    return messages_for_api

async def main_repl():
    console.print(Panel("[bold]Calc Agent Initializing...[/bold]", title_align="center"))
    
    overall_messages_history = [] # This will maintain the full conversation history

    welcome_system_prompt = "You are a helpful and friendly assistant. Start your very first message with the exact phrase: 'Welcome, I am your assistant!'. After this greeting, you can ask how you can help or wait for their first query. Do not use any tools for this initial greeting."
    logger.info(f"Defined system prompt for welcome: {welcome_system_prompt}")

    # Prepare messages for the very first API call (welcome message)
    initial_user_greeting_message = {"role": "user", "content": "Greetings, assistant!"}
    messages_for_welcome_call = [initial_user_greeting_message]
    logger.info(f"Messages for welcome call: {messages_for_welcome_call}")

    console.print(Panel("[italic]Claude is preparing its welcome message...[/italic]"))
    # Get the welcome response; execute_conversation_turn will append Claude's response to messages_for_welcome_call
    updated_messages_after_welcome = await execute_conversation_turn(messages_for_welcome_call, system_prompt=welcome_system_prompt)
    overall_messages_history.extend(updated_messages_after_welcome) # Add the initial exchange to overall history

    console.print(Panel("[bold cyan]Interactive session started. Type 'exit' to end.[/bold cyan]"))

    loop = asyncio.get_event_loop()
    while True:
        try:
            user_input = await loop.run_in_executor(None, console.input, "[bold cyan]Leck[/bold cyan]: ")
        except KeyboardInterrupt:
            console.print("\n[bold orange]Exiting on KeyboardInterrupt...[/bold orange]")
            break
        except EOFError: 
            console.print("\n[bold orange]Exiting on EOF...[/bold orange]")
            break

        if user_input.strip().lower() == "exit":
            console.print("[bold orange]Exiting agent.[/bold orange]")
            break
        
        if not user_input.strip(): 
            continue

        logger.info(f"User REPL Input: {user_input}")
        overall_messages_history.append({"role": "user", "content": user_input})
        
        # Pass the current state of overall_messages_history for the API call
        # execute_conversation_turn will modify and return it
        overall_messages_history = await execute_conversation_turn(overall_messages_history) 

if __name__ == "__main__":
    try:
        asyncio.run(main_repl())
    except Exception as e:
        logger.critical(f"Unhandled exception in main_repl: {e}", exc_info=True)
        console.print(Panel(f"[bold red]Critical Error in REPL:[/bold red] {e}", title="[bold red]System Failure[/bold red]"))