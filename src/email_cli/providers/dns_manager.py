"""DNS management for email domain configuration."""

import dns.resolver
import dns.update
import dns.tsigkeyring
import requests
from typing import Dict, List, Optional, Any, Tuple
from ..utils.utils import validate_domain, error_exit, success_message, info_message, sanitize_input


class DNSProvider:
    """Base class for DNS providers."""
    
    def __init__(self, credentials: Dict[str, str]):
        self.credentials = credentials
    
    def create_mx_record(self, domain: str, mail_server: str, priority: int = 10) -> bool:
        """Create MX record."""
        raise NotImplementedError
    
    def create_spf_record(self, domain: str, include_servers: List[str]) -> bool:
        """Create SPF record."""
        raise NotImplementedError
    
    def create_dkim_record(self, domain: str, selector: str, public_key: str) -> bool:
        """Create DKIM record."""
        raise NotImplementedError
    
    def create_dmarc_record(self, domain: str, policy: str = 'reject') -> bool:
        """Create DMARC record."""
        raise NotImplementedError


class CloudflareProvider(DNSProvider):
    """Cloudflare DNS provider."""
    
    def __init__(self, credentials: Dict[str, str]):
        super().__init__(credentials)
        self.api_token = credentials.get('api_token')
        self.zone_id = credentials.get('zone_id')
        self.base_url = 'https://api.cloudflare.com/client/v4'
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json'
        }
    
    def create_mx_record(self, domain: str, mail_server: str, priority: int = 10) -> bool:
        """Create MX record via Cloudflare API."""
        try:
            data = {
                'type': 'MX',
                'name': domain,
                'content': mail_server,
                'priority': priority,
                'ttl': 3600
            }
            
            response = requests.post(
                f'{self.base_url}/zones/{self.zone_id}/dns_records',
                headers=self._get_headers(),
                json=data
            )
            
            if response.status_code == 200:
                success_message(f"MX record created: {domain} -> {mail_server} (priority: {priority})")
                return True
            else:
                error_exit(f"Failed to create MX record: {response.text}")
                
        except Exception as e:
            error_exit(f"Cloudflare API error: {e}")
    
    def create_spf_record(self, domain: str, include_servers: List[str]) -> bool:
        """Create SPF record via Cloudflare API."""
        try:
            include_text = ' '.join([f'include:{server}' for server in include_servers])
            spf_record = f'v=spf1 {include_text} ~all'
            
            data = {
                'type': 'TXT',
                'name': domain,
                'content': spf_record,
                'ttl': 3600
            }
            
            response = requests.post(
                f'{self.base_url}/zones/{self.zone_id}/dns_records',
                headers=self._get_headers(),
                json=data
            )
            
            if response.status_code == 200:
                success_message(f"SPF record created: {spf_record}")
                return True
            else:
                error_exit(f"Failed to create SPF record: {response.text}")
                
        except Exception as e:
            error_exit(f"Cloudflare API error: {e}")
    
    def create_dkim_record(self, domain: str, selector: str, public_key: str) -> bool:
        """Create DKIM record via Cloudflare API."""
        try:
            dkim_record = f'v=DKIM1; k=rsa; p={public_key}'
            
            data = {
                'type': 'TXT',
                'name': f'{selector}._domainkey.{domain}',
                'content': dkim_record,
                'ttl': 3600
            }
            
            response = requests.post(
                f'{self.base_url}/zones/{self.zone_id}/dns_records',
                headers=self._get_headers(),
                json=data
            )
            
            if response.status_code == 200:
                success_message(f"DKIM record created: {selector}._domainkey.{domain}")
                return True
            else:
                error_exit(f"Failed to create DKIM record: {response.text}")
                
        except Exception as e:
            error_exit(f"Cloudflare API error: {e}")
    
    def create_dmarc_record(self, domain: str, policy: str = 'reject') -> bool:
        """Create DMARC record via Cloudflare API."""
        try:
            dmarc_record = f'v=DMARC1; p={policy}; rua=mailto:dmarc@{domain}; ruf=mailto:dmarc@{domain}'
            
            data = {
                'type': 'TXT',
                'name': f'_dmarc.{domain}',
                'content': dmarc_record,
                'ttl': 3600
            }
            
            response = requests.post(
                f'{self.base_url}/zones/{self.zone_id}/dns_records',
                headers=self._get_headers(),
                json=data
            )
            
            if response.status_code == 200:
                success_message(f"DMARC record created: _dmarc.{domain}")
                return True
            else:
                error_exit(f"Failed to create DMARC record: {response.text}")
                
        except Exception as e:
            error_exit(f"Cloudflare API error: {e}")


