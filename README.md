# Email CLI Tool

[![Python Version](https://img.shields.io/badge/python-3.7%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)](https://github.com/yourusername/email-cli)

A fast, secure CLI email tool for custom domain email management. This tool allows you to manage multiple email domains, create custom email accounts, send and receive emails directly from your command line with enterprise-grade features.

## Features

- **🚀 Quick Setup Wizard**: Interactive setup with preset email providers (Gmail, Outlook, Yahoo, etc.)
- **📧 Email Templates**: Pre-built templates for common email types (welcome, newsletter, support, etc.)
- **📦 Bulk Account Creation**: Create multiple email accounts at once with patterns or from files
- **🌐 Multiple Domain Support**: Configure SMTP/IMAP settings for multiple domains
- **🔐 Secure Credential Storage**: Uses system keyring for secure password storage
- **💾 Local Email Caching**: SQLite database for fast offline access
- **📨 Full Email Operations**: Send, receive, read, and manage emails
- **🖥️ Cross-Platform**: Works on Windows, macOS, and Linux
- **⚡ Fast CLI Interface**: Built with Click for intuitive command structure

## Prerequisites

- Python 3.7 or higher
- pip (Python package manager)
- System keyring service (built-in on most systems)

## System Requirements

- **Windows**: Windows 10 or later
- **macOS**: macOS 10.12 or later  
- **Linux**: Most modern distributions with Python 3.7+

## Installation

### Option 1: Install from Source (Recommended)

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/email-cli.git
   cd email-cli
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install the package in development mode:
   ```bash
   pip install -e .
   ```

### Option 2: Install via pip (when published)

```bash
pip install email-cli-tool
```

## Quick Start

### 🚀 Option 1: Quick Setup Wizard (Recommended)

The easiest way to get started is with the interactive setup wizard:

```bash
email-cli setup-wizard --interactive
```

This will guide you through:
1. Selecting your email provider (Gmail, Outlook, Yahoo, etc.)
2. Entering your domain and credentials
3. Testing the connection
4. Creating your first email account

### 📧 Option 2: Quick Provider Preset Setup

Or use a preset provider directly:

```bash
# Setup Gmail
email-cli setup-wizard --provider gmail --domain yourdomain.com --username you@yourdomain.com

# Setup Outlook
email-cli setup-wizard --provider outlook --domain yourdomain.com --username you@yourdomain.com
```

### 📦 Option 3: Bulk Email Account Creation

Create multiple email accounts at once:

```bash
# Create accounts with prefix pattern
email-cli bulk-create yourdomain.com --prefix user --count 5

# Create accounts from file
email-cli bulk-create yourdomain.com --names-file usernames.txt

# Create with custom pattern
email-cli bulk-create yourdomain.com --pattern "staff{n}" --count 10 --start-num 100
```

### 📧 Send Emails with Templates

Use pre-built templates for common email types:

```bash
# List available templates
email-cli templates

# Send welcome email using template
email-cli send-template \
  --template welcome \
  --from-email welcome@yourdomain.com \
  --to newuser@example.com \
  --interactive

# Send newsletter with custom variables
email-cli send-template \
  --template newsletter \
  --from-email news@yourdomain.com \
  --to subscriber@example.com \
  --vars '{"name":"John","newsletter_title":"Monthly Update","date":"2024-01-15"}'
```

### 📨 Traditional Email Operations

```bash
# Create a single email account
email-cli create custom-email@yourdomain.com

# Send a custom email
email-cli send \
  --from-email custom-email@yourdomain.com \
  --to recipient@example.com \
  --subject "Test Email" \
  --body "This is a test email from the CLI tool!"

# View inbox
email-cli inbox --email custom-email@yourdomain.com

# Read an email
email-cli read 123
```

## Command Reference

### 🚀 Quick Setup Commands

#### `email-cli setup-wizard`
Interactive setup wizard for quick domain configuration.

**Options:**
- `--interactive`: Run interactive setup wizard
- `--provider`: Use preset provider (gmail, outlook, yahoo, icloud, godaddy, bluehost, siteground, custom)
- `--domain`: Domain name to configure
- `--username`: Email username
- `--password`: Email password (will prompt if not provided)

**Examples:**
```bash
# Interactive wizard
email-cli setup-wizard --interactive

# Quick Gmail setup
email-cli setup-wizard --provider gmail --domain yourdomain.com --username you@yourdomain.com

# Quick Outlook setup
email-cli setup-wizard --provider outlook --domain yourdomain.com --username you@yourdomain.com
```

### 📦 Bulk Operations

#### `email-cli bulk-create <domain>`
Create multiple email accounts for a domain.

**Options:**
- `--prefix`: Username prefix (e.g., "info", "support", "admin")
- `--count`: Number of accounts to create
- `--names-file`: File containing usernames (one per line)
- `--pattern`: Username pattern with {n} placeholder (e.g., "user{n}")
- `--start-num`: Starting number for pattern (default: 1)
- `--provider`: Email provider for account creation
- `--no-dns`: Skip DNS setup
- `--dry-run`: Show what would be created without creating

**Examples:**
```bash
# Create numbered accounts
email-cli bulk-create yourdomain.com --prefix user --count 5

# Create from file
email-cli bulk-create yourdomain.com --names-file usernames.txt

# Create with custom pattern
email-cli bulk-create yourdomain.com --pattern "staff{n}" --count 10 --start-num 100

# Dry run to preview
email-cli bulk-create yourdomain.com --prefix admin --count 3 --dry-run
```

### 📧 Template Commands

#### `email-cli send-template`
Send an email using a template.

**Options:**
- `--template`: Email template to use
- `--from-email`: From email address (required)
- `--to`: To email address (required)
- `--subject`: Email subject (overrides template)
- `--body`: Email body (overrides template)
- `--cc`: CC email addresses (comma-separated)
- `--bcc`: BCC email addresses (comma-separated)
- `--html`: HTML body (alternative to text body)
- `--vars`: Template variables as JSON string
- `--interactive`: Interactive template filling

**Examples:**
```bash
# Send welcome email interactively
email-cli send-template --template welcome --from-email welcome@yourdomain.com --to user@example.com --interactive

# Send with JSON variables
email-cli send-template --template newsletter --from-email news@yourdomain.com --to user@example.com --vars '{"name":"John","date":"2024-01-15"}'

# Override template subject
email-cli send-template --template support --from-email support@yourdomain.com --to user@example.com --subject "Your ticket #12345"
```

#### `email-cli templates`
List all available email templates.

#### `email-cli template-info <template_name>`
Show detailed information about a template.

**Example:**
```bash
email-cli template-info welcome
```

### 🔍 Email Validation Commands

#### `email-cli validate-email <email>`
Validate an email address with advanced checks.

**Options:**
- `--smtp-check`: Include SMTP validation (slower)
- `--json`: Output results as JSON

**Examples:**
```bash
# Basic validation
email-cli validate-email user@example.com

# Full validation with SMTP check
email-cli validate-email user@example.com --smtp-check

# JSON output
email-cli validate-email user@example.com --json
```

#### `email-cli validate-domain <domain>`
Validate a domain and check DNS records.

**Options:**
- `--json`: Output results as JSON

**Example:**
```bash
email-cli validate-domain example.com
```

#### `email-cli validate-emails <emails_file>`
Validate multiple emails from a file.

**Options:**
- `--smtp-check`: Include SMTP validation (slower)
- `--json`: Output results as JSON
- `--output`: Save results to file

**Example:**
```bash
# Validate emails from file
email-cli validate-emails emails.txt

# Full validation with output
email-cli validate-emails emails.txt --smtp-check --output results.json
```

#### `email-cli check-deliverability <email>`
Check email deliverability and risk level.

**Options:**
- `--json`: Output results as JSON

**Example:**
```bash
email-cli check-deliverability user@example.com
```

### Domain Management

#### `email-cli setup <domain>`
Configure a new email domain with SMTP/IMAP settings.

**Options:**
- `--smtp-server`: SMTP server address (required)
- `--smtp-port`: SMTP port (default: 587)
- `--imap-server`: IMAP server address (required)
- `--imap-port`: IMAP port (default: 993)
- `--username`: Email username (required)
- `--password`: Email password (will prompt if not provided)
- `--no-ssl`: Disable SSL
- `--no-tls`: Disable TLS

**Example:**
```bash
email-cli setup gmail.com \
  --smtp-server smtp.gmail.com \
  --smtp-port 587 \
  --imap-server imap.gmail.com \
  --imap-port 993 \
  --username your-email@gmail.com
```

#### `email-cli domains`
List all configured domains.

#### `email-cli test <domain>`
Test connection for a specific domain.

### Account Management

#### `email-cli create <email>`
Create a new email account for a configured domain.

#### `email-cli accounts`
List all created email accounts.

### Email Operations

#### `email-cli send`
Send an email.

**Options:**
- `--from-email`: From email address (required)
- `--to`: To email address (required)
- `--subject`: Email subject (required)
- `--body`: Email body (will prompt if not provided)
- `--cc`: CC email addresses (comma-separated)
- `--bcc`: BCC email addresses (comma-separated)
- `--html`: HTML body (alternative to text body)

#### `email-cli inbox --email <email>`
View inbox emails.

**Options:**
- `--limit`: Number of emails to show (default: 20)
- `--sync`: Sync emails from server first

#### `email-cli read <email_id>`
Read a specific email by ID.

#### `email-cli delete <email_id>`
Delete an email (with confirmation).

#### `email-cli mark <email_id>`
Mark an email as read or unread.

**Options:**
- `--unread`: Mark as unread instead of read

#### `email-cli sync --email <email>`
Sync emails from server to local storage.

**Options:**
- `--folder`: Folder to sync (default: INBOX)
- `--limit`: Number of emails to fetch (default: 50)

#### `email-cli folders --email <email>`
List available folders for an email account.

## Configuration

The tool stores configuration in `~/.email-cli/`:

- `config.yaml`: Domain configurations and settings
- `emails.db`: SQLite database with cached emails
- Passwords are stored in the system keyring

### Example Configuration

```yaml
default_domain: gmail.com
domains:
  gmail.com:
    smtp_server: smtp.gmail.com
    smtp_port: 587
    imap_server: imap.gmail.com
    imap_port: 993
    username: your-email@gmail.com
    use_ssl: true
    use_tls: true
smtp_timeout: 30
imap_timeout: 30
```

## 📧 Email Templates

The Email CLI includes pre-built templates for common email types:

### Available Templates

| Template | Purpose | Variables |
|----------|---------|-----------|
| **welcome** | Welcome new users | `name`, `company_name`, `custom_message`, `sender_name` |
| **newsletter** | Send newsletters | `name`, `newsletter_title`, `date`, `newsletter_content`, `website_url`, `unsubscribe_url`, `company_name` |
| **announcement** | Company announcements | `name`, `announcement_title`, `announcement_message`, `affected_groups`, `contact_info`, `sender_name`, `company_name` |
| **followup** | Follow-up emails | `name`, `original_topic`, `followup_message`, `sender_name` |
| **support** | Customer support replies | `name`, `company_name`, `ticket_number`, `support_response`, `phone_number`, `support_agent_name` |
| **invoice** | Invoice notifications | `name`, `invoice_number`, `company_name`, `service_description`, `amount`, `due_date`, `payment_instructions`, `sender_name` |

### Template Examples

#### Welcome Email Template
```bash
email-cli send-template \
  --template welcome \
  --from-email welcome@yourcompany.com \
  --to newuser@example.com \
  --interactive
```

This will prompt for:
- `name`: John Doe
- `company_name`: Your Company
- `custom_message`: We're excited to have you join our team!
- `sender_name`: Jane Smith

#### Newsletter Template
```bash
email-cli send-template \
  --template newsletter \
  --from-email news@yourcompany.com \
  --to subscriber@example.com \
  --vars '{
    "name": "Sarah",
    "newsletter_title": "January Updates",
    "date": "2024-01-15",
    "newsletter_content": "This month we launched new features...",
    "website_url": "https://yourcompany.com/jan-updates",
    "unsubscribe_url": "https://yourcompany.com/unsubscribe",
    "company_name": "Your Company"
  }'
```

## Common Email Provider Settings

### Supported Providers in Setup Wizard

| Provider | SMTP Server | IMAP Server | Notes |
|----------|-------------|-------------|-------|
| **Gmail** | `smtp.gmail.com:587` | `imap.gmail.com:993` | Requires App Password for 2FA |
| **Outlook** | `smtp-mail.outlook.com:587` | `outlook.office365.com:993` | Works with Outlook.com, Hotmail, Live.com |
| **Yahoo** | `smtp.mail.yahoo.com:587` | `imap.mail.yahoo.com:993` | May require App Password |
| **iCloud** | `smtp.mail.me.com:587` | `imap.mail.me.com:993` | Requires app-specific password for 2FA |
| **GoDaddy** | `smtpout.secureserver.net:80` | `imap.secureserver.net:993` | Custom domain email |
| **Bluehost** | `mail.bluehost.com:587` | `mail.bluehost.com:993` | Replace with actual server |
| **SiteGround** | `smtp.siteground.com:465` | `imap.siteground.com:993` | Use assigned server |

### Manual Provider Settings

#### Gmail
- SMTP: `smtp.gmail.com:587` (TLS)
- IMAP: `imap.gmail.com:993` (SSL)
- Requires App Password for 2FA accounts

#### Outlook/Hotmail
- SMTP: `smtp-mail.outlook.com:587` (TLS)
- IMAP: `outlook.office365.com:993` (SSL)

#### Yahoo
- SMTP: `smtp.mail.yahoo.com:587` (TLS)
- IMAP: `imap.mail.yahoo.com:993` (SSL)

#### Custom Domain
Check with your email provider for specific SMTP/IMAP settings.

## Security

- Passwords are stored using the system keyring (Windows Credential Manager, macOS Keychain, Linux Secret Service)
- All SMTP/IMAP connections use SSL/TLS by default
- Local database is stored in user home directory with appropriate permissions

## Advanced Features

### Connection Pooling
The tool includes intelligent connection pooling to improve performance:
- Automatic connection reuse for multiple operations
- Configurable pool sizes and timeouts
- Graceful connection recovery

### Rate Limiting
Built-in rate limiting prevents overwhelming email servers:
- Configurable send/receive rate limits
- Automatic backoff on server errors
- Queue management for bulk operations

### Security Features
- **Encrypted Storage**: All sensitive data encrypted at rest
- **Secure Authentication**: Support for OAuth2 and App Passwords
- **Audit Logging**: Comprehensive logging of all operations
- **Input Validation**: Protection against injection attacks

### Performance Optimization
- **Local Caching**: Fast offline access to emails
- **Batch Operations**: Efficient bulk email processing
- **Background Sync**: Automatic email synchronization
- **Memory Management**: Optimized for large email volumes

## Troubleshooting

### Connection Issues
1. Verify SMTP/IMAP server addresses and ports
2. Check if your email provider requires App Passwords
3. Ensure SSL/TLS settings match provider requirements
4. Use `email-cli test <domain>` to diagnose connection issues
5. Check firewall settings and network connectivity

### Authentication Issues
1. Verify username and password
2. For Gmail with 2FA, generate and use an App Password
3. Check if account is locked or requires additional verification
4. Ensure proper encoding of special characters in credentials

### Sync Issues
1. Check internet connection
2. Verify domain configuration with `email-cli test <domain>`
3. Try manual sync with `email-cli sync --email <your-email>`
4. Check available disk space for local cache
5. Verify database permissions

### Performance Issues
1. Clear local cache: `rm ~/.email-cli/emails.db`
2. Adjust connection pool settings in config
3. Use rate limiting to prevent server throttling
4. Monitor system resources usage

### Common Error Messages
- **"Authentication failed"**: Check credentials or use App Password
- **"Connection timeout"**: Verify network and server settings
- **"SSL handshake failed"**: Check SSL/TLS configuration
- **"Database locked"**: Ensure single instance or restart application

## Development

### Project Structure
```
email-cli/
|-- src/
|   |-- email_cli/
|   |   |-- __init__.py
|   |   |-- cli.py              # Main CLI commands
|   |   |-- account_manager.py  # Email account operations
|   |   |-- email_engine.py     # SMTP/IMAP operations
|   |   |-- storage.py          # Database operations
|   |   |-- config.py           # Configuration management
|   |   |-- utils.py            # Utility functions
|   |   |-- security.py         # Security and encryption
|   |   |-- logger.py           # Logging configuration
|   |   |-- metrics.py          # Performance metrics
|   |   |-- rate_limiter.py     # Rate limiting
|   |   |-- connection_pool.py  # Connection pooling
|   |   |-- db_pool.py          # Database connection pool
|   |   |-- config_validator.py # Configuration validation
|-- tests/                      # Test suite
|-- docs/                       # Documentation
|-- requirements.txt
|-- requirements-dev.txt        # Development dependencies
|-- setup.py
|-- README.md
|-- .gitignore
|-- config.yaml.example
```

### Development Setup

1. Clone the repository and create virtual environment as shown in installation section

2. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

3. Run tests:
   ```bash
   python -m pytest tests/
   ```

4. Run with coverage:
   ```bash
   python -m pytest --cov=src/email_cli tests/
   ```

5. Run linting:
   ```bash
   flake8 src/email_cli/
   black src/email_cli/
   ```

### Running from Source
```bash
python -m src.email_cli.cli --help
```

### Code Style
This project follows:
- **PEP 8** for Python code formatting
- **Black** for automatic code formatting
- **Flake8** for linting
- **Type hints** for better code documentation

### Testing
- **Unit tests**: Cover individual components
- **Integration tests**: Test email provider connections
- **Security tests**: Verify encryption and authentication
- **Performance tests**: Benchmark operations

### Building Documentation
```bash
cd docs/
make html
```

## Contributing

We welcome contributions! Please follow these guidelines:

### How to Contribute
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Ensure all tests pass: `python -m pytest`
5. Run code formatting: `black src/email_cli/`
6. Commit your changes: `git commit -m 'Add amazing feature'`
7. Push to branch: `git push origin feature/amazing-feature`
8. Open a Pull Request

### Contribution Guidelines
- **Code Quality**: Ensure all code passes linting and tests
- **Documentation**: Update README and docstrings for new features
- **Testing**: Add tests for new functionality
- **Security**: Follow security best practices
- **Performance**: Consider performance implications of changes

### Bug Reports
Please use GitHub Issues to report bugs with:
- Detailed description of the issue
- Steps to reproduce
- Environment information (OS, Python version)
- Error messages and logs

### Feature Requests
We welcome feature requests! Please include:
- Use case and motivation
- Proposed implementation (if any)
- Potential impact on existing functionality

## Changelog

### Version 1.0.0
- Initial release
- Multi-domain email support
- Secure credential storage
- Local email caching
- Full CLI interface

## License

MIT License - feel free to use and modify for your needs.

## Support

- **Documentation**: Check this README and inline help
- **Issues**: Report bugs on GitHub Issues
- **Discussions**: Use GitHub Discussions for questions
- **Email**: Contact maintainers for security issues

## Acknowledgments

- Built with [Click](https://click.palletsprojects.com/) for CLI interface
- Uses [keyring](https://keyring.readthedocs.io/) for secure storage
- Inspired by various email management tools
#   e m a i l c l i 
 
 