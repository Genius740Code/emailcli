"""Main CLI interface for the email CLI tool."""

import click
import sys
import time
from datetime import datetime
from typing import Optional, List
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed
from .utils.account_manager import AccountManager
from .providers.dns_manager import DNSManager
from .providers.email_provider import EmailProviderManager
from .providers.provider_presets import EmailProviderPresets, EmailTemplatePresets
from .security.email_validator import EmailValidator
from .utils.utils import validate_email, validate_domain, error_exit, success_message, info_message, get_user_input, sanitize_input, generate_secure_token
from .core.metrics import get_metrics_collector, track_operation
from .core.rate_limiter import get_rate_limiter, with_rate_limit


@click.group()
@click.version_option(version="1.0.0")
@click.option('--config-dir', type=click.Path(), help='Custom configuration directory')
@click.pass_context
def main(ctx, config_dir):
    """Email CLI Tool - Fast CLI email management for custom domains.

    FEATURES:
      - Quick setup wizard with provider presets
      - Email templates for common use cases  
      - Bulk account creation
      - Secure credential storage
      - Multi-domain support

    QUICK START:
      email-cli setup-wizard --interactive    # Interactive setup
      email-cli templates                      # List templates
      email-cli bulk-create domain.com --prefix user --count 5

    Use 'email-cli COMMAND --help' for detailed command help.
    """
    ctx.ensure_object(dict)
    ctx.obj['config_dir'] = config_dir


# @main.command('setup-domain-config')
# @click.argument('domain')
# @click.option('--smtp-server', required=True, help='SMTP server address')
# @click.option('--smtp-port', default=587, type=int, help='SMTP port (default: 587)')
# @click.option('--imap-server', required=True, help='IMAP server address')
# @click.option('--imap-port', default=993, type=int, help='IMAP port (default: 993)')
# @click.option('--username', required=True, help='Email username')
# @click.option('--password', help='Email password (will prompt if not provided)')
# @click.option('--no-ssl', is_flag=True, help='Disable SSL')
# @click.option('--no-tls', is_flag=True, help='Disable TLS')
# def setup_domain(domain, smtp_server, smtp_port, imap_server, imap_port, username, password, no_ssl, no_tls):
#     """Setup a new email domain configuration."""
#     # Input validation and sanitization
#     domain = sanitize_input(domain)
#     smtp_server = sanitize_input(smtp_server)
#     imap_server = sanitize_input(imap_server)
#     username = sanitize_input(username)
#     
#     if not validate_domain(domain):
#         error_exit(f"Invalid domain: {domain}")
#     
#     if not validate_email(username) and '@' in username:
#         error_exit(f"Invalid username format: {username}")
#     
#     if not password:
#         password = get_user_input("Enter password", hide_input=True)
#     
#     use_ssl = not no_ssl
#     use_tls = not no_tls
#     
#     # Validate port ranges
#     if not (1 <= smtp_port <= 65535):
#         error_exit(f"Invalid SMTP port: {smtp_port}")
#     if not (1 <= imap_port <= 65535):
#         error_exit(f"Invalid IMAP port: {imap_port}")
#     
#     account_manager = AccountManager()
#     account_manager.setup_domain(
#         domain, smtp_server, smtp_port, imap_server, imap_port,
#         username, password, use_ssl, use_tls
#     )


@main.command('setup-domain')
@click.argument('domain')
@click.option('--smtp-server', required=True, help='SMTP server address')
@click.option('--smtp-port', default=587, type=int, help='SMTP port (default: 587)')
@click.option('--imap-server', required=True, help='IMAP server address')
@click.option('--imap-port', default=993, type=int, help='IMAP port (default: 993)')
@click.option('--username', required=True, help='Email username')
@click.option('--password', help='Email password (will prompt if not provided)')
@click.option('--no-ssl', is_flag=True, help='Disable SSL')
@click.option('--no-tls', is_flag=True, help='Disable TLS')
def setup_domain(domain, smtp_server, smtp_port, imap_server, imap_port, username, password, no_ssl, no_tls):
    """Setup a new email domain configuration."""
    # Input validation and sanitization
    domain = sanitize_input(domain)
    smtp_server = sanitize_input(smtp_server)
    imap_server = sanitize_input(imap_server)
    username = sanitize_input(username)
    
    if not validate_domain(domain):
        error_exit(f"Invalid domain: {domain}")
    
    if not validate_email(username) and '@' in username:
        error_exit(f"Invalid username format: {username}")
    
    if not password:
        password = get_user_input("Enter password", hide_input=True)
    
    use_ssl = not no_ssl
    use_tls = not no_tls
    
    # Validate port ranges
    if not (1 <= smtp_port <= 65535):
        error_exit(f"Invalid SMTP port: {smtp_port}")
    if not (1 <= imap_port <= 65535):
        error_exit(f"Invalid IMAP port: {imap_port}")
    
    account_manager = AccountManager()
    account_manager.setup_domain(
        domain, smtp_server, smtp_port, imap_server, imap_port,
        username, password, use_ssl, use_tls
    )


