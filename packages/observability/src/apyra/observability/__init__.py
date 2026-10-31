"""Observability primitives for Apyra."""

from __future__ import annotations

from .errors import (
    ErrorEvent,
    ErrorMonitoringContext,
    ErrorReporter,
    InMemoryErrorReporter,
    capture_exception,
    capture_message,
    error_monitor,
    get_error_reporter,
    monitor_errors,
    set_error_reporter,
)
from .logging import configure_logging, get_request_id, set_request_id
from .performance import (
    PerformanceMonitor,
    PerformanceRecord,
    PerformanceStats,
    PerformanceTimer,
    get_performance_monitor,
    measure,
    record_duration,
    set_performance_monitor,
    time_operation,
)

setup_logging = configure_logging

__all__ = [
    "ErrorEvent",
    "ErrorMonitoringContext",
    "ErrorReporter",
    "InMemoryErrorReporter",
    "PerformanceMonitor",
    "PerformanceRecord",
    "PerformanceStats",
    "PerformanceTimer",
    "capture_exception",
    "capture_message",
    "configure_logging",
    "error_monitor",
    "get_error_reporter",
    "get_performance_monitor",
    "get_request_id",
    "measure",
    "monitor_errors",
    "record_duration",
    "set_error_reporter",
    "set_performance_monitor",
    "set_request_id",
    "time_operation",
]
