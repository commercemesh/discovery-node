import logging
import sys
from logging.handlers import RotatingFileHandler
import os


def get_logger(name):
    """
    Get a configured logger instance with both file and console handlers.

    Args:
        name (str): The name of the logger, typically __name__ of the calling module

    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Create formatters
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # Create and configure file handler
    log_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs"
    )
    os.makedirs(log_dir, exist_ok=True)

    file_handler = RotatingFileHandler(
        filename=os.path.join(log_dir, "ingestor.log"),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_formatter)

    # Create and configure console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