@main.command('setup-wizard')
@click.option('--interactive', is_flag=True, help='Interactive setup wizard')
@click.option('--domain', help='Domain name to configure')
@click.option('--email', help='Email address to create (e.g., hello@domain.com)')
@click.option('--dns-provider', help='DNS provider (cloudflare, route53, godaddy, etc.)')
@click.option('--api-key', help='DNS provider API key')
@click.option('--mail-server', help='Mail server address (default: mail.domain.com)')
def setup_wizard(interactive, domain, email, dns_provider, api_key, mail_server):
    """Interactive setup wizard for domain-based email configuration."""
    account_manager = AccountManager()
    
    if interactive or not domain:
        # Interactive mode
        click.echo("Email CLI Domain Setup Wizard")
        click.echo("=" * 40)
        
        # Get domain
        if not domain:
            domain = get_user_input("Enter your domain name (e.g., example.com)")
        
        domain = sanitize_input(domain)
        if not domain or '.' not in domain or len(domain) < 4:
            error_exit(f"Invalid domain: {domain}")
        
        # Get email address to create
        if not email:
            email = get_user_input(f"Enter email address to create (e.g., hello@{domain})")
        
        email = sanitize_input(email)
        if not email or '@' not in email or '.' not in email.split('@')[1]:
            error_exit(f"Invalid email address: {email}")
        
        # Verify email belongs to domain
        if not email.endswith(f"@{domain}"):
            error_exit(f"Email address must belong to domain {domain}")
        
        click.echo(f"Interactive mode with domain: {domain}, email: {email}")
    else:
        # Non-interactive mode
        click.echo(f"Non-interactive mode with domain: {domain}, email: {email}")
        
        if not email:
            error_exit("--email is required when using --domain")
        
        if not email.endswith(f"@{domain}"):
            error_exit(f"Email address must belong to domain {domain}")
        
        domain = sanitize_input(domain)
        email = sanitize_input(email)
        
        # Simple domain validation
        if not domain or '.' not in domain or len(domain) < 4:
            error_exit(f"Invalid domain: {domain}")
        
        # Simple email validation
        if not email or '@' not in email or '.' not in email.split('@')[1]:
            error_exit(f"Invalid email address: {email}")
        
        click.echo("All validation passed!")
        
        # Setup domain and create email
        password = generate_secure_token(16)
        default_mail_server = mail_server or f"mail.{domain}"
        
        account_manager.setup_domain(
            domain, default_mail_server, 587, default_mail_server, 993,
            email, password, True, True
        )
        
        account_manager.create_account(email)
        success_message(f"Email account {email} created successfully!")
        success_message(f"Generated password: {password}")


@main.command()
@click.argument('email')
@click.option('--provider', help='Email provider for account creation')
@click.option('--password', help='Password for new account (will auto-generate if not provided)')
@click.option('--first-name', help='First name for account')
@click.option('--last-name', help='Last name for account')
@click.option('--no-dns', is_flag=True, help='Skip DNS setup')
def create(email, provider, password, first_name, last_name, no_dns):
    """Create a new email account."""
    account_manager = AccountManager()
    
    if provider:
        # Create account via provider API
        from ..config.config import ConfigManager
        config_manager = ConfigManager()
        
        # Get provider credentials
        provider_config = config_manager.get_provider_config(provider)
        if not provider_config:
            error_exit(f"Provider {provider} not configured. Use 'email-cli config-provider {provider}' first.")
        
        # Generate password if not provided
        if not password:
            password = generate_secure_token(16)
        
        # Create account via provider
        provider_manager = EmailProviderManager()
        user_info = provider_manager.create_email_account(
            provider, provider_config, email, password, first_name, last_name
        )
        
        # Setup DNS if not disabled
        if not no_dns:
            dns_manager = DNSManager()
            domain = email.split('@')[1]
            
            # Get DNS provider config
            dns_config = config_manager.get_dns_config(domain)
            if dns_config:
                info_message(f"Setting up DNS for {domain}...")
                mail_server = provider_config.get('mail_server', f'mail.{domain}')
                spf_includes = provider_config.get('spf_includes', [provider_config.get('spf_include', mail_server)])
                
                dns_manager.setup_email_dns(
                    domain, dns_config['provider'], dns_config['credentials'],
                    mail_server, spf_includes
                )
            else:
                info_message("DNS provider not configured. Run 'email-cli setup-dns' to configure DNS.")
        
        # Create local account record
        account_manager.create_account(email)
        success_message(f"Account {email} created successfully!")
        if password and provider:
            info_message(f"Generated password: {password}")
    else:
        # Create local account only
        account_manager.create_account(email)


@main.command()
@click.argument('domain')
@click.option('--prefix', help='Username prefix (e.g., "info", "support", "admin")')
@click.option('--count', type=int, help='Number of accounts to create')
@click.option('--names-file', help='File containing usernames (one per line)')
@click.option('--pattern', help='Username pattern with {n} placeholder (e.g., "user{n}")')
@click.option('--start-num', default=1, type=int, help='Starting number for pattern (default: 1)')
@click.option('--provider', help='Email provider for account creation')
@click.option('--no-dns', is_flag=True, help='Skip DNS setup')
@click.option('--dry-run', is_flag=True, help='Show what would be created without creating')
def bulk_create(domain, prefix, count, names_file, pattern, start_num, provider, no_dns, dry_run):
    """Create multiple email accounts for a domain."""
    account_manager = AccountManager()
    
    domain = sanitize_input(domain)
    if not validate_domain(domain):
        error_exit(f"Invalid domain: {domain}")
    
    # Generate list of usernames
    usernames = []
    
    if names_file:
        # Read from file
        try:
            with open(names_file, 'r') as f:
                usernames = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            error_exit(f"Names file not found: {names_file}")
    elif pattern:
        # Generate from pattern
        if not count:
            error_exit("--count is required when using --pattern")
        
        for i in range(start_num, start_num + count):
            usernames.append(pattern.format(n=i))
    elif prefix:
        # Generate from prefix
        if not count:
            error_exit("--count is required when using --prefix")
        
        for i in range(start_num, start_num + count):
            usernames.append(f"{prefix}{i}")
    else:
        error_exit("Must specify one of: --prefix, --pattern, or --names-file")
    
    # Validate usernames
    emails = []
    for username in usernames:
        email = f"{username}@{domain}"
        if validate_email(email):
            emails.append(email)
        else:
            click.echo(f"WARNING: Skipping invalid email: {email}")
    
    if not emails:
        error_exit("No valid email addresses to create")
    
    # Show summary
    click.echo(f"Bulk Email Account Creation")
    click.echo("=" * 40)
    click.echo(f"Domain: {domain}")
    click.echo(f"Accounts to create: {len(emails)}")
    click.echo(f"Provider: {provider or 'Local only'}")
    
    if dry_run:
        click.echo("\nDry run - accounts that would be created:")
        for email in emails:
            click.echo(f"  - {email}")
        return
    
    # Confirm creation
    if not click.confirm(f"\nCreate {len(emails)} email accounts for {domain}?"):
        info_message("Bulk creation cancelled")
        return
    
    # Create accounts
    success_count = 0
    failed_emails = []
    
    for email in emails:
        try:
            if provider:
                # Create via provider
                from ..config.config import ConfigManager
                config_manager = ConfigManager()
                
                provider_config = config_manager.get_provider_config(provider)
                if not provider_config:
                    error_exit(f"Provider {provider} not configured. Use 'email-cli config-provider {provider}' first.")
                
                # Generate password
                password = generate_secure_token(16)
                
                # Create account via provider
                provider_manager = EmailProviderManager()
                user_info = provider_manager.create_email_account(
                    provider, provider_config, email, password
                )
                
                # Setup DNS if not disabled
                if not no_dns:
                    dns_manager = DNSManager()
                    dns_config = config_manager.get_dns_config(domain)
                    if dns_config:
                        mail_server = provider_config.get('mail_server', f'mail.{domain}')
                        spf_includes = provider_config.get('spf_includes', [provider_config.get('spf_include', mail_server)])
                        
                        dns_manager.setup_email_dns(
                            domain, dns_config['provider'], dns_config['credentials'],
                            mail_server, spf_includes
                        )
                
                # Create local account record
                account_manager.create_account(email)
                success_message(f"Created: {email} (Password: {password})")
                success_count += 1
                
            else:
                # Create local account only
                account_manager.create_account(email)
                success_message(f"Created: {email}")
                success_count += 1
                
        except Exception as e:
            failed_emails.append(email)
            click.echo(f"Failed to create {email}: {e}")
    
    # Summary
    click.echo(f"\nCreation Summary:")
    click.echo(f"Successful: {success_count}")
    click.echo(f"Failed: {len(failed_emails)}")
    
    if failed_emails:
        click.echo("\nFailed accounts:")
        for email in failed_emails:
            click.echo(f"  - {email}")


