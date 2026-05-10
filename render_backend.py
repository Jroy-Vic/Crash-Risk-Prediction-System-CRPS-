from pathlib import Path
import sys
import os

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "services" / "backend"

sys.path.append(str(PROJECT_ROOT))
sys.path.append(str(BACKEND_DIR))

from services.backend.app import app