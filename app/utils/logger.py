import logging
import sys
from typing import Optional
import os

def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    Setup and configure a logger instance.

    Args:
        name: The name of the logger (typically __name__ from the calling module)
        level: Optional logging level (DEBUG, INFO, etc.). If None, defaults to DEBUG.

    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)

    # Set level: default to DEBUG if not specified
    if level:
        logger.setLevel(getattr(logging, level.upper()))
    else:
        logger.setLevel(logging.DEBUG)  # Default to DEBUG

    # Only add handlers if the logger doesn't already have them
    if not logger.handlers:
        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)  # Ensure handler allows DEBUG

        # Create formatter
        formatter = logging.Formatter(
            fmt='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # Create file handler (optional, for persistent debugging)
        os.makedirs('logs', exist_ok=True)
        file_handler = logging.FileHandler('logs/debug.log')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Ensure logs propagate to parent loggers
    logger.propagate = True

    return logger