@main.command()
@click.option('--from-email', required=True, help='From email address')
@click.option('--to', required=True, help='To email address')
@click.option('--subject', required=True, help='Email subject')
@click.option('--body', help='Email body (will prompt if not provided)')
@click.option('--cc', help='CC email addresses (comma-separated)')
@click.option('--bcc', help='BCC email addresses (comma-separated)')
@click.option('--html', help='HTML body (alternative to text body)')
@with_rate_limit(lambda **kwargs: kwargs.get('from_email', '').split('@')[-1] if '@' in kwargs.get('from_email', '') else None)
@track_operation("cli_send_email")
def send(from_email, to, subject, body, cc, bcc, html):
    """Send an email."""
    start_time = time.time()
    
    # Input validation and sanitization
    from_email = sanitize_input(from_email)
    to = sanitize_input(to)
    subject = sanitize_input(subject)
    
    if not validate_email(from_email):
        error_exit(f"Invalid from email: {from_email}")
    
    # Validate and parse recipient addresses
    recipients = [to]
    if cc:
        cc = sanitize_input(cc)
        recipients.extend([email.strip() for email in cc.split(',') if email.strip()])
    if bcc:
        bcc = sanitize_input(bcc)
        recipients.extend([email.strip() for email in bcc.split(',') if email.strip()])
    
    for recipient in recipients:
        if not validate_email(recipient):
            error_exit(f"Invalid recipient email: {recipient}")
    
    if not body and not html:
        body = get_user_input("Enter email body")
    
    account_manager = AccountManager()
    account_manager.send_email(from_email, to, subject, body or "", cc, bcc, html)
    
    # Record additional metrics
    metrics = get_metrics_collector()
    metrics.increment_counter("emails_sent")
    metrics.set_gauge("last_email_sent", time.time())


@main.command()
@click.option('--template', help='Email template to use')
@click.option('--from-email', required=True, help='From email address')
@click.option('--to', required=True, help='To email address')
@click.option('--subject', help='Email subject (overrides template)')
@click.option('--body', help='Email body (overrides template)')
@click.option('--cc', help='CC email addresses (comma-separated)')
@click.option('--bcc', help='BCC email addresses (comma-separated)')
@click.option('--html', help='HTML body (alternative to text body)')
@click.option('--vars', help='Template variables as JSON string')
@click.option('--interactive', is_flag=True, help='Interactive template filling')
@with_rate_limit(lambda **kwargs: kwargs.get('from_email', '').split('@')[-1] if '@' in kwargs.get('from_email', '') else None)
@track_operation("cli_send_template_email")
def send_template(template, from_email, to, subject, body, cc, bcc, html, vars, interactive):
    """Send an email using a template."""
    import json
    
    if template:
        template_data = EmailTemplatePresets.get_template(template)
        if not template_data:
            error_exit(f"Template '{template}' not found")
        
        # Parse variables
        variables = {}
        if vars:
            try:
                variables = json.loads(vars)
            except json.JSONDecodeError:
                error_exit("Invalid JSON in --vars parameter")
        
        # Interactive mode for missing variables
        if interactive:
            click.echo(f"Template: {template_data['name']}")
            click.echo(f"Required variables: {', '.join(template_data['variables'])}")
            
            for var in template_data['variables']:
                if var not in variables:
                    value = get_user_input(f"Enter value for '{var}'")
                    variables[var] = value
        
        # Render template
        rendered = EmailTemplatePresets.render_template(template, variables)
        
        # Use template content unless overridden
        subject = subject or rendered['subject']
        body = body or rendered['body']
    
    # Validate inputs
    from_email = sanitize_input(from_email)
    to = sanitize_input(to)
    subject = sanitize_input(subject)
    
    if not validate_email(from_email):
        error_exit(f"Invalid from email: {from_email}")
    
    if not validate_email(to):
        error_exit(f"Invalid to email: {to}")
    
    if not body and not html:
        error_exit("Email body is required")
    
    # Send email using existing send functionality
    account_manager = AccountManager()
    account_manager.send_email(from_email, to, subject, body or "", cc, bcc, html)
    
    success_message("Template email sent successfully!")


