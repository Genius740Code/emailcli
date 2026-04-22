"""Configuration validation and schema checking for the email CLI tool."""

import yaml
import jsonschema
from typing import Dict, Any, List, Optional
from pathlib import Path
from .logger import get_logger
from .utils import validate_domain, validate_port, validate_server_address, error_exit


class ConfigValidator:
    """Validates configuration files and schemas."""
    
    # Configuration schema
    CONFIG_SCHEMA = {
        "type": "object",
        "properties": {
            "domains": {
                "type": "object",
                "patternProperties": {
                    "^[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$": {
                        "type": "object",
                        "required": ["smtp_server", "smtp_port", "imap_server", "imap_port", "username"],
                        "properties": {
                            "smtp_server": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": 253
                            },
                            "smtp_port": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 65535
                            },
                            "imap_server": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": 253
                            },
                            "imap_port": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 65535
                            },
                            "username": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": 254
                            },
                            "password": {
                                "type": "string",
                                "minLength": 8,
                                "maxLength": 1000
                            },
                            "use_ssl": {
                                "type": "boolean"
                            },
                            "use_tls": {
                                "type": "boolean"
                            },
                            "timeout": {
                                "type": "integer",
                                "minimum": 5,
                                "maximum": 300
                            }
                        },
                        "additionalProperties": False
                    }
                },
                "additionalProperties": False
            },
            "default_domain": {
                "type": ["string", "null"],
                "pattern": "^[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
            },
            "smtp_timeout": {
                "type": "integer",
                "minimum": 5,
                "maximum": 300
            },
            "imap_timeout": {
                "type": "integer",
                "minimum": 5,
                "maximum": 300
            },
            "use_ssl": {
                "type": "boolean"
            },
            "use_tls": {
                "type": "boolean"
            },
            "rate_limiting": {
                "type": "object",
                "properties": {
                    "max_requests_per_second": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100
                    },
                    "max_requests_per_minute": {
                        "type": "integer",
                        "minimum": 10,
                        "maximum": 1000
                    },
                    "max_requests_per_hour": {
                        "type": "integer",
                        "minimum": 100,
                        "maximum": 10000
                    }
                },
                "additionalProperties": False
            },
            "logging": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "string",
                        "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
                    },
                    "max_file_size": {
                        "type": "integer",
                        "minimum": 1024,
                        "maximum": 104857600  # 100MB
                    },
                    "backup_count": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10
                    }
                },
                "additionalProperties": False
            }
        },
        "additionalProperties": False
    }
    
    def __init__(self):
        self.logger = get_logger()
    
    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate configuration against schema and business rules."""
        errors = []
        
        # JSON Schema validation
        try:
            jsonschema.validate(config, self.CONFIG_SCHEMA)
        except jsonschema.ValidationError as e:
            errors.append(f"Schema validation error: {e.message}")
            return errors
        
        # Business logic validation
        errors.extend(self._validate_business_rules(config))
        
        if errors:
            self.logger.error("Configuration validation failed", errors=errors)
        else:
            self.logger.info("Configuration validation passed")
        
        return errors
    
    def _validate_business_rules(self, config: Dict[str, Any]) -> List[str]:
        """Validate business rules beyond schema validation."""
        errors = []
        
        # Validate domains
        domains = config.get('domains', {})
        default_domain = config.get('default_domain')
        
        if default_domain and default_domain not in domains:
            errors.append(f"Default domain '{default_domain}' not found in domains configuration")
        
        for domain_name, domain_config in domains.items():
            # Validate domain name
            if not validate_domain(domain_name):
                errors.append(f"Invalid domain name: {domain_name}")
                continue
            
            # Validate server addresses
            smtp_server = domain_config.get('smtp_server', '')
            imap_server = domain_config.get('imap_server', '')
            
            if not validate_server_address(smtp_server):
                errors.append(f"Invalid SMTP server address for domain {domain_name}: {smtp_server}")
            
            if not validate_server_address(imap_server):
                errors.append(f"Invalid IMAP server address for domain {domain_name}: {imap_server}")
            
            # Validate ports
            smtp_port = domain_config.get('smtp_port')
            imap_port = domain_config.get('imap_port')
            
            if not validate_port(smtp_port):
                errors.append(f"Invalid SMTP port for domain {domain_name}: {smtp_port}")
            
            if not validate_port(imap_port):
                errors.append(f"Invalid IMAP port for domain {domain_name}: {imap_port}")
            
            # Check for common port mismatches
            port_warnings = self._check_port_mismatches(smtp_port, imap_port, domain_name)
            errors.extend(port_warnings)
            
            # Validate username format (basic email check)
            username = domain_config.get('username', '')
            if '@' not in username or len(username) > 254:
                errors.append(f"Invalid username format for domain {domain_name}: {username}")
            
            # Validate password strength if present
            password = domain_config.get('password', '')
            if password and len(password) < 8:
                errors.append(f"Password too weak for domain {domain_name} (minimum 8 characters)")
        
        # Validate global timeouts
        smtp_timeout = config.get('smtp_timeout')
        imap_timeout = config.get('imap_timeout')
        
        if smtp_timeout and (smtp_timeout < 5 or smtp_timeout > 300):
            errors.append(f"Invalid SMTP timeout: {smtp_timeout} (must be between 5 and 300 seconds)")
        
        if imap_timeout and (imap_timeout < 5 or imap_timeout > 300):
            errors.append(f"Invalid IMAP timeout: {imap_timeout} (must be between 5 and 300 seconds)")
        
        # Validate rate limiting
        rate_limiting = config.get('rate_limiting', {})
        if rate_limiting:
            rps = rate_limiting.get('max_requests_per_second')
            rpm = rate_limiting.get('max_requests_per_minute')
            rph = rate_limiting.get('max_requests_per_hour')
            
            if rps and rpm and rps > rpm:
                errors.append(f"Rate per second ({rps}) cannot exceed rate per minute ({rpm})")
            
            if rpm and rph and rpm > rph:
                errors.append(f"Rate per minute ({rpm}) cannot exceed rate per hour ({rph})")
        
        return errors
    
    def _check_port_mismatches(self, smtp_port: int, imap_port: int, domain: str) -> List[str]:
        """Check for common port configuration issues."""
        warnings = []
        
        # Common SMTP/IMAP port pairs
        common_pairs = {
            (25, 143),      # Plain SMTP/IMAP
            (587, 143),     # SMTP with TLS/Plain IMAP
            (465, 993),     # SMTP SSL/IMAP SSL
            (587, 993),     # SMTP with TLS/IMAP SSL
            (25, 993),      # Plain SMTP/IMAP SSL (unusual)
            (465, 143),     # SMTP SSL/Plain IMAP (unusual)
        }
        
        if (smtp_port, imap_port) not in common_pairs:
            warnings.append(f"Unusual port combination for domain {domain}: SMTP {smtp_port}, IMAP {imap_port}")
        
        # Check for port conflicts
        if smtp_port == imap_port:
            warnings.append(f"SMTP and IMAP ports are the same for domain {domain}: {smtp_port}")
        
        return warnings
    
    def validate_config_file(self, config_file: Path) -> List[str]:
        """Validate a configuration file."""
        errors = []
        
        if not config_file.exists():
            errors.append(f"Configuration file does not exist: {config_file}")
            return errors
        
        if not config_file.is_file():
            errors.append(f"Configuration path is not a file: {config_file}")
            return errors
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            if not isinstance(config, dict):
                errors.append("Configuration file must contain a YAML object/dictionary")
                return errors
            
            errors.extend(self.validate_config(config))
            
        except yaml.YAMLError as e:
            errors.append(f"Invalid YAML syntax: {e}")
        except Exception as e:
            errors.append(f"Error reading configuration file: {e}")
        
        return errors
    
    def create_default_config(self) -> Dict[str, Any]:
        """Create a default valid configuration."""
        return {
            "domains": {},
            "default_domain": None,
            "smtp_timeout": 30,
            "imap_timeout": 30,
            "use_ssl": True,
            "use_tls": True,
            "rate_limiting": {
                "max_requests_per_second": 10,
                "max_requests_per_minute": 100,
                "max_requests_per_hour": 1000
            },
            "logging": {
                "level": "INFO",
                "max_file_size": 10485760,  # 10MB
                "backup_count": 5
            }
        }
    
    def sanitize_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize configuration by removing sensitive or invalid data."""
        sanitized = {}
        
        # Copy safe fields
        safe_fields = ['default_domain', 'smtp_timeout', 'imap_timeout', 'use_ssl', 'use_tls']
        for field in safe_fields:
            if field in config:
                sanitized[field] = config[field]
        
        # Sanitize domains
        if 'domains' in config:
            sanitized['domains'] = {}
            for domain_name, domain_config in config['domains'].items():
                if isinstance(domain_config, dict):
                    sanitized_domain = {}
                    
                    # Copy safe domain fields
                    safe_domain_fields = ['smtp_server', 'smtp_port', 'imap_server', 
                                        'imap_port', 'username', 'use_ssl', 'use_tls', 'timeout']
                    for field in safe_domain_fields:
                        if field in domain_config:
                            sanitized_domain[field] = domain_config[field]
                    
                    # Mask password
                    if 'password' in domain_config:
                        sanitized_domain['password'] = '[MASKED]'
                    
                    sanitized['domains'][domain_name] = sanitized_domain
        
        # Copy rate limiting
        if 'rate_limiting' in config:
            sanitized['rate_limiting'] = config['rate_limiting']
        
        # Copy logging
        if 'logging' in config:
            sanitized['logging'] = config['logging']
        
        return sanitized


def validate_and_load_config(config_file: Path) -> Dict[str, Any]:
    """Validate and load configuration file."""
    validator = ConfigValidator()
    errors = validator.validate_config_file(config_file)
    
    if errors:
        error_exit("Configuration validation failed:\n" + "\n".join(f"- {error}" for error in errors))
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        error_exit(f"Failed to load configuration: {e}")


def get_config_schema() -> Dict[str, Any]:
    """Get the configuration schema for documentation."""
    return ConfigValidator.CONFIG_SCHEMA.copy()
