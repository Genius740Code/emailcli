"""Account management for the email CLI tool."""

import keyring
import hashlib
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from datetime import datetime
from typing import Dict, Any, Optional, List
from .config import ConfigManager
from .storage import StorageManager
from .email_engine import EmailEngine
from .utils import validate_email, error_exit, success_message, info_message, sanitize_input, generate_secure_token


class AccountManager:
    """Manages email accounts and domain configurations."""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.storage_manager = StorageManager()
        self._encryption_key = self._get_or_create_encryption_key()
    
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for credential storage."""
        try:
            # Try to get existing key from keyring
            key_data = keyring.get_password("email-cli-encryption", "master-key")
            if key_data:
                return base64.urlsafe_b64decode(key_data.encode())
        except:
            pass
        
        # Generate new key
        key = Fernet.generate_key()
        try:
            keyring.set_password("email-cli-encryption", "master-key", 
                               base64.urlsafe_b64encode(key).decode())
        except Exception as e:
            error_exit(f"Failed to store encryption key: {e}")
        
        return key
    
    def _encrypt_password(self, password: str) -> str:
        """Encrypt password using Fernet encryption."""
        fernet = Fernet(self._encryption_key)
        encrypted_password = fernet.encrypt(password.encode('utf-8'))
        return base64.urlsafe_b64encode(encrypted_password).decode()
    
    def _decrypt_password(self, encrypted_password: str) -> str:
        """Decrypt password using Fernet encryption."""
        try:
            fernet = Fernet(self._encryption_key)
            encrypted_data = base64.urlsafe_b64decode(encrypted_password.encode())
            decrypted_password = fernet.decrypt(encrypted_data)
            return decrypted_password.decode('utf-8')
        except Exception as e:
            error_exit(f"Failed to decrypt password: {e}")
    
    def setup_domain(self, domain: str, smtp_server: str, smtp_port: int,
                     imap_server: str, imap_port: int, username: str,
                     password: str, use_ssl: bool = True, use_tls: bool = True) -> None:
        """Setup a new email domain configuration with secure credential storage."""
        # Sanitize inputs
        domain = sanitize_input(domain)
        smtp_server = sanitize_input(smtp_server)
        imap_server = sanitize_input(imap_server)
        username = sanitize_input(username)
        
        # Validate password strength
        if len(password) < 8:
            error_exit("Password must be at least 8 characters long")
        
        # Encrypt and store password
        encrypted_password = self._encrypt_password(password)
        service_name = f"email-cli-{domain}"
        keyring.set_password(service_name, username, encrypted_password)
        
        # Add domain configuration (without password)
        self.config_manager.add_domain(
            domain, smtp_server, smtp_port, imap_server, imap_port,
            username, "[ENCRYPTED]", use_ssl, use_tls
        )
        
        success_message(f"Domain {domain} configured successfully")
    
    def create_account(self, email: str) -> None:
        """Create a new email account."""
        if not validate_email(email):
            error_exit(f"Invalid email address: {email}")
        
        # Extract domain from email
        domain = email.split('@')[1]
        
        # Check if domain is configured
        domain_config = self.config_manager.get_domain_config(domain)
        if not domain_config:
            error_exit(f"Domain {domain} is not configured. Use 'email-cli setup {domain}' first.")
        
        # Get and decrypt password from keyring
        service_name = f"email-cli-{domain}"
        encrypted_password = keyring.get_password(service_name, domain_config['username'])
        if not encrypted_password:
            error_exit(f"Password not found for domain {domain}")
        
        password = self._decrypt_password(encrypted_password)
        
        # Test connection
        domain_config['password'] = password
        engine = EmailEngine(domain_config)
        success, message = engine.test_connection()
        if not success:
            error_exit(f"Connection test failed: {message}")
        
        # Create account in storage
        self.storage_manager.create_account(email, domain)
        
        success_message(f"Account {email} created successfully")
    
    def list_accounts(self) -> List[Dict[str, Any]]:
        """List all configured email accounts."""
        return self.storage_manager.get_accounts()
    
    def send_email(self, from_email: str, to_address: str, subject: str, 
                   body_text: str, cc_address: Optional[str] = None,
                   bcc_address: Optional[str] = None, body_html: Optional[str] = None) -> None:
        """Send an email."""
        # Validate from email
        if not validate_email(from_email):
            error_exit(f"Invalid from email: {from_email}")
        
        if not validate_email(to_address):
            error_exit(f"Invalid to email: {to_address}")
        
        # Get account
        account = self.storage_manager.get_account(from_email)
        if not account:
            error_exit(f"Account {from_email} not found")
        
        # Get domain configuration
        domain = account['domain']
        domain_config = self.config_manager.get_domain_config(domain)
        if not domain_config:
            error_exit(f"Domain {domain} not configured")
        
        # Get and decrypt password from keyring
        service_name = f"email-cli-{domain}"
        encrypted_password = keyring.get_password(service_name, domain_config['username'])
        if not encrypted_password:
            error_exit(f"Password not found for domain {domain}")
        
        password = self._decrypt_password(encrypted_password)
        
        # Send email
        domain_config['password'] = password
        engine = EmailEngine(domain_config)
        
        # Save sent email to storage
        email_data = {
            'account_email': from_email,
            'message_id': f"sent-{hash(body_text)}-{hash(subject)}",
            'from_address': from_email,
            'to_address': to_address,
            'cc_address': cc_address,
            'bcc_address': bcc_address,
            'subject': subject,
            'body_text': body_text,
            'body_html': body_html,
            'folder': 'SENT',
            'is_read': True,
            'is_sent': True,
            'received_date': datetime.now().isoformat(),
            'size_bytes': len(body_text) + len(subject)
        }
        
        self.storage_manager.save_email(email_data)
        
        # Send via SMTP
        engine.send_email(
            to_address, subject, body_text, from_email,
            cc_address, bcc_address, body_html
        )
    
    def sync_emails(self, email: str, folder: str = 'INBOX', limit: int = 50) -> int:
        """Sync emails from server to local storage."""
        # Get account
        account = self.storage_manager.get_account(email)
        if not account:
            error_exit(f"Account {email} not found")
        
        # Get domain configuration
        domain = account['domain']
        domain_config = self.config_manager.get_domain_config(domain)
        if not domain_config:
            error_exit(f"Domain {domain} not configured")
        
        # Get and decrypt password from keyring
        service_name = f"email-cli-{domain}"
        encrypted_password = keyring.get_password(service_name, domain_config['username'])
        if not encrypted_password:
            error_exit(f"Password not found for domain {domain}")
        
        password = self._decrypt_password(encrypted_password)
        
        # Fetch emails
        domain_config['password'] = password
        engine = EmailEngine(domain_config)
        
        info_message(f"Fetching emails from {folder}...")
        emails = engine.fetch_emails(folder, limit)
        
        # Save emails to storage
        saved_count = 0
        for email_data in emails:
            email_data['account_email'] = email
            email_data['folder'] = folder
            try:
                self.storage_manager.save_email(email_data)
                saved_count += 1
            except Exception as e:
                print(f"Warning: Failed to save email: {e}")
        
        success_message(f"Synced {saved_count} emails from {folder}")
        return saved_count
    
    def get_inbox(self, email: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get inbox emails for an account."""
        return self.storage_manager.get_emails(email, 'INBOX', limit)
    
    def read_email(self, email_id: int) -> Optional[Dict[str, Any]]:
        """Read a specific email."""
        return self.storage_manager.get_email(email_id)
    
    def list_domains(self) -> Dict[str, Dict[str, Any]]:
        """List all configured domains."""
        return self.config_manager.list_domains()
    
    def test_domain_connection(self, domain: str) -> None:
        """Test connection for a domain."""
        domain_config = self.config_manager.get_domain_config(domain)
        if not domain_config:
            error_exit(f"Domain {domain} not configured")
        
        # Get and decrypt password from keyring
        service_name = f"email-cli-{domain}"
        encrypted_password = keyring.get_password(service_name, domain_config['username'])
        if not encrypted_password:
            error_exit(f"Password not found for domain {domain}")
        
        password = self._decrypt_password(encrypted_password)
        
        # Test connection
        domain_config['password'] = password
        engine = EmailEngine(domain_config)
        success, message = engine.test_connection()
        
        if success:
            success_message(f"Connection test for {domain} successful: {message}")
        else:
            error_exit(f"Connection test for {domain} failed: {message}")
    
    def get_folders(self, email: str) -> List[str]:
        """Get available folders for an email account."""
        # Get account
        account = self.storage_manager.get_account(email)
        if not account:
            error_exit(f"Account {email} not found")
        
        # Get domain configuration
        domain = account['domain']
        domain_config = self.config_manager.get_domain_config(domain)
        if not domain_config:
            error_exit(f"Domain {domain} not configured")
        
        # Get and decrypt password from keyring
        service_name = f"email-cli-{domain}"
        encrypted_password = keyring.get_password(service_name, domain_config['username'])
        if not encrypted_password:
            error_exit(f"Password not found for domain {domain}")
        
        password = self._decrypt_password(encrypted_password)
        
        # Get folders
        domain_config['password'] = password
        engine = EmailEngine(domain_config)
        return engine.get_folders()