@main.command()
def templates():
    """List available email templates."""
    click.echo("Available Email Templates")
    click.echo("=" * 40)
    
    templates = EmailTemplatePresets.list_templates()
    for template in templates:
        click.echo(f"\n{template['name']} ({template['key']})")
        click.echo(f"  Variables: {', '.join(template['variables'])}")
        if template.get('description'):
            click.echo(f"  Description: {template['description']}")


@main.command()
@click.argument('template_name')
def template_info(template_name):
    """Show detailed information about a template."""
    template = EmailTemplatePresets.get_template(template_name)
    if not template:
        error_exit(f"Template '{template_name}' not found")
    
    click.echo(f"Template: {template['name']}")
    click.echo("=" * 40)
    click.echo(f"Subject: {template['subject']}")
    click.echo(f"\nBody Preview:")
    # Show first few lines of body
    body_lines = template['body'].split('\n')[:5]
    for line in body_lines:
        click.echo(f"  {line}")
    if len(template['body'].split('\n')) > 5:
        click.echo("  ...")
    
    click.echo(f"\nRequired Variables:")
    for var in template['variables']:
        click.echo(f"  - {var}")


@main.command()
@click.option('--email', required=True, help='Email account to check')
@click.option('--limit', default=20, type=int, help='Number of emails to show (default: 20)')
@click.option('--sync', is_flag=True, help='Sync emails from server first')
def inbox(email, limit, sync):
    """View inbox emails."""
    account_manager = AccountManager()
    
    if sync:
        account_manager.sync_emails(email)
    
    emails = account_manager.get_inbox(email, limit)
    
    if not emails:
        info_message(f"No emails found in inbox for {email}")
        return
    
    click.echo(f"\nInbox for {email} (showing {len(emails)} most recent):")
    click.echo("-" * 80)
    
    for email_data in emails:
        # Format date
        try:
            date = datetime.fromisoformat(email_data['received_date'].replace('Z', '+00:00'))
            date_str = date.strftime("%Y-%m-%d %H:%M")
        except:
            date_str = email_data['received_date']
        
        # Format subject (truncate if too long)
        subject = email_data['subject'] or '(No subject)'
        if len(subject) > 50:
            subject = subject[:47] + "..."
        
        # Show read/unread indicator
        read_indicator = " " if email_data['is_read'] else "·"
        
        click.echo(f"{read_indicator} [{email_data['id']:3d}] {date_str} | {subject}")
        click.echo(f"     From: {email_data['from_address']}")
        click.echo()


@main.command()
@click.argument('email_id', type=int)
def read(email_id):
    """Read a specific email."""
    account_manager = AccountManager()
    email_data = account_manager.read_email(email_id)
    
    if not email_data:
        error_exit(f"Email with ID {email_id} not found")
    
    # Format date
    try:
        date = datetime.fromisoformat(email_data['received_date'].replace('Z', '+00:00'))
        date_str = date.strftime("%Y-%m-%d %H:%M:%S")
    except:
        date_str = email_data['received_date']
    
    click.echo(f"Email ID: {email_data['id']}")
    click.echo(f"Date: {date_str}")
    click.echo(f"From: {email_data['from_address']}")
    click.echo(f"To: {email_data['to_address']}")
    if email_data['cc_address']:
        click.echo(f"CC: {email_data['cc_address']}")
    click.echo(f"Subject: {email_data['subject']}")
    click.echo("-" * 80)
    
    # Show body
    if email_data['body_text']:
        click.echo(email_data['body_text'])
    elif email_data['body_html']:
        click.echo("(HTML email - text version not available)")
        click.echo(email_data['body_html'])
    else:
        click.echo("(No body content)")
    
    # Show attachments
    if email_data['attachments']:
        click.echo("\nAttachments:")
        for attachment in email_data['attachments']:
            size_kb = attachment['size'] / 1024
            click.echo(f"  - {attachment['filename']} ({attachment['content_type']}, {size_kb:.1f} KB)")


@main.command()
def domains():
    """List all configured domains."""
    account_manager = AccountManager()
    domains = account_manager.list_domains()
    
    if not domains:
        info_message("No domains configured")
        return
    
    click.echo("Configured domains:")
    click.echo("-" * 60)
    
    for domain, config in domains.items():
        click.echo(f"Domain: {domain}")
        click.echo(f"  SMTP: {config['smtp_server']}:{config['smtp_port']}")
        click.echo(f"  IMAP: {config['imap_server']}:{config['imap_port']}")
        click.echo(f"  Username: {config['username']}")
        click.echo(f"  SSL: {'Yes' if config['use_ssl'] else 'No'}")
        click.echo(f"  TLS: {'Yes' if config['use_tls'] else 'No'}")
        click.echo()


@main.command()
def accounts():
    """List all email accounts."""
    account_manager = AccountManager()
    accounts = account_manager.list_accounts()
    
    if not accounts:
        info_message("No accounts created")
        return
    
    click.echo("Email accounts:")
    click.echo("-" * 60)
    
    for account in accounts:
        try:
            created_date = datetime.fromisoformat(account['created_date'])
            date_str = created_date.strftime("%Y-%m-%d %H:%M")
        except:
            date_str = account['created_date']
        
        click.echo(f"Email: {account['email']}")
        click.echo(f"  Domain: {account['domain']}")
        click.echo(f"  Created: {date_str}")
        click.echo()


@main.command()
@click.argument('domain')
def test(domain):
    """Test connection for a domain."""
    account_manager = AccountManager()
    account_manager.test_domain_connection(domain)


@main.command()
@click.option('--email', required=True, help='Email account to sync')
@click.option('--folder', default='INBOX', help='Folder to sync (default: INBOX)')
@click.option('--limit', default=50, type=int, help='Number of emails to fetch (default: 50)')
def sync(email, folder, limit):
    """Sync emails from server to local storage."""
    account_manager = AccountManager()
    account_manager.sync_emails(email, folder, limit)


