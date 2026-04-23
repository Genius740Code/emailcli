"""Monitoring and metrics collection for the email CLI tool."""

import time
import threading
import psutil
import json
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
from pathlib import Path
from ..utils.logger import get_logger
from ..utils.utils import get_config_dir


@dataclass
class OperationMetric:
    """Metric for a single operation."""
    operation: str
    duration: float
    success: bool
    timestamp: float
    error_type: Optional[str] = None
    domain: Optional[str] = None
    email_count: Optional[int] = None
    bytes_processed: Optional[int] = None
    additional_data: Optional[Dict[str, Any]] = None


@dataclass
class SystemMetrics:
    """System performance metrics."""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_usage_percent: float
    active_connections: int
    timestamp: float


@dataclass
class DatabaseMetrics:
    """Database performance metrics."""
    total_accounts: int
    total_emails: int
    database_size_mb: float
    query_count: int
    avg_query_time: float
    cache_hit_ratio: float
    timestamp: float


class MetricsCollector:
    """Collects and manages performance metrics."""
    
    def __init__(self):
        self.logger = get_logger()
        self.metrics_dir = get_config_dir() / "metrics"
        self.metrics_dir.mkdir(exist_ok=True)
        
        # Operation metrics storage
        self.operation_metrics = defaultdict(lambda: deque(maxlen=1000))
        self.operation_stats = defaultdict(lambda: {
            'total_count': 0,
            'success_count': 0,
            'failure_count': 0,
            'total_duration': 0.0,
            'min_duration': float('inf'),
            'max_duration': 0.0,
            'avg_duration': 0.0
        })
        
        # System metrics storage
        self.system_metrics = deque(maxlen=1440)  # 24 hours of minute data
        self.database_metrics = deque(maxlen=1440)
        
        # Real-time counters
        self.counters = defaultdict(int)
        self.gauges = defaultdict(float)
        
        # Thread safety
        self._lock = threading.Lock()
        self._collection_thread = None
        self._start_collection_thread()
    
    def _start_collection_thread(self):
        """Start background thread for collecting system metrics."""
        if self._collection_thread is None or not self._collection_thread.is_alive():
            self._collection_thread = threading.Thread(target=self._collect_system_metrics, daemon=True)
            self._collection_thread.start()
    
    def _collect_system_metrics(self):
        """Collect system metrics periodically."""
        while True:
            try:
                time.sleep(60)  # Collect every minute
                
                # Get system metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage(self.metrics_dir.anchor)
                
                # Get active connections (approximation)
                try:
                    connections = len(psutil.net_connections())
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    connections = 0
                
                system_metric = SystemMetrics(
                    cpu_percent=cpu_percent,
                    memory_percent=memory.percent,
                    memory_used_mb=memory.used / 1024 / 1024,
                    disk_usage_percent=disk.percent,
                    active_connections=connections,
                    timestamp=time.time()
                )
                
                with self._lock:
                    self.system_metrics.append(system_metric)
                
                self.logger.debug("System metrics collected", 
                                cpu=cpu_percent, 
                                memory=memory.percent, 
                                disk=disk.percent)
                
            except Exception as e:
                self.logger.error("Error collecting system metrics", exception=e)
    
    def record_operation(self, operation: str, duration: float, success: bool = True,
                       error_type: Optional[str] = None, domain: Optional[str] = None,
                       email_count: Optional[int] = None, bytes_processed: Optional[int] = None,
                       **additional_data):
        """Record an operation metric."""
        metric = OperationMetric(
            operation=operation,
            duration=duration,
            success=success,
            timestamp=time.time(),
            error_type=error_type,
            domain=domain,
            email_count=email_count,
            bytes_processed=bytes_processed,
            additional_data=additional_data if additional_data else None
        )
        
        with self._lock:
            # Store raw metric
            self.operation_metrics[operation].append(metric)
            
            # Update statistics
            stats = self.operation_stats[operation]
            stats['total_count'] += 1
            
            if success:
                stats['success_count'] += 1
            else:
                stats['failure_count'] += 1
            
            stats['total_duration'] += duration
            stats['min_duration'] = min(stats['min_duration'], duration)
            stats['max_duration'] = max(stats['max_duration'], duration)
            stats['avg_duration'] = stats['total_duration'] / stats['total_count']
            
            # Update counters
            self.counters[f"{operation}_total"] += 1
            if success:
                self.counters[f"{operation}_success"] += 1
            else:
                self.counters[f"{operation}_failure"] += 1
            
            # Update gauges
            self.gauges[f"{operation}_last_duration"] = duration
            self.gauges[f"{operation}_success_rate"] = (
                stats['success_count'] / stats['total_count'] * 100
            )
    
    def record_database_metrics(self, total_accounts: int, total_emails: int,
                              database_size_mb: float, query_count: int,
                              avg_query_time: float, cache_hit_ratio: float):
        """Record database performance metrics."""
        metric = DatabaseMetrics(
            total_accounts=total_accounts,
            total_emails=total_emails,
            database_size_mb=database_size_mb,
            query_count=query_count,
            avg_query_time=avg_query_time,
            cache_hit_ratio=cache_hit_ratio,
            timestamp=time.time()
        )
        
        with self._lock:
            self.database_metrics.append(metric)
    
    def increment_counter(self, name: str, value: int = 1):
        """Increment a counter metric."""
        with self._lock:
            self.counters[name] += value
    
    def set_gauge(self, name: str, value: float):
        """Set a gauge metric."""
        with self._lock:
            self.gauges[name] = value
    
    def get_operation_stats(self, operation: str, minutes: int = 60) -> Dict[str, Any]:
        """Get statistics for a specific operation."""
        current_time = time.time()
        cutoff_time = current_time - (minutes * 60)
        
        with self._lock:
            # Filter recent metrics
            recent_metrics = [
                m for m in self.operation_metrics.get(operation, [])
                if m.timestamp >= cutoff_time
            ]
            
            if not recent_metrics:
                return {}
            
            # Calculate statistics
            durations = [m.duration for m in recent_metrics]
            successes = [m for m in recent_metrics if m.success]
            failures = [m for m in recent_metrics if not m.success]
            
            error_types = defaultdict(int)
            domains = defaultdict(int)
            
            for m in recent_metrics:
                if m.error_type:
                    error_types[m.error_type] += 1
                if m.domain:
                    domains[m.domain] += 1
            
            return {
                'operation': operation,
                'time_range_minutes': minutes,
                'total_operations': len(recent_metrics),
                'successful_operations': len(successes),
                'failed_operations': len(failures),
                'success_rate': len(successes) / len(recent_metrics) * 100,
                'avg_duration': sum(durations) / len(durations),
                'min_duration': min(durations),
                'max_duration': max(durations),
                'error_types': dict(error_types),
                'domains': dict(domains),
                'operations_per_minute': len(recent_metrics) / minutes
            }
    
    def get_system_stats(self, minutes: int = 60) -> Dict[str, Any]:
        """Get system performance statistics."""
        current_time = time.time()
        cutoff_time = current_time - (minutes * 60)
        
        with self._lock:
            recent_metrics = [
                m for m in self.system_metrics
                if m.timestamp >= cutoff_time
            ]
            
            if not recent_metrics:
                return {}
            
            cpu_values = [m.cpu_percent for m in recent_metrics]
            memory_values = [m.memory_percent for m in recent_metrics]
            disk_values = [m.disk_usage_percent for m in recent_metrics]
            connection_values = [m.active_connections for m in recent_metrics]
            
            return {
                'time_range_minutes': minutes,
                'avg_cpu_percent': sum(cpu_values) / len(cpu_values),
                'max_cpu_percent': max(cpu_values),
                'avg_memory_percent': sum(memory_values) / len(memory_values),
                'max_memory_percent': max(memory_values),
                'avg_disk_usage': sum(disk_values) / len(disk_values),
                'max_disk_usage': max(disk_values),
                'avg_connections': sum(connection_values) / len(connection_values),
                'max_connections': max(connection_values)
            }
    
    def get_database_stats(self, minutes: int = 60) -> Dict[str, Any]:
        """Get database performance statistics."""
        current_time = time.time()
        cutoff_time = current_time - (minutes * 60)
        
        with self._lock:
            recent_metrics = [
                m for m in self.database_metrics
                if m.timestamp >= cutoff_time
            ]
            
            if not recent_metrics:
                return {}
            
            email_counts = [m.total_emails for m in recent_metrics]
            query_times = [m.avg_query_time for m in recent_metrics]
            cache_ratios = [m.cache_hit_ratio for m in recent_metrics]
            
            return {
                'time_range_minutes': minutes,
                'current_accounts': recent_metrics[-1].total_accounts,
                'current_emails': recent_metrics[-1].total_emails,
                'current_database_size_mb': recent_metrics[-1].database_size_mb,
                'avg_query_time': sum(query_times) / len(query_times),
                'avg_cache_hit_ratio': sum(cache_ratios) / len(cache_ratios),
                'total_queries': sum(m.query_count for m in recent_metrics)
            }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all available metrics."""
        with self._lock:
            return {
                'counters': dict(self.counters),
                'gauges': dict(self.gauges),
                'operation_stats': dict(self.operation_stats),
                'timestamp': time.time()
            }
    
    def export_metrics(self, filename: Optional[str] = None) -> str:
        """Export metrics to a JSON file."""
        if filename is None:
            filename = f"metrics_{int(time.time())}.json"
        
        filepath = self.metrics_dir / filename
        
        # Collect all metrics
        all_metrics = {
            'export_timestamp': time.time(),
            'counters': dict(self.counters),
            'gauges': dict(self.gauges),
            'operation_stats': dict(self.operation_stats),
            'recent_operations': {
                op: [asdict(m) for m in list(deque_obj)[-10:]]  # Last 10 per operation
                for op, deque_obj in self.operation_metrics.items()
            },
            'system_metrics': [asdict(m) for m in list(self.system_metrics)[-60:]],  # Last hour
            'database_metrics': [asdict(m) for m in list(self.database_metrics)[-60:]]   # Last hour
        }
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(all_metrics, f, indent=2, default=str)
            
            self.logger.info("Metrics exported successfully", filepath=str(filepath))
            return str(filepath)
            
        except Exception as e:
            self.logger.error("Failed to export metrics", exception=e)
            raise
    
    def reset_metrics(self):
        """Reset all metrics."""
        with self._lock:
            self.operation_metrics.clear()
            self.operation_stats.clear()
            self.system_metrics.clear()
            self.database_metrics.clear()
            self.counters.clear()
            self.gauges.clear()
        
        self.logger.info("All metrics reset")
    
    def cleanup_old_metrics(self, hours: int = 24):
        """Clean up old metrics data."""
        cutoff_time = time.time() - (hours * 3600)
        
        with self._lock:
            # Clean operation metrics
            for operation, metrics_deque in self.operation_metrics.items():
                while metrics_deque and metrics_deque[0].timestamp < cutoff_time:
                    metrics_deque.popleft()
            
            # Clean system and database metrics
            while self.system_metrics and self.system_metrics[0].timestamp < cutoff_time:
                self.system_metrics.popleft()
            
            while self.database_metrics and self.database_metrics[0].timestamp < cutoff_time:
                self.database_metrics.popleft()
        
        self.logger.info("Old metrics cleaned up", hours=hours)


# Global metrics collector instance
_metrics_collector = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def track_operation(operation: str):
    """Decorator to automatically track operation metrics."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            metrics = get_metrics_collector()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                metrics.record_operation(operation, duration, success=True)
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                metrics.record_operation(operation, duration, success=False, 
                                      error_type=type(e).__name__)
                raise
        
        return wrapper
    return decorator
