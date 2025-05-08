from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Dict, Any, Type

class ToolBase(ABC):
    name: str
    description: str
    input_schema: Type[BaseModel]

    @abstractmethod
    def execute(self, **kwargs: Any) -> Any:
        pass

    def get_anthropic_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema.model_json_schema()
        } 