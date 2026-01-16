"""Logging configuration for auto_citation_agent."""

import logging
import sys
from typing import Optional


def setup_logging(level: int = logging.INFO, format_string: Optional[str] = None) -> None:
    """Configure root logger for the application.
    
    Args:
        level: Logging level (default: INFO)
        format_string: Custom format string. If None, uses default.
    """
    if format_string is None:
        format_string = "[%(levelname)s] %(message)s"
    
    logging.basicConfig(
        level=level,
        format=format_string,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,  # Override any existing configuration
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)
