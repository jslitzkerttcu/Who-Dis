#!/usr/bin/env python3
"""Docker HEALTHCHECK script -- stdlib-only, replaces curl dependency."""
import sys
import urllib.request

try:
    resp = urllib.request.urlopen("http://localhost:5000/health", timeout=5)
    sys.exit(0 if resp.status == 200 else 1)
except Exception:
    sys.exit(1)
