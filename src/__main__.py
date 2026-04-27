"""Allow ``python -m src`` to dispatch to ``src.main:main``."""

from __future__ import annotations

import sys

from src.main import main

if __name__ == "__main__":
    sys.exit(main())
