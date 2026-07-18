"""
Thread Utilities for PySide6
Provides standard QRunnable Workers to run tasks in the global QThreadPool.
"""
from PySide6.QtCore import QRunnable, QThreadPool
from utils.logger import Logger

class Worker(QRunnable):
    """Generic worker runnable to execute any callable function in a background thread pool."""
    
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            self.fn(*self.args, **self.kwargs)
        except Exception as e:
            Logger.error("WorkerThread", f"Exception in background execution: {e}")


def run_in_background(fn, *args, **kwargs):
    """Helper to run a function asynchronously in the global QThreadPool."""
    worker = Worker(fn, *args, **kwargs)
    QThreadPool.globalInstance().start(worker)
