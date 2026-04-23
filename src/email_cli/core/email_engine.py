"""Email engine for SMTP/IMAP operations."""

import smtplib
import imaplib
import ssl
import email
import socket
import threading
import time
from contextlib import contextmanager
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from ..utils.utils import error_exit, success_message, sanitize_input, hash_string, validate_server_address, validate_port
from .connection_pool import get_connection_pool, with_retry
from ..utils.logger import get_logger


class EmailEngine:
    """Handles SMTP and IMAP operations for email sending and receiving."""
    
    def __init__(self, domain_config: Dict[str, Any]):
        self.logger = get_logger()
        self.domain_config = domain_config
        
        # Validate configuration
        self._validate_config()
        
        self.smtp_server = domain_config['smtp_server']
        self.smtp_port = domain_config['smtp_port']
        self.imap_server = domain_config['imap_server']
        self.imap_port = domain_config['imap_port']
        self.username = domain_config['username']
        self.password = domain_config['password']
        self.use_ssl = domain_config.get('use_ssl', True)
        self.use_tls = domain_config.get('use_tls', True)
        self._connection_pool = get_connection_pool()
        self._timeout = domain_config.get('timeout', 30)
        
        self.logger.info("EmailEngine initialized", 
                        smtp_server=self.smtp_server,
                        imap_server=self.imap_server,
                        username=self.username)
    
    def _validate_config(self) -> None:
        """Validate domain configuration."""
        config = self.domain_config
        
        # Validate required fields
        required_fields = ['smtp_server', 'smtp_port', 'imap_server', 'imap_port', 'username', 'password']
        for field in required_fields:
            if field not in config or not config[field]:
                error_exit(f"Missing required configuration field: {field}")
        
        # Validate server addresses
        if not validate_server_address(config['smtp_server']):
            error_exit(f"Invalid SMTP server address: {config['smtp_server']}")
        
        if not validate_server_address(config['imap_server']):
            error_exit(f"Invalid IMAP server address: {config['imap_server']}")
        
        # Validate ports
        if not validate_port(config['smtp_port']):
            error_exit(f"Invalid SMTP port: {config['smtp_port']}")
        
        if not validate_port(config['imap_port']):
            error_exit(f"Invalid IMAP port: {config['imap_port']}")
        
        self.logger.info("Configuration validation passed")
    
    @with_retry(max_attempts=3, delay=1.0)
    def send_email(self, to_address: str, subject: str, body_text: str,
                   from_address: str, cc_address: Optional[str] = None,
                   bcc_address: Optional[str] = None, body_html: Optional[str] = None) -> bool:
        """Send an email using SMTP with connection pooling and retry logic."""
        start_time = time.time()
        
        # Sanitize inputs
        to_address = sanitize_input(to_address)
        subject = sanitize_input(subject)
        from_address = sanitize_input(from_address)
        
        self.logger.info("Starting email send operation", 
                        to_address=to_address, 
                        from_address=from_address, 
                        subject=subject[:50])
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = from_address
            msg['To'] = to_address
            msg['Subject'] = subject
            msg['Date'] = email.utils.formatdate(localtime=True)
            msg['Message-ID'] = email.utils.make_msgid()
            
            if cc_address:
                cc_address = sanitize_input(cc_address)
                msg['Cc'] = cc_address
            
            # Add body with size limits
            if body_text and len(body_text) < 25 * 1024 * 1024:  # 25MB limit
                text_part = MIMEText(body_text, 'plain', 'utf-8')
                msg.attach(text_part)
            
            if body_html and len(body_html) < 25 * 1024 * 1024:  # 25MB limit
                html_part = MIMEText(body_html, 'html', 'utf-8')
                msg.attach(html_part)
            
            # Combine all recipients
            all_recipients = [to_address]
            if cc_address:
                all_recipients.extend([email.strip() for email in cc_address.split(',') if email.strip()])
            if bcc_address:
                bcc_address = sanitize_input(bcc_address)
                all_recipients.extend([email.strip() for email in bcc_address.split(',') if email.strip()])
            
            # Connect to SMTP server and send using connection pool
            with self._connection_pool.get_smtp_connection(self.domain_config) as server:
                server.send_message(msg, from_addr=from_address, to_addrs=all_recipients)
            
            duration = time.time() - start_time
            self.logger.log_operation("send_email", duration=duration, success=True, 
                                    to=to_address, recipients=len(all_recipients))
            
            success_message(f"Email sent successfully to {to_address}")
            return True
            
        except smtplib.SMTPRecipientsRefused as e:
            self.logger.error("SMTP recipients refused", exception=e, recipients=all_recipients)
            error_exit(f"Recipients refused: {e}")
        except smtplib.SMTPSenderRefused as e:
            self.logger.error("SMTP sender refused", exception=e, sender=from_address)
            error_exit(f"Sender refused: {e}")
        except smtplib.SMTPDataError as e:
            self.logger.error("SMTP data error", exception=e)
            error_exit(f"SMTP data error: {e}")
        except socket.timeout:
            self.logger.error("SMTP connection timeout")
            error_exit("Connection timeout. Please try again.")
        except Exception as e:
            duration = time.time() - start_time
            self.logger.log_operation("send_email", duration=duration, success=False, 
                                    exception=e, to=to_address)
            error_exit(f"Failed to send email: {e}")
    
        
    @with_retry(max_attempts=3, delay=1.0)
    def fetch_emails(self, folder: str = 'INBOX', limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch emails from IMAP server with optimized performance."""
        start_time = time.time()
        
        folder = sanitize_input(folder)
        limit = min(limit, 1000)  # Prevent excessive memory usage
        
        self.logger.info("Starting email fetch operation", folder=folder, limit=limit)
        
        try:
            with self._connection_pool.get_imap_connection(self.domain_config) as imap:
                # Select folder
                status, messages = imap.select(f'"{folder}"')
                if status != 'OK':
                    error_exit(f"Failed to select folder {folder}")
                
                # Search for all emails with date limit for performance
                search_criteria = '(UNSEEN)'
                status, email_ids = imap.search(None, search_criteria)
                if status != 'OK':
                    error_exit("Failed to search for emails")
                
                email_ids = email_ids[0].split()
                emails = []
                
                # Fetch latest emails (reverse order) with batch processing
                batch_size = 10
                fetched_count = 0
                
                for i in range(0, min(len(email_ids), limit), batch_size):
                    batch_ids = email_ids[-(i + batch_size):len(email_ids) - i] if i > 0 else email_ids[-batch_size:]
                    
                    # Fetch batch
                    for email_id in reversed(batch_ids):
                        try:
                            # Fetch email headers first for performance
                            status, msg_data = imap.fetch(email_id, '(BODY.PEEK[HEADER] FLAGS)')
                            if status != 'OK':
                                continue
                            
                            # Parse headers only initially
                            raw_header = msg_data[0][1]
                            header_message = email.message_from_bytes(raw_header)
                            
                            # Extract basic data
                            email_data = self._parse_email_headers(header_message, email_id.decode())
                            emails.append(email_data)
                            fetched_count += 1
                            
                        except Exception as e:
                            self.logger.warning("Failed to parse email header", 
                                             email_id=email_id.decode(), exception=e)
                            continue
                
                duration = time.time() - start_time
                self.logger.log_operation("fetch_emails", duration=duration, success=True, 
                                        folder=folder, fetched_count=fetched_count, 
                                        total_found=len(email_ids))
                
                return emails
                
        except Exception as e:
            duration = time.time() - start_time
            self.logger.log_operation("fetch_emails", duration=duration, success=False, 
                                    folder=folder, exception=e)
            error_exit(f"Failed to fetch emails: {e}")
    
    def _parse_email_headers(self, email_message: email.message.Message, message_id: str) -> Dict[str, Any]:
        """Parse email headers only for performance optimization."""
        # Extract headers
        subject = self._decode_header(email_message['subject'] or '')
        from_address = self._decode_header(email_message['from'] or '')
        to_address = self._decode_header(email_message['to'] or '')
        cc_address = self._decode_header(email_message['cc'] or '')
        date_str = email_message['date'] or ''
        
        # Parse date
        try:
            received_date = email.utils.parsedate_to_datetime(date_str).isoformat()
        except:
            received_date = datetime.now().isoformat()
        
        return {
            'message_id': message_id,
            'from_address': from_address,
            'to_address': to_address,
            'cc_address': cc_address,
            'subject': subject,
            'body_text': '',  # Lazy loaded
            'body_html': '',  # Lazy loaded
            'received_date': received_date,
            'size_bytes': 0,  # Will be calculated on full fetch
            'attachments': []  # Will be populated on full fetch
        }
    
    def _parse_email(self, email_message: email.message.Message, message_id: str) -> Dict[str, Any]:
        """Parse a full email message and extract relevant data."""
        # Extract headers
        subject = self._decode_header(email_message['subject'] or '')
        from_address = self._decode_header(email_message['from'] or '')
        to_address = self._decode_header(email_message['to'] or '')
        cc_address = self._decode_header(email_message['cc'] or '')
        date_str = email_message['date'] or ''
        
        # Parse date
        try:
            received_date = email.utils.parsedate_to_datetime(date_str).isoformat()
        except:
            received_date = datetime.now().isoformat()
        
        # Extract body
        body_text = ''
        body_html = ''
        attachments = []
        total_size = 0
        
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get('Content-Disposition', ''))
                
                if 'attachment' in content_disposition:
                    # Handle attachment
                    filename = part.get_filename()
                    if filename:
                        attachment_data = part.get_payload(decode=True) or b''
                        attachments.append({
                            'filename': self._decode_header(filename),
                            'content_type': content_type,
                            'size': len(attachment_data)
                        })
                        total_size += len(attachment_data)
                elif content_type == 'text/plain' and not body_text:
                    body_data = part.get_payload(decode=True) or b''
                    body_text = body_data.decode('utf-8', errors='ignore')
                    total_size += len(body_data)
                elif content_type == 'text/html' and not body_html:
                    body_data = part.get_payload(decode=True) or b''
                    body_html = body_data.decode('utf-8', errors='ignore')
                    total_size += len(body_data)
        else:
            # Single part message
            body_data = email_message.get_payload(decode=True) or b''
            body_text = body_data.decode('utf-8', errors='ignore')
            total_size += len(body_data)
        
        return {
            'message_id': message_id,
            'from_address': from_address,
            'to_address': to_address,
            'cc_address': cc_address,
            'subject': subject,
            'body_text': body_text[:1000000],  # Limit to 1MB
            'body_html': body_html[:1000000],  # Limit to 1MB
            'received_date': received_date,
            'size_bytes': total_size,
            'attachments': attachments[:50]  # Limit to 50 attachments
        }
    
    def _decode_header(self, header: str) -> str:
        """Decode email header."""
        if not header:
            return ''
        
        decoded_parts = decode_header(header)
        result = []
        
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                try:
                    result.append(part.decode(encoding or 'utf-8', errors='ignore'))
                except:
                    result.append(part.decode('utf-8', errors='ignore'))
            else:
                result.append(str(part))
        
        return ''.join(result)
    
    def test_connection(self) -> Tuple[bool, str]:
        """Test SMTP and IMAP connections with enhanced logging."""
        start_time = time.time()
        smtp_success = False
        imap_success = False
        errors = []
        
        self.logger.info("Starting connection test", 
                        smtp_server=self.smtp_server, 
                        imap_server=self.imap_server)
        
        # Test SMTP
        try:
            with self._connection_pool.get_smtp_connection(self.domain_config) as server:
                smtp_success = True
                self.logger.info("SMTP connection test successful")
        except Exception as e:
            errors.append(f"SMTP: {e}")
            self.logger.error("SMTP connection test failed", exception=e)
        
        # Test IMAP
        try:
            with self._connection_pool.get_imap_connection(self.domain_config) as imap:
                imap.select('INBOX')
                imap_success = True
                self.logger.info("IMAP connection test successful")
        except Exception as e:
            errors.append(f"IMAP: {e}")
            self.logger.error("IMAP connection test failed", exception=e)
        
        duration = time.time() - start_time
        success = smtp_success and imap_success
        message = "Both SMTP and IMAP connections successful" if success else "; ".join(errors)
        
        self.logger.log_operation("test_connection", duration=duration, success=success,
                                smtp_success=smtp_success, imap_success=imap_success)
        
        return success, message
    
    @with_retry(max_attempts=3, delay=1.0)
    def get_folders(self) -> List[str]:
        """Get list of available folders/mailboxes."""
        start_time = time.time()
        
        self.logger.info("Starting folder listing operation")
        
        try:
            with self._connection_pool.get_imap_connection(self.domain_config) as imap:
                status, folders = imap.list()
                if status != 'OK':
                    error_exit("Failed to list folders")
                
                folder_names = []
                for folder in folders:
                    folder_str = folder.decode('utf-8')
                    # Extract folder name from IMAP response
                    if '"' in folder_str:
                        folder_name = folder_str.split('"')[-2]
                    else:
                        folder_name = folder_str.split()[-1]
                    folder_names.append(folder_name)
                
                duration = time.time() - start_time
                self.logger.log_operation("get_folders", duration=duration, success=True,
                                        folder_count=len(folder_names))
                
                return folder_names
                
        except Exception as e:
            duration = time.time() - start_time
            self.logger.log_operation("get_folders", duration=duration, success=False, exception=e)
            error_exit(f"Failed to get folders: {e}")
