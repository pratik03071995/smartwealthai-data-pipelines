from pathlib import Path
from ..config import settings

def tmp_path(filename: str) -> Path:
    p = Path(settings.tmp_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p / filename