class GoDaddyProvider(DNSProvider):
    """GoDaddy DNS provider."""
    
    def __init__(self, credentials: Dict[str, str]):
        super().__init__(credentials)
        self.api_key = credentials.get('api_key')
        self.api_secret = credentials.get('api_secret')
        self.base_url = 'https://api.godaddy.com/v1'
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            'Authorization': f'sso-key {self.api_key}:{self.api_secret}',
            'Content-Type': 'application/json'
        }
    
    def create_mx_record(self, domain: str, mail_server: str, priority: int = 10) -> bool:
        """Create MX record via GoDaddy API."""
        try:
            data = [{
                'type': 'MX',
                'name': '@',
                'data': mail_server,
                'priority': priority,
                'ttl': 3600
            }]
            
            response = requests.patch(
                f'{self.base_url}/domains/{domain}/records/MX',
                headers=self._get_headers(),
                json=data
            )
            
            if response.status_code == 200:
                success_message(f"MX record created: {domain} -> {mail_server} (priority: {priority})")
                return True
            else:
                error_exit(f"Failed to create MX record: {response.text}")
                
        except Exception as e:
            error_exit(f"GoDaddy API error: {e}")
    
    def create_spf_record(self, domain: str, include_servers: List[str]) -> bool:
        """Create SPF record via GoDaddy API."""
        try:
            include_text = ' '.join([f'include:{server}' for server in include_servers])
            spf_record = f'v=spf1 {include_text} ~all'
            
            data = [{
                'type': 'TXT',
                'name': '@',
                'data': spf_record,
                'ttl': 3600
            }]
            
            response = requests.patch(
                f'{self.base_url}/domains/{domain}/records/TXT',
                headers=self._get_headers(),
                json=data
            )
            
            if response.status_code == 200:
                success_message(f"SPF record created: {spf_record}")
                return True
            else:
                error_exit(f"Failed to create SPF record: {response.text}")
                
        except Exception as e:
            error_exit(f"GoDaddy API error: {e}")
    
    def create_dkim_record(self, domain: str, selector: str, public_key: str) -> bool:
        """Create DKIM record via GoDaddy API."""
        try:
            dkim_record = f'v=DKIM1; k=rsa; p={public_key}'
            
            data = [{
                'type': 'TXT',
                'name': f'{selector}._domainkey',
                'data': dkim_record,
                'ttl': 3600
            }]
            
            response = requests.patch(
                f'{self.base_url}/domains/{domain}/records/TXT',
                headers=self._get_headers(),
                json=data
            )
            
            if response.status_code == 200:
                success_message(f"DKIM record created: {selector}._domainkey.{domain}")
                return True
            else:
                error_exit(f"Failed to create DKIM record: {response.text}")
                
        except Exception as e:
            error_exit(f"GoDaddy API error: {e}")
    
    def create_dmarc_record(self, domain: str, policy: str = 'reject') -> bool:
        """Create DMARC record via GoDaddy API."""
        try:
            dmarc_record = f'v=DMARC1; p={policy}; rua=mailto:dmarc@{domain}; ruf=mailto:dmarc@{domain}'
            
            data = [{
                'type': 'TXT',
                'name': '_dmarc',
                'data': dmarc_record,
                'ttl': 3600
            }]
            
            response = requests.patch(
                f'{self.base_url}/domains/{domain}/records/TXT',
                headers=self._get_headers(),
                json=data
            )
            
            if response.status_code == 200:
                success_message(f"DMARC record created: _dmarc.{domain}")
                return True
            else:
                error_exit(f"Failed to create DMARC record: {response.text}")
                
        except Exception as e:
            error_exit(f"GoDaddy API error: {e}")


