from pydantic import BaseModel, Field
from .tool_base import ToolBase # Relative import
from typing import Any

class PercentageInput(BaseModel):
    base_number: float = Field(..., description="The number to calculate the percentage of (e.g., 420).")
    percentage: float = Field(..., description="The percentage to apply (e.g., 17 for 17%).")

class PercentageTool(ToolBase):
    name = "calculate_percentage"
    description = "Calculates a percentage of a given number. For example, 'What is 17% of 420?'."
    input_schema = PercentageInput

    def execute(self, base_number: float, percentage: float, **kwargs: Any) -> Any:
        return (percentage / 100) * base_number

# The old schema dictionary is no longer needed here
# percentage_schema = {
# "name": "calculate_percentage",
# "description": "Calculates a percentage of a given number. For example, 'What is 17% of 420?'.",
# "input_schema": PercentageInput.model_json_schema()
# } 