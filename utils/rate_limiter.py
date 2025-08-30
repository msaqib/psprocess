"""
Rate limiting utilities for API requests
"""

import time
import threading
from typing import Dict, Optional
from utils.logger import get_logger

logger = get_logger(__name__)

class RateLimiter:
    """Thread-safe rate limiter to control request frequency"""
    
    def __init__(self, requests_per_minute: int, name: str = "RateLimiter"):
        self.requests_per_minute = requests_per_minute
        self.min_interval = 60.0 / requests_per_minute
        self.last_request = 0.0
        self.name = name
        self.lock = threading.Lock()
        self.request_count = 0
        
        logger.info(f"Initialized {name} with {requests_per_minute} requests/minute "
                   f"(min interval: {self.min_interval:.2f}s)")
    
    def wait_if_needed(self) -> float:
        """Wait if necessary to maintain rate limit. Returns actual wait time."""
        with self.lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request
            
            wait_time = 0.0
            if time_since_last < self.min_interval:
                wait_time = self.min_interval - time_since_last
                logger.debug(f"{self.name}: Rate limiting - sleeping for {wait_time:.2f}s")
                time.sleep(wait_time)
            
            self.last_request = time.time()
            self.request_count += 1
            
            if self.request_count % 10 == 0:  # Log every 10 requests
                logger.info(f"{self.name}: Processed {self.request_count} requests")
            
            return wait_time
    
    def reset(self):
        """Reset the rate limiter"""
        with self.lock:
            self.last_request = 0.0
            self.request_count = 0
            logger.info(f"{self.name}: Rate limiter reset")

class MultiRateLimiter:
    """Manage multiple rate limiters for different services"""
    
    def __init__(self):
        self.limiters: Dict[str, RateLimiter] = {}
        
    def add_limiter(self, name: str, requests_per_minute: int) -> RateLimiter:
        """Add a new rate limiter"""
        limiter = RateLimiter(requests_per_minute, name)
        self.limiters[name] = limiter
        return limiter
    
    def get_limiter(self, name: str) -> Optional[RateLimiter]:
        """Get a rate limiter by name"""
        return self.limiters.get(name)
    
    def wait_for_service(self, service_name: str) -> float:
        """Wait for a specific service's rate limit"""
        limiter = self.get_limiter(service_name)
        if limiter:
            return limiter.wait_if_needed()
        else:
            logger.warning(f"No rate limiter found for service: {service_name}")
            return 0.0
    
    def reset_all(self):
        """Reset all rate limiters"""
        for limiter in self.limiters.values():
            limiter.reset()

class AdaptiveRateLimiter(RateLimiter):
    """Rate limiter that adapts based on response times and errors"""
    
    def __init__(self, initial_requests_per_minute: int, name: str = "AdaptiveRateLimiter"):
        super().__init__(initial_requests_per_minute, name)
        self.initial_rate = initial_requests_per_minute
        self.current_rate = initial_requests_per_minute
        self.error_count = 0
        self.success_count = 0
        self.last_error_time = 0.0
        
    def record_success(self):
        """Record a successful request"""
        with self.lock:
            self.success_count += 1
            
            # Gradually increase rate if we have many successes
            if self.success_count > 0 and self.success_count % 20 == 0:
                if self.current_rate < self.initial_rate * 1.5:  # Cap at 150% of initial
                    self.current_rate = min(self.current_rate + 1, self.initial_rate * 1.5)
                    self.min_interval = 60.0 / self.current_rate
                    logger.info(f"{self.name}: Increased rate to {self.current_rate} req/min")
    
    def record_error(self, error_type: str = "unknown"):
        """Record an error and potentially slow down"""
        with self.lock:
            self.error_count += 1
            self.last_error_time = time.time()
            
            # Decrease rate on errors
            if self.error_count % 3 == 0:  # Every 3 errors
                old_rate = self.current_rate
                self.current_rate = max(self.current_rate * 0.8, self.initial_rate * 0.3)
                self.min_interval = 60.0 / self.current_rate
                logger.warning(f"{self.name}: Error '{error_type}' - decreased rate from "
                             f"{old_rate:.1f} to {self.current_rate:.1f} req/min")
    
    def should_backoff(self) -> bool:
        """Check if we should back off due to recent errors"""
        current_time = time.time()
        return (current_time - self.last_error_time) < 60.0 and self.error_count > 5