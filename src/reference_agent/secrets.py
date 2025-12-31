import os
from typing import Optional


def resolve_secret(ref: Optional[str]) -> Optional[str]:
    if not ref:
        return None
    return os.getenv(ref)
