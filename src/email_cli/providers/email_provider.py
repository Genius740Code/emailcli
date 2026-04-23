"""Email provider API integration for account provisioning."""

import requests
import json
from typing import Dict, List, Optional, Any
from ..utils.utils import validate_email, error_exit, success_message, info_message, sanitize_input, generate_secure_token


class EmailProvider:
    """Base class for email service providers."""
    
    def __init__(self, credentials: Dict[str, str]):
        self.credentials = credentials
    
    def create_email_account(self, email: str, password: str, first_name: str = None, 
                           last_name: str = None) -> Dict[str, Any]:
        """Create a new email account."""
        raise NotImplementedError
    
    def delete_email_account(self, email: str) -> bool:
        """Delete an email account."""
        raise NotImplementedError
    
    def list_email_accounts(self, domain: str = None) -> List[Dict[str, Any]]:
        """List email accounts."""
        raise NotImplementedError
    
    def update_email_password(self, email: str, new_password: str) -> bool:
        """Update email account password."""
        raise NotImplementedError
    
    def get_account_info(self, email: str) -> Optional[Dict[str, Any]]:
        """Get account information."""
        raise NotImplementedError


class GoogleWorkspaceProvider(EmailProvider):
    """Google Workspace (G Suite) email provider."""
    
    def __init__(self, credentials: Dict[str, str]):
        super().__init__(credentials)
        self.admin_email = credentials.get('admin_email')
        self.service_account_key = credentials.get('service_account_key')
        self.domain = credentials.get('domain')
        self.base_url = 'https://admin.googleapis.com/admin/directory/v1'
        self._access_token = None
    
    def _get_access_token(self) -> str:
        """Get OAuth2 access token."""
        if self._access_token:
            return self._access_token
        
        try:
            # For simplicity, using service account flow
            # In production, you'd use google-auth library
            key_data = json.loads(self.service_account_key)
            
            # This is simplified - you'd normally use google-auth-python
            import base64
            import time
            import jwt
            
            # Create JWT
            now = int(time.time())
            payload = {
                'iss': key_data['client_email'],
                'scope': 'https://www.googleapis.com/auth/admin.directory.user',
                'aud': 'https://oauth2.googleapis.com/token',
                'exp': now + 3600,
                'iat': now
            }
            
            # Sign JWT
            private_key = key_data['private_key']
            jwt_token = jwt.encode(payload, private_key, algorithm='RS256')
            
            # Exchange for access token
            response = requests.post(
                'https://oauth2.googleapis.com/token',
                data={
                    'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                    'assertion': jwt_token
                }
            )
            
            if response.status_code == 200:
                self._access_token = response.json()['access_token']
                return self._access_token
            else:
                error_exit(f"Failed to get access token: {response.text}")
                
        except Exception as e:
            error_exit(f"Google Workspace authentication failed: {e}")
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            'Authorization': f'Bearer {self._get_access_token()}',
            'Content-Type': 'application/json'
        }
    
    def create_email_account(self, email: str, password: str, first_name: str = None, 
                           last_name: str = None) -> Dict[str, Any]:
        """Create Google Workspace email account."""
        try:
            email = sanitize_input(email)
            password = sanitize_input(password)
            
            if not validate_email(email):
                error_exit(f"Invalid email address: {email}")
            
            # Extract name parts
            if not first_name or not last_name:
                local_part = email.split('@')[0]
                parts = local_part.split('.')
                first_name = parts[0].capitalize() if parts else 'User'
                last_name = parts[1].capitalize() if len(parts) > 1 else 'Account'
            
            user_data = {
                'primaryEmail': email,
                'name': {
                    'givenName': first_name,
                    'familyName': last_name
                },
                'password': password,
                'orgUnitPath': '/'
            }
            
            response = requests.post(
                f'{self.base_url}/users',
                headers=self._get_headers(),
                json=user_data
            )
            
            if response.status_code == 200:
                user_info = response.json()
                success_message(f"Google Workspace account created: {email}")
                return user_info
            else:
                error_exit(f"Failed to create Google Workspace account: {response.text}")
                
        except Exception as e:
            error_exit(f"Google Workspace account creation failed: {e}")
    
    def delete_email_account(self, email: str) -> bool:
        """Delete Google Workspace email account."""
        try:
            email = sanitize_input(email)
            
            response = requests.delete(
                f'{self.base_url}/users/{email}',
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                success_message(f"Google Workspace account deleted: {email}")
                return True
            else:
                error_exit(f"Failed to delete Google Workspace account: {response.text}")
                
        except Exception as e:
            error_exit(f"Google Workspace account deletion failed: {e}")
    
    def list_email_accounts(self, domain: str = None) -> List[Dict[str, Any]]:
        """List Google Workspace email accounts."""
        try:
            domain = domain or self.domain
            if not domain:
                error_exit("Domain not specified")
            
            response = requests.get(
                f'{self.base_url}/users',
                headers=self._get_headers(),
                params={'domain': domain, 'maxResults': 500}
            )
            
            if response.status_code == 200:
                users = response.json().get('users', [])
                return users
            else:
                error_exit(f"Failed to list Google Workspace accounts: {response.text}")
                
        except Exception as e:
            error_exit(f"Google Workspace account listing failed: {e}")
    
    def update_email_password(self, email: str, new_password: str) -> bool:
        """Update Google Workspace email password."""
        try:
            email = sanitize_input(email)
            new_password = sanitize_input(new_password)
            
            user_data = {'password': new_password}
            
            response = requests.put(
                f'{self.base_url}/users/{email}',
                headers=self._get_headers(),
                json=user_data
            )
            
            if response.status_code == 200:
                success_message(f"Password updated for {email}")
                return True
            else:
                error_exit(f"Failed to update password: {response.text}")
                
        except Exception as e:
            error_exit(f"Password update failed: {e}")
    
    def get_account_info(self, email: str) -> Optional[Dict[str, Any]]:
        """Get Google Workspace account information."""
        try:
            email = sanitize_input(email)
            
            response = requests.get(
                f'{self.base_url}/users/{email}',
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception:
            return None


class Microsoft365Provider(EmailProvider):
    """Microsoft 365 email provider."""
    
    def __init__(self, credentials: Dict[str, str]):
        super().__init__(credentials)
        self.tenant_id = credentials.get('tenant_id')
        self.client_id = credentials.get('client_id')
        self.client_secret = credentials.get('client_secret')
        self.base_url = f'https://graph.microsoft.com/v1.0'
        self._access_token = None
    
    def _get_access_token(self) -> str:
        """Get OAuth2 access token."""
        if self._access_token:
            return self._access_token
        
        try:
            response = requests.post(
                f'https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token',
                data={
                    'grant_type': 'client_credentials',
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                    'scope': 'https://graph.microsoft.com/.default'
                }
            )
            
            if response.status_code == 200:
                self._access_token = response.json()['access_token']
                return self._access_token
            else:
                error_exit(f"Failed to get Microsoft 365 access token: {response.text}")
                
        except Exception as e:
            error_exit(f"Microsoft 365 authentication failed: {e}")
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            'Authorization': f'Bearer {self._get_access_token()}',
            'Content-Type': 'application/json'
        }
    
    def create_email_account(self, email: str, password: str, first_name: str = None, 
                           last_name: str = None) -> Dict[str, Any]:
        """Create Microsoft 365 email account."""
        try:
            email = sanitize_input(email)
            password = sanitize_input(password)
            
            if not validate_email(email):
                error_exit(f"Invalid email address: {email}")
            
            # Extract name parts
            if not first_name or not last_name:
                local_part = email.split('@')[0]
                parts = local_part.split('.')
                first_name = parts[0].capitalize() if parts else 'User'
                last_name = parts[1].capitalize() if len(parts) > 1 else 'Account'
            
            user_data = {
                'accountEnabled': True,
                'displayName': f'{first_name} {last_name}',
                'mailNickname': email.split('@')[0],
                'userPrincipalName': email,
                'passwordProfile': {
                    'password': password,
                    'forceChangePasswordNextSignIn': False
                },
                'usageLocation': 'US'
            }
            
            response = requests.post(
                f'{self.base_url}/users',
                headers=self._get_headers(),
                json=user_data
            )
            
            if response.status_code == 201:
                user_info = response.json()
                success_message(f"Microsoft 365 account created: {email}")
                return user_info
            else:
                error_exit(f"Failed to create Microsoft 365 account: {response.text}")
                
        except Exception as e:
            error_exit(f"Microsoft 365 account creation failed: {e}")
    
    def delete_email_account(self, email: str) -> bool:
        """Delete Microsoft 365 email account."""
        try:
            email = sanitize_input(email)
            
            response = requests.delete(
                f'{self.base_url}/users/{email}',
                headers=self._get_headers()
            )
            
            if response.status_code == 204:
                success_message(f"Microsoft 365 account deleted: {email}")
                return True
            else:
                error_exit(f"Failed to delete Microsoft 365 account: {response.text}")
                
        except Exception as e:
            error_exit(f"Microsoft 365 account deletion failed: {e}")
    
    def list_email_accounts(self, domain: str = None) -> List[Dict[str, Any]]:
        """List Microsoft 365 email accounts."""
        try:
            response = requests.get(
                f'{self.base_url}/users',
                headers=self._get_headers(),
                params={'$select': 'displayName,mail,userPrincipalName,accountEnabled'}
            )
            
            if response.status_code == 200:
                users = response.json().get('value', [])
                if domain:
                    users = [user for user in users if domain in user.get('mail', '')]
                return users
            else:
                error_exit(f"Failed to list Microsoft 365 accounts: {response.text}")
                
        except Exception as e:
            error_exit(f"Microsoft 365 account listing failed: {e}")
    
    def update_email_password(self, email: str, new_password: str) -> bool:
        """Update Microsoft 365 email password."""
        try:
            email = sanitize_input(email)
            new_password = sanitize_input(new_password)
            
            user_data = {
                'passwordProfile': {
                    'password': new_password,
                    'forceChangePasswordNextSignIn': False
                }
            }
            
            response = requests.patch(
                f'{self.base_url}/users/{email}',
                headers=self._get_headers(),
                json=user_data
            )
            
            if response.status_code == 200:
                success_message(f"Password updated for {email}")
                return True
            else:
                error_exit(f"Failed to update password: {response.text}")
                
        except Exception as e:
            error_exit(f"Password update failed: {e}")
    
    def get_account_info(self, email: str) -> Optional[Dict[str, Any]]:
        """Get Microsoft 365 account information."""
        try:
            email = sanitize_input(email)
            
            response = requests.get(
                f'{self.base_url}/users/{email}',
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception:
            return None


class CustomEmailProvider(EmailProvider):
    """Custom email provider with generic API."""
    
    def __init__(self, credentials: Dict[str, str]):
        super().__init__(credentials)
        self.api_url = credentials.get('api_url')
        self.api_key = credentials.get('api_key')
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    def create_email_account(self, email: str, password: str, first_name: str = None, 
                           last_name: str = None) -> Dict[str, Any]:
        """Create custom email account."""
        try:
            email = sanitize_input(email)
            password = sanitize_input(password)
            
            if not validate_email(email):
                error_exit(f"Invalid email address: {email}")
            
            # Extract name parts
            if not first_name or not last_name:
                local_part = email.split('@')[0]
                parts = local_part.split('.')
                first_name = parts[0].capitalize() if parts else 'User'
                last_name = parts[1].capitalize() if len(parts) > 1 else 'Account'
            
            user_data = {
                'email': email,
                'password': password,
                'first_name': first_name,
                'last_name': last_name
            }
            
            response = requests.post(
                f'{self.api_url}/users',
                headers=self.headers,
                json=user_data
            )
            
            if response.status_code in [200, 201]:
                user_info = response.json()
                success_message(f"Custom email account created: {email}")
                return user_info
            else:
                error_exit(f"Failed to create custom email account: {response.text}")
                
        except Exception as e:
            error_exit(f"Custom email account creation failed: {e}")
    
    def delete_email_account(self, email: str) -> bool:
        """Delete custom email account."""
        try:
            email = sanitize_input(email)
            
            response = requests.delete(
                f'{self.api_url}/users/{email}',
                headers=self.headers
            )
            
            if response.status_code in [200, 204]:
                success_message(f"Custom email account deleted: {email}")
                return True
            else:
                error_exit(f"Failed to delete custom email account: {response.text}")
                
        except Exception as e:
            error_exit(f"Custom email account deletion failed: {e}")
    
    def list_email_accounts(self, domain: str = None) -> List[Dict[str, Any]]:
        """List custom email accounts."""
        try:
            params = {}
            if domain:
                params['domain'] = domain
            
            response = requests.get(
                f'{self.api_url}/users',
                headers=self.headers,
                params=params
            )
            
            if response.status_code == 200:
                users = response.json().get('users', [])
                return users
            else:
                error_exit(f"Failed to list custom email accounts: {response.text}")
                
        except Exception as e:
            error_exit(f"Custom email account listing failed: {e}")
    
    def update_email_password(self, email: str, new_password: str) -> bool:
        """Update custom email password."""
        try:
            email = sanitize_input(email)
            new_password = sanitize_input(new_password)
            
            user_data = {'password': new_password}
            
            response = requests.patch(
                f'{self.api_url}/users/{email}',
                headers=self.headers,
                json=user_data
            )
            
            if response.status_code == 200:
                success_message(f"Password updated for {email}")
                return True
            else:
                error_exit(f"Failed to update password: {response.text}")
                
        except Exception as e:
            error_exit(f"Password update failed: {e}")
    
    def get_account_info(self, email: str) -> Optional[Dict[str, Any]]:
        """Get custom email account information."""
        try:
            email = sanitize_input(email)
            
            response = requests.get(
                f'{self.api_url}/users/{email}',
                headers=self.headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception:
            return None


class EmailProviderManager:
    """Manages email provider integrations."""
    
    def __init__(self):
        self.providers = {
            'google_workspace': GoogleWorkspaceProvider,
            'microsoft_365': Microsoft365Provider,
            'custom': CustomEmailProvider
        }
    
    def get_provider(self, provider_name: str, credentials: Dict[str, str]) -> EmailProvider:
        """Get email provider instance."""
        provider_class = self.providers.get(provider_name.lower())
        if not provider_class:
            error_exit(f"Unsupported email provider: {provider_name}. Supported: {list(self.providers.keys())}")
        
        return provider_class(credentials)
    
    def create_email_account(self, provider_name: str, credentials: Dict[str, str],
                            email: str, password: str, first_name: str = None,
                            last_name: str = None) -> Dict[str, Any]:
        """Create email account using specified provider."""
        provider = self.get_provider(provider_name, credentials)
        return provider.create_email_account(email, password, first_name, last_name)
    
    def delete_email_account(self, provider_name: str, credentials: Dict[str, str],
                           email: str) -> bool:
        """Delete email account using specified provider."""
        provider = self.get_provider(provider_name, credentials)
        return provider.delete_email_account(email)
    
    def list_email_accounts(self, provider_name: str, credentials: Dict[str, str],
                           domain: str = None) -> List[Dict[str, Any]]:
        """List email accounts using specified provider."""
        provider = self.get_provider(provider_name, credentials)
        return provider.list_email_accounts(domain)
    
    def update_email_password(self, provider_name: str, credentials: Dict[str, str],
                            email: str, new_password: str) -> bool:
        """Update email password using specified provider."""
        provider = self.get_provider(provider_name, credentials)
        return provider.update_email_password(email, new_password)
    
    def get_account_info(self, provider_name: str, credentials: Dict[str, str],
                        email: str) -> Optional[Dict[str, Any]]:
        """Get account information using specified provider."""
        provider = self.get_provider(provider_name, credentials)
        return provider.get_account_info(email)
