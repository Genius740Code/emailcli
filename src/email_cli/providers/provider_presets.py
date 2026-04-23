"""Email provider presets for quick domain setup."""

from typing import Dict, Any, List


class EmailProviderPresets:
    """Pre-configured email provider settings for quick setup."""
    
    DNS_PROVIDERS = {
        'cloudflare': {
            'name': 'Cloudflare',
            'description': 'Cloudflare DNS API',
            'api_required': True,
            'features': ['full_dns_management', 'automatic_ssl', 'ddos_protection']
        },
        'route53': {
            'name': 'AWS Route53',
            'description': 'Amazon Web Services DNS',
            'api_required': True,
            'features': ['aws_integration', 'high_availability', 'global_infrastructure']
        },
        'godaddy': {
            'name': 'GoDaddy',
            'description': 'GoDaddy DNS API',
            'api_required': True,
            'features': ['domain_registrar', 'web_hosting', 'email_services']
        },
        'namecheap': {
            'name': 'Namecheap',
            'description': 'Namecheap DNS API',
            'api_required': True,
            'features': ['budget_friendly', 'domain_registration', 'basic_dns']
        },
        'custom': {
            'name': 'Custom/Manual',
            'description': 'Manual DNS configuration',
            'api_required': False,
            'features': ['manual_setup', 'any_provider']
        }
    }
    
    # Legacy presets for backward compatibility
    LEGACY_PRESETS = {
        'gmail': {
            'name': 'Gmail',
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'imap_server': 'imap.gmail.com',
            'imap_port': 993,
            'use_ssl': True,
            'use_tls': True,
            'description': 'Google Gmail (requires App Password for 2FA)',
            'notes': 'Enable "Less secure apps" or use App Password for 2FA'
        },
        'outlook': {
            'name': 'Outlook/Hotmail',
            'smtp_server': 'smtp-mail.outlook.com',
            'smtp_port': 587,
            'imap_server': 'outlook.office365.com',
            'imap_port': 993,
            'use_ssl': True,
            'use_tls': True,
            'description': 'Microsoft Outlook/Hotmail',
            'notes': 'Works with Outlook.com, Hotmail, Live.com'
        }
    }
    
    @classmethod
    def get_dns_provider(cls, provider_name: str) -> Dict[str, Any]:
        """Get DNS provider configuration."""
        return cls.DNS_PROVIDERS.get(provider_name.lower(), cls.DNS_PROVIDERS['custom'])
    
    @classmethod
    def get_preset(cls, provider_name: str) -> Dict[str, Any]:
        """Get a specific provider preset (legacy support)."""
        return cls.LEGACY_PRESETS.get(provider_name.lower(), {})
    
    @classmethod
    def list_dns_providers(cls) -> List[Dict[str, Any]]:
        """List all available DNS providers."""
        return [
            {
                'key': key,
                **provider
            }
            for key, provider in cls.DNS_PROVIDERS.items()
        ]
    
    @classmethod
    def list_presets(cls) -> List[Dict[str, Any]]:
        """List all available presets (legacy support)."""
        return [
            {
                'key': key,
                **preset
            }
            for key, preset in cls.LEGACY_PRESETS.items()
        ]
    
    @classmethod
    def get_dns_provider_names(cls) -> List[str]:
        """Get list of DNS provider names."""
        return list(cls.DNS_PROVIDERS.keys())
    
    @classmethod
    def get_preset_names(cls) -> List[str]:
        """Get list of preset names (legacy support)."""
        return list(cls.LEGACY_PRESETS.keys())
    
    @classmethod
    def generate_domain_config(cls, domain: str, mail_server: str = None) -> Dict[str, Any]:
        """Generate domain-based email configuration."""
        if not mail_server:
            mail_server = f"mail.{domain}"
        
        return {
            'name': f'{domain} Email',
            'smtp_server': mail_server,
            'smtp_port': 587,
            'imap_server': mail_server,
            'imap_port': 993,
            'use_ssl': True,
            'use_tls': True,
            'description': f'Custom domain email for {domain}',
            'notes': f'Uses mail server at {mail_server}'
        }
    
    @classmethod
    def detect_provider_from_email(cls, email: str) -> str:
        """Detect email provider from email address (legacy support)."""
        domain = email.split('@')[1].lower() if '@' in email else ''
        
        # Common domain mappings
        domain_mappings = {
            'gmail.com': 'gmail',
            'googlemail.com': 'gmail',
            'outlook.com': 'outlook',
            'hotmail.com': 'outlook',
            'live.com': 'outlook',
            'yahoo.com': 'yahoo',
            'ymail.com': 'yahoo',
            'icloud.com': 'icloud',
            'me.com': 'icloud',
            'mac.com': 'icloud'
        }
        
        return domain_mappings.get(domain, 'custom')
    
    @classmethod
    def get_default_dns_records(cls, domain: str, mail_server: str = None) -> Dict[str, Any]:
        """Get default DNS records for domain-based email setup."""
        if not mail_server:
            mail_server = f"mail.{domain}"
        
        return {
            'mx': {
                'name': '@',
                'value': mail_server,
                'priority': 10
            },
            'a': {
                'name': mail_server,
                'value': '[SERVER_IP]',  # User needs to replace this
                'ttl': 3600
            },
            'spf': {
                'name': '@',
                'value': f'v=spf1 mx include:{mail_server} ~all',
                'type': 'TXT'
            },
            'dmarc': {
                'name': '_dmarc',
                'value': f'v=DMARC1; p=quarantine; rua=mailto:dmarc@{domain}',
                'type': 'TXT'
            },
            'dkim': {
                'name': 'default._domainkey',
                'value': '[GENERATED_DKIM_RECORD]',  # Will be generated
                'type': 'TXT'
            }
        }