@main.command()
@click.option('--email', required=True, help='Email account')
def folders(email):
    """List available folders for an email account."""
    account_manager = AccountManager()
    folders = account_manager.get_folders(email)
    
    if not folders:
        info_message(f"No folders found for {email}")
        return
    
    click.echo(f"Available folders for {email}:")
    for folder in folders:
        click.echo(f"  - {folder}")


@main.command()
@click.argument('email_id', type=int)
@click.confirmation_option(prompt='Are you sure you want to delete this email?')
def delete(email_id):
    """Delete an email."""
    from ..storage.storage import StorageManager
    storage = StorageManager()
    storage.delete_email(email_id)
    success_message(f"Email {email_id} deleted")


@main.command()
@click.argument('email_id', type=int)
@click.option('--unread', is_flag=True, help='Mark as unread instead of read')
def mark(email_id, unread):
    """Mark an email as read or unread."""
    from ..storage.storage import StorageManager
    storage = StorageManager()
    storage.mark_email_read(email_id, not unread)
    
    status = "unread" if unread else "read"
    success_message(f"Email {email_id} marked as {status}")


@main.command()
@click.option('--operation', help='Show metrics for specific operation')
@click.option('--minutes', default=60, type=int, help='Time range in minutes (default: 60)')
@click.option('--export', help='Export metrics to file')
@click.option('--system', is_flag=True, help='Show system metrics')
@click.option('--database', is_flag=True, help='Show database metrics')
def metrics(operation, minutes, export, system, database):
    """Show performance metrics and statistics."""
    metrics_collector = get_metrics_collector()
    
    if export:
        filepath = metrics_collector.export_metrics(export)
        success_message(f"Metrics exported to {filepath}")
        return
    
    click.echo("Email CLI Performance Metrics")
    click.echo("=" * 50)
    
    # Show operation metrics
    if operation:
        stats = metrics_collector.get_operation_stats(operation, minutes)
        if stats:
            click.echo(f"\nOperation: {operation} (last {minutes} minutes)")
            click.echo("-" * 40)
            click.echo(f"Total operations: {stats['total_operations']}")
            click.echo(f"Success rate: {stats['success_rate']:.1f}%")
            click.echo(f"Average duration: {stats['avg_duration']:.3f}s")
            click.echo(f"Min/Max duration: {stats['min_duration']:.3f}s / {stats['max_duration']:.3f}s")
            click.echo(f"Operations per minute: {stats['operations_per_minute']:.1f}")
            
            if stats['error_types']:
                click.echo("\nError types:")
                for error_type, count in stats['error_types'].items():
                    click.echo(f"  {error_type}: {count}")
            
            if stats['domains']:
                click.echo("\nDomain usage:")
                for domain, count in stats['domains'].items():
                    click.echo(f"  {domain}: {count}")
        else:
            info_message(f"No metrics found for operation '{operation}'")
    else:
        # Show all operation stats
        all_metrics = metrics_collector.get_all_metrics()
        if all_metrics['operation_stats']:
            click.echo("\nOperation Summary:")
            click.echo("-" * 30)
            for op, stats in all_metrics['operation_stats'].items():
                success_rate = (stats['success_count'] / stats['total_count'] * 100) if stats['total_count'] > 0 else 0
                click.echo(f"{op}: {stats['total_count']} ops, {success_rate:.1f}% success, {stats['avg_duration']:.3f}s avg")
    
    # Show system metrics
    if system:
        sys_stats = metrics_collector.get_system_stats(minutes)
        if sys_stats:
            click.echo(f"\nSystem Metrics (last {minutes} minutes):")
            click.echo("-" * 40)
            click.echo(f"CPU: {sys_stats['avg_cpu_percent']:.1f}% avg, {sys_stats['max_cpu_percent']:.1f}% max")
            click.echo(f"Memory: {sys_stats['avg_memory_percent']:.1f}% avg, {sys_stats['max_memory_percent']:.1f}% max")
            click.echo(f"Disk: {sys_stats['avg_disk_usage']:.1f}% avg, {sys_stats['max_disk_usage']:.1f}% max")
            click.echo(f"Connections: {sys_stats['avg_connections']:.1f} avg, {sys_stats['max_connections']} max")
    
    # Show database metrics
    if database:
        db_stats = metrics_collector.get_database_stats(minutes)
        if db_stats:
            click.echo(f"\nDatabase Metrics (last {minutes} minutes):")
            click.echo("-" * 40)
            click.echo(f"Accounts: {db_stats['current_accounts']}")
            click.echo(f"Emails: {db_stats['current_emails']}")
            click.echo(f"Database size: {db_stats['current_database_size_mb']:.1f} MB")
            click.echo(f"Avg query time: {db_stats['avg_query_time']:.3f}s")
            click.echo(f"Cache hit ratio: {db_stats['avg_cache_hit_ratio']:.1f}%")
            click.echo(f"Total queries: {db_stats['total_queries']}")


@main.command()
@click.option('--hours', default=24, type=int, help='Clean up metrics older than N hours (default: 24)')
@click.confirmation_option(prompt='Are you sure you want to clean up old metrics?')
def cleanup_metrics(hours):
    """Clean up old metrics data."""
    metrics_collector = get_metrics_collector()
    metrics_collector.cleanup_old_metrics(hours)
    success_message(f"Cleaned up metrics older than {hours} hours")


@main.command()
@click.confirmation_option(prompt='Are you sure you want to reset all metrics?')
def reset_metrics():
    """Reset all metrics data."""
    metrics_collector = get_metrics_collector()
    metrics_collector.reset_metrics()
    success_message("All metrics have been reset")


