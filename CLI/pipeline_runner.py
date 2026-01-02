"""
Enhanced pipeline runner with progress tracking
"""

import sys
import os
import signal
from contextlib import contextmanager

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from utils.progress import ProgressTracker, PhaseProgressTracker


class InterruptHandler:
    """
    Handle keyboard interrupts gracefully
    """

    def __init__(self):
        self.interrupted = False
        self.original_handler = None

    def __enter__(self):
        self.original_handler = signal.signal(signal.SIGINT, self._handler)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        signal.signal(signal.SIGINT, self.original_handler)
        return False

    def _handler(self, signum, frame):
        self.interrupted = True
        print("\n\nOperation interrupted by user (Ctrl+C)")
        sys.exit(0)


@contextmanager
def phase_progress(phase_name, total_steps=1):
    """
    Context manager for tracking phase progress
    """
    tracker = PhaseProgressTracker(phase_name, total_steps)
    tracker.start()

    with InterruptHandler() as handler:
        try:
            yield tracker
        finally:
            if not handler.interrupted:
                tracker.finish()


def run_with_progress(func, operation_name="Processing"):
    """
    Run a function with progress tracking
    """
    with ProgressTracker(operation_name) as progress:
        try:
            result = func(progress)
            return result
        except KeyboardInterrupt:
            print("\n\nOperation interrupted")
            sys.exit(0)


class APICallTracker:
    """
    Track API calls and token usage during operations
    """

    def __init__(self):
        self.total_tokens = 0
        self.total_requests = 0
        self.calls = []

    def record_call(self, endpoint, tokens=0, duration=0):
        self.total_tokens += tokens
        self.total_requests += 1
        self.calls.append({
            'endpoint': endpoint,
            'tokens': tokens,
            'duration': duration
        })

    def get_summary(self):
        return {
            'total_tokens': self.total_tokens,
            'total_requests': self.total_requests,
            'avg_tokens_per_request': self.total_tokens / max(1, self.total_requests)
        }

    def print_summary(self):
        summary = self.get_summary()
        print(f"\nAPI Usage Summary:")
        print(f"  Requests: {summary['total_requests']}")
        print(f"  Total Tokens: {summary['total_tokens']:,}")
        if summary['total_requests'] > 0:
            print(f"  Avg Tokens/Request: {summary['avg_tokens_per_request']:.0f}")
