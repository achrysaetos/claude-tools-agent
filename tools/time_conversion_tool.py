from pydantic import BaseModel, Field
from enum import Enum
from .tool_base import ToolBase # Relative import
from typing import Any

class TimeUnit(str, Enum):
    SECONDS = "seconds"
    MINUTES = "minutes"
    HOURS = "hours"
    DAYS = "days"

class TimeConversionInput(BaseModel):
    value: float = Field(..., description="The time value to convert.")
    from_unit: TimeUnit = Field(..., description="The unit to convert from.")
    to_unit: TimeUnit = Field(..., description="The unit to convert to.")

class TimeConversionTool(ToolBase):
    name = "convert_time"
    description = "Converts time durations between seconds, minutes, hours, and days."
    input_schema = TimeConversionInput

    def execute(self, value: float, from_unit: TimeUnit, to_unit: TimeUnit, **kwargs: Any) -> Any:
        if from_unit == to_unit:
            return value

        to_seconds_factors = {
            TimeUnit.SECONDS: 1,
            TimeUnit.MINUTES: 60,
            TimeUnit.HOURS: 3600,
            TimeUnit.DAYS: 86400
        }

        if from_unit not in to_seconds_factors or to_unit not in to_seconds_factors:
            return "Invalid time units for conversion."

        value_in_seconds = value * to_seconds_factors[from_unit]
        
        return value_in_seconds / to_seconds_factors[to_unit]

# The old schema dictionary is no longer needed here
# time_conversion_schema = {
# "name": "convert_time",
# "description": "Converts time durations between seconds, minutes, hours, and days.",
# "input_schema": TimeConversionInput.model_json_schema()
# } 