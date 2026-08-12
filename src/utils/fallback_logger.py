import os
import logging
from pathlib import Path
from typing import Any

# Ensure logs directory exists
project_root = Path(__file__).resolve().parent.parent.parent
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

fallback_file = logs_dir / "fallbacks.log"

fallback_logger = logging.getLogger("FallbackLogger")
fallback_logger.setLevel(logging.WARNING)

# Avoid adding duplicate handlers if imported multiple times
if not fallback_logger.handlers:
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s (%(module_name)s): %(message)s")
    
    fh = logging.FileHandler(fallback_file, encoding="utf-8")
    fh.setLevel(logging.WARNING)
    fh.setFormatter(formatter)
    
    fallback_logger.addHandler(fh)


def log_fallback(source_module: str, reason: str, fallback_value: Any = None):
    """
    Centralized Fallback Logger.
    Logs every fallback event with timestamp, module name, reason, and fallback value to logs/fallbacks.log.
    """
    msg = f"⚠️ FALLBACK TRIGGERED | Reason: {reason}"
    if fallback_value is not None:
        msg += f" | Used Value: {fallback_value}"
    
    fallback_logger.warning(msg, extra={"module_name": source_module})
