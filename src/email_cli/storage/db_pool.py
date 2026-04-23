"""Database connection pooling and optimization utilities."""

import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Dict, Any, Optional, List
from queue import Queue, Empty
from dataclasses import dataclass
from ..utils.logger import get_logger


@dataclass
class DBConfig:
    """Configuration for database connection pooling."""
    max_connections: int = 10
    max_idle_time: int = 300  # 5 minutes
    connection_timeout: float = 30.0
    enable_wal_mode: bool = True
    cache_size: int = 10000
    temp_store: str = "MEMORY"
    synchronous_mode: str = "NORMAL"


class DatabasePool:
    """SQLite connection pool with enhanced performance features."""
    
    def __init__(self, db_file: str, config: DBConfig):
        self.db_file = db_file
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
                        self.logger.debug("Cleaned up idle DB connection", connection_id=conn_id)
                        
            except Exception as e:
                self.logger.error("Error in DB cleanup thread", exception=e)
    
    def _create_connection_id(self) -> str:
        """Create unique connection ID."""
        return f"conn_{threading.current_thread().ident}_{int(time.time() * 1000)}"
    
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection with optimizations."""
        try:
            conn = sqlite3.connect(
                self.db_file,
                timeout=self.config.connection_timeout,
                check_same_thread=False
            )
            
            # Set row factory for dictionary-like access
            conn.row_factory = sqlite3.Row
            
            # Performance optimizations
            if self.config.enable_wal_mode:
                conn.execute('PRAGMA journal_mode=WAL')
            
            conn.execute(f'PRAGMA synchronous={self.config.synchronous_mode}')
            conn.execute(f'PRAGMA cache_size={self.config.cache_size}')
            conn.execute(f'PRAGMA temp_store={self.config.temp_store}')
            conn.execute('PRAGMA mmap_size=268435456')  # 256MB memory mapping
            
            # Enable query planner optimizations
            conn.execute('PRAGMA optimize')
            
            self.logger.debug("Created new DB connection")
            return conn
            
        except Exception as e:
            self.logger.error("Failed to create DB connection", exception=e)
            raise
    
    def _close_connection(self, conn_id: str):
        """Close and remove a connection from the pool."""
        if conn_id in self._connections:
            try:
                conn = self._connections.pop(conn_id)
                conn.close()
            except Exception as e:
                self.logger.debug("Error closing DB connection", connection_id=conn_id, exception=e)
            
            self._last_used.pop(conn_id, None)
    
    def get_connection(self) -> sqlite3.Connection:
        """Get a connection from the pool or create a new one."""
        with self._lock:
            # Try to get an existing connection
            try:
                conn_id = self._pool.get_nowait()
                if conn_id in self._connections:
                    self._last_used[conn_id] = time.time()
                    return self._connections[conn_id]
                else:
                    # Connection ID not found, create new
                    self._pool.put(conn_id, block=False)
            except Empty:
                pass
            
            # Create new connection
            try:
                conn_id = self._create_connection_id()
                conn = self._create_connection()
                self._connections[conn_id] = conn
                self._last_used[conn_id] = time.time()
                
                self.logger.debug("Created new DB connection", connection_id=conn_id)
                return conn
                
            except Exception as e:
                self.logger.error("Failed to get DB connection", exception=e)
                raise
    
    def return_connection(self, conn: sqlite3.Connection):
        """Return a connection to the pool."""
        with self._lock:
            # Find connection ID
            conn_id = None
            for cid, connection in self._connections.items():
                if connection is conn:
                    conn_id = cid
                    break
            
            if conn_id:
                self._last_used[conn_id] = time.time()
    
    def close_all_connections(self):
        """Close all connections in the pool."""
        with self._lock:
            for conn_id in list(self._connections.keys()):
                self._close_connection(conn_id)
    
    @contextmanager
    def get_connection_context(self):
        """Context manager for database connections."""
        conn = None
        try:
            conn = self.get_connection()
            yield conn
            self.return_connection(conn)
        except Exception as e:
            self.logger.error("Database operation failed", exception=e)
            if conn:
                # Don't return failed connection to pool
                conn_id = None
                with self._lock:
                    for cid, connection in self._connections.items():
                        if connection is conn:
                            conn_id = cid
                            break
                
                if conn_id:
                    self._close_connection(conn_id)
            raise
    
    def execute_query(self, query: str, params: tuple = None, fetch_one: bool = False, 
                      fetch_all: bool = True) -> Optional[Any]:
        """Execute a query with automatic connection management."""
        start_time = time.time()
        
        try:
            with self.get_connection_context() as conn:
                cursor = conn.cursor()
                
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                if fetch_one:
                    result = cursor.fetchone()
                elif fetch_all:
                    result = cursor.fetchall()
                else:
                    result = cursor.lastrowid
                
                conn.commit()
                
                duration = time.time() - start_time
                self.logger.debug("Query executed successfully", 
                                query=query[:100], 
                                duration=duration,
                                rows_affected=cursor.rowcount)
                
                return result
                
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error("Query execution failed", 
                            query=query[:100], 
                            exception=e, 
                            duration=duration)
            raise
    
    def execute_many(self, query: str, params_list: List[tuple]) -> None:
        """Execute multiple queries with automatic connection management."""
        start_time = time.time()
        
        try:
            with self.get_connection_context() as conn:
                cursor = conn.cursor()
                cursor.executemany(query, params_list)
                conn.commit()
                
                duration = time.time() - start_time
                self.logger.debug("Batch query executed successfully", 
                                query=query[:100], 
                                duration=duration,
                                rows_affected=cursor.rowcount,
                                batch_size=len(params_list))
                
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error("Batch query execution failed", 
                            query=query[:100], 
                            exception=e, 
                            duration=duration)
            raise
    
    def optimize_database(self):
        """Optimize database performance."""
        start_time = time.time()
        
        try:
            with self.get_connection_context() as conn:
                # Analyze tables for query optimization
                tables = ['accounts', 'emails']
                for table in tables:
                    conn.execute(f'ANALYZE {table}')
                
                # Rebuild indexes
                conn.execute('REINDEX')
                
                # Update table statistics
                conn.execute('PRAGMA optimize')
                
                # Vacuum to reclaim space
                conn.execute('VACUUM')
                
                conn.commit()
                
                duration = time.time() - start_time
                self.logger.log_operation("optimize_database", duration=duration, success=True)
                
        except Exception as e:
            duration = time.time() - start_time
            self.logger.log_operation("optimize_database", duration=duration, success=False, exception=e)
            raise


# Global database pool instance
_db_pool = None


def get_db_pool(db_file: str = None) -> DatabasePool:
    """Get the global database pool instance."""
    global _db_pool
    if _db_pool is None:
        from ..utils.utils import get_database_file
        if db_file is None:
            db_file = str(get_database_file())
        
        config = DBConfig()
        _db_pool = DatabasePool(db_file, config)
    return _db_pool


class QueryBuilder:
    """Helper class for building SQL queries safely."""
    
    @staticmethod
    def select(table: str, columns: List[str] = None, where: str = None, 
               order_by: str = None, limit: int = None, offset: int = None) -> str:
        """Build a SELECT query."""
        query_parts = ["SELECT"]
        
        if columns:
            query_parts.append(", ".join(columns))
        else:
            query_parts.append("*")
        
        query_parts.append(f"FROM {table}")
        
        if where:
            query_parts.append(f"WHERE {where}")
        
        if order_by:
            query_parts.append(f"ORDER BY {order_by}")
        
        if limit:
            query_parts.append(f"LIMIT {limit}")
        
        if offset:
            query_parts.append(f"OFFSET {offset}")
        
        return " ".join(query_parts)
    
    @staticmethod
    def insert(table: str, columns: List[str], on_conflict: str = None) -> str:
        """Build an INSERT query."""
        placeholders = ", ".join(["?" for _ in columns])
        query = f"INSERT {on_conflict or ''} INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
        return query
    
    @staticmethod
    def update(table: str, columns: List[str], where: str = None) -> str:
        """Build an UPDATE query."""
        set_clause = ", ".join([f"{col} = ?" for col in columns])
        query = f"UPDATE {table} SET {set_clause}"
        
        if where:
            query += f" WHERE {where}"
        
        return query
    
    @staticmethod
    def delete(table: str, where: str = None) -> str:
        """Build a DELETE query."""
        query = f"DELETE FROM {table}"
        
        if where:
            query += f" WHERE {where}"
        
        return query
