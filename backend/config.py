import os
from pathlib import Path


def load_env(path=".env", environ=None):
    """Read simple KEY=value entries without executing shell expansions.

    Existing process environment wins. Supports whole-line comments and optional
    matching quotes; intentionally does not implement shell or interpolation.
    """
    environ = os.environ if environ is None else environ
    path = Path(path)
    if not path.exists():
        return
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not key.isidentifier():
            raise ValueError(f"Invalid .env entry on line {number}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        environ.setdefault(key, value)
