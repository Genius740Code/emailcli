"""Utility functions for the email CLI tool."""

import os
import sys
import getpass
import re
import hashlib
import secrets
import traceback
from pathlib import Path
from typing import Optional
from functools import lru_cache
from .logger import get_logger


def get_config_dir() -> Path:
    """Get the configuration directory for the email CLI tool."""
    home = Path.home()
    config_dir = home / ".email-cli"
    config_dir.mkdir(exist_ok=True)
    return config_dir


def get_config_file() -> Path:
    """Get the path to the configuration file."""
    return get_config_dir() / "config.yaml"


def get_database_file() -> Path:
    """Get the path to the SQLite database file."""
    return get_config_dir() / "emails.db"


@lru_cache(maxsize=1024)
def validate_email(email: str) -> bool:
    """Enhanced email validation with comprehensive checks."""
    logger = get_logger()
    
    if not email or not isinstance(email, str):
        logger.debug("Email validation failed: empty or non-string input")
        return False
    
    if len(email) > 254:
        logger.debug("Email validation failed: too long", length=len(email))
        return False
    
    # Basic format validation
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        logger.debug("Email validation failed: invalid format", email=email[:50])
        return False
    
    # Split and validate parts
    try:
        local, domain = email.split('@', 1)
        
        # Local part validation
        if len(local) > 64:
            logger.debug("Email validation failed: local part too long", local_length=len(local))
            return False
        
        if local.startswith('.') or local.endswith('.'):
            logger.debug("Email validation failed: local part starts/ends with dot")
            return False
        
        # Domain part validation
        if len(domain) > 255:
            logger.debug("Email validation failed: domain part too long", domain_length=len(domain))
            return False
        
        # Check for consecutive dots
        if '..' in email:
            logger.debug("Email validation failed: consecutive dots")
            return False
        
        # Check for dangerous patterns
        dangerous_patterns = [r'\.\.', r'\.$', r'^\.']
        for pattern in dangerous_patterns:
            if re.search(pattern, email):
                logger.debug("Email validation failed: dangerous pattern", pattern=pattern)
                return False
        
        logger.debug("Email validation passed", email=email[:50])
        return True
        
    except ValueError:
        logger.debug("Email validation failed: malformed email")
        return False


@lru_cache(maxsize=512)
def validate_domain(domain: str) -> bool:
    """Enhanced domain validation with comprehensive checks."""
    logger = get_logger()
    
    if not domain or not isinstance(domain, str):
        logger.debug("Domain validation failed: empty or non-string input")
        return False
    
    if len(domain) > 253:
        logger.debug("Domain validation failed: too long", length=len(domain))
        return False
    
    # Basic format validation
    pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?))*$'
    if not re.match(pattern, domain):
        logger.debug("Domain validation failed: invalid format", domain=domain[:50])
        return False
    
    # Additional checks
    if domain.startswith('.') or domain.endswith('.'):
        logger.debug("Domain validation failed: starts/ends with dot")
        return False
    
    if '..' in domain:
        logger.debug("Domain validation failed: consecutive dots")
        return False
    
    # Check label lengths
    labels = domain.split('.')
    for label in labels:
        if len(label) > 63:
            logger.debug("Domain validation failed: label too long", label=label, length=len(label))
            return False
    
    # Check for dangerous TLDs
    dangerous_tlds = ['.exe', '.bat', '.cmd', '.scr', '.pif', '.com']
    for tld in dangerous_tlds:
        if domain.lower().endswith(tld):
            logger.warning("Potentially dangerous TLD detected", domain=domain, tld=tld)
    
    logger.debug("Domain validation passed", domain=domain[:50])
    return True


