"""Main CLI interface for the email CLI tool."""

import click
import sys
import time
from datetime import datetime
from typing import Optional, List
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed
from .account_manager import AccountManager
from .utils import validate_email, validate_domain, error_exit, success_message, info_message, get_user_input, sanitize_input
from .metrics import get_metrics_collector, track_operation
from .rate_limiter import get_rate_limiter, with_rate_limit


@click.group()
@click.version_option(version="1.0.0")
@click.option('--config-dir', type=click.Path(), help='Custom configuration directory')
@click.pass_context
def main(ctx, config_dir):
    """Email CLI Tool - A fast CLI email tool for custom domain email management."""
    ctx.ensure_object(dict)
    ctx.obj['config_dir'] = config_dir


@main.command()
@click.argument('domain')
@click.option('--smtp-server', required=True, help='SMTP server address')
@click.option('--smtp-port', default=587, type=int, help='SMTP port (default: 587)')
@click.option('--imap-server', required=True, help='IMAP server address')
@click.option('--imap-port', default=993, type=int, help='IMAP port (default: 993)')
@click.option('--username', required=True, help='Email username')
@click.option('--password', help='Email password (will prompt if not provided)')
@click.option('--no-ssl', is_flag=True, help='Disable SSL')
@click.option('--no-tls', is_flag=True, help='Disable TLS')
def setup(domain, smtp_server, smtp_port, imap_server, imap_port, username, password, no_ssl, no_tls):
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


@main.command()
@click.argument('email')
def create(email):
    """Create a new email account."""
    account_manager = AccountManager()
    account_manager.create_account(email)


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
    from .storage import StorageManager
    storage = StorageManager()
    storage.delete_email(email_id)
    success_message(f"Email {email_id} deleted")


@main.command()
@click.argument('email_id', type=int)
@click.option('--unread', is_flag=True, help='Mark as unread instead of read')
def mark(email_id, unread):
    """Mark an email as read or unread."""
    from .storage import StorageManager
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
