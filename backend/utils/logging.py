"""
Logging configuration for AthleAgent backend.
"""

import logging
import sys
from pathlib import Path

# Create logs directory
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "athleagent.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Create logger
logger = logging.getLogger("athleagent")

# Set specific loggers to appropriate levels
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)  # Reduce Uvicorn access logs


