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
# ---

MAX_TOOL_ITERATIONS_PER_TURN = 5 # Max tool uses before forcing a text response or ending turn

async def execute_conversation_turn(messages_history: list, system_prompt: typing.Optional[str] = None):
    """Processes a single turn of the conversation, handling tool use if necessary."""
    logger.debug(f"Executing turn. Current history depth: {len(messages_history)}")
    logger.debug(f"Messages before API call: {messages_history}")
    if system_prompt:
        logger.debug(f"Using system prompt for this turn: {system_prompt}")

    # The loop here is to handle sequential tool use if Claude decides to use multiple tools
    # or make multiple attempts before a final answer for *this specific user input*.
    for _ in range(MAX_TOOL_ITERATIONS_PER_TURN):
        assistant_response_content_blocks = [] # To build the assistant's turn
        full_claude_response_obj = None
        text_generated_this_iteration = False
        tool_calls_made_this_iteration = False

        with Live(Spinner("dots", text="Claude is thinking..."), console=console, transient=True, refresh_per_second=10) as live_spinner:
            try:
                api_params = {
                    "model": "claude-3-5-haiku-20241022",
                    "max_tokens": 4096,
                    "tools": tool_executor.get_all_tool_schemas(),
                    "messages": messages_history,
                }
                if system_prompt:
                    api_params["system"] = system_prompt
                
                full_claude_response_obj = client.messages.create(**api_params)
                logger.debug(f"Claude raw response object: {full_claude_response_obj}")
            except anthropic.APIError as e:
                logger.error(f"Anthropic API Error: {e}")
                console.print(Panel(f"[bold red]API Error:[/bold red] {e}", title="[bold red]Error[/bold red]"))
                # Add error as assistant message to history IF it makes sense for the flow
                # For now, we return and let the REPL decide if it wants to retry or inform user.
                # If we add to history, ensure it's in the correct format.
                # messages_history.append({"role": "assistant", "content": [{"type": "text", "text": f"I encountered an API error: {e}"}]}) 
                return # Indicate failure to the caller
        
        if not full_claude_response_obj or not full_claude_response_obj.content:
            logger.warning("Received empty or no content from Claude.")
            console.print(Panel("Claude returned an empty response.", title="[bold red]System Message[/bold red]"))
            # Add an assistant message indicating this empty response to history
            messages_history.append({"role": "assistant", "content": [{"type": "text", "text": "I received an empty response from the model."}]})
            return

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
        
        # Append Claude's response (text and/or tool uses) to history
        if assistant_response_content_blocks:
            messages_history.append({"role": "assistant", "content": assistant_response_content_blocks})
            logger.debug(f"Appended assistant response to history: {assistant_response_content_blocks}")

        if full_claude_response_obj.stop_reason == "tool_use":
            tool_results_for_next_iteration = []
            actual_tool_use_found = False
            for block in assistant_response_content_blocks: # Iterate over what we just added
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
                messages_history.append({"role": "user", "content": tool_results_for_next_iteration}) # This is a "user" message containing tool_results
                logger.debug(f"Appended tool results to messages for next iteration: {tool_results_for_next_iteration}")
                # Continue the loop to let Claude process the tool results
            elif not actual_tool_use_found:
                logger.warning("Stop reason was tool_use, but no tool_use blocks found in THIS assistant message. Breaking tool loop.")
                # This case should be rare if API is consistent.
                # If there was text, it was printed. If not, Claude might be stuck.
                return # Exit turn processing
            else: # tool use indicated but no results generated (e.g. all tools failed internally without throwing to executor)
                logger.warning("Tool use indicated but no tool results generated. Breaking tool loop.")
                return # Exit turn processing
        
        elif full_claude_response_obj.stop_reason in ["end_turn", "max_tokens"]:
            if not text_generated_this_iteration and not tool_calls_made_this_iteration:
                 logger.warning(f"Claude returned an empty or unexpected response. Stop reason: {full_claude_response_obj.stop_reason}")
                 if not any(c.type == 'text' for c in assistant_response_content_blocks):
                    # Ensure assistant says something if it truly produced nothing textual after stop_reason=end_turn
                    no_text_msg = "I didn't produce a textual response for that."
                    messages_history.append({"role": "assistant", "content": [{"type": "text", "text": no_text_msg}]})
                    # console.print(Panel(no_text_msg, title="[bold red]System Message[/bold red]")) # Already handled by empty response check earlier potentially
            # If there was text or even just a tool call request that didn't result in further tool_use stop_reason,
            # it means this iteration is Claude's final response for the user's query.
            logger.success(f"Turn ended. Stop reason: {full_claude_response_obj.stop_reason}")
            return # Exit the turn processing, back to REPL for new user input
        else:
            logger.error(f"Unhandled stop reason: {full_claude_response_obj.stop_reason}")
            console.print(Panel(f"Unhandled stop reason: {full_claude_response_obj.stop_reason}", title="[bold red]System Error[/bold red]"))
            return # Exit turn processing

    # If loop finishes due to MAX_TOOL_ITERATIONS_PER_TURN
    logger.warning(f"Reached max tool iterations ({MAX_TOOL_ITERATIONS_PER_TURN}) for this turn.")
    console.print(Panel(f"Reached max tool iterations ({MAX_TOOL_ITERATIONS_PER_TURN}). Claude will now attempt to respond without further tools.", title="[bold orange]System Warning[/bold orange]"))
    # Optionally, send one last message to Claude asking it to summarize or respond without tools.
    # For simplicity now, we just return, and the REPL will await new user input. The history contains the last state.


