#!/usr/bin/env python3
"""
DEPRECATED ENTRYPOINT — Onelife Intelligence Dashboard

This file exists only as a compatibility wrapper.
Do NOT reintroduce legacy dashboard generation logic here.

Canonical builder:
    build_v7.py

Reason:
    The older intelligence dashboard generator caused regressions where GitHub Pages
    served the wrong version instead of the preferred newer V7 dashboard.
    Any caller still using `generate_intelligence.py` must be transparently routed
    to `build_v7.py` so the new dashboard remains the only published version.
"""

import os
import subprocess
import sys

WORKSPACE = os.path.expanduser("~/.openclaw/workspace/onelife-intelligence")
CANONICAL = os.path.join(WORKSPACE, "build_v7.py")


def main() -> int:
    print(
        "[DEPRECATED] generate_intelligence.py called. Redirecting to build_v7.py",
        file=sys.stderr,
    )

    if not os.path.exists(CANONICAL):
        print(f"[FATAL] Canonical builder missing: {CANONICAL}", file=sys.stderr)
        return 1

    result = subprocess.run([sys.executable, CANONICAL], cwd=WORKSPACE)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
