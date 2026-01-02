"""
Real-time progress indicator for API calls and long operations
"""

import sys
import time
import threading
from datetime import datetime, timedelta


class ProgressIndicator:
    """
    Live progress indicator showing operation status, elapsed time, and metrics
    """

    def __init__(self, operation_name="Processing"):
        self.operation_name = operation_name
        self.start_time = None
        self.running = False
        self.thread = None
        self.tokens = 0
        self.requests = 0
        self.current_task = ""

    def start(self, task=""):
        self.start_time = time.time()
        self.running = True
        self.current_task = task
        self.thread = threading.Thread(target=self._display_loop, daemon=True)
        self.thread.start()

    def update(self, task="", tokens=0, requests=0):
        if task:
            self.current_task = task
        if tokens > 0:
            self.tokens += tokens
        if requests > 0:
            self.requests += requests

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        sys.stdout.write('\r' + ' ' * 100 + '\r')
        sys.stdout.flush()

    def _display_loop(self):
        while self.running:
            elapsed = time.time() - self.start_time
            elapsed_str = self._format_time(elapsed)

            parts = [self.current_task or self.operation_name]
            parts.append(f"(esc to interrupt)")
            parts.append(f"{elapsed_str}")

            if self.tokens > 0:
                tokens_str = f"{self.tokens:,}" if self.tokens < 1000 else f"{self.tokens/1000:.1f}k"
                parts.append(f"↓ {tokens_str} tokens")

            if self.requests > 0:
                parts.append(f"{self.requests} requests")

            status_line = " · ".join(parts)

            sys.stdout.write(f'\r{status_line}')
            sys.stdout.flush()
            time.sleep(0.1)

    def _format_time(self, seconds):
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins}m {secs}s"
        else:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            return f"{hours}h {mins}m"


class ProgressTracker:
    """
    Context manager for tracking progress of operations
    """

    def __init__(self, operation_name="Processing", task=""):
        self.indicator = ProgressIndicator(operation_name)
        self.initial_task = task

    def __enter__(self):
        self.indicator.start(self.initial_task)
        return self.indicator

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.indicator.stop()
        return False


def track_api_call(func):
    """
    Decorator to track API calls with progress indicator
    """
    def wrapper(*args, **kwargs):
        operation = func.__name__.replace('_', ' ').title()

        with ProgressTracker(operation, "Making API call...") as progress:
            try:
                result = func(*args, **kwargs)
                return result
            except KeyboardInterrupt:
                progress.update(task="Interrupted by user")
                raise
            except Exception as e:
                progress.update(task=f"Error: {str(e)[:50]}")
                raise

    return wrapper


class StatusBar:
    """
    Simple status bar for showing current operation
    """

    @staticmethod
    def show(message):
        sys.stdout.write(f'\r{message}')
        sys.stdout.flush()

    @staticmethod
    def clear():
        sys.stdout.write('\r' + ' ' * 100 + '\r')
        sys.stdout.flush()

    @staticmethod
    def done(message="Done"):
        StatusBar.clear()
        print(f"[OK] {message}")


class PhaseProgressTracker:
    """
    Track progress through multi-step pipeline phases
    """

    def __init__(self, phase_name, total_steps):
        self.phase_name = phase_name
        self.total_steps = total_steps
        self.current_step = 0
        self.start_time = time.time()
        self.indicator = ProgressIndicator(phase_name)

    def start(self):
        self.indicator.start(f"Starting {self.phase_name}...")

    def next_step(self, step_name, tokens=0, requests=0):
        self.current_step += 1
        task = f"[{self.current_step}/{self.total_steps}] {step_name}"
        self.indicator.update(task=task, tokens=tokens, requests=requests)

    def finish(self):
        elapsed = time.time() - self.start_time
        self.indicator.stop()
        elapsed_str = self.indicator._format_time(elapsed)
        print(f"[OK] {self.phase_name} complete in {elapsed_str}")
        if self.indicator.tokens > 0:
            print(f"     Total tokens: {self.indicator.tokens:,}")
        if self.indicator.requests > 0:
            print(f"     Total requests: {self.indicator.requests}")
