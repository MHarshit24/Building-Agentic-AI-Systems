import logging
import os


def setup_logger(name):
    """
    Creates and configures a logger.
    Logs to both console and file.
    """

    # Create logs folder if not exists
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    logs_dir = os.path.join(parent_dir, 'logs')
    
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Prevent duplicate logs
    if logger.hasHandlers():
        logger.handlers.clear()

    # Log format
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )

    # File handler
    file_handler = logging.FileHandler(os.path.join(logs_dir, "app.log"))
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
