"""Conversion utilities."""
import itertools
from typing import Union, Tuple, Iterable, Callable, List, Sequence

from .comparison import is_match_res
from .reporting import Absent


RecursiveListTuple = List[Union[Tuple, Tuple["RecursiveListTuple"]]]


def make_tuple(
    value: object,
    convert_none: bool = False,
) -> Union[Tuple, object]:
    """
    Converts a value into a tuple.

    :param value: value to make the tuple out of
    :param convert_none: whether to convert None
    :return: the value or the value converted to a tuple
    """
    if isinstance(value, list):
        return tuple(value)
    if not isinstance(value, tuple) and (convert_none or value is not None):
        return (value,)
    return value


def sort_and_group(iterable: Iterable, key: Callable) -> List[Tuple]:
    """
    Sorts an iterable and groups the items by the given key function.

    :param iterable: iterable of items
    :param key: key function to sort by
    :return: groups of items sorted by key
    """
    groups = [
        (k, list(g))
        for k, g in itertools.groupby(sorted(iterable, key=key), key=key)
    ]
    return groups


def nested_groups(
    iterable: Iterable,
    key_funcs: Sequence[Callable],
) -> RecursiveListTuple:
    """
    Creates nested groups from the given ``iterable`` using ``key_funcs``

    :param iterable: iterable of items
    :param key_funcs: key functions to sort by, applied in a waterfall
    :return: recursively nested groups of items sorted by key functions
    """
    first, rest = key_funcs[0], key_funcs[1:]
    grouping = sort_and_group(iterable, first)
    if rest:
        return [(key, nested_groups(group, rest)) for key, group in grouping]
    else:
        return grouping


# Below function was designed to be used when defining types in the
# configuration schema. For example make_iterables([str, ContextVale])
# will return  [[str], (str,), [ContextValue], (ContextValue,)].
def make_iterables(values: Iterable) -> List[Union[List, Tuple]]:
    """
    Create a list of lists and tuples for each of the values.

    :param values: an iterable of values
    :return: list containing one list and tuple for each value
    """
    iterables = []
    for value in values:
        iterables.append([value])
        iterables.append((value,))
    return iterables


def full_status(status: str) -> str:
    """
    Human readable status label.

    :param status: status label
    :return: human-readable status label
    """
    if status == "p":
        return "Passed"
    elif status == "f":
        return "Failed"
    elif status == "i":
        return "Ignored"
    return ""


def expand_match_res(
    rows: List[Tuple],
    level: int = 0,
    ignore_key: bool = False,
    key_path: List = None,
):
    """
    Recursively expands and yields all rows of items to display.

    :param rows: comparison results
    :param level: recursive parameter for level of nesting
    :param ignore_key: recursive parameter for ignoring a key
    :param key_path: recursive parameter to build the sequence of keys
    :return: rows used in building comparison result table
    """
    if key_path is None:
        key_path = []

    for row in rows:
        # While comparing dict value (list type), dict key is ignored, thus
        # a special object `Absent` is used as key, which means no key here.
        key = row[0] if ignore_key is False else Absent
        if key is not Absent:  # `None` or empty string can also be used as key
            key_path.append(key)

        match = row[1]
        val = row[2]

        if isinstance(val, tuple):
            if val[0] == 0:  # value
                yield (tuple(key_path), level, key, match, (val[1], val[2]))
            elif is_match_res(val[0]):  # ``_rec_compare``d container
                yield (tuple(key_path), level, key, match, "")
                yield from expand_match_res(
                    val[1],
                    level=level + 1,
                    ignore_key=True if val[0] == 11 else False,
                    key_path=key_path,
                )
            elif val[0] in (1, 2):  # ``fmt``ed container
                yield (tuple(key_path), level, key, match, "")
                yield from expand_fmt_res(
                    val[1],
                    level=level + 1,
                    ignore_key=True if val[0] == 1 else False,
                    key_path=key_path,
                    match=match,
                )
            else:
                raise ValueError(f"{val[0]}")
        else:
            raise TypeError

        if key is not Absent:
            key_path.pop()


def expand_fmt_res(
    rows: List[Tuple],
    level: int,
    ignore_key: bool,
    key_path: List[str],
    match: str,
):

    for row in rows:
        key = row[0] if ignore_key is False else Absent
        if key is not Absent:  # `None` or empty string can also be used as key
            key_path.append(key)

        val = row if ignore_key else row[1]

        if not isinstance(val, tuple):
            raise TypeError

        if val[0] == 0:  # value
            yield (tuple(key_path), level, key, match, (val[1], val[2]))
        elif val[0] in (1, 2):  # container
            yield (tuple(key_path), level, key, match, "")
            yield from expand_fmt_res(
                val[1],
                level=level + 1,
                ignore_key=True if val[0] == 1 else False,
                key_path=key_path,
                match=match,
            )
        else:
            raise ValueError

        if key is not Absent:
            key_path.pop()


