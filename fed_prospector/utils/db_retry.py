"""Deadlock retry decorator for MySQL operations."""

import functools
import logging
import time

import mysql.connector

logger = logging.getLogger(__name__)


def retry_on_deadlock(max_retries=3, backoff_factor=0.5):
    """Retry a function when MySQL deadlock (error 1213) occurs.

    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Base sleep time between retries (multiplied by attempt number)
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except mysql.connector.errors.DatabaseError as e:
                    if e.errno == 1213 and attempt < max_retries:  # Deadlock
                        wait = backoff_factor * (attempt + 1)
                        logger.warning(
                            "Deadlock detected in %s (attempt %d/%d), retrying in %.1fs",
                            func.__name__, attempt + 1, max_retries, wait
                        )
                        time.sleep(wait)
                    else:
                        raise
        return wrapper
    return decorator
