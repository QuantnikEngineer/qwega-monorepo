"""
Run script for Quantnik Common Integration Service.
"""
import sys
import uvicorn
from app.core.config import settings

# Disable stdout buffering for real-time logs
sys.stdout.reconfigure(line_buffering=True)

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
