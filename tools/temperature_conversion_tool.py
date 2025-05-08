from pydantic import BaseModel, Field
from enum import Enum
from .tool_base import ToolBase # Relative import
from typing import Any

class TemperatureUnit(str, Enum):
    CELSIUS = "C"
    FAHRENHEIT = "F"

class TemperatureConversionInput(BaseModel):
    value: float = Field(..., description="The temperature value to convert.")
    from_unit: TemperatureUnit = Field(..., description="The unit to convert from (Celsius or Fahrenheit).")
    to_unit: TemperatureUnit = Field(..., description="The unit to convert to (Celsius or Fahrenheit).")

class TemperatureConversionTool(ToolBase):
    name = "convert_temperature"
    description = "Converts temperatures between Celsius (C) and Fahrenheit (F)."
    input_schema = TemperatureConversionInput

    def execute(self, value: float, from_unit: TemperatureUnit, to_unit: TemperatureUnit, **kwargs: Any) -> Any:
        if from_unit == to_unit:
            return value
        if from_unit == TemperatureUnit.CELSIUS and to_unit == TemperatureUnit.FAHRENHEIT:
            return (value * 9/5) + 32
        elif from_unit == TemperatureUnit.FAHRENHEIT and to_unit == TemperatureUnit.CELSIUS:
            return (value - 32) * 5/9
        return "Invalid temperature units for conversion."

# The old schema dictionary is no longer needed here
# temperature_conversion_schema = {
# "name": "convert_temperature",
# "description": "Converts temperatures between Celsius (C) and Fahrenheit (F).",
# "input_schema": TemperatureConversionInput.model_json_schema()
# } 