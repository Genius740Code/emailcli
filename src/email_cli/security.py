"""Security utilities and validation for the email CLI tool."""

import re
import hashlib
import secrets
from typing import Dict, Any, List, Optional
from .utils import error_exit, sanitize_input


class SecurityValidator:
    """Enhanced security validation and sanitization."""
    
    @staticmethod
    def validate_email_address(email: str) -> bool:
        """Validate email address with comprehensive checks."""
        if not email or len(email) > 254:
            return False
        
        email = sanitize_input(email)
        
        # RFC 5322 compliant email regex
        pattern = r'^[a-zA-Z0-9.!#$%&\'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
        
        if not re.match(pattern, email):
            return False
        
        # Additional checks
        local_part, domain = email.split('@', 1)
        
        # Check for suspicious patterns
        if '..' in email or email.startswith('.') or email.endswith('.'):
            return False
        
        # Check domain validity
        if not SecurityValidator.validate_domain_name(domain):
            return False
        
        return True
    
    @staticmethod
    def validate_domain_name(domain: str) -> bool:
        """Validate domain name with security checks."""
        if not domain or len(domain) > 253:
            return False
        
        domain = sanitize_input(domain)
        
        # Domain validation regex
        pattern = r'^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(?:\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$'
        
        if not re.match(pattern, domain):
            return False
        
        # Security checks
        if domain.startswith('.') or domain.endswith('.'):
            return False
        
        if '..' in domain:
            return False
        
        # Check for dangerous TLDs (optional)
        dangerous_tlds = ['.tk', '.ml', '.ga', '.cf']
        if any(domain.endswith(tld) for tld in dangerous_tlds):
            return False
        
        return True
    
    @staticmethod
    def validate_password_strength(password: str) -> Dict[str, Any]:
        """Validate password strength and return feedback."""
        if not password:
            return {"valid": False, "errors": ["Password cannot be empty"]}
        
        errors = []
        suggestions = []
        
        # Length requirements
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long")
        elif len(password) < 12:
            suggestions.append("Consider using at least 12 characters for better security")
        
        # Character variety
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)
        
        if not has_upper:
            errors.append("Password must contain at least one uppercase letter")
        if not has_lower:
            errors.append("Password must contain at least one lowercase letter")
        if not has_digit:
            errors.append("Password must contain at least one digit")
        if not has_special:
            suggestions.append("Consider adding special characters for better security")
        
        # Common password patterns
        common_passwords = ['password', '123456', 'qwerty', 'admin', 'letmein']
        if password.lower() in common_passwords:
            errors.append("Password is too common and easily guessable")
        
        # Repeated characters
        if len(set(password)) < len(password) * 0.5:
            suggestions.append("Avoid using too many repeated characters")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "suggestions": suggestions,
            "strength": SecurityValidator._calculate_password_strength(password)
        }
    
    @staticmethod
    def _calculate_password_strength(password: str) -> str:
        """Calculate password strength score."""
        score = 0
        
        # Length contribution
        score += min(len(password) * 2, 20)
        
        # Character variety
        if any(c.isupper() for c in password):
            score += 5
        if any(c.islower() for c in password):
            score += 5
        if any(c.isdigit() for c in password):
            score += 5
        if any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password):
            score += 10
        
        # Entropy
        unique_chars = len(set(password))
        score += min(unique_chars * 2, 20)
        
        if score < 30:
            return "weak"
        elif score < 50:
            return "medium"
        elif score < 70:
            return "strong"
        else:
            return "very_strong"
    
    @staticmethod
    def sanitize_file_path(file_path: str) -> str:
        """Sanitize file path to prevent directory traversal."""
        if not file_path:
            return ""
        
        # Remove dangerous characters
        dangerous = ['..', '\\', '/', ':', '*', '?', '"', '<', '>', '|']
        sanitized = file_path
        for danger in dangerous:
            sanitized = sanitized.replace(danger, '')
        
        return sanitized[:255]  # Limit length
    
    @staticmethod
    def validate_smtp_server(server: str) -> bool:
        """Validate SMTP server address."""
        if not server:
            return False
        
        server = sanitize_input(server)
        
        # IP address or hostname pattern
        ip_pattern = r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$'
        hostname_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?))*$'
        
        return bool(re.match(ip_pattern, server) or re.match(hostname_pattern, server))
    
    @staticmethod
    def validate_port_number(port: int) -> bool:
        """Validate port number."""
        return isinstance(port, int) and 1 <= port <= 65535
    
    @staticmethod
    def generate_session_token() -> str:
        """Generate a secure session token."""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def hash_sensitive_data(data: str, salt: Optional[str] = None) -> str:
        """Hash sensitive data with salt."""
        if salt is None:
            salt = secrets.token_hex(16)
        
        return hashlib.pbkdf2_hmac('sha256', 
                                 data.encode('utf-8'), 
                                 salt.encode('utf-8'), 
                                 100000).hex()
    
    @staticmethod
    def validate_email_content(content: str) -> Dict[str, Any]:
        """Validate email content for security issues."""
        if not content:
            return {"valid": True, "warnings": []}
        
        warnings = []
        
        # Check for potential security issues
        suspicious_patterns = [
            (r'<script[^>]*>.*?</script>', "JavaScript code detected"),
            (r'javascript:', "JavaScript protocol detected"),
            (r'on\w+\s*=', "Event handler detected"),
            (r'<iframe[^>]*>', "Iframe detected"),
            (r'<object[^>]*>', "Object tag detected"),
            (r'<embed[^>]*>', "Embed tag detected"),
        ]
        
        for pattern, warning in suspicious_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                warnings.append(warning)
        
        # Check for phishing indicators
        phishing_keywords = ['click here', 'verify your account', 'urgent', 'suspended', 
                           'limited time', 'act now', 'confirm identity']
        
        content_lower = content.lower()
        found_keywords = [kw for kw in phishing_keywords if kw in content_lower]
        
        if found_keywords:
            warnings.append(f"Potential phishing keywords: {', '.join(found_keywords)}")
        
        return {
            "valid": len(warnings) == 0,
            "warnings": warnings
        }


class RateLimiter:
    """Simple rate limiting for security."""
    
    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.attempts: Dict[str, List[float]] = {}
    
    def is_allowed(self, identifier: str) -> bool:
        """Check if action is allowed for identifier."""
        import time
        
        current_time = time.time()
        
        if identifier not in self.attempts:
            self.attempts[identifier] = []
        
        # Remove old attempts outside window
        self.attempts[identifier] = [
            attempt for attempt in self.attempts[identifier]
            if current_time - attempt < self.window_seconds
        ]
        
        # Check if under limit
        if len(self.attempts[identifier]) >= self.max_attempts:
            return False
        
        # Record this attempt
        self.attempts[identifier].append(current_time)
        return True
    
    def get_remaining_attempts(self, identifier: str) -> int:
        """Get remaining attempts for identifier."""
        import time
        
        current_time = time.time()
        
        if identifier not in self.attempts:
            return self.max_attempts
        
        # Remove old attempts
        self.attempts[identifier] = [
            attempt for attempt in self.attempts[identifier]
            if current_time - attempt < self.window_seconds
        ]
        
        return max(0, self.max_attempts - len(self.attempts[identifier]))
