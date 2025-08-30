"""
Logging utilities for the Play Store Data Collector
"""

import logging
import os
from datetime import datetime
from typing import Optional
import config

def setup_logging(
    log_level: str = config.LOG_LEVEL,
    log_file: str = config.LOG_FILE,
    log_format: str = config.LOG_FORMAT
) -> logging.Logger:
    """Setup logging configuration"""
    
    # Create logs directory if it doesn't exist
    log_dir = config.PATHS['logs']
    os.makedirs(log_dir, exist_ok=True)
    
    # Full path for log file
    log_path = os.path.join(log_dir, log_file)
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=[
            logging.FileHandler(log_path, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # Create main logger
    logger = logging.getLogger('playstore_collector')
    logger.info(f"Logging initialized - Level: {log_level}, File: {log_path}")
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module"""
    return logging.getLogger(f'playstore_collector.{name}')

class LogManager:
    """Centralized log management"""
    
    def __init__(self):
        self.main_logger = setup_logging()
        self.module_loggers = {}
    
    def get_module_logger(self, module_name: str) -> logging.Logger:
        """Get or create a logger for a specific module"""
        if module_name not in self.module_loggers:
            self.module_loggers[module_name] = get_logger(module_name)
        return self.module_loggers[module_name]
    
    def log_collection_start(self, app_id: str, collection_type: str):
        """Log the start of a data collection process"""
        self.main_logger.info(f"Starting {collection_type} collection for {app_id}")
    
    def log_collection_complete(self, app_id: str, collection_type: str, items_collected: int, duration: float):
        """Log the completion of a data collection process"""
        self.main_logger.info(
            f"Completed {collection_type} collection for {app_id}: "
            f"{items_collected} items in {duration:.2f}s"
        )
    
    def log_error(self, module: str, error: Exception, context: Optional[str] = None):
        """Log an error with context"""
        logger = self.get_module_logger(module)
        error_msg = f"Error in {module}: {str(error)}"
        if context:
            error_msg += f" (Context: {context})"
        logger.error(error_msg, exc_info=True)
    
    def log_rate_limit(self, service: str, wait_time: float):
        """Log rate limiting activity"""
        logger = self.get_module_logger('rate_limiter')
        logger.debug(f"Rate limited {service}: waited {wait_time:.2f}s")
    
    def create_session_log_file(self, session_id: str) -> str:
        """Create a separate log file for a specific session"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_log_file = f"session_{session_id}_{timestamp}.log"
        session_log_path = os.path.join(config.PATHS['logs'], session_log_file)
        
        # Create session-specific handler
        session_handler = logging.FileHandler(session_log_path, encoding='utf-8')
        session_handler.setFormatter(logging.Formatter(config.LOG_FORMAT))
        
        # Add handler to main logger
        self.main_logger.addHandler(session_handler)
        
        self.main_logger.info(f"Session log created: {session_log_path}")
        return session_log_path

# Global log manager instance
log_manager = LogManager()