def validate_port(port: int) -> bool:
    """Validate port number."""
    logger = get_logger()
    
    if not isinstance(port, int):
        logger.debug("Port validation failed: not an integer", type=type(port))
        return False
    
    if not (1 <= port <= 65535):
        logger.debug("Port validation failed: out of range", port=port)
        return False
    
    # Check for common service ports
    common_ports = {20, 21, 22, 23, 25, 53, 80, 110, 143, 443, 993, 995, 587, 465, 2525}
    if port not in common_ports:
        logger.info("Uncommon port used", port=port)
    
    return True


def validate_server_address(address: str) -> bool:
    """Validate server address (hostname or IP)."""
    logger = get_logger()
    
    if not address or not isinstance(address, str):
        return False
    
    # Length check
    if len(address) > 253:
        return False
    
    # IP address validation
    ip_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    if re.match(ip_pattern, address):
        logger.debug("Valid IP address detected", address=address)
        return True
    
    # Hostname validation
    hostname_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?))*$'
    if re.match(hostname_pattern, address):
        logger.debug("Valid hostname detected", address=address[:50])
        return True
    
    logger.debug("Invalid server address", address=address[:50])
    return False


def error_exit(message: str, exception: Optional[Exception] = None, **kwargs) -> None:
    """Print error message, log it, and exit."""
    logger = get_logger()
    logger.error(message, exception=exception, **kwargs)
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def success_message(message: str) -> None:
    """Print success message and log it."""
    logger = get_logger()
    logger.info(message)
    print(f"Success: {message}")


def info_message(message: str) -> None:
    """Print info message and log it."""
    logger = get_logger()
    logger.info(message)
    print(f"Info: {message}")


def sanitize_input(input_str: str, max_length: int = 1000) -> str:
    """Enhanced input sanitization to prevent injection attacks."""
    logger = get_logger()
    
    if not input_str:
        return ""
    
    # Log original input for security auditing (only first 100 chars)
    logger.debug("Sanitizing input", original=input_str[:100], length=len(input_str))
    
    # Type checking
    if not isinstance(input_str, str):
        logger.warning("Non-string input provided", type=type(input_str))
        input_str = str(input_str)
    
    # Remove potentially dangerous characters with regex
    dangerous_patterns = [
        r'[<>&"\'`$|;(){}\[\]]',  # HTML/SQL injection chars
        r'\x00-\x1f\x7f-\x9f',    # Control characters
        r'[\r\n]+',               # Multiple newlines
        r'\s{2,}',                # Multiple spaces
    ]
    
    sanitized = input_str
    for pattern in dangerous_patterns:
        old_sanitized = sanitized
        sanitized = re.sub(pattern, ' ', sanitized)
        if sanitized != old_sanitized:
            logger.debug("Removed dangerous pattern", pattern=pattern)
    
    # Additional security checks
    if re.search(r'(javascript:|data:|vbscript:)', sanitized, re.IGNORECASE):
        logger.warning("Potentially dangerous URI scheme detected", input=sanitized[:100])
        sanitized = re.sub(r'(javascript:|data:|vbscript:)', '', sanitized, flags=re.IGNORECASE)
    
    # Normalize whitespace and limit length
    sanitized = re.sub(r'\s+', ' ', sanitized.strip())
    
    if len(sanitized) > max_length:
        logger.warning("Input truncated due to length limit", original_length=len(sanitized), max_length=max_length)
        sanitized = sanitized[:max_length].rstrip()
    
    # Final validation
    if not sanitized:
        logger.warning("Input became empty after sanitization")
        return ""
    
    logger.debug("Input sanitized successfully", final_length=len(sanitized))
    return sanitized


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure token."""
    return secrets.token_urlsafe(length)


def hash_string(data: str) -> str:
    """Hash a string using SHA-256."""
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def get_user_input(prompt: str, default: Optional[str] = None, hide_input: bool = False) -> str:
    """Get user input with optional default value."""
    if hide_input:
        user_input = getpass.getpass(f"{prompt}: ").strip()
        return user_input
    elif default:
        user_input = input(f"{prompt} [{default}]: ").strip()
        return user_input if user_input else default
    return input(f"{prompt}: ").strip()
