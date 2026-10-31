"""Tests for error and performance monitoring primitives."""

from __future__ import annotations

import pytest

from apyra.observability import (
    InMemoryErrorReporter,
    PerformanceMonitor,
    capture_exception,
    capture_message,
    get_performance_monitor,
    measure,
    monitor_errors,
    record_duration,
    set_error_reporter,
    set_performance_monitor,
    time_operation,
)


def test_capture_exception_records_event() -> None:
    reporter = InMemoryErrorReporter()
    set_error_reporter(reporter)
    try:
        raise ValueError("boom")
    except ValueError as exc:
        event_id = capture_exception(exc, tags={"source": "test"}, context={"value": 1})

    events = reporter.events()
    assert len(events) == 1
    assert events[0].event_id == event_id
    assert events[0].exception_type == "ValueError"
    assert events[0].message == "boom"
    assert events[0].tags == {"source": "test"}
    assert events[0].context == {"value": 1}


def test_capture_message_records_message() -> None:
    reporter = InMemoryErrorReporter()
    event_id = capture_message("hello", reporter=reporter, level="warning")
    events = reporter.events()
    assert len(events) == 1
    assert events[0].event_id == event_id
    assert events[0].message == "hello"
    assert events[0].level == "warning"


def test_monitor_errors_captures_and_reraises() -> None:
    reporter = InMemoryErrorReporter()
    set_error_reporter(reporter)
    with pytest.raises(RuntimeError), monitor_errors():
        raise RuntimeError("failure")
    assert len(reporter.events()) == 1


def test_monitor_errors_can_suppress() -> None:
    reporter = InMemoryErrorReporter()
    set_error_reporter(reporter)
    with monitor_errors(reraise=False):
        raise RuntimeError("failure")
    assert len(reporter.events()) == 1


def test_performance_monitor_aggregates() -> None:
    monitor = PerformanceMonitor()
    set_performance_monitor(monitor)
    with monitor.measure("operation"):
        pass
    record_duration("operation", 0.01)
    stats = monitor.stats("operation")
    assert stats["operation"].count == 2
    assert stats["operation"].min_seconds >= 0


def test_measure_and_time_operation() -> None:
    monitor = PerformanceMonitor()
    set_performance_monitor(monitor)
    with measure("block"):
        pass
    with time_operation("block"):
        pass
    assert get_performance_monitor().stats("block")["block"].count == 2


def test_performance_timer() -> None:
    from apyra.observability.performance import PerformanceTimer

    monitor = PerformanceMonitor()
    with PerformanceTimer(monitor, "timer") as timer:
        timer.stop() if False else None
    # Manual usage:
    manual = PerformanceTimer(monitor, "manual").start()
    elapsed = manual.stop()
    assert elapsed >= 0
    assert monitor.stats("manual")["manual"].count == 1


def test_error_monitor_decorator() -> None:
    from apyra.observability.errors import error_monitor

    reporter = InMemoryErrorReporter()
    set_error_reporter(reporter)

    @error_monitor
    def fail() -> None:
        raise ValueError("decorated")

    with pytest.raises(ValueError):
        fail()
    assert len(reporter.events()) == 1


@pytest.fixture(autouse=True)
def _reset_monitoring_state() -> None:
    from apyra.observability import PerformanceMonitor, set_error_reporter, set_performance_monitor
    from apyra.observability.errors import InMemoryErrorReporter

    set_error_reporter(InMemoryErrorReporter())
    set_performance_monitor(PerformanceMonitor())


def test_config_validation() -> None:
    from apyra.observability.errors import InMemoryErrorReporter

    with pytest.raises(ValueError):
        InMemoryErrorReporter(max_events=0)
    with pytest.raises(ValueError):
        PerformanceMonitor(max_records=0)
