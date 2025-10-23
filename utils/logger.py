# Logging configuration
import logging
import os
from datetime import datetime

def setup_logger(name='usf_moving', log_file=None):
    """Setup application logger"""
    
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    # Prevent duplicate logs if handlers already exist
    if logger.handlers:
        return logger
    # Do not propagate to root to avoid duplicate console logs
    logger.propagate = False
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(levelname)s - %(message)s'
    )
    
    # File handler
    if log_file is None:
        log_file = f"logs/usf_moving_{datetime.now().strftime('%Y%m%d')}.log"
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(detailed_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Provide a module-level logger for convenience imports
logger = setup_logger()