"""
Structured Logging for Portin

Replaces print() with proper structured logging.
Uses structlog for clean, parseable output.
"""

import logging
import sys
from typing import Any

import structlog


def setup_logging(level: str = "INFO", json_output: bool = False):
    """
    Configure structured logging.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_output: If True, output JSON for log aggregation
    """
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )
    
    # Configure structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.processors.StackInfoRenderer(),
    ]
    
    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.plain_traceback,
        ))
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = None) -> Any:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


# ─────────────────────────────────────────────────────────────
# CONVENIENCE FUNCTIONS (drop-in replacement for print)
# ─────────────────────────────────────────────────────────────

_default_logger = None

def _get_default_logger():
    global _default_logger
    if _default_logger is None:
        setup_logging()
        _default_logger = get_logger("portin")
    return _default_logger


def log_info(msg: str, **kwargs):
    """Log info message."""
    _get_default_logger().info(msg, **kwargs)


def log_warning(msg: str, **kwargs):
    """Log warning message."""
    _get_default_logger().warning(msg, **kwargs)


def log_error(msg: str, **kwargs):
    """Log error message."""
    _get_default_logger().error(msg, **kwargs)


def log_debug(msg: str, **kwargs):
    """Log debug message."""
    _get_default_logger().debug(msg, **kwargs)


# ─────────────────────────────────────────────────────────────
# PROGRESS LOGGING
# ─────────────────────────────────────────────────────────────

class ProgressLogger:
    """
    Log progress through a batch operation.
    
    Usage:
        progress = ProgressLogger(total=100, prefix="Enriching")
        for company in companies:
            progress.update(company.name)
            ...
    """
    
    def __init__(self, total: int, prefix: str = "Processing"):
        self.total = total
        self.current = 0
        self.prefix = prefix
        self.logger = get_logger("progress")
    
    def update(self, item_name: str = None):
        """Update progress."""
        self.current += 1
        pct = (self.current / self.total) * 100 if self.total > 0 else 0
        
        self.logger.info(
            f"{self.prefix}",
            current=self.current,
            total=self.total,
            percent=f"{pct:.1f}%",
            item=item_name
        )
    
    def complete(self):
        """Mark as complete."""
        self.logger.info(
            f"{self.prefix} complete",
            total=self.total
        )


# Initialize logging when module is imported
setup_logging()
