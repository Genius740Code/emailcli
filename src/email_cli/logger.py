"""Logging configuration and utilities for the email CLI tool."""

import logging
import sys
from pathlib import Path
from typing import Optional
from .utils import get_config_dir


class EmailCLILogger:
    """Enhanced logger for the email CLI tool with structured logging."""
    
    def __init__(self, name: str = "email-cli", level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Avoid duplicate handlers
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self) -> None:
        """Setup console and file handlers with proper formatting."""
        # Create formatters
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler
        log_dir = get_config_dir() / "logs"
        log_dir.mkdir(exist_ok=True)
        
        file_handler = logging.FileHandler(log_dir / "email-cli.log")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message with optional context."""
        if kwargs:
            message = f"{message} | Context: {kwargs}"
        self.logger.debug(message)
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message with optional context."""
        if kwargs:
            message = f"{message} | Context: {kwargs}"
        self.logger.info(message)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message with optional context."""
        if kwargs:
            message = f"{message} | Context: {kwargs}"
        self.logger.warning(message)
    
    def error(self, message: str, exception: Optional[Exception] = None, **kwargs) -> None:
        """Log error message with optional exception and context."""
        if exception:
            message = f"{message} | Exception: {type(exception).__name__}: {str(exception)}"
        if kwargs:
            message = f"{message} | Context: {kwargs}"
        self.logger.error(message)
    
    def critical(self, message: str, exception: Optional[Exception] = None, **kwargs) -> None:
        """Log critical message with optional exception and context."""
        if exception:
            message = f"{message} | Exception: {type(exception).__name__}: {str(exception)}"
        if kwargs:
            message = f"{message} | Context: {kwargs}"
        self.logger.critical(message)
    
    def log_operation(self, operation: str, duration: float = None, success: bool = True, **kwargs) -> None:
        """Log operation with timing and success status."""
        message = f"Operation: {operation} | Success: {success}"
        if duration is not None:
            message += f" | Duration: {duration:.3f}s"
        if kwargs:
            message += f" | Details: {kwargs}"
        
        if success:
            self.info(message)
        else:
            self.error(message)
    
    def log_security_event(self, event: str, severity: str = "INFO", **kwargs) -> None:
        """Log security-related events."""
        message = f"SECURITY: {event}"
        if kwargs:
            message += f" | Details: {kwargs}"
        
        log_level = getattr(logging, severity.upper(), logging.INFO)
        self.logger.log(log_level, message)


# Global logger instance
_logger = None


def get_logger() -> EmailCLILogger:
    """Get the global logger instance."""
    global _logger
    if _logger is None:
        _logger = EmailCLILogger()
    return _logger


def log_exception(func):
    """Decorator to automatically log exceptions in functions."""
    def wrapper(*args, **kwargs):
        logger = get_logger()
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Exception in {func.__name__}", exception=e, args=args, kwargs=kwargs)
            raise
    return wrapper
