"""Database storage layer for the email CLI tool."""

import sqlite3
import json
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from .utils import get_database_file, error_exit, sanitize_input
from .db_pool import get_db_pool, QueryBuilder
from .logger import get_logger


class StorageManager:
    """Manages SQLite database storage for emails and accounts."""
    
    def __init__(self):
        self.logger = get_logger()
        self.db_file = get_database_file()
        self.db_pool = get_db_pool(str(self.db_file))
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize the database with required tables and optimized indexes."""
        start_time = time.time()
        
        try:
            # Create accounts table
            accounts_sql = '''
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    domain TEXT NOT NULL,
                    created_date TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    last_sync_date TEXT,
                    sync_status TEXT DEFAULT 'pending'
                )
            '''
            self.db_pool.execute_query(accounts_sql)
            
            # Create emails table
            emails_sql = '''
                CREATE TABLE IF NOT EXISTS emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_email TEXT NOT NULL,
                    message_id TEXT UNIQUE NOT NULL,
                    from_address TEXT NOT NULL,
                    to_address TEXT NOT NULL,
                    cc_address TEXT,
                    bcc_address TEXT,
                    subject TEXT NOT NULL,
                    body_text TEXT,
                    body_html TEXT,
                    folder TEXT DEFAULT 'INBOX',
                    is_read BOOLEAN DEFAULT 0,
                    is_sent BOOLEAN DEFAULT 0,
                    received_date TEXT NOT NULL,
                    size_bytes INTEGER DEFAULT 0,
                    attachments TEXT,
                    hash_id TEXT,
                    FOREIGN KEY (account_email) REFERENCES accounts (email)
                )
            '''
            self.db_pool.execute_query(emails_sql)
            
            # Create optimized indexes
            indexes = [
                'CREATE INDEX IF NOT EXISTS idx_emails_account ON emails (account_email)',
                'CREATE INDEX IF NOT EXISTS idx_emails_folder ON emails (folder)',
                'CREATE INDEX IF NOT EXISTS idx_emails_date ON emails (received_date DESC)',
                'CREATE INDEX IF NOT EXISTS idx_emails_read ON emails (is_read)',
                'CREATE INDEX IF NOT EXISTS idx_emails_message_id ON emails (message_id)',
                'CREATE INDEX IF NOT EXISTS idx_emails_hash_id ON emails (hash_id)',
                'CREATE INDEX IF NOT EXISTS idx_emails_composite ON emails (account_email, folder, received_date DESC)',
                'CREATE INDEX IF NOT EXISTS idx_accounts_email ON accounts (email)',
                'CREATE INDEX IF NOT EXISTS idx_accounts_domain ON accounts (domain)'
            ]
            
            for index_sql in indexes:
                self.db_pool.execute_query(index_sql)
            
            duration = time.time() - start_time
            self.logger.log_operation("database_init", duration=duration, success=True)
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.log_operation("database_init", duration=duration, success=False, exception=e)
            error_exit(f"Database initialization failed: {e}")
    
    def create_account(self, email: str, domain: str) -> None:
        """Create a new email account."""
        start_time = time.time()
        
        email = sanitize_input(email)
        domain = sanitize_input(domain)
        
        try:
            query = QueryBuilder.insert(
                'accounts', 
                ['email', 'domain', 'created_date', 'last_sync_date']
            )
            
            self.db_pool.execute_query(
                query, 
                (email, domain, datetime.now().isoformat(), None),
                fetch_all=False
            )
            
            duration = time.time() - start_time
            self.logger.log_operation("create_account", duration=duration, success=True, 
                                    email=email, domain=domain)
            
        except sqlite3.IntegrityError:
            duration = time.time() - start_time
            self.logger.log_operation("create_account", duration=duration, success=False, 
                                    email=email, error="already_exists")
            error_exit(f"Account {email} already exists")
        except Exception as e:
            duration = time.time() - start_time
            self.logger.log_operation("create_account", duration=duration, success=False, 
                                    email=email, exception=e)
            error_exit(f"Failed to create account: {e}")
    
    def get_accounts(self) -> List[Dict[str, Any]]:
        """Get all email accounts."""
        start_time = time.time()
        
        try:
            query = QueryBuilder.select(
                'accounts',
                where='is_active = 1',
                order_by='created_date DESC'
            )
            
            results = self.db_pool.execute_query(query, fetch_all=True)
            
            duration = time.time() - start_time
            self.logger.log_operation("get_accounts", duration=duration, success=True, 
                                    count=len(results))
            
            return [dict(row) for row in results]
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.log_operation("get_accounts", duration=duration, success=False, exception=e)
            error_exit(f"Failed to retrieve accounts: {e}")
    
    def get_account(self, email: str) -> Optional[Dict[str, Any]]:
        """Get a specific email account."""
        email = sanitize_input(email)
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    'SELECT * FROM accounts WHERE email = ? AND is_active = 1',
                    (email,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            error_exit(f"Failed to retrieve account: {e}")
    
    def save_email(self, email_data: Dict[str, Any]) -> None:
        """Save an email to the database with optimization."""
        # Sanitize and validate inputs
        email_data = {k: sanitize_input(str(v)) if isinstance(v, str) else v for k, v in email_data.items()}
        
        # Generate hash for deduplication
        hash_content = f"{email_data.get('message_id', '')}{email_data.get('subject', '')}{email_data.get('from_address', '')}"
        hash_id = hash_content[:64]  # Limit hash length
        
        try:
            with self._get_connection() as conn:
                # Check for duplicates first
                cursor = conn.execute(
                    'SELECT id FROM emails WHERE hash_id = ? AND account_email = ?',
                    (hash_id, email_data['account_email'])
                )
                if cursor.fetchone():
                    return  # Skip duplicate
                
                conn.execute('''
                    INSERT OR IGNORE INTO emails (
                        account_email, message_id, from_address, to_address,
                        cc_address, bcc_address, subject, body_text, body_html,
                        folder, is_read, is_sent, received_date, size_bytes, attachments, hash_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    email_data['account_email'],
                    email_data['message_id'],
                    email_data['from_address'],
                    email_data['to_address'],
                    email_data.get('cc_address'),
                    email_data.get('bcc_address'),
                    email_data['subject'][:1000],  # Limit subject length
                    email_data.get('body_text', '')[:1000000],  # Limit body length
                    email_data.get('body_html', '')[:1000000],  # Limit HTML length
                    email_data.get('folder', 'INBOX')[:100],  # Limit folder length
                    email_data.get('is_read', False),
                    email_data.get('is_sent', False),
                    email_data['received_date'],
                    min(email_data.get('size_bytes', 0), 100000000),  # Limit size
                    json.dumps(email_data.get('attachments', [])[:50]),  # Limit attachments
                    hash_id
                ))
                conn.commit()
        except sqlite3.Error as e:
            error_exit(f"Failed to save email: {e}")
    
    def get_emails(self, account_email: str, folder: str = 'INBOX', 
                   limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get emails for an account with optimized query."""
        account_email = sanitize_input(account_email)
        folder = sanitize_input(folder)
        limit = min(limit, 1000)  # Prevent excessive memory usage
        
        try:
            with self._get_connection() as conn:
                cursor = conn.execute('''
                    SELECT id, message_id, from_address, to_address, subject, 
                           folder, is_read, is_sent, received_date, size_bytes
                    FROM emails 
                    WHERE account_email = ? AND folder = ?
                    ORDER BY received_date DESC
                    LIMIT ? OFFSET ?
                ''', (account_email, folder, limit, offset))
                
                emails = []
                for row in cursor.fetchall():
                    email_dict = dict(row)
                    # Lazy load attachments and body content
                    email_dict['attachments'] = []
                    email_dict['body_text'] = ''
                    email_dict['body_html'] = ''
                    emails.append(email_dict)
                
                return emails
        except sqlite3.Error as e:
            error_exit(f"Failed to retrieve emails: {e}")
    
    def get_email(self, email_id: int, lazy_load: bool = False) -> Optional[Dict[str, Any]]:
        """Get a specific email by ID with optional lazy loading."""
        try:
            with self._get_connection() as conn:
                if lazy_load:
                    # Only fetch essential fields for lazy loading
                    cursor = conn.execute('''
                        SELECT id, message_id, from_address, to_address, subject, 
                               folder, is_read, is_sent, received_date, size_bytes
                        FROM emails WHERE id = ?
                    ''', (email_id,))
                else:
                    cursor = conn.execute('SELECT * FROM emails WHERE id = ?', (email_id,))
                
                row = cursor.fetchone()
                
                if row:
                    email_dict = dict(row)
                    
                    if not lazy_load:
                        if email_dict.get('attachments'):
                            try:
                                email_dict['attachments'] = json.loads(email_dict['attachments'])
                            except json.JSONDecodeError:
                                email_dict['attachments'] = []
                    else:
                        # Lazy loading placeholders
                        email_dict['attachments'] = []
                        email_dict['body_text'] = ''
                        email_dict['body_html'] = ''
                    
                    # Mark as read
                    conn.execute('UPDATE emails SET is_read = 1 WHERE id = ?', (email_id,))
                    conn.commit()
                    
                    return email_dict
                return None
        except sqlite3.Error as e:
            error_exit(f"Failed to retrieve email: {e}")
    
    def get_email_body(self, email_id: int) -> Optional[Dict[str, str]]:
        """Get only the body content of an email for lazy loading."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    'SELECT body_text, body_html FROM emails WHERE id = ?',
                    (email_id,)
                )
                row = cursor.fetchone()
                
                if row:
                    return {
                        'body_text': row['body_text'] or '',
                        'body_html': row['body_html'] or ''
                    }
                return None
        except sqlite3.Error as e:
            error_exit(f"Failed to retrieve email body: {e}")
    
    def get_email_attachments(self, email_id: int) -> List[Dict[str, Any]]:
        """Get attachments for an email."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    'SELECT attachments FROM emails WHERE id = ?',
                    (email_id,)
                )
                row = cursor.fetchone()
                
                if row and row['attachments']:
                    try:
                        return json.loads(row['attachments'])
                    except json.JSONDecodeError:
                        return []
                return []
        except sqlite3.Error as e:
            error_exit(f"Failed to retrieve attachments: {e}")
    
    def mark_email_read(self, email_id: int, is_read: bool = True) -> None:
        """Mark an email as read or unread."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    'UPDATE emails SET is_read = ? WHERE id = ?',
                    (is_read, email_id)
                )
                conn.commit()
        except sqlite3.Error as e:
            error_exit(f"Failed to update email: {e}")
    
    def delete_email(self, email_id: int) -> None:
        """Delete an email."""
        try:
            with self._get_connection() as conn:
                conn.execute('DELETE FROM emails WHERE id = ?', (email_id,))
                conn.commit()
        except sqlite3.Error as e:
            error_exit(f"Failed to delete email: {e}")
    
    def get_email_count(self, account_email: str, folder: str = 'INBOX') -> int:
        """Get the count of emails for an account."""
        account_email = sanitize_input(account_email)
        folder = sanitize_input(folder)
        
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    'SELECT COUNT(*) FROM emails WHERE account_email = ? AND folder = ?',
                    (account_email, folder)
                )
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            error_exit(f"Failed to get email count: {e}")
    
    def update_account_sync_status(self, email: str, sync_date: str, status: str = 'success') -> None:
        """Update account sync status."""
        email = sanitize_input(email)
        try:
            with self._get_connection() as conn:
                conn.execute(
                    'UPDATE accounts SET last_sync_date = ?, sync_status = ? WHERE email = ?',
                    (sync_date, status, email)
                )
                conn.commit()
        except sqlite3.Error as e:
            error_exit(f"Failed to update sync status: {e}")
    
    def cleanup_old_emails(self, days: int = 90) -> int:
        """Clean up old emails to save space."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    'DELETE FROM emails WHERE received_date < date("now", "-%d days")' % days
                )
                deleted_count = cursor.rowcount
                conn.commit()
                
                # Vacuum database to reclaim space
                conn.execute('VACUUM')
                
                return deleted_count
        except sqlite3.Error as e:
            error_exit(f"Failed to cleanup old emails: {e}")
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics for monitoring."""
        try:
            with self._get_connection() as conn:
                # Get table sizes
                cursor = conn.execute('SELECT COUNT(*) FROM accounts')
                account_count = cursor.fetchone()[0]
                
                cursor = conn.execute('SELECT COUNT(*) FROM emails')
                email_count = cursor.fetchone()[0]
                
                cursor = conn.execute('SELECT SUM(size_bytes) FROM emails')
                total_size = cursor.fetchone()[0] or 0
                
                cursor = conn.execute('SELECT name FROM sqlite_master WHERE type="table"')
                tables = [row[0] for row in cursor.fetchall()]
                
                # Get database file size
                import os
                db_size = os.path.getsize(self.db_file) if os.path.exists(self.db_file) else 0
                
                return {
                    'accounts_count': account_count,
                    'emails_count': email_count,
                    'total_email_size': total_size,
                    'database_file_size': db_size,
                    'tables': tables
                }
        except sqlite3.Error as e:
            error_exit(f"Failed to get database stats: {e}")
    
    def optimize_database(self) -> None:
        """Optimize database performance."""
        try:
            with self._get_connection() as conn:
                # Analyze tables for query optimization
                for table in ['accounts', 'emails']:
                    conn.execute(f'ANALYZE {table}')
                
                # Rebuild indexes
                conn.execute('REINDEX')
                
                # Update table statistics
                conn.execute('PRAGMA optimize')
                
                conn.commit()
        except sqlite3.Error as e:
            error_exit(f"Failed to optimize database: {e}")
