"""
This module contains the Config class, which manages application configuration settings.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    """Configuration settings for the application."""

    db_path: Path
    cache_timeout: int
    max_cache_size: int
    request_timeout: int
