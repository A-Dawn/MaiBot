"""为存储链路提供统一的阶段耗时日志，不记录请求或文件内容。"""

from contextlib import contextmanager
from functools import wraps
from structlog.stdlib import BoundLogger
from typing import Any, Callable, Dict, Iterator, ParamSpec, TypeVar

import threading
import time

P = ParamSpec("P")
R = TypeVar("R")


@contextmanager
def log_operation(
    logger: BoundLogger, operation: str, *, report: bool = False, **details: Any
) -> Iterator[Dict[str, Any]]:
    """快速操作记 DEBUG，慢操作或异常记 WARNING，定期维护可显式记 INFO。"""
    started_at = time.perf_counter()
    thread_name = threading.current_thread().name
    log = logger.info if report else logger.debug
    log(f"存储操作开始: operation={operation} thread={thread_name} details={details}")
    outcome = "failed"
    try:
        yield details
        outcome = "completed"
    finally:
        elapsed = time.perf_counter() - started_at
        log = logger.warning if elapsed >= 0.5 or outcome == "failed" else logger.info if report else logger.debug
        log(
            f"存储操作结束: operation={operation} thread={thread_name} "
            f"耗时={elapsed:.3f}s outcome={outcome} details={details}"
        )


def timed_operation(logger: BoundLogger, operation: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """测量同步操作的整体耗时，保留异常和函数签名。"""

    def decorate(function: Callable[P, R]) -> Callable[P, R]:
        @wraps(function)
        def measured(*args: P.args, **kwargs: P.kwargs) -> R:
            with log_operation(logger, operation):
                return function(*args, **kwargs)

        return measured

    return decorate
