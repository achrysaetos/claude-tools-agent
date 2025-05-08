from typing import Dict, Any, List
from tools.tool_base import ToolBase

class ToolExecutor:
    def __init__(self):
        self.tools: Dict[str, ToolBase] = {}

    def register_tool(self, tool_instance: ToolBase):
        if not isinstance(tool_instance, ToolBase):
            raise ValueError("Provided tool must be an instance of a class derived from ToolBase")
        self.tools[tool_instance.name] = tool_instance
        print(f"Registered tool: {tool_instance.name}")

    def execute_tool(self, name: str, **kwargs: Any) -> Any:
        if name not in self.tools:
            return f"Error: Tool '{name}' not found."
        
        tool_instance = self.tools[name]
        # Validate kwargs against the tool's input_schema Pydantic model
        try:
            # The input for the tool execute method will be the validated and parsed model
            # For Pydantic v2, it's model_validate, for v1 it was parse_obj
            # Assuming Pydantic v2+ as it's more current
            validated_input = tool_instance.input_schema.model_validate(kwargs) 
        except Exception as e: # Catches Pydantic ValidationError
             return f"Error: Invalid input for tool '{name}'. Details: {e}"

        try:
            # Pass the validated and structured input to the tool's execute method
            # Pydantic model_dump() converts the model instance to a dict
            return tool_instance.execute(**validated_input.model_dump()) 
        except Exception as e:
            return f"Error executing tool '{name}': {e}"

    def get_all_tool_schemas(self) -> List[Dict[str, Any]]:
        return [tool.get_anthropic_schema() for tool in self.tools.values()] 