import os
from pydantic import BaseModel, Field
from typing import Any
from .tool_base import ToolBase # Corrected relative import
from loguru import logger

class CreateDirectoryInput(BaseModel):
    directory_path: str = Field(..., description="The full path of the directory to create. E.g., 'path/to/my_new_directory'.")

class CreateDirectoryTool(ToolBase):
    name = "create_directory"
    description = "Creates a new directory at the specified path. If intermediate directories do not exist, they will also be created."
    input_schema = CreateDirectoryInput

    def execute(self, directory_path: str, **kwargs: Any) -> str:
        try:
            os.makedirs(directory_path, exist_ok=True)
            logger.success(f"Successfully created directory (or it already existed): {directory_path}")
            return f"Successfully created directory (or it already existed): {directory_path}"
        except Exception as e:
            logger.error(f"Failed to create directory {directory_path}. Error: {e}")
            return f"Failed to create directory {directory_path}. Error: {e}" 