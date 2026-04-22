"""Rate limiting and request throttling for email operations."""

import time
import threading
from collections import deque, defaultdict
from typing import Dict, Optional, Callable
from dataclasses import dataclass
from .logger import get_logger


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    max_requests_per_second: int = 10
    max_requests_per_minute: int = 100
    max_requests_per_hour: int = 1000
    burst_size: int = 20
    cleanup_interval: int = 300  # 5 minutes


class RateLimiter:
    """Thread-safe rate limiter with multiple time windows."""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.logger = get_logger()
        
        # Request tracking for different time windows
        self._requests_per_second = deque()
        self._requests_per_minute = deque()
        self._requests_per_hour = deque()
        
        # Per-domain tracking
        self._domain_requests = defaultdict(lambda: {
            'second': deque(),
            'minute': deque(),
            'hour': deque()
        })
        
        self._lock = threading.Lock()
        self._cleanup_thread = None
        self._start_cleanup_thread()
    
    def _start_cleanup_thread(self):
        """Start background thread to cleanup old requests."""
        if self._cleanup_thread is None or not self._cleanup_thread.is_alive():
            self._cleanup_thread = threading.Thread(target=self._cleanup_old_requests, daemon=True)
            self._cleanup_thread.start()
    
    def _cleanup_old_requests(self):
        """Cleanup old request records periodically."""
        while True:
            try:
                time.sleep(60)  # Check every minute
                current_time = time.time()
                
                with self._lock:
                    # Cleanup global counters
                    cutoff_second = current_time - 1
                    cutoff_minute = current_time - 60
                    cutoff_hour = current_time - 3600
                    
                    # Cleanup per-second requests
                    while self._requests_per_second and self._requests_per_second[0] < cutoff_second:
                        self._requests_per_second.popleft()
                    
                    # Cleanup per-minute requests
                    while self._requests_per_minute and self._requests_per_minute[0] < cutoff_minute:
                        self._requests_per_minute.popleft()
                    
                    # Cleanup per-hour requests
                    while self._requests_per_hour and self._requests_per_hour[0] < cutoff_hour:
                        self._requests_per_hour.popleft()
                    
                    # Cleanup per-domain requests
                    for domain, requests in self._domain_requests.items():
                        while requests['second'] and requests['second'][0] < cutoff_second:
                            requests['second'].popleft()
                        
                        while requests['minute'] and requests['minute'][0] < cutoff_minute:
                            requests['minute'].popleft()
                        
                        while requests['hour'] and requests['hour'][0] < cutoff_hour:
                            requests['hour'].popleft()
                        
                        # Remove empty domains
                        if not any(requests.values()):
                            del self._domain_requests[domain]
                    
                    self.logger.debug("Rate limiter cleanup completed", 
                                    domains_tracked=len(self._domain_requests))
                        
            except Exception as e:
                self.logger.error("Error in rate limiter cleanup thread", exception=e)
    
    def _check_rate_limit(self, requests: deque, max_requests: int, window: int, current_time: float) -> bool:
        """Check if rate limit is exceeded for a specific time window."""
        cutoff = current_time - window
        
        # Remove old requests
        while requests and requests[0] < cutoff:
            requests.popleft()
        
        return len(requests) < max_requests
    
    def can_make_request(self, domain: str = None) -> bool:
        """Check if a request can be made based on rate limits."""
        current_time = time.time()
        
        with self._lock:
            # Check global rate limits
            if not self._check_rate_limit(self._requests_per_second, 
                                         self.config.max_requests_per_second, 1, current_time):
                self.logger.warning("Global per-second rate limit exceeded")
                return False
            
            if not self._check_rate_limit(self._requests_per_minute, 
                                         self.config.max_requests_per_minute, 60, current_time):
                self.logger.warning("Global per-minute rate limit exceeded")
                return False
            
            if not self._check_rate_limit(self._requests_per_hour, 
                                         self.config.max_requests_per_hour, 3600, current_time):
                self.logger.warning("Global per-hour rate limit exceeded")
                return False
            
            # Check per-domain rate limits if domain is specified
            if domain:
                domain_requests = self._domain_requests[domain]
                
                # Per-domain limits (more restrictive than global)
                domain_second_limit = min(self.config.max_requests_per_second, 5)
                domain_minute_limit = min(self.config.max_requests_per_minute, 50)
                domain_hour_limit = min(self.config.max_requests_per_hour, 500)
                
                if not self._check_rate_limit(domain_requests['second'], 
                                             domain_second_limit, 1, current_time):
                    self.logger.warning("Per-domain per-second rate limit exceeded", domain=domain)
                    return False
                
                if not self._check_rate_limit(domain_requests['minute'], 
                                             domain_minute_limit, 60, current_time):
                    self.logger.warning("Per-domain per-minute rate limit exceeded", domain=domain)
                    return False
                
                if not self._check_rate_limit(domain_requests['hour'], 
                                             domain_hour_limit, 3600, current_time):
                    self.logger.warning("Per-domain per-hour rate limit exceeded", domain=domain)
                    return False
            
            return True
    
    def record_request(self, domain: str = None):
        """Record a request for rate limiting."""
        current_time = time.time()
        
        with self._lock:
            # Record in global counters
            self._requests_per_second.append(current_time)
            self._requests_per_minute.append(current_time)
            self._requests_per_hour.append(current_time)
            
            # Record in per-domain counters if domain is specified
            if domain:
                domain_requests = self._domain_requests[domain]
                domain_requests['second'].append(current_time)
                domain_requests['minute'].append(current_time)
                domain_requests['hour'].append(current_time)
    
    def wait_if_needed(self, domain: str = None) -> float:
        """Wait if rate limit would be exceeded and return wait time."""
        if self.can_make_request(domain):
            return 0.0
        
        # Calculate wait time based on the most restrictive limit
        current_time = time.time()
        wait_times = []
        
        with self._lock:
            # Check global limits
            if len(self._requests_per_second) >= self.config.max_requests_per_second:
                oldest_request = self._requests_per_second[0]
                wait_time = 1.0 - (current_time - oldest_request)
                wait_times.append(max(0, wait_time))
            
            if len(self._requests_per_minute) >= self.config.max_requests_per_minute:
                oldest_request = self._requests_per_minute[0]
                wait_time = 60.0 - (current_time - oldest_request)
                wait_times.append(max(0, wait_time))
            
            if len(self._requests_per_hour) >= self.config.max_requests_per_hour:
                oldest_request = self._requests_per_hour[0]
                wait_time = 3600.0 - (current_time - oldest_request)
                wait_times.append(max(0, wait_time))
            
            # Check per-domain limits
            if domain:
                domain_requests = self._domain_requests[domain]
                
                domain_second_limit = min(self.config.max_requests_per_second, 5)
                if len(domain_requests['second']) >= domain_second_limit:
                    oldest_request = domain_requests['second'][0]
                    wait_time = 1.0 - (current_time - oldest_request)
                    wait_times.append(max(0, wait_time))
                
                domain_minute_limit = min(self.config.max_requests_per_minute, 50)
                if len(domain_requests['minute']) >= domain_minute_limit:
                    oldest_request = domain_requests['minute'][0]
                    wait_time = 60.0 - (current_time - oldest_request)
                    wait_times.append(max(0, wait_time))
                
                domain_hour_limit = min(self.config.max_requests_per_hour, 500)
                if len(domain_requests['hour']) >= domain_hour_limit:
                    oldest_request = domain_requests['hour'][0]
                    wait_time = 3600.0 - (current_time - oldest_request)
                    wait_times.append(max(0, wait_time))
        
        if wait_times:
            wait_time = max(wait_times)
            self.logger.info("Rate limiting active", domain=domain, wait_time=wait_time)
            time.sleep(wait_time)
            return wait_time
        
        return 0.0
    
    def get_rate_limit_status(self, domain: str = None) -> Dict[str, any]:
        """Get current rate limit status."""
        current_time = time.time()
        
        with self._lock:
            status = {
                'global': {
                    'requests_per_second': len(self._requests_per_second),
                    'max_per_second': self.config.max_requests_per_second,
                    'requests_per_minute': len(self._requests_per_minute),
                    'max_per_minute': self.config.max_requests_per_minute,
                    'requests_per_hour': len(self._requests_per_hour),
                    'max_per_hour': self.config.max_requests_per_hour,
                }
            }
            
            if domain and domain in self._domain_requests:
                domain_requests = self._domain_requests[domain]
                status['domain'] = {
                    'domain': domain,
                    'requests_per_second': len(domain_requests['second']),
                    'max_per_second': min(self.config.max_requests_per_second, 5),
                    'requests_per_minute': len(domain_requests['minute']),
                    'max_per_minute': min(self.config.max_requests_per_minute, 50),
                    'requests_per_hour': len(domain_requests['hour']),
                    'max_per_hour': min(self.config.max_requests_per_hour, 500),
                }
            
            return status


def with_rate_limit(domain_func: Optional[Callable] = None):
    """Decorator to add rate limiting to functions."""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            rate_limiter = get_rate_limiter()
            
            # Extract domain from function arguments if domain_func is provided
            domain = None
            if domain_func:
                try:
                    domain = domain_func(*args, **kwargs)
                except Exception:
                    pass
            
            # Wait if needed and record the request
            rate_limiter.wait_if_needed(domain)
            rate_limiter.record_request(domain)
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Global rate limiter instance
_rate_limiter = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        config = RateLimitConfig()
        _rate_limiter = RateLimiter(config)
    return _rate_limiter