@main.command()
@click.argument('domain')
@click.option('--provider', required=True, help='DNS provider (cloudflare, godaddy)')
@click.option('--api-key', help='API key for DNS provider')
@click.option('--api-secret', help='API secret (for GoDaddy)')
@click.option('--zone-id', help='Zone ID (for Cloudflare)')
@click.option('--api-token', help='API token (for Cloudflare)')
def setup_dns(domain, provider, api_key, api_secret, zone_id, api_token):
    """Configure DNS provider for a domain."""
    from .config import ConfigManager
    config_manager = ConfigManager()
    
    domain = sanitize_input(domain)
    provider = sanitize_input(provider)
    
    if not validate_domain(domain):
        error_exit(f"Invalid domain: {domain}")
    
    # Collect credentials based on provider
    credentials = {}
    
    if provider.lower() == 'cloudflare':
        if not api_token:
            api_token = get_user_input("Enter Cloudflare API token", hide_input=True)
        if not zone_id:
            zone_id = get_user_input("Enter Cloudflare zone ID")
        credentials = {
            'api_token': api_token,
            'zone_id': zone_id
        }
    elif provider.lower() == 'godaddy':
        if not api_key:
            api_key = get_user_input("Enter GoDaddy API key", hide_input=True)
        if not api_secret:
            api_secret = get_user_input("Enter GoDaddy API secret", hide_input=True)
        credentials = {
            'api_key': api_key,
            'api_secret': api_secret
        }
    else:
        error_exit(f"Unsupported DNS provider: {provider}")
    
    # Save DNS configuration
    config_manager.set_dns_config(domain, provider, credentials)
    success_message(f"DNS provider {provider} configured for {domain}")


@main.command()
@click.argument('provider_name')
@click.option('--type', required=True, help='Provider type (google_workspace, microsoft_365, custom)')
@click.option('--admin-email', help='Admin email (for Google Workspace)')
@click.option('--service-account-key', help='Service account key file path (for Google Workspace)')
@click.option('--tenant-id', help='Tenant ID (for Microsoft 365)')
@click.option('--client-id', help='Client ID (for Microsoft 365)')
@click.option('--client-secret', help='Client secret (for Microsoft 365)')
@click.option('--api-url', help='API URL (for custom provider)')
@click.option('--api-key', help='API key (for custom provider)')
@click.option('--mail-server', help='Default mail server for DNS setup')
@click.option('--spf-include', help='SPF include server')
def config_provider(provider_name, type, admin_email, service_account_key, tenant_id, 
                   client_id, client_secret, api_url, api_key, mail_server, spf_include):
    """Configure email provider for account creation."""
    from .config import ConfigManager
    config_manager = ConfigManager()
    
    provider_name = sanitize_input(provider_name)
    type = sanitize_input(type)
    
    # Collect credentials based on provider type
    credentials = {}
    
    if type.lower() == 'google_workspace':
        if not admin_email:
            admin_email = get_user_input("Enter Google Workspace admin email")
        if not service_account_key:
            service_account_key = get_user_input("Enter path to service account key file")
        
        # Read service account key file
        try:
            with open(service_account_key, 'r') as f:
                credentials['service_account_key'] = f.read()
        except Exception as e:
            error_exit(f"Failed to read service account key file: {e}")
        
        credentials['admin_email'] = admin_email
        credentials['mail_server'] = mail_server or 'smtp.gmail.com'
        credentials['spf_include'] = spf_include or '_netblocks.google.com'
        
    elif type.lower() == 'microsoft_365':
        if not tenant_id:
            tenant_id = get_user_input("Enter Microsoft 365 tenant ID")
        if not client_id:
            client_id = get_user_input("Enter Microsoft 365 client ID", hide_input=True)
        if not client_secret:
            client_secret = get_user_input("Enter Microsoft 365 client secret", hide_input=True)
        
        credentials = {
            'tenant_id': tenant_id,
            'client_id': client_id,
            'client_secret': client_secret,
            'mail_server': mail_server or 'smtp.office365.com',
            'spf_include': spf_include or 'spf.protection.outlook.com'
        }
        
    elif type.lower() == 'custom':
        if not api_url:
            api_url = get_user_input("Enter custom provider API URL")
        if not api_key:
            api_key = get_user_input("Enter custom provider API key", hide_input=True)
        
        credentials = {
            'api_url': api_url,
            'api_key': api_key,
            'mail_server': mail_server or 'mail.' + provider_name,
            'spf_include': spf_include or provider_name
        }
    else:
        error_exit(f"Unsupported provider type: {type}")
    
    # Save provider configuration
    config_manager.set_provider_config(provider_name, type, credentials)
    success_message(f"Email provider {provider_name} ({type}) configured")


@main.command()
@click.argument('domain')
@click.option('--mail-server', required=True, help='Mail server for MX record')
@click.option('--priority', default=10, type=int, help='MX record priority (default: 10)')
@click.option('--spf-includes', help='Comma-separated list of SPF includes')
@click.option('--dkim-selector', help='DKIM selector')
@click.option('--dkim-key-file', help='Path to DKIM private key file')
@click.option('--dmarc-policy', default='reject', help='DMARC policy (reject, quarantine, none)')
@click.option('--generate-dkim', is_flag=True, help='Generate new DKIM key pair')
def setup_email_dns(domain, mail_server, priority, spf_includes, dkim_selector, 
                   dkim_key_file, dmarc_policy, generate_dkim):
    """Setup email DNS records for a domain."""
    from .config import ConfigManager
    config_manager = ConfigManager()
    
    domain = sanitize_input(domain)
    mail_server = sanitize_input(mail_server)
    
    if not validate_domain(domain):
        error_exit(f"Invalid domain: {domain}")
    
    # Get DNS provider config
    dns_config = config_manager.get_dns_config(domain)
    if not dns_config:
        error_exit(f"DNS provider not configured for {domain}. Run 'email-cli setup-dns {domain}' first.")
    
    dns_manager = DNSManager()
    
    # Parse SPF includes
    spf_list = []
    if spf_includes:
        spf_list = [s.strip() for s in spf_includes.split(',') if s.strip()]
    
    # Handle DKIM
    dkim_public_key = None
    if generate_dkim:
        private_key, public_key = dns_manager.generate_dkim_key_pair()
        dkim_public_key = public_key
        
        # Save private key
        key_file = dkim_key_file or f'{domain}_dkim_private.pem'
        with open(key_file, 'w') as f:
            f.write(private_key)
        success_message(f"DKIM private key saved to {key_file}")
        info_message(f"Keep this key secure! You'll need it for email signing.")
        
        if not dkim_selector:
            dkim_selector = 'default'
    
    elif dkim_key_file:
        # Extract public key from private key file
        try:
            with open(dkim_key_file, 'r') as f:
                private_key = f.read()
            
            # Generate public key from private key
            _, dkim_public_key = dns_manager.generate_dkim_key_pair()
            
            if not dkim_selector:
                dkim_selector = 'default'
        except Exception as e:
            error_exit(f"Failed to read DKIM key file: {e}")
    
    # Setup DNS records
    dns_manager.setup_email_dns(
        domain, dns_config['provider'], dns_config['credentials'],
        mail_server, spf_list, dkim_selector, dkim_public_key, dmarc_policy
    )


