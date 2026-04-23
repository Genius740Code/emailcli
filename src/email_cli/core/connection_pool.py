"""Connection pooling and retry mechanisms for email operations."""

import time
import threading
import smtplib
import imaplib
import ssl
import socket
from contextlib import contextmanager
from typing import Dict, Any, Optional, Callable
from queue import Queue, Empty
from dataclasses import dataclass
from ..utils.logger import get_logger
from ..utils.utils import error_exit


@dataclass
class ConnectionConfig:
    """Configuration for connection pooling."""
    max_connections: int = 5
    max_idle_time: int = 300  # 5 minutes
    connection_timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0
    backoff_factor: float = 2.0


class ConnectionPool:
    """Generic connection pool for SMTP and IMAP connections."""
    
    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.logger = get_logger()
        self._pool = Queue(maxsize=config.max_connections)
        self._connections = {}
        self._last_used = {}
        self._lock = threading.Lock()
        self._cleanup_thread = None
        self._start_cleanup_thread()
    
    def _start_cleanup_thread(self):
        """Start background thread to cleanup idle connections."""
        if self._cleanup_thread is None or not self._cleanup_thread.is_alive():
            self._cleanup_thread = threading.Thread(target=self._cleanup_idle_connections, daemon=True)
            self._cleanup_thread.start()
    
    def _cleanup_idle_connections(self):
        """Cleanup idle connections periodically."""
        while True:
            try:
                time.sleep(60)  # Check every minute
                current_time = time.time()
                
                with self._lock:
                    expired_connections = []
                    for conn_id, last_used in self._last_used.items():
                        if current_time - last_used > self.config.max_idle_time:
                            expired_connections.append(conn_id)
                    
                    for conn_id in expired_connections:
                        self._close_connection(conn_id)
                        self.logger.debug("Cleaned up idle connection", connection_id=conn_id)
                        
            except Exception as e:
                self.logger.error("Error in cleanup thread", exception=e)
    
    def _create_connection_id(self, connection_type: str, config: Dict[str, Any]) -> str:
        """Create unique connection ID based on configuration."""
        key_parts = [
            connection_type,
            config.get('smtp_server', config.get('imap_server', '')),
            str(config.get('smtp_port', config.get('imap_port', ''))),
            config.get('username', '')
        ]
        return hash('|'.join(key_parts))
    
    def _create_smtp_connection(self, config: Dict[str, Any]):
        """Create a new SMTP connection."""
        try:
            if config.get('use_ssl', True):
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(
                    config['smtp_server'], 
                    config['smtp_port'],
                    timeout=self.config.connection_timeout,
                    context=context
                )
            else:
                server = smtplib.SMTP(
                    config['smtp_server'],
                    config['smtp_port'],
                    timeout=self.config.connection_timeout
                )
                if config.get('use_tls', True):
                    context = ssl.create_default_context()
                    server.starttls(context=context)
            
            server.login(config['username'], config['password'])
            return server
            
        except Exception as e:
            self.logger.error("Failed to create SMTP connection", exception=e)
            raise
    
    def _create_imap_connection(self, config: Dict[str, Any]):
        """Create a new IMAP connection."""
        try:
            if config.get('use_ssl', True):
                context = ssl.create_default_context()
                imap = imaplib.IMAP4_SSL(
                    config['imap_server'],
                    config['imap_port'],
                    ssl_context=context,
                    timeout=self.config.connection_timeout
                )
            else:
                imap = imaplib.IMAP4(
                    config['imap_server'],
                    config['imap_port'],
                    timeout=self.config.connection_timeout
                )
            
            imap.login(config['username'], config['password'])
            return imap
            
        except Exception as e:
            self.logger.error("Failed to create IMAP connection", exception=e)
            raise
    
    def _close_connection(self, conn_id: str):
        """Close and remove a connection from the pool."""
        if conn_id in self._connections:
            try:
                conn = self._connections.pop(conn_id)
                if hasattr(conn, 'quit'):
                    conn.quit()
                elif hasattr(conn, 'logout'):
                    conn.logout()
                else:
                    conn.close()
            except Exception as e:
                self.logger.debug("Error closing connection", connection_id=conn_id, exception=e)
            
            self._last_used.pop(conn_id, None)
    
    def get_connection(self, connection_type: str, config: Dict[str, Any]):
        """Get a connection from the pool or create a new one."""
        conn_id = self._create_connection_id(connection_type, config)
        
        with self._lock:
            # Check if we have a cached connection
            if conn_id in self._connections:
                self._last_used[conn_id] = time.time()
                return self._connections[conn_id]
            
            # Create new connection
            try:
                if connection_type == 'smtp':
                    conn = self._create_smtp_connection(config)
                elif connection_type == 'imap':
                    conn = self._create_imap_connection(config)
                else:
                    raise ValueError(f"Unsupported connection type: {connection_type}")
                
                self._connections[conn_id] = conn
                self._last_used[conn_id] = time.time()
                
                self.logger.debug("Created new connection", 
                                connection_type=connection_type, 
                                connection_id=conn_id)
                
                return conn
                
            except Exception as e:
                self.logger.error("Failed to get connection", 
                                connection_type=connection_type, 
                                exception=e)
                raise
    
    def return_connection(self, connection_type: str, config: Dict[str, Any]):
        """Return a connection to the pool (mark as available)."""
        conn_id = self._create_connection_id(connection_type, config)
        
        with self._lock:
            if conn_id in self._connections:
                self._last_used[conn_id] = time.time()
    
    def close_all_connections(self):
        """Close all connections in the pool."""
        with self._lock:
            for conn_id in list(self._connections.keys()):
                self._close_connection(conn_id)
    
    @contextmanager
    def get_smtp_connection(self, config: Dict[str, Any]):
        """Context manager for SMTP connections with retry logic."""
        connection = None
        last_exception = None
        
        for attempt in range(self.config.retry_attempts):
            try:
                connection = self.get_connection('smtp', config)
                yield connection
                self.return_connection('smtp', config)
                return
                
            except Exception as e:
                last_exception = e
                self.logger.warning(f"SMTP connection attempt {attempt + 1} failed", 
                                  exception=e, attempt=attempt + 1)
                
                if attempt < self.config.retry_attempts - 1:
                    delay = self.config.retry_delay * (self.config.backoff_factor ** attempt)
                    self.logger.info(f"Retrying SMTP connection in {delay:.2f}s")
                    time.sleep(delay)
                else:
                    # Close the failed connection
                    if connection:
                        conn_id = self._create_connection_id('smtp', config)
                        self._close_connection(conn_id)
        
        error_exit("Failed to establish SMTP connection after multiple attempts", 
                  exception=last_exception)
    
    @contextmanager
    def get_imap_connection(self, config: Dict[str, Any]):
        """Context manager for IMAP connections with retry logic."""
        connection = None
        last_exception = None
        
        for attempt in range(self.config.retry_attempts):
            try:
                connection = self.get_connection('imap', config)
                yield connection
                self.return_connection('imap', config)
                return
                
            except Exception as e:
                last_exception = e
                self.logger.warning(f"IMAP connection attempt {attempt + 1} failed", 
                                  exception=e, attempt=attempt + 1)
                
                if attempt < self.config.retry_attempts - 1:
                    delay = self.config.retry_delay * (self.config.backoff_factor ** attempt)
                    self.logger.info(f"Retrying IMAP connection in {delay:.2f}s")
                    time.sleep(delay)
                else:
                    # Close the failed connection
                    if connection:
                        conn_id = self._create_connection_id('imap', config)
                        self._close_connection(conn_id)
        
        error_exit("Failed to establish IMAP connection after multiple attempts", 
                  exception=last_exception)


# Global connection pool instance
_connection_pool = None


def get_connection_pool() -> ConnectionPool:
    """Get the global connection pool instance."""
    global _connection_pool
    if _connection_pool is None:
        config = ConnectionConfig()
        _connection_pool = ConnectionPool(config)
    return _connection_pool


def with_retry(max_attempts: int = 3, delay: float = 1.0, backoff_factor: float = 2.0):
    """Decorator for adding retry logic to functions."""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            logger = get_logger()
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(f"Function {func.__name__} attempt {attempt + 1} failed", 
                                 exception=e, attempt=attempt + 1)
                    
                    if attempt < max_attempts - 1:
                        current_delay = delay * (backoff_factor ** attempt)
                        logger.info(f"Retrying {func.__name__} in {current_delay:.2f}s")
                        time.sleep(current_delay)
                    else:
                        logger.error(f"Function {func.__name__} failed after {max_attempts} attempts")
            
            raise last_exception
        return wrapper
    return decorator
