"""Time related utilities."""

import collections
import datetime
import functools
import os
import re
import sys
import threading
import time
import traceback
from functools import lru_cache
from typing import (
    Any,
    Callable,
    Generator,
    List,
    Mapping,
    Optional,
    Tuple,
    Type,
    Union,
)

from datetime import timezone

import tzlocal

PollInterval = Union[float, Tuple[float, float]]

DEFAULT_INTERVAL = 0.2


class TimeoutException(Exception):
    """Timeout exception error."""

    pass


class TimeoutExceptionInfo:
    """
    Holds timeout exception information.
    """

    def __init__(self, start_time=None):
        """
        Mark the time for started waiting.
        """
        if start_time is None:
            self.started = time.time()
        else:
            self.started = start_time

    def msg(self):
        """
        Return a message to be used by TimeoutException containing
        timing information.
        """
        ended = time.time()
        started_wait = datetime.datetime.fromtimestamp(self.started).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        raised_date = datetime.datetime.fromtimestamp(ended).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        duration = ended - self.started
        return "Started at {}, raised at {} after {}s.".format(
            started_wait, raised_date, round(duration, 2)
        )


class KThread(threading.Thread):
    """
    A subclass of threading.Thread, with a kill() method.
    """

    def __init__(self, *args, **kwargs):
        threading.Thread.__init__(self, *args, **kwargs)
        self._will_kill = False

    def start(self):
        """Start the thread."""
        self.__run_backup = self.run
        self.run = self.__run  # Force the Thread to install the trace
        threading.Thread.start(self)

    def __run(self):
        """Hacked run function, which installs the trace."""
        sys.settrace(self.globaltrace)
        self.__run_backup()
        self.run = self.__run_backup

    def globaltrace(self, frame, event, arg):
        return self.localtrace if event == "call" else None

    def localtrace(self, frame, event, arg):
        if self._will_kill and event == "line":
            raise SystemExit()

        return self.localtrace

    def kill(self):
        self._will_kill = True


def timeout(
    seconds: int, err_msg: str = "Timeout after {} seconds."
) -> Callable[[Callable], Callable]:
    """
    Decorator for a normal function to limit its execution time.

    :param seconds: Time limit for task execution.
    :type seconds: ``int``
    :param err_msg: Error message on timeout.
    :type err_msg: ``str``
    :return: Decorated function.
    :rtype: ``callable``
    """

    def timeout_decorator(func):
        """The real decorator used for setup, teardown and testcase methods."""

        def _new_func(result, old_func, old_func_args, old_func_kwargs):
            try:
                result.append(old_func(*old_func_args, **old_func_kwargs))
            except Exception:
                result[0] = False
                result.append(traceback.format_exc())

        def wrapper(*args, **kwargs):
            result = [True]
            new_kwargs = {
                "result": result,
                "old_func": func,
                "old_func_args": args,
                "old_func_kwargs": kwargs,
            }
            thd = KThread(target=_new_func, args=(), kwargs=new_kwargs)
            thd.start()
            thd.join(seconds)
            if thd.is_alive():
                thd.kill()
                thd.join()
                raise TimeoutException(err_msg.format(seconds))
            else:
                return result

        return functools.wraps(func)(wrapper)

    return timeout_decorator


def wait(
    predicate: Callable[[], bool],
    timeout: int,
    interval: float = 0.05,
    raise_on_timeout: bool = True,
) -> bool:
    """
    Wait until a predicate evaluates to True.

    :param predicate: Input predicate.
    :type predicate: ``callable``
    :param timeout:  Timeout duration.
    :type timeout: ``int``
    :param interval: Sleep interval for predicate check.
    :type interval: ``float``
    :param raise_on_timeout: Raise exception if hits timeout, defaults to True.
    :type raise_on_timeout: ``bool``
    :return: Predicate result.
    :rtype: ``bool``
    """
    start_time = time.time()
    end_time = start_time + timeout
    while True:
        res = predicate()
        error_msg = getattr(res, "error_msg", "")
        if res is True:
            return res
        elif time.time() < end_time:
            # no timeout yet
            time.sleep(interval)
        else:
            if raise_on_timeout:
                msg = "Timeout after {} seconds.".format(timeout)
                if error_msg:
                    msg = "{}{}{}".format(msg, os.linesep, error_msg)
                raise TimeoutException(msg)
            else:
                return res


