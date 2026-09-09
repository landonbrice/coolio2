#!/usr/bin/env python3
"""Daily snapshot: refresh live data (or fall back to cache) then rebuild the
static HTML. Research / not financial advice.

Runs the data step then the build step in-process, fail-soft. Because
``dashboard_data.main()`` always writes a valid state (live or cached), this
ALWAYS produces a current ``output/dashboard.html`` -- online or offline.
"""
import sys

import dashboard_data
import build_dashboard


def main():
    rc = dashboard_data.main()          # writes output/dashboard_state.json (0 even when cached)
    if rc not in (0, None):
        print("dashboard_data failed hard; attempting build from any existing state",
              file=sys.stderr)
    bc = build_dashboard.main()         # writes output/dashboard.html from the JSON
    return bc or 0


if __name__ == "__main__":
    raise SystemExit(main())