async def main_repl():
    console.print(Panel("[bold]Calc Agent Initializing...[/bold]", title_align="center"))
    messages_history = []

    # 1. System prompt for welcome message
    welcome_system_prompt = "You are a helpful and friendly assistant. Your user is named Leck. Start your very first message with the exact phrase: 'Welcome, Leck, I am your assistant!'. After this greeting, you can ask how you can help or wait for Leck's first query. Do not use any tools for this initial greeting."
    messages_history.append({"role": "system", "content": welcome_system_prompt})
    logger.info(f"Added system prompt for welcome: {welcome_system_prompt}")

    # 2. Dummy user message to trigger the welcome
    initial_user_greeting = "Greetings, assistant!"
    messages_history.append({"role": "user", "content": initial_user_greeting})
    logger.info(f"Added initial dummy user greeting: {initial_user_greeting}")

    # 3. Get Claude's welcome message
    console.print(Panel("[italic]Claude is preparing its welcome message...[/italic]"))
    await execute_conversation_turn(messages_history, system_prompt=welcome_system_prompt)
    # The welcome message should have been printed by execute_conversation_turn and added to history.

    console.print(Panel("[bold cyan]Interactive session started. Type 'exit' to end.[/bold cyan]"))

    # 4. Main REPL loop
    while True:
        try:
            user_input = await asyncio.to_thread(console.input, "[bold cyan]Leck[/bold cyan]: ")
        except KeyboardInterrupt:
            console.print("\n[bold orange]Exiting on KeyboardInterrupt...[/bold orange]")
            break
        except EOFError: # Happens if stdin is closed, e.g. piping input
            console.print("\n[bold orange]Exiting on EOF...[/bold orange]")
            break

        if user_input.strip().lower() == "exit":
            console.print("[bold orange]Exiting agent.[/bold orange]")
            break
        
        if not user_input.strip(): # Handle empty input
            continue

        logger.info(f"User REPL Input: {user_input}")
        messages_history.append({"role": "user", "content": user_input})
        
        await execute_conversation_turn(messages_history)
        # The execute_conversation_turn now appends all its work to messages_history directly
        # and prints output using the console.

if __name__ == "__main__":
    try:
        asyncio.run(main_repl())
    except Exception as e:
        logger.critical(f"Unhandled exception in main_repl: {e}", exc_info=True)
        console.print(Panel(f"[bold red]Critical Error in REPL:[/bold red] {e}", title="[bold red]System Failure[/bold red]"))