@main.command()
@click.argument('domain')
def check_dns(domain):
    """Check existing DNS records for a domain."""
    domain = sanitize_input(domain)
    
    if not validate_domain(domain):
        error_exit(f"Invalid domain: {domain}")
    
    dns_manager = DNSManager()
    records = dns_manager.check_existing_records(domain)
    
    click.echo(f"DNS Records for {domain}:")
    click.echo("=" * 50)
    
    # MX Records
    click.echo("\nMX Records:")
    if records['mx']:
        for mx in records['mx']:
            click.echo(f"  {mx['exchange']} (priority: {mx['preference']})")
    else:
        click.echo("  None found")
    
    # SPF Record
    click.echo("\nSPF Record:")
    if records['spf']:
        click.echo(f"  {records['spf']}")
    else:
        click.echo("  None found")
    
    # DKIM Records
    click.echo("\nDKIM Records:")
    if records['dkim']:
        for dkim in records['dkim']:
            click.echo(f"  {dkim['selector']}._domainkey.{domain}")
            click.echo(f"    {dkim['record'][:100]}...")
    else:
        click.echo("  None found")
    
    # DMARC Record
    click.echo("\nDMARC Record:")
    if records['dmarc']:
        click.echo(f"  {records['dmarc']}")
    else:
        click.echo("  None found")


@main.command()
@click.argument('provider')
@click.argument('email')
@click.option('--password', help='New password')
def delete_account(provider, email, password):
    """Delete an email account via provider."""
    from .config import ConfigManager
    config_manager = ConfigManager()
    
    email = sanitize_input(email)
    provider = sanitize_input(provider)
    
    if not validate_email(email):
        error_exit(f"Invalid email address: {email}")
    
    # Get provider credentials
    provider_config = config_manager.get_provider_config(provider)
    if not provider_config:
        error_exit(f"Provider {provider} not configured")
    
    # Delete account via provider
    provider_manager = EmailProviderManager()
    success = provider_manager.delete_email_account(provider, provider_config, email)
    
    if success:
        # Remove from local storage
        from ..storage.storage import StorageManager
        storage = StorageManager()
        try:
            storage.delete_account(email)
        except:
            pass  # Account might not exist locally
        
        success_message(f"Account {email} deleted successfully")
    else:
        error_exit(f"Failed to delete account {email}")


@main.command()
@click.argument('provider')
@click.option('--domain', help='Filter by domain')
def list_provider_accounts(provider, domain):
    """List email accounts from provider."""
    from .config import ConfigManager
    config_manager = ConfigManager()
    
    provider = sanitize_input(provider)
    
    # Get provider credentials
    provider_config = config_manager.get_provider_config(provider)
    if not provider_config:
        error_exit(f"Provider {provider} not configured")
    
    # List accounts via provider
    provider_manager = EmailProviderManager()
    accounts = provider_manager.list_email_accounts(provider, provider_config, domain)
    
    if not accounts:
        info_message(f"No accounts found for provider {provider}")
        return
    
    click.echo(f"Accounts from {provider}:")
    click.echo("-" * 60)
    
    for account in accounts:
        email = account.get('primaryEmail') or account.get('mail') or account.get('email')
        name = account.get('name', {}).get('fullName') or account.get('displayName') or 'N/A'
        enabled = account.get('accountEnabled', account.get('suspended') != True)
        
        click.echo(f"Email: {email}")
        click.echo(f"  Name: {name}")
        click.echo(f"  Enabled: {'Yes' if enabled else 'No'}")
        click.echo()


@main.command()
@click.argument('email')
@click.option('--smtp-check', is_flag=True, help='Include SMTP validation (slower)')
@click.option('--json', is_flag=True, help='Output results as JSON')
def validate_email(email, smtp_check, json):
    """Validate an email address with advanced checks."""
    import json as json_module
    
    email = sanitize_input(email)
    
    click.echo(f"🔍 Validating email: {email}")
    click.echo("=" * 50)
    
    # Basic validation first
    if not validate_email(email):
        error_exit("Invalid email format")
    
    # Advanced validation
    result = EmailValidator.validate_email_advanced(email)
    
    if smtp_check:
        smtp_result = EmailValidator.validate_smtp(email)
        result['smtp_valid'] = smtp_result['is_valid']
        result['errors'].extend(smtp_result['errors'])
        result['warnings'].extend(smtp_result['warnings'])
    
    if json:
        click.echo(json_module.dumps(result, indent=2))
        return
    
    # Display results
    click.echo(f"✅ Valid: {'Yes' if result['is_valid'] else 'No'}")
    click.echo(f"📊 Score: {result['score']}/100")
    
    if result['is_disposable']:
        click.echo("⚠️  Disposable email detected")
    
    if result['has_typo']:
        click.echo(f"💡 Suggested correction: {result['suggested_correction']}")
    
    click.echo(f"🌐 Domain valid: {'Yes' if result['domain_valid'] else 'No'}")
    
    if result['mx_records']:
        click.echo(f"📬 MX records: {len(result['mx_records'])}")
        for mx in result['mx_records'][:3]:  # Show first 3
            click.echo(f"    {mx}")
    
    if smtp_check:
        click.echo(f"📧 SMTP valid: {'Yes' if result.get('smtp_valid', False) else 'No'}")
    
    if result['errors']:
        click.echo("\n❌ Errors:")
        for error in result['errors']:
            click.echo(f"    • {error}")
    
    if result['warnings']:
        click.echo("\n⚠️  Warnings:")
        for warning in result['warnings']:
            click.echo(f"    • {warning}")


