from dataclasses import dataclass
from pathlib import Path

@dataclass
class Config:
    db_path: Path
    cache_timeout: int
    max_cache_size: int
    request_timeout: int 