def wait_until_predicate(
    predicate: Callable[[], bool], timeout: int, interval: float = 1.0
):
    """
    Inverting wait() method behavior to raise if predicate() is True
    instead of raising on timeout.

    :param predicate: any callable object
    :type predicate: ``callable``
    :param timeout: timeout in seconds
    :type timeout: ``float``
    :param interval: interval at which to check the predicate in seconds
    :type interval: ``float``

    :raises:
    :exc:`RuntimeError` if the predicate is True.
    """
    try:
        res = wait(predicate, timeout, interval, raise_on_timeout=True)
    except TimeoutException:
        return
    else:
        raise RuntimeError(
            "Early finish of wait(), predicate: {}.".format(res)
        )


def retry_until_timeout(
    exception: Type[Exception],
    item: Callable[..., Any],
    timeout: int,
    args: List[Any] = None,
    kwargs: Mapping[str, Any] = None,
    interval: float = 0.05,
    raise_on_timeout: bool = True,
) -> Any:
    """
    Retry calling an item until timeout duration while ignoring exceptions.

    :param exception: Exception class to catch.
    :type exception: ``type``
    :param item: Function to call.
    :type item: ``callable``
    :param args: Positional args to pass to ``item``
    :type args: ``Optional[Iterable[Any]]``
    :param kwargs: Keyword args to pass to ``item``
    :type kwargs: ``Optional[Dict[str, Any]]``
    :param interval: time to wait between successive call attempts, in seconds.
    :type interval: ``int``
    :param raise_on_timeout: Whether to raise a TimeoutException on timeout,
        defaults to True.
    :return: Result of item.
    :rtype: ``Any``
    """
    timeout_info = TimeoutExceptionInfo()
    end_time = timeout_info.started + timeout
    while True:
        try:
            res = item(*args or tuple(), **kwargs or {})
        except exception as exc:
            if time.time() < end_time:
                # no timeout yet
                time.sleep(interval)
            else:
                if raise_on_timeout:
                    raise TimeoutException(
                        "Timeout waiting for {0}"
                        " to return without {1}. {2}. {3}".format(
                            item.__name__,
                            exception.__name__,
                            timeout_info.msg(),
                            str(exc),
                        )
                    )
                else:
                    return None
        else:
            return res


def utcnow() -> datetime.datetime:
    """Timezone aware UTC now."""
    return datetime.datetime.now(tz=timezone.utc)


def now() -> datetime.datetime:
    """Timezone aware local time."""
    return datetime.datetime.now().astimezone()


@lru_cache(None)
def iana_tz() -> str:
    """IANA TZ identifier"""
    return str(tzlocal.get_localzone())


_Interval = collections.namedtuple("_Interval", "start end")


class Interval(_Interval):
    """Class that represents a block of time."""

    @property
    def elapsed(self):
        """Return duration in seconds."""
        if self.start and self.end:
            return (self.end - self.start).total_seconds()
        return None


class TimerCtxManager:
    """
    Context manager for storing durations.
    Uses tz aware utc timestamps.
    """

    def __init__(self, timer, key):

        self.timer = timer
        self.key = key
        self.start_ts = None

    def __enter__(self):
        self.start_ts = now()

    def __exit__(self, exc_type, exc_value, _):
        if self.key in self.timer:
            self.timer[self.key].append(
                Interval(start=self.start_ts, end=now())
            )
        else:
            self.timer[self.key] = [Interval(start=self.start_ts, end=now())]


class Timer(dict):
    """Dict wrapper with a method for recording durations."""

    def record(self, key):
        """
        Records duration for the given `key`.

        .. code-block:: python

            >>> timer = Timer()
            >>> with timer.record('my-key'):
            >>>  ... custom code ...
            >>>  ... custom code ...
            >>> timer.last(key='my-key').elapsed
            21.5
        """
        return TimerCtxManager(timer=self, key=key)

    def start(self, key):
        """Record the start timestamp for the given key."""
        if key in self:
            self[key].append(Interval(now(), None))
        else:
            self[key] = [Interval(now(), None)]

    def end(self, key):
        """
        Record the end timestamp for the given key.
        """
        if key not in self or self.last(key).end is not None:
            raise KeyError(f"`start` missing for {key}, cannot record end.")

        self[key][-1] = Interval(self[key][-1].start, now())

    def merge(self, timer):
        for key in timer:
            if key in self:
                self[key].extend(timer[key])
            else:
                self[key] = timer[key]

    def first(self, key):
        return self[key][1]

    def last(self, key):
        return self[key][-1]


DURATION_REGEX = re.compile(
    r"((?P<hours>\d+)[H|h])?\s*"
    r"((?P<minutes>\d+)[M|m])?\s*?"
    r"((?P<seconds>\d+)[S|s])?"
)

DURATION_MSG = (
    "Invalid duration pattern: {pattern}."
    " Please use the format <hours>h <minutes>m <seconds>s"
    " (e.g. `2h 30m`, `15m`, `3m 15s`, `10s`) with nonzero values."
)


