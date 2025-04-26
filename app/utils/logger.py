import logging
import sys
from typing import Optional

def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    Setup and configure a logger instance.

    Args:
        name: The name of the logger (typically __name__ from the calling module)
        level: Optional logging level (DEBUG, INFO, etc.). If None, inherits from root logger.

    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)

    # Don't set a level - this allows for external configuration (like pytest --log-cli-level)
    if level:
        logger.setLevel(getattr(logging, level.upper()))

    # Only add handler if the logger doesn't already have handlers
    if not logger.handlers:
        # Create console handler
        handler = logging.StreamHandler(sys.stdout)

        # Create formatter
        formatter = logging.Formatter(
            fmt='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Add formatter to handler
        handler.setFormatter(formatter)

        # Add handler to logger
        logger.addHandler(handler)

    return logger

# Example usage in other files:
# from utils.logger import setup_logger
# logger = setup_logger(__name__)