class EmailTemplatePresets:
    """Pre-configured email templates for quick sending."""
    
    TEMPLATES = {
        'welcome': {
            'name': 'Welcome Email',
            'subject': 'Welcome to {{company_name}}!',
            'body': '''Dear {{name}},

Welcome to {{company_name}}! We're excited to have you on board.

{{custom_message}}

Best regards,
{{sender_name}}
{{company_name}}''',
            'variables': ['name', 'company_name', 'custom_message', 'sender_name']
        },
        'newsletter': {
            'name': 'Newsletter',
            'subject': '{{newsletter_title}} - {{date}}',
            'body': '''Hello {{name}},

{{newsletter_content}}

Read more on our website: {{website_url}}

Unsubscribe: {{unsubscribe_url}}
{{company_name}}''',
            'variables': ['name', 'newsletter_title', 'date', 'newsletter_content', 'website_url', 'unsubscribe_url', 'company_name']
        },
        'announcement': {
            'name': 'Company Announcement',
            'subject': 'Important Announcement: {{announcement_title}}',
            'body': '''Dear {{name}},

{{announcement_message}}

This announcement affects: {{affected_groups}}

For more information, contact: {{contact_info}}

Thank you,
{{sender_name}}
{{company_name}}''',
            'variables': ['name', 'announcement_title', 'announcement_message', 'affected_groups', 'contact_info', 'sender_name', 'company_name']
        },
        'followup': {
            'name': 'Follow-up Email',
            'subject': 'Following up on {{original_topic}}',
            'body': '''Hi {{name}},

Just wanted to follow up on our discussion about {{original_topic}}.

{{followup_message}}

Please let me know if you have any questions.

Best regards,
{{sender_name}}''',
            'variables': ['name', 'original_topic', 'followup_message', 'sender_name']
        },
        'support': {
            'name': 'Customer Support',
            'subject': 'Re: Support Request #{{ticket_number}}',
            'body': '''Dear {{name}},

Thank you for contacting {{company_name}} support.

Regarding your request #{{ticket_number}}:
{{support_response}}

If you need further assistance, please reply to this email or call us at {{phone_number}}.

Best regards,
{{support_agent_name}}
{{company_name}} Support Team''',
            'variables': ['name', 'company_name', 'ticket_number', 'support_response', 'phone_number', 'support_agent_name']
        },
        'invoice': {
            'name': 'Invoice Notification',
            'subject': 'Invoice #{{invoice_number}} from {{company_name}}',
            'body': '''Dear {{name}},

Please find attached invoice #{{invoice_number}} for {{service_description}}.

Amount: {{amount}}
Due Date: {{due_date}}

{{payment_instructions}}

Thank you for your business!

Best regards,
{{sender_name}}
{{company_name}}''',
            'variables': ['name', 'invoice_number', 'company_name', 'service_description', 'amount', 'due_date', 'payment_instructions', 'sender_name']
        }
    }
    
    @classmethod
    def get_template(cls, template_name: str) -> Dict[str, Any]:
        """Get a specific email template."""
        return cls.TEMPLATES.get(template_name, {})
    
    @classmethod
    def list_templates(cls) -> List[Dict[str, Any]]:
        """List all available templates."""
        return [
            {
                'key': key,
                **template
            }
            for key, template in cls.TEMPLATES.items()
        ]
    
    @classmethod
    def get_template_names(cls) -> List[str]:
        """Get list of template names."""
        return list(cls.TEMPLATES.keys())
    
    @classmethod
    def render_template(cls, template_name: str, variables: Dict[str, str]) -> Dict[str, str]:
        """Render a template with provided variables."""
        template = cls.get_template(template_name)
        if not template:
            return {'subject': '', 'body': ''}
        
        subject = template.get('subject', '')
        body = template.get('body', '')
        
        # Replace variables
        for var, value in variables.items():
            placeholder = f'{{{{{var}}}}}'
            subject = subject.replace(placeholder, value)
            body = body.replace(placeholder, value)
        
        return {'subject': subject, 'body': body}
