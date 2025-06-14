# this file dynamically loads the application configuration from config.json

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class Config:
    """Configuration data class that represents the application configuration."""
    download_directory: str
    application_port: int = 8000
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.download_directory:
            raise ValueError("download_directory cannot be empty")
        
        # Convert to absolute path and ensure it exists
        path = Path(self.download_directory).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        self.download_directory = str(path)
        
        # Validate port number
        if not isinstance(self.application_port, int) or not (1 <= self.application_port <= 65535):
            raise ValueError("application_port must be an integer between 1 and 65535")

class ConfigService:
    """Service for loading and providing application configuration."""
    
    def __init__(self, config_file: str = 'config.json'):
        self.config_file = config_file
    
    def get_config(self) -> Config:
        """
        Dynamically loads and returns configuration from config.json.
        Always reads from file (no caching) for real-time configuration updates.
        """
        try:
            with open(self.config_file, 'r') as file:
                config_data = json.load(file)
            
            # Convert camelCase to snake_case for Python conventions
            download_directory = config_data.get('downloadDirectory', '')
            application_port = config_data.get('applicationPort', 8000)
            
            return Config(
                download_directory=download_directory,
                application_port=application_port
            )
            
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file '{self.config_file}' not found")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
        except Exception as e:
            raise RuntimeError(f"Unknown error loading configuration: {e}")