@main.command()
@click.argument('domain')
@click.option('--json', is_flag=True, help='Output results as JSON')
def validate_domain(domain, json):
    """Validate a domain and check DNS records."""
    import json as json_module
    
    domain = sanitize_input(domain)
    
    click.echo(f"🔍 Validating domain: {domain}")
    click.echo("=" * 50)
    
    result = EmailValidator.validate_domain(domain)
    
    if json:
        click.echo(json_module.dumps(result, indent=2))
        return
    
    # Display results
    click.echo(f"✅ Valid: {'Yes' if result['is_valid'] else 'No'}")
    click.echo(f"📊 Score: {result['score']}/100")
    
    click.echo(f"📬 MX records: {'Yes' if result['has_mx_record'] else 'No'}")
    if result['mx_records']:
        for mx in result['mx_records'][:3]:  # Show first 3
            click.echo(f"    {mx}")
    
    click.echo(f"🌐 A records: {'Yes' if result['has_a_record'] else 'No'}")
    click.echo(f"🛡️  SPF record: {'Yes' if result['has_spf_record'] else 'No'}")
    click.echo(f"🔒 DMARC record: {'Yes' if result['has_dmarc_record'] else 'No'}")
    
    if result['errors']:
        click.echo("\n❌ Errors:")
        for error in result['errors']:
            click.echo(f"    • {error}")
    
    if result['warnings']:
        click.echo("\n⚠️  Warnings:")
        for warning in result['warnings']:
            click.echo(f"    • {warning}")


@main.command()
@click.argument('emails_file')
@click.option('--smtp-check', is_flag=True, help='Include SMTP validation (slower)')
@click.option('--json', is_flag=True, help='Output results as JSON')
@click.option('--output', help='Save results to file')
def validate_emails(emails_file, smtp_check, json, output):
    """Validate multiple emails from a file."""
    import json as json_module
    
    try:
        with open(emails_file, 'r') as f:
            emails = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        error_exit(f"File not found: {emails_file}")
    
    if not emails:
        error_exit("No emails found in file")
    
    click.echo(f"🔍 Validating {len(emails)} emails...")
    click.echo("=" * 50)
    
    results = EmailValidator.batch_validate_emails(emails)
    
    if smtp_check:
        # Add SMTP validation for each email
        for i, result in enumerate(results):
            if result['is_valid']:
                smtp_result = EmailValidator.validate_smtp(result['email'])
                results[i]['smtp_valid'] = smtp_result['is_valid']
                results[i]['errors'].extend(smtp_result['errors'])
                results[i]['warnings'].extend(smtp_result['warnings'])
    
    # Summary
    valid_count = sum(1 for r in results if r['is_valid'])
    invalid_count = len(results) - valid_count
    
    click.echo(f"📊 Results Summary:")
    click.echo(f"✅ Valid: {valid_count}")
    click.echo(f"❌ Invalid: {invalid_count}")
    click.echo(f"📈 Success rate: {valid_count/len(results)*100:.1f}%")
    
    if json or output:
        output_data = {
            'summary': {
                'total': len(results),
                'valid': valid_count,
                'invalid': invalid_count,
                'success_rate': valid_count/len(results)*100
            },
            'results': results
        }
        
        if json:
            click.echo(json_module.dumps(output_data, indent=2))
        
        if output:
            with open(output, 'w') as f:
                json_module.dump(output_data, f, indent=2)
            success_message(f"Results saved to {output}")
    
    # Show invalid emails
    invalid_emails = [r for r in results if not r['is_valid']]
    if invalid_emails and not json:
        click.echo(f"\n❌ Invalid emails:")
        for result in invalid_emails[:10]:  # Show first 10
            click.echo(f"    • {result['email']}: {result['errors'][0] if result['errors'] else 'Unknown error'}")
        
        if len(invalid_emails) > 10:
            click.echo(f"    ... and {len(invalid_emails) - 10} more")


@main.command()
@click.argument('email')
@click.option('--json', is_flag=True, help='Output results as JSON')
def check_deliverability(email, json):
    """Check email deliverability and risk level."""
    import json as json_module
    
    email = sanitize_input(email)
    
    click.echo(f"📧 Checking deliverability: {email}")
    click.echo("=" * 50)
    
    result = EmailValidator.check_email_deliverability(email)
    
    if json:
        click.echo(json_module.dumps(result, indent=2))
        return
    
    # Display results
    risk_emoji = {'low': '🟢', 'medium': '🟡', 'high': '🔴', 'unknown': '⚪'}
    click.echo(f"📊 Deliverable: {'Yes' if result['deliverable'] else 'No'}")
    click.echo(f"{risk_emoji.get(result['risk_level'], '⚪')} Risk level: {result['risk_level'].upper()}")
    
    if result['suggestions']:
        click.echo("\n💡 Suggestions:")
        for suggestion in result['suggestions']:
            click.echo(f"    • {suggestion}")
    
    if result['errors']:
        click.echo("\n❌ Errors:")
        for error in result['errors']:
            click.echo(f"    • {error}")


@lru_cache(maxsize=128)
def _format_email_list(emails: List[dict]) -> List[str]:
    """Format email list for display with caching."""
    formatted = []
    for email_data in emails:
        # Format date
        try:
            date = datetime.fromisoformat(email_data['received_date'].replace('Z', '+00:00'))
            date_str = date.strftime("%Y-%m-%d %H:%M")
        except:
            date_str = email_data['received_date']
        
        # Format subject (truncate if too long)
        subject = email_data['subject'] or '(No subject)'
        if len(subject) > 50:
            subject = subject[:47] + "..."
        
        # Show read/unread indicator
        read_indicator = " " if email_data['is_read'] else "·"
        
        formatted.append(f"{read_indicator} [{email_data['id']:3d}] {date_str} | {subject}")
        formatted.append(f"     From: {email_data['from_address']}")
    
    return formatted


if __name__ == '__main__':
    main()
