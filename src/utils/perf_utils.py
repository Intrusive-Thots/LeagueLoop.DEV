"""
Performance optimization utilities for LeagueLoop.
Provides thread pooling, event-based waiting, and other performance helpers.
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Any, Optional


class BoundedExecutor:
    """
    Thread-safe bounded thread pool executor with task tracking.
    Prevents unbounded thread creation and provides better resource management.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, max_workers: int = 4, thread_name_prefix: str = "worker"):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, max_workers: int = 4, thread_name_prefix: str = "worker"):
        if self._initialized:
            return
        
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix
        )
        self._task_count = 0
        self._task_lock = threading.Lock()
        self._shutdown = False
        self._initialized = True
    
    def submit(self, fn: Callable, *args, **kwargs) -> Optional[Future]:
        """Submit a task to the executor."""
        with self._task_lock:
            if self._shutdown:
                return None
            self._task_count += 1
        
        return self._executor.submit(fn, *args, **kwargs)
    
    def shutdown(self, wait: bool = True):
        """Shutdown the executor."""
        with self._task_lock:
            self._shutdown = True
        
        self._executor.shutdown(wait=wait)
    
    def get_task_count(self) -> int:
        """Get total number of submitted tasks."""
        with self._task_lock:
            return self._task_count
    
    @classmethod
    def get_instance(cls) -> 'BoundedExecutor':
        """Get the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance


class InterruptibleWait:
    """
    Event-based waiting that can be interrupted immediately.
    Replacement for blocking time.sleep() calls.
    """
    
    def __init__(self):
        self._event = threading.Event()
        self._stopped = False
    
    def wait(self, timeout: float) -> bool:
        """
        Wait for specified timeout or until stopped.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if stopped, False if timeout occurred
        """
        if self._stopped:
            return True
        
        # Wait returns True if event is set (stopped), False if timeout
        return self._event.wait(timeout)
    
    def stop(self):
        """Stop any waiting threads immediately."""
        self._stopped = True
        self._event.set()
    
    def reset(self):
        """Reset the stop flag and clear the event."""
        self._stopped = False
        self._event.clear()
    
    def is_stopped(self) -> bool:
        """Check if stopped."""
        return self._stopped


class WorkerLoop:
    """
    Helper class for creating interruptible worker loops.
    Replaces patterns like:
        while running:
            do_work()
            time.sleep(interval)
    
    With:
        while not waiter.is_stopped():
            do_work()
            if waiter.wait(interval):
                break
    """
    
    def __init__(self, name: str = "worker"):
        self.name = name
        self._waiter = InterruptibleWait()
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self, work_func: Callable[[], None], interval: float = 1.0):
        """
        Start the worker loop.
        
        Args:
            work_func: Function to call in each iteration
            interval: Time between iterations in seconds
        """
        if self._running:
            return
        
        self._running = True
        self._waiter.reset()
        
        def loop():
            while not self._waiter.is_stopped():
                try:
                    work_func()
                except Exception as e:
                    # Log error but continue loop
                    from utils.logger import Logger
                    Logger.error(self.name, f"Worker error: {e}")
                
                if self._waiter.wait(interval):
                    break
            
            self._running = False
        
        self._thread = threading.Thread(target=loop, daemon=True, name=self.name)
        self._thread.start()
    
    def stop(self, timeout: Optional[float] = None):
        """
        Stop the worker loop.
        
        Args:
            timeout: Maximum time to wait for thread to finish
        """
        self._waiter.stop()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
    
    def is_running(self) -> bool:
        """Check if worker is running."""
        return self._running


def create_shared_session(pool_connections: int = 20, pool_maxsize: int = 20, max_retries: int = 2):
    """
    Create a shared requests.Session with optimized connection pooling.
    
    Args:
        pool_connections: Number of connection pools to cache
        pool_maxsize: Maximum number of connections per pool
        max_retries: Maximum number of retries per request
    
    Returns:
        Optimized requests.Session instance
    """
    import requests
    from requests.adapters import HTTPAdapter
    
    session = requests.Session()
    adapter = HTTPAdapter(
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize,
        max_retries=max_retries,
        pool_block=False
    )
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    
    return session


__all__ = [
    'BoundedExecutor',
    'InterruptibleWait',
    'WorkerLoop',
    'create_shared_session',
]
