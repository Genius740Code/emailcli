"""Email validation and domain verification utilities."""

import re
import dns.resolver
import dns.exception
import socket
import smtplib
import requests
from typing import Dict, List, Optional, Tuple, Any
from ..utils.utils import validate_email, validate_domain, info_message, warning_message, error_message


class EmailValidator:
    """Advanced email validation and domain verification."""
    
    # Common disposable email domains
    DISPOSABLE_DOMAINS = {
        '10minutemail.com', '20minutemail.com', 'guerillamail.com', 'mailinator.com',
        'tempmail.org', 'temp-mail.org', 'yopmail.com', 'maildrop.cc', 'throwaway.email',
        'mailnull.com', 'spamgourmet.com', 'meltmail.com', 'tempmail.com', 'jetable.org',
        'spambox.us', 'spamhole.com', 'spamfree24.eu', 'spamfree24.net', 'spamfree24.org',
        'trashmail.com', 'trashmail.net', 'trashmail.org', 'trashmail.io', 'tempmail.de',
        'tempmail.net', 'tempmail.us', 'tempmail.co', 'tempmail.info', 'tempmail.biz',
        'tempmail.email', 'tempmail.link', 'tempmail.site', 'tempmail.space', 'tempmail.tech',
        'tempmail.world', 'tempmail.xyz', 'tempmail.app', 'tempmail.dev', 'tempmail.host',
        'tempmail.me', 'tempmail.online', 'tempmail.pro', 'tempmail.store', 'tempmail.today',
        'tempmail.top', 'tempmail.website', 'tempmail.work', 'tempmail.wtf', 'tempmail.zone'
    }
    
    # Common typo domains
    TYPO_DOMAINS = {
        'gmail.co': 'gmail.com',
        'gmail.con': 'gmail.com',
        'gmial.com': 'gmail.com',
        'gmaill.com': 'gmail.com',
        'gmailcom': 'gmail.com',
        'yahoo.co': 'yahoo.com',
        'yahoo.con': 'yahoo.com',
        'yaho.com': 'yahoo.com',
        'outlook.co': 'outlook.com',
        'outlook.con': 'outlook.com',
        'hotmal.com': 'hotmail.com',
        'hotmial.com': 'hotmail.com',
        'icloud.co': 'icloud.com',
        'icloud.con': 'icloud.com'
    }
    
    @classmethod
    def validate_email_advanced(cls, email: str) -> Dict[str, Any]:
        """Advanced email validation with multiple checks."""
        result = {
            'email': email,
            'is_valid': False,
            'is_disposable': False,
            'has_typo': False,
            'suggested_correction': None,
            'domain_valid': False,
            'mx_records': [],
            'smtp_valid': False,
            'errors': [],
            'warnings': [],
            'score': 0  # 0-100 confidence score
        }
        
        # Basic format validation
        if not validate_email(email):
            result['errors'].append('Invalid email format')
            return result
        
        # Check for disposable email
        domain = email.split('@')[1].lower()
        if domain in cls.DISPOSABLE_DOMAINS:
            result['is_disposable'] = True
            result['warnings'].append('Disposable email domain detected')
            result['score'] -= 20
        
        # Check for common typos
        if domain in cls.TYPO_DOMAINS:
            result['has_typo'] = True
            result['suggested_correction'] = email.replace(domain, cls.TYPO_DOMAINS[domain])
            result['warnings'].append(f'Possible typo: {domain} -> {cls.TYPO_DOMAINS[domain]}')
            result['score'] -= 10
        
        # Domain validation
        domain_result = cls.validate_domain(domain)
        result['domain_valid'] = domain_result['is_valid']
        result['mx_records'] = domain_result['mx_records']
        result['errors'].extend(domain_result['errors'])
        result['warnings'].extend(domain_result['warnings'])
        result['score'] += domain_result['score']
        
        # SMTP validation (optional, can be slow)
        try:
            smtp_result = cls.validate_smtp(email)
            result['smtp_valid'] = smtp_result['is_valid']
            result['errors'].extend(smtp_result['errors'])
            result['warnings'].extend(smtp_result['warnings'])
            result['score'] += smtp_result['score']
        except Exception as e:
            result['warnings'].append(f'SMTP validation failed: {e}')
        
        # Calculate final score
        result['score'] = max(0, min(100, result['score']))
        result['is_valid'] = len(result['errors']) == 0 and result['score'] >= 70
        
        return result
    
    @classmethod
    def validate_domain(cls, domain: str) -> Dict[str, Any]:
        """Validate domain and check DNS records."""
        result = {
            'domain': domain,
            'is_valid': False,
            'has_mx_record': False,
            'mx_records': [],
            'has_a_record': False,
            'has_spf_record': False,
            'has_dmarc_record': False,
            'errors': [],
            'warnings': [],
            'score': 0
        }
        
        if not validate_domain(domain):
            result['errors'].append('Invalid domain format')
            return result
        
        try:
            # Check MX records
            try:
                mx_answers = dns.resolver.resolve(domain, 'MX')
                result['has_mx_record'] = True
                result['mx_records'] = [str(mx) for mx in mx_answers]
                result['score'] += 40
            except dns.resolver.NoAnswer:
                result['warnings'].append('No MX records found')
            except dns.exception.DNSException as e:
                result['errors'].append(f'DNS MX lookup failed: {e}')
            
            # Check A records
            try:
                dns.resolver.resolve(domain, 'A')
                result['has_a_record'] = True
                result['score'] += 20
            except dns.resolver.NoAnswer:
                result['warnings'].append('No A records found')
            except dns.exception.DNSException:
                pass  # A records are optional for email
            
            # Check SPF record
            try:
                spf_answers = dns.resolver.resolve(domain, 'TXT')
                for txt in spf_answers:
                    txt_str = str(txt)
                    if txt_str.startswith('v=spf1'):
                        result['has_spf_record'] = True
                        result['score'] += 10
                        break
            except dns.resolver.NoAnswer:
                result['warnings'].append('No SPF record found')
            except dns.exception.DNSException:
                pass
            
            # Check DMARC record
            try:
                dmarc_answers = dns.resolver.resolve(f'_dmarc.{domain}', 'TXT')
                for txt in dmarc_answers:
                    txt_str = str(txt)
                    if txt_str.startswith('v=DMARC1'):
                        result['has_dmarc_record'] = True
                        result['score'] += 10
                        break
            except dns.resolver.NoAnswer:
                result['warnings'].append('No DMARC record found')
            except dns.exception.DNSException:
                pass
            
            result['is_valid'] = len(result['errors']) == 0
            
        except Exception as e:
            result['errors'].append(f'Domain validation failed: {e}')
        
        return result
    
    @classmethod
    def validate_smtp(cls, email: str, timeout: int = 10) -> Dict[str, Any]:
        """Validate email via SMTP connection."""
        result = {
            'email': email,
            'is_valid': False,
            'smtp_server': None,
            'errors': [],
            'warnings': [],
            'score': 0
        }
        
        domain = email.split('@')[1]
        
        # Get MX records
        try:
            mx_answers = dns.resolver.resolve(domain, 'MX')
            mx_records = sorted(mx_answers, key=lambda x: x.preference)
            mx_host = str(mx_records[0].exchange)
            result['smtp_server'] = mx_host
        except:
            result['errors'].append('No MX records found for SMTP validation')
            return result
        
        # Try SMTP connection
        try:
            with smtplib.SMTP(timeout=timeout) as smtp:
                smtp.connect(mx_host)
                smtp.helo()
                
                # Try to verify the email address (VRFY command)
                try:
                    response = smtp.verify(email)
                    if response.startswith('250'):
                        result['is_valid'] = True
                        result['score'] = 20
                    else:
                        result['warnings'].append('Email address not verified by SMTP')
                except smtplib.SMTPException:
                    # VRFY is often disabled, so we can't rely on it
                    result['warnings'].append('SMTP VRFY command not available')
                    result['score'] = 5  # Give partial credit for successful connection
                
        except smtplib.SMTPException as e:
            result['errors'].append(f'SMTP connection failed: {e}')
        except Exception as e:
            result['errors'].append(f'SMTP validation error: {e}')
        
        return result
    
    @classmethod
    def check_email_deliverability(cls, email: str) -> Dict[str, Any]:
        """Check email deliverability using external services."""
        result = {
            'email': email,
            'deliverable': False,
            'risk_level': 'unknown',
            'suggestions': [],
            'errors': []
        }
        
        # This would typically use external APIs like Hunter.io, ZeroBounce, etc.
        # For now, we'll do basic checks
        
        basic_validation = cls.validate_email_advanced(email)
        if not basic_validation['is_valid']:
            result['errors'].extend(basic_validation['errors'])
            result['risk_level'] = 'high'
            return result
        
        # Check if it's a disposable email
        if basic_validation['is_disposable']:
            result['risk_level'] = 'high'
            result['suggestions'].append('Avoid using disposable email addresses')
        
        # Check for typos
        if basic_validation['has_typo']:
            result['risk_level'] = 'medium'
            result['suggestions'].append(f'Did you mean: {basic_validation["suggested_correction"]}')
        
        # Check domain reputation (basic check)
        domain = email.split('@')[1]
        if cls._check_domain_reputation(domain):
            result['deliverable'] = True
            result['risk_level'] = 'low'
        else:
            result['risk_level'] = 'medium'
            result['suggestions'].append('Domain has potential delivery issues')
        
        return result
    
    @classmethod
    def _check_domain_reputation(cls, domain: str) -> bool:
        """Basic domain reputation check."""
        # This is a simplified version - in production, you'd use reputation APIs
        try:
            # Check if domain resolves
            socket.gethostbyname(domain)
            return True
        except socket.gaierror:
            return False
    
    @classmethod
    def suggest_email_corrections(cls, email: str) -> List[str]:
        """Suggest corrections for potentially misspelled emails."""
        suggestions = []
        
        if not validate_email(email):
            return suggestions
        
        domain = email.split('@')[1].lower()
        local = email.split('@')[0]
        
        # Check for typo domains
        if domain in cls.TYPO_DOMAINS:
            corrected_domain = cls.TYPO_DOMAINS[domain]
            suggestions.append(f"{local}@{corrected_domain}")
        
        # Check for common local part issues
        if '.' not in local and len(local) > 1:
            # Suggest adding dot for long usernames
            if len(local) > 6:
                suggestions.append(f"{local[:3]}.{local[3:]}@{domain}")
        
        return suggestions
    
    @classmethod
    def batch_validate_emails(cls, emails: List[str]) -> List[Dict[str, Any]]:
        """Validate multiple emails efficiently."""
        results = []
        
        for email in emails:
            try:
                result = cls.validate_email_advanced(email)
                results.append(result)
            except Exception as e:
                results.append({
                    'email': email,
                    'is_valid': False,
                    'errors': [str(e)],
                    'score': 0
                })
        
        return results