def parse_duration(duration: str) -> int:
    """
    Parse given duration string and return duration value in seconds.

    :param duration: Duration value in format `<hours>H <minutes>M <seconds>S`
    :type duration: ``str``
    :return: Duration in seconds
    :rtype: ``int``

    """

    def _get_value(match_obj, group_name):
        val = match_obj.group(group_name)
        return int(val) if val is not None else 0

    match = DURATION_REGEX.match(duration)
    err_msg = DURATION_MSG.format(pattern=duration)

    if not match:
        raise ValueError(err_msg)

    hours = _get_value(match, "hours")
    minutes = _get_value(match, "minutes")
    seconds = _get_value(match, "seconds")

    result = (hours * 3600) + (minutes * 60) + seconds

    if result <= 0:
        raise ValueError(err_msg)

    return (hours * 3600) + (minutes * 60) + seconds


def format_duration(duration: int) -> str:
    """
    Format seconds in hours / minutes / seconds in readable format.

    >>> format_duration(3730)
    1 hours 2 minutes 10 seconds

    :param duration: Total duration in seconds
    :type duration: ``number``
    :return: Duration in readable format.
    :rtype: ``str``
    """
    assert duration > 0, "`duration` must be nonzero number."

    hours = duration / 3600
    minutes = duration // 60 % 60
    seconds = duration % 60

    result = []
    if hours >= 1:
        result.append("{} hours".format(hours))
    if minutes >= 1:
        result.append("{} minutes".format(minutes))
    if seconds:
        result.append("{} seconds".format(seconds))

    return " ".join(result)


def exponential_interval(
    initial: float = 0.1,
    multiplier: float = 2,
    maximum: Optional[float] = None,
    minimum: Optional[float] = None,
) -> Generator[float, None, None]:
    """
    Generator that returns exponentially increasing/decreasing values,
    can be used for generating values for `time.sleep` for periodic checks.

    :param initial: Initial value for the sequence.
    :type initial: ``number``
    :param multiplier: Multiplier for generating new values in the sequence.
                    Each new value will be generated by multiplication of
                    the multiplier and the last generated value of the sequence.
    :type multiplier: ``number``
    :param minimum: Optional minimum value for generated numbers.
    :type minimum: ``number``
    :param maximum: Optional maximum value for generated numbers.
    :type maximum: ``number``
    :return: Sequence of values
    :rtype: ``generator`` of ``number``
    """
    val = initial
    while True:
        if minimum is not None and val < minimum:
            yield minimum
        if maximum is not None and val > maximum:
            yield maximum
        else:
            yield val
            val *= multiplier


def get_sleeper(
    interval: PollInterval,
    timeout: float = 10,
    raise_timeout_with_msg: Optional[Union[str, Callable[[], str]]] = None,
    timeout_info: bool = False,
) -> Generator[bool, None, None]:
    """
    Generator that implements sleep steps for replacing
    *while True: do task; time.sleep()* code blocks. Depending on the interval
    argument, it can sleeps with constant interval or start with min_interval
    and then doubles the interval in each iteration up to max_interval.

    It yields True until timeout is reached where it then yields False or
    raises a TimeoutException based on input arguments.

    :param interval: Sleep time between each yield in seconds.
    :type interval: ``float`` or tuple of ``float`` as
                    (min_interval, max_interval)
    :param timeout: Timeout in seconds
    :type timeout: ``float``
    :param raise_timeout_with_msg: Message or Function to be used for raising
                                   an optional TimeoutException.
    :type raise_timeout_with_msg: ``NoneType`` or ``str`` or ``callable``
    :param timeout_info: Include timeout exception timing information in
                         exception message raised.
    :type timeout_info: ``bool``
    """
    start = time.time()
    timeout_info_obj = TimeoutExceptionInfo(start)
    end = start + timeout

    incr_interval = False
    if isinstance(interval, tuple):
        interval, max_interval = interval
        incr_interval = True

    while True:
        yield True
        time.sleep(interval)
        if time.time() > end:
            if raise_timeout_with_msg:
                if callable(raise_timeout_with_msg):
                    msg = raise_timeout_with_msg()
                else:
                    msg = raise_timeout_with_msg
                if timeout_info:
                    msg = "{}. {}".format(msg, timeout_info_obj.msg())
                raise TimeoutException(msg)
            break

        if incr_interval:
            interval = min(interval * 2, max_interval)

    yield False


def with_timer(func: Callable) -> Callable:
    """
    Decorator to add function execution as event to timer
    """

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        with self.timer.record(func.__name__):
            return func(self, *args, **kwargs)

    return wrapper
