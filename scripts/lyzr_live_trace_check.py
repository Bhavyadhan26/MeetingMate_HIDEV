from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.observability.lyzr_live_trace_check import main


if __name__ == "__main__":
    sys.exit(main())
