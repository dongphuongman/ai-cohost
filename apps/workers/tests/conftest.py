"""Make ``apps/workers`` importable when pytest is invoked from the repo root."""
import os
import sys

WORKERS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKERS_ROOT not in sys.path:
    sys.path.insert(0, WORKERS_ROOT)
