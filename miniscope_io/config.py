from typing import Literal
from pathlib import Path
from pydantic import BaseSettings, Field

LOG_LEVELS = Literal['DEBUG', 'INFO', 'WARNING', 'EXCEPTION']

class Config(BaseSettings):
    """
    Use as an .env file located in the current working directory or
    """
    BASE_DIR: Path = Field(
        default_factory=lambda: Path.home() / 'miniscope_io',
        description="Root directory where logs, temporary files, and output data is kept by default")
    LOG_DIR: Path = Field(
        default = 'logs',
        description = "Location for storing logs, if not an abolute path, relative to BASE_DIR"
    )
    LOG_LEVEL: LOG_LEVELS = Field(
        default = "WARNING",
        description = "Filter log messages by severity"
    )

    class Config:
        _homepath = Path.home() / 'miniscope_io' / '.env'
        if _homepath.exists():
            env_file = str(_homepath)
        else:
            env_file = '.env'
        env_file_encoding = 'utf-8'
        env_prefix = "MIO_"