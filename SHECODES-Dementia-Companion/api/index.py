"""
Entrypoint for Vercel Serverless Function Deployment.
Exposes the Flask `app` instance to Vercel's Python runtime.
"""

import os
import sys

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import app

# Export for Vercel
app = app
