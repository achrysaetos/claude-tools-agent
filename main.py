import anthropic
import asyncio
import os
import dotenv

dotenv.load_dotenv()

client = anthropic.Anthropic(
    api_key=os.getenv("CLAUDE_API_KEY"),
)

# Tool Schemas
calculator_schema = {
    "name": "calculate",
    "description": "A calculator for basic arithmetic operations: addition (+), subtraction (-), multiplication (*), and division (/).",
    "input_schema": {
        "type": "object",
        "properties": {
            "num1": {"type": "number", "description": "The first number."},
            "num2": {"type": "number", "description": "The second number."},
            "operator": {
                "type": "string",
                "description": "The operator to use, one of ['+', '-', '*', '/'].",
            },
        },
        "required": ["num1", "num2", "operator"],
    },
}

percentage_schema = {
    "name": "calculate_percentage",
    "description": "Calculates a percentage of a given number. For example, 'What is 17% of 420?'.",
    "input_schema": {
        "type": "object",
        "properties": {
            "base_number": {"type": "number", "description": "The number to calculate the percentage of (e.g., 420)."},
            "percentage": {"type": "number", "description": "The percentage to apply (e.g., 17 for 17%)."}
        },
        "required": ["base_number", "percentage"]
    }
}

temperature_conversion_schema = {
    "name": "convert_temperature",
    "description": "Converts temperatures between Celsius (C) and Fahrenheit (F).",
    "input_schema": {
        "type": "object",
        "properties": {
            "value": {"type": "number", "description": "The temperature value to convert."},
            "from_unit": {"type": "string", "enum": ["C", "F"], "description": "The unit to convert from (Celsius or Fahrenheit)."},
            "to_unit": {"type": "string", "enum": ["C", "F"], "description": "The unit to convert to (Celsius or Fahrenheit)."}
        },
        "required": ["value", "from_unit", "to_unit"]
    }
}

time_conversion_schema = {
    "name": "convert_time",
    "description": "Converts time durations between seconds, minutes, hours, and days.",
    "input_schema": {
        "type": "object",
        "properties": {
            "value": {"type": "number", "description": "The time value to convert."},
            "from_unit": {"type": "string", "enum": ["seconds", "minutes", "hours", "days"], "description": "The unit to convert from."},
            "to_unit": {"type": "string", "enum": ["seconds", "minutes", "hours", "days"], "description": "The unit to convert to."}
        },
        "required": ["value", "from_unit", "to_unit"]
    }
}

all_tools = [calculator_schema, percentage_schema, temperature_conversion_schema, time_conversion_schema]

# Tool implementations
def calculate(num1: float, num2: float, operator: str):
    if operator == "+":
        return num1 + num2
    elif operator == "-":
        return num1 - num2
    elif operator == "*":
        return num1 * num2
    elif operator == "/":
        if num2 == 0:
            return "Error: Division by zero"
        return num1 / num2
    else:
        return "Invalid operator"

def calculate_percentage(base_number: float, percentage: float):
    return (percentage / 100) * base_number

def convert_temperature(value: float, from_unit: str, to_unit: str):
    if from_unit == to_unit:
        return value
    if from_unit == "C" and to_unit == "F":
        return (value * 9/5) + 32
    elif from_unit == "F" and to_unit == "C":
        return (value - 32) * 5/9
    return "Invalid temperature units for conversion."

def convert_time(value: float, from_unit: str, to_unit: str):
    if from_unit == to_unit:
        return value

    # Conversion factors to seconds
    to_seconds_factors = {
        "seconds": 1,
        "minutes": 60,
        "hours": 3600,
        "days": 86400
    }

    if from_unit not in to_seconds_factors or to_unit not in to_seconds_factors:
        return "Invalid time units for conversion."

    value_in_seconds = value * to_seconds_factors[from_unit]
    
    return value_in_seconds / to_seconds_factors[to_unit]


async def query(query_string: str):
    print(f"\nUser: {query_string}")
    messages = [{"role": "user", "content": query_string}]
    
    while True:
        response = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=2048,
            tools=all_tools,
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
                    tool_input = content_block.input
                    tool_use_id = content_block.id
                    
                    print(f"Tool Used: {tool_name}, Input: {tool_input}")

                    result = None
                    if tool_name == "calculate":
                        result = calculate(
                            num1=float(tool_input["num1"]), 
                            num2=float(tool_input["num2"]), 
                            operator=tool_input["operator"]
                        )
                    elif tool_name == "calculate_percentage":
                        result = calculate_percentage(
                            base_number=float(tool_input["base_number"]), 
                            percentage=float(tool_input["percentage"])
                        )
                    elif tool_name == "convert_temperature":
                        result = convert_temperature(
                            value=float(tool_input["value"]),
                            from_unit=tool_input["from_unit"],
                            to_unit=tool_input["to_unit"]
                        )
                    elif tool_name == "convert_time":
                        result = convert_time(
                            value=float(tool_input["value"]),
                            from_unit=tool_input["from_unit"],
                            to_unit=tool_input["to_unit"]
                        )
                    
                    print(f"Tool Result: {result}")
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
        
        elif has_text_response and response.stop_reason in ["end_turn", "max_tokens"]:
            final_answer = ""
            for block in assistant_response_content:
                if block["type"] == "text":
                    final_answer += block["text"] + " "
            return final_answer.strip()
        
        elif not has_text_response and response.stop_reason in ["end_turn", "max_tokens"]:
            if not any(block.type == "tool_use" for block in response.content):
                 print("Claude returned an empty or unexpected response. Ending conversation.")
                 return "Sorry, I couldn't process that."
        
        if len(messages) > 10:
            print("Reached max conversation turns. Ending.")
            return "Sorry, I couldn't resolve that in a few steps."


if __name__ == "__main__":
    async def main():
        result2 = await query("What's 17% of 420?")
        print(f"Final Answer: {result2}")

        result3 = await query("Convert 100°F to Celsius.")
        print(f"Final Answer: {result3}")

        result4 = await query("How many seconds are there in 3.5 days?")
        print(f"Final Answer: {result4}")

        result6 = await query("What is the capital of France?")
        print(f"Final Answer: {result6}")

    asyncio.run(main())