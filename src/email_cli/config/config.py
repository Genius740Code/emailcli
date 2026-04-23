"""Configuration management for the email CLI tool."""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from ..utils.utils import get_config_file, error_exit, validate_domain
from .config_validator import ConfigValidator, validate_and_load_config


class ConfigManager:
    """Manages configuration for the email CLI tool."""
    
    def __init__(self):
        self.config_file = get_config_file()
        self.validator = ConfigValidator()
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default with validation."""
        if self.config_file.exists():
            return validate_and_load_config(self.config_file)
        else:
            return self._create_default_config()
    
    def _create_default_config(self) -> Dict[str, Any]:
        """Create default configuration with validation."""
        default_config = self.validator.create_default_config()
        self.save_config(default_config)
        return default_config
    
    def save_config(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Save configuration to file with validation."""
        config_to_save = config or self.config
        
        # Validate before saving
        errors = self.validator.validate_config(config_to_save)
        if errors:
            error_exit("Cannot save invalid configuration:\n" + "\n".join(f"- {error}" for error in errors))
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config_to_save, f, default_flow_style=False, indent=2)
        except Exception as e:
            error_exit(f"Failed to save configuration: {e}")
    
    def add_domain(self, domain: str, smtp_server: str, smtp_port: int,
                   imap_server: str, imap_port: int, username: str,
                   password: str, use_ssl: bool = True, use_tls: bool = True) -> None:
        """Add a new domain configuration with validation."""
        if not validate_domain(domain):
            error_exit(f"Invalid domain: {domain}")
        
        # Create domain configuration
        domain_config = {
            'smtp_server': smtp_server,
            'smtp_port': smtp_port,
            'imap_server': imap_server,
            'imap_port': imap_port,
            'username': username,
            'password': password,
            'use_ssl': use_ssl,
            'use_tls': use_tls
        }
        
        # Validate domain configuration
        temp_config = self.config.copy()
        temp_config['domains'][domain] = domain_config
        
        errors = self.validator.validate_config(temp_config)
        if errors:
            error_exit(f"Invalid domain configuration:\n" + "\n".join(f"- {error}" for error in errors))
        
        # Add to configuration
        self.config['domains'][domain] = domain_config
        
        if not self.config.get('default_domain'):
            self.config['default_domain'] = domain
        
        self.save_config()
    
    def validate_current_config(self) -> List[str]:
        """Validate the current configuration."""
        return self.validator.validate_config(self.config)
    
    def get_domain_config(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific domain."""
        return self.config['domains'].get(domain)
    
    def list_domains(self) -> Dict[str, Dict[str, Any]]:
        """List all configured domains."""
        return self.config.get('domains', {})
    
    def remove_domain(self, domain: str) -> None:
        """Remove a domain configuration."""
        if domain in self.config['domains']:
            del self.config['domains'][domain]
            
            if self.config.get('default_domain') == domain:
                self.config['default_domain'] = next(
                    iter(self.config['domains']), None
                )
            
            self.save_config()
        else:
            error_exit(f"Domain {domain} not found")
    
    def get_default_domain(self) -> Optional[str]:
        """Get the default domain."""
        return self.config.get('default_domain')
    
    def set_default_domain(self, domain: str) -> None:
        """Set the default domain."""
        if domain not in self.config['domains']:
            error_exit(f"Domain {domain} not configured")
        
        self.config['default_domain'] = domain
        self.save_config()
    
    def set_dns_config(self, domain: str, provider: str, credentials: Dict[str, str]) -> None:
        """Set DNS provider configuration for a domain."""
        if not validate_domain(domain):
            error_exit(f"Invalid domain: {domain}")
        
        # Initialize dns_providers section if it doesn't exist
        if 'dns_providers' not in self.config:
            self.config['dns_providers'] = {}
        
        # Store DNS configuration (without sensitive logging)
        self.config['dns_providers'][domain] = {
            'provider': provider,
            'credentials': credentials
        }
        
        self.save_config()
    
    def get_dns_config(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get DNS provider configuration for a domain."""
        return self.config.get('dns_providers', {}).get(domain)
    
    def set_provider_config(self, provider_name: str, provider_type: str, credentials: Dict[str, str]) -> None:
        """Set email provider configuration."""
        # Initialize email_providers section if it doesn't exist
        if 'email_providers' not in self.config:
            self.config['email_providers'] = {}
        
        # Store provider configuration
        self.config['email_providers'][provider_name] = {
            'type': provider_type,
            'credentials': credentials
        }
        
        self.save_config()
    
    def get_provider_config(self, provider_name: str) -> Optional[Dict[str, Any]]:
        """Get email provider configuration."""
        return self.config.get('email_providers', {}).get(provider_name)
    
    def list_email_providers(self) -> Dict[str, Dict[str, Any]]:
        """List all configured email providers."""
        return self.config.get('email_providers', {})
    
    def list_dns_providers(self) -> Dict[str, Dict[str, Any]]:
        """List all configured DNS providers."""
        return self.config.get('dns_providers', {})
