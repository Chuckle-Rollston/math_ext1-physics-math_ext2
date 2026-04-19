import os
import sys

# Make the project root importable when Vercel invokes this as api/index.py
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app  # noqa: E402,F401  (Vercel looks for `app`)
