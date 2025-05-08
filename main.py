import anthropic
import asyncio
import os
import dotenv

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
    print(f"\nUser: {query_string}")
    messages = [{"role": "user", "content": query_string}]
    
    while True:
        response = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=2048,
            tools=tool_executor.get_all_tool_schemas(), # ToolExecutor now provides schemas
            messages=messages,
        )

        assistant_response_content = []
        has_text_response = False

        for content_block in response.content:
            if content_block.type == "text":
                print(f"Claude: {content_block.text}")
                assistant_response_content.append({"type": "text", "text": content_block.text})
                has_text_response = True
            elif content_block.type == "tool_use":
                assistant_response_content.append({"type": "tool_use", "id": content_block.id, "name": content_block.name, "input": content_block.input})

        messages.append({"role": "assistant", "content": assistant_response_content})

        if response.stop_reason == "tool_use":
            tool_results_content = []
            for content_block in response.content:
                if content_block.type == "tool_use":
                    tool_name = content_block.name
                    tool_input = content_block.input # This is a dict
                    tool_use_id = content_block.id
                    
                    print(f"Tool Used: {tool_name}, Input: {tool_input}")

                    # Execute tool using ToolExecutor
                    # ToolExecutor now handles validation and passing kwargs to the tool's execute method
                    result = tool_executor.execute_tool(tool_name, **tool_input)
                    
                    print(f"Tool Result: {result}")
                    tool_results_content.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": str(result), # Ensure result is stringified for Anthropic API
                    })
            
            if tool_results_content:
                 messages.append({
                    "role": "user",
                    "content": tool_results_content
                })
        
        elif has_text_response and response.stop_reason in ["end_turn", "max_tokens"]:
            final_answer = ""
            for block in assistant_response_content:
                if block["type"] == "text":
                    final_answer += block["text"] + " "
            return final_answer.strip()
        
        elif not has_text_response and response.stop_reason in ["end_turn", "max_tokens"]:
            # Check if there was any tool use either, if not, it's an empty response
            if not any(block.get("type") == "tool_use" for block in assistant_response_content):
                 print("Claude returned an empty or unexpected response. Ending conversation.")
                 return "Sorry, I couldn't process that."
        
        if len(messages) > 10: # Max conversation turns
            print("Reached max conversation turns. Ending.")
            # Attempt to return any partial text response if available
            final_answer = ""
            for block in assistant_response_content:
                if block["type"] == "text":
                    final_answer += block["text"] + " "
            if final_answer.strip():
                return final_answer.strip()
            return "Sorry, I couldn't resolve that in a few steps."


if __name__ == "__main__":
    async def main():
        # Test cases
        queries = [
            "What's 17% of 420?",
            "Convert 100°F to Celsius.",
            "How many seconds are there in 3.5 days?",
            "Calculate 10 + 5",
            "What is the capital of France?" # Non-tool query
        ]

        for q in queries:
            try:
                result = await query(q)
                print(f"Final Answer: {result}")
            except Exception as e:
                print(f"Error processing query '{q}': {e}")
            print("-" * 20)

    asyncio.run(main())