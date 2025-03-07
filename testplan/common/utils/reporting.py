"""
This module contains utilities that are mostly used
to make assertion comparison data report friendly.
"""

import re
from collections.abc import Mapping, Iterable

from testplan.common.utils.context import ContextValue

NATIVE_TYPES = (str, int, float, bool, memoryview, bytes, bytearray)


class AbsentType:
    """
    A singleton to represent the lack of a value in a comparison.
    None is not used to avoid the situation where a key may be
    present and it's value is ``None``.
    """

    __instance = None
    descr = "ABSENT"

    def __new__(cls):
        if not isinstance(cls.__instance, cls):
            cls.__instance = object.__new__(cls)
        return cls.__instance

    def __repr__(self):
        return self.descr


Absent = AbsentType()


def callable_name(callable_obj):
    """
    Extract the name of a callable object

    :param callable_obj: Callable object
    :type callable_obj: Any object as long as it is callable

    :return: Either the function name or the name of the class of the callable
    :rtype: ``str``
    """
    from .comparison import Callable

    if isinstance(callable_obj, Callable):
        return str(callable_obj)

    doc = getattr(callable_obj, "__doc__", None)
    if doc:
        return doc.strip()
    return (
        getattr(callable_obj, "__name__", None)
        or callable_obj.__class__.__name__
    )


def fmt(obj):
    """
    Recursively formats an object as plain old data.

    :param obj: The object to format

    :return: The plain old data representation
             of "obj" that can be serialised to JSON
    :rtype: ``object`` or a ``(object, object)`` pair
    """

    def render(obj, key=None):
        """
        Performs rendering to JSON dict
        """
        obj_t = type(obj)

        if obj is Absent:
            ret = (0, None, str(obj))
        elif obj is None:
            ret = (0, None, None)
        elif issubclass(obj_t, NATIVE_TYPES):
            ret = (0, obj_t.__name__, obj)
        elif isinstance(obj, ContextValue):
            ret = (0, "ContextValue", str(obj))
        elif callable(obj):
            ret = (0, "func", callable_name(obj))
        elif issubclass(obj_t, Mapping):
            ret = (
                2,
                [render(value, obj_key) for obj_key, value in obj.items()],
            )
        elif issubclass(obj_t, Iterable):
            ret = (1, [render(value) for value in obj])
        elif issubclass(obj_t, re.Pattern):
            ret = (0, "REGEX", obj.pattern)
        else:
            ret = (0, obj_t.__name__, str(obj))
        if key:
            return key, ret
        return ret

    return render(obj)