# TODO: position parameter is misleading and it allows extracting
#             the key or match information as value
#             "left" or "right" choices would be enough for clarity and
#             would fail earlier upon any change to structure
def extract_values(comparison: List[Tuple], position: int) -> List:
    """
    Extracts one-side of a comparison result based on value position.

    :param comparison: list of key, match, and value pair quadruples
    :param position: index pointing to particular value
    :return: list of key, match, and value triples
    """
    result = []
    for item in comparison:
        result.append((item[0], item[1], item[position]))
    return result


def flatten_formatted_object(formatted_obj):
    """
    Flatten the formatted object which is the result of function
    ``testplan.common.utils.reporting.fmt``.

    :param formatted_obj: The formatted object

    :return: List representation of flattened object
    :rtype: ``list``
    """

    def flatten(obj, level=0, ignore_key=True):
        if ignore_key:
            key = ""
        else:
            key, obj = obj[0], obj[1]

        if isinstance(obj, tuple):
            if obj[0] == 0:
                yield (level, key, (obj[1], obj[2]))
            elif obj[0] in (1, 2):
                yield (level, key, "")
                for row in obj[1]:
                    yield from flatten(
                        row, level=level + 1, ignore_key=(obj[0] == 1)
                    )
            else:
                raise ValueError("Invalid data found in formatted object")
        else:
            raise ValueError("Invalid data found in formatted object")

    if formatted_obj[0] == 0:
        return list(flatten(formatted_obj))
    else:
        result_table = []
        for level, key, val in flatten(formatted_obj, level=-1):
            result_table.append([level, key, val])

        if formatted_obj[0] == 2:
            for idx in range(1, len(result_table)):
                if not result_table[idx][1]:  # no key
                    result_table[idx][0] -= 1

        while True:
            level_decreased = False
            prev_level = 0
            for idx in range(1, len(result_table)):
                level = result_table[idx][0]
                if level > prev_level + 1:
                    for inner_idx in range(idx, len(result_table)):
                        if result_table[inner_idx][0] > prev_level:
                            level_decreased = True
                            result_table[inner_idx][0] -= 1
                        else:
                            break
                prev_level = level
            if level_decreased is False:
                break

        return result_table[1:]


def flatten_dict_comparison(comparison: List[Tuple]) -> List[List]:
    """
    Flatten the comparison object from dictionary match into a tabular format.

    :param comparison: list of comparison results
    :return: result table to be used in display
    """
    result_table = []  # level, key, left, right, result

    left = list(expand_match_res(extract_values(comparison, 2)))
    right = list(expand_match_res(extract_values(comparison, 3)))

    while left or right:
        lpart, rpart = None, None
        if left and right:
            # NOTE: if the left keypath is longer we entered a nested structure
            #           on one side only
            #           if the key is Absent only on left side, then we just insert an
            #           empty row for visual separation
            if (
                len(left[0][0]) > len(right[0][0])
                or left[0][2] is Absent
                and left[0][2] != right[0][2]
            ):
                lpart = left.pop(0)
            # NOTE: same as above but from right-hand side perspective
            elif (
                len(left[0][0]) < len(right[0][0])
                or right[0][2] is Absent
                and left[0][2] != right[0][2]
            ):
                rpart = right.pop(0)
            else:
                lpart, rpart = left.pop(0), right.pop(0)
        # NOTE: if any of the sides is exhausted we proceed with the other
        elif left:
            lpart = left.pop(0)
        elif right:
            rpart = right.pop(0)

        level = lpart[1] if lpart else rpart[1]
        key = lpart[2] if lpart else rpart[2]
        if key is Absent:
            level -= 1
            # key = '(group)'

        status = full_status(lpart[3] if lpart else rpart[3])
        lval = lpart[4] if lpart else None
        rval = rpart[4] if rpart else None
        result_table.append(
            [level, "" if key is Absent else key, status, lval, rval]
        )

    while True:
        level_decreased = False
        prev_level = 0
        for idx in range(len(result_table)):
            level = result_table[idx][0]
            if level > prev_level + 1:
                for inner_idx in range(idx, len(result_table)):
                    if result_table[inner_idx][0] > prev_level:
                        level_decreased = True
                        result_table[inner_idx][0] -= 1
                    else:
                        break
            prev_level = level
        if level_decreased is False:
            break

    return result_table
