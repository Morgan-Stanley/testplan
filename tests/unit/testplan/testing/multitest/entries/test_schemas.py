from itertools import count

import pytest

from testplan.common.utils.comparison import Expected
from testplan.common.utils.convert import delta_decode_level
from testplan.testing.multitest.entries import assertions, base
from testplan.testing.multitest.entries.schemas import registry


@pytest.mark.parametrize(
    "entry",
    [
        assertions.DictMatch({"a": 1}, {"b": 1}),
        assertions.Equal(2, 3),
        base.CodeLog("[ ! -e $file ] && echo done", "bash"),
    ],
    ids=count(0),
)
def test_entry_attr_strip(entry):
    data = registry.serialize(entry)
    assert all(
        x not in data
        for x in (
            "category",
            "flag",
            "file_path",
            "line_no",
            "code_context",
        )
    )
    assert (
        "timestamp" in data
        and "utc_time" not in data
        and "machine_time" not in data
    )


@pytest.mark.parametrize(
    "entry",
    [
        base.BaseEntry("desc", "NON_DEFAULT"),
        base.BaseEntry("desc", None, "NON_DEFAULT"),
    ],
    ids=count(0),
)
def test_entry_attr_strip_2(entry):
    data = registry.serialize(entry)
    assert "category" in data or "flag" in data


@pytest.mark.parametrize(
    "value",
    [{"a": 1, "b": 2}, {"a": 1, "b": [2, [3, [4]]]}],
    ids=count(0),
)
def test_dictlog_delta_encode(value):
    entry = base.DictLog(value)
    data = registry.serialize(entry)
    assert all(
        isinstance(r, int) or len(r) == 2 for r in data["flattened_dict"]
    )
    assert all(len(r) == 3 for r in delta_decode_level(data["flattened_dict"]))


@pytest.mark.parametrize(
    "value, expected",
    [
        (
            {"a": 1, "b": 2},
            {"a": 1, "b": 2},
        ),
        (
            {"a": 1, "b": 2, "c": 3},
            {"a": 1, "b": [2]},
        ),
        (
            {"a": 1, "b": [2, [3, [4]]]},
            {"a": 1},
        ),
    ],
    ids=count(0),
)
def test_dictmatch_delta_encode(value, expected):
    entry = assertions.DictMatch(
        value=value,
        expected=expected,
    )
    data = registry.serialize(entry)
    assert all(isinstance(r, int) or len(r) == 4 for r in data["comparison"])
    assert all(len(r) == 5 for r in delta_decode_level(data["comparison"]))


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "values": [{"a": 1}, {"a": 1, "b": 2}, {"a": 1, "b": 2, "c": 3}],
            "comparisons": [Expected({"a": int, "b": 2})] * 2
            + [Expected({"a": 1, "c": 3})],
            "key_weightings": {"b": 200},
        }
    ],
    ids=count(0),
)
def test_dictmatchall_delta_encode(kwargs):
    entry = assertions.DictMatchAll(**kwargs)
    data = registry.serialize(entry)
    comparisons = map(lambda x: x["comparison"], data["matches"])
    assert all(
        isinstance(r, int) or len(r) == 4 for c in comparisons for r in c
    )
    assert all(len(r) == 5 for c in comparisons for r in delta_decode_level(c))