class DNSManager:
    """Manages DNS records for email domains."""
    
    def __init__(self):
        self.providers = {
            'cloudflare': CloudflareProvider,
            'godaddy': GoDaddyProvider
        }
    
    def get_provider(self, provider_name: str, credentials: Dict[str, str]) -> DNSProvider:
        """Get DNS provider instance."""
        provider_class = self.providers.get(provider_name.lower())
        if not provider_class:
            error_exit(f"Unsupported DNS provider: {provider_name}. Supported: {list(self.providers.keys())}")
        
        return provider_class(credentials)
    
    def verify_domain(self, domain: str) -> bool:
        """Verify domain exists and is accessible."""
        try:
            domain = sanitize_input(domain)
            if not validate_domain(domain):
                error_exit(f"Invalid domain: {domain}")
            
            # Check if domain resolves
            resolver = dns.resolver.Resolver()
            resolver.resolve(domain, 'A')
            return True
            
        except dns.resolver.NXDOMAIN:
            error_exit(f"Domain {domain} does not exist")
        except dns.resolver.NoAnswer:
            error_exit(f"Domain {domain} has no A record")
        except Exception as e:
            error_exit(f"DNS verification failed: {e}")
    
    def check_existing_records(self, domain: str) -> Dict[str, Any]:
        """Check existing DNS records for a domain."""
        try:
            domain = sanitize_input(domain)
            records = {
                'mx': [],
                'spf': None,
                'dkim': [],
                'dmarc': None
            }
            
            resolver = dns.resolver.Resolver()
            
            # Check MX records
            try:
                mx_records = resolver.resolve(domain, 'MX')
                for mx in mx_records:
                    records['mx'].append({
                        'preference': mx.preference,
                        'exchange': str(mx.exchange)
                    })
            except dns.resolver.NoAnswer:
                pass
            
            # Check SPF record
            try:
                spf_records = resolver.resolve(domain, 'TXT')
                for record in spf_records:
                    if str(record.text).startswith('v=spf1'):
                        records['spf'] = str(record.text).strip('"')
                        break
            except dns.resolver.NoAnswer:
                pass
            
            # Check DMARC record
            try:
                dmarc_records = resolver.resolve(f'_dmarc.{domain}', 'TXT')
                for record in dmarc_records:
                    if str(record.text).startswith('v=DMARC1'):
                        records['dmarc'] = str(record.text).strip('"')
                        break
            except dns.resolver.NoAnswer:
                pass
            
            # Check for common DKIM selectors
            common_selectors = ['k1', 's1', 'mail', 'default', 'selector1', 'selector2']
            for selector in common_selectors:
                try:
                    dkim_records = resolver.resolve(f'{selector}._domainkey.{domain}', 'TXT')
                    for record in dkim_records:
                        if str(record.text).startswith('v=DKIM1'):
                            records['dkim'].append({
                                'selector': selector,
                                'record': str(record.text).strip('"')
                            })
                except dns.resolver.NoAnswer:
                    pass
            
            return records
            
        except Exception as e:
            error_exit(f"Failed to check DNS records: {e}")
    
    def setup_email_dns(self, domain: str, provider_name: str, credentials: Dict[str, str],
                       mail_server: str, spf_includes: List[str], dkim_selector: str = None,
                       dkim_public_key: str = None, dmarc_policy: str = 'reject') -> bool:
        """Setup complete email DNS configuration."""
        try:
            domain = sanitize_input(domain)
            mail_server = sanitize_input(mail_server)
            
            # Verify domain first
            self.verify_domain(domain)
            
            # Get provider
            provider = self.get_provider(provider_name, credentials)
            
            # Check existing records
            existing = self.check_existing_records(domain)
            
            info_message(f"Setting up email DNS for {domain}")
            
            # Create MX record
            if existing['mx']:
                info_message(f"Existing MX records found: {existing['mx']}")
            provider.create_mx_record(domain, mail_server)
            
            # Create SPF record
            if existing['spf']:
                info_message(f"Existing SPF record found: {existing['spf']}")
            provider.create_spf_record(domain, spf_includes)
            
            # Create DKIM record if provided
            if dkim_selector and dkim_public_key:
                if existing['dkim']:
                    info_message(f"Existing DKIM records found: {existing['dkim']}")
                provider.create_dkim_record(domain, dkim_selector, dkim_public_key)
            
            # Create DMARC record
            if existing['dmarc']:
                info_message(f"Existing DMARC record found: {existing['dmarc']}")
            provider.create_dmarc_record(domain, dmarc_policy)
            
            success_message(f"Email DNS setup completed for {domain}")
            return True
            
        except Exception as e:
            error_exit(f"DNS setup failed: {e}")
    
    def generate_dkim_key_pair(self) -> Tuple[str, str]:
        """Generate DKIM key pair (private and public)."""
        try:
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.backends import default_backend
            
            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            
            # Serialize private key
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode('utf-8')
            
            # Get public key
            public_key = private_key.public_key()
            public_numbers = public_key.public_numbers()
            
            # Convert to base64 format for DNS
            public_der = public_key.public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            import base64
            public_base64 = base64.b64encode(public_der).decode('utf-8')
            
            return private_pem, public_base64
            
        except ImportError:
            error_exit("cryptography library required for DKIM key generation")
        except Exception as e:
            error_exit(f"Failed to generate DKIM keys: {e}")
