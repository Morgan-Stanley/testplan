import pytest

from testplan.common.utils.convert import flatten_dict_comparison


comparisons = [
    # expected = {38: 5, 555: [{600: 'A'}], 54: 2, 851: 4}
    # actual = {38: 4, 54: 2, 20001: "SAMPLE"}
    [
        (38, "f", (0, "int", 5), (0, "int", 4)),
        (555, "f", (1, [(2, [(600, (0, "str", "A"))])]), (0, None, "ABSENT")),
        (54, "p", (0, "int", 2), (0, "int", 2)),
        (851, "f", (0, "int", 4), (0, None, "ABSENT")),
        (20001, "f", (0, None, "ABSENT"), (0, "str", "SAMPLE")),
    ],
]
result_tables = [
    # expansion and extraction of left side from below comparison would
    # produce an placeholder row
    # ((555,), 1, 'ABSENT', 'f', '')
    # which should not be popped together with a right side entry
    # unless the same repeating group is present
    [
        [0, 38, "f", ("int", 5), ("int", 4)],
        [0, 555, "f", "", (None, "ABSENT")],
        [0, "", "f", "", None],
        [1, 600, "f", ("str", "A"), None],
        [0, 54, "p", ("int", 2), ("int", 2)],
        [0, 851, "f", ("int", 4), (None, "ABSENT")],
        [0, 20001, "f", (None, "ABSENT"), ("str", "SAMPLE")],
    ],
]


@pytest.mark.parametrize(
    "comparison, result_table", zip(comparisons, result_tables)
)
def test_flatten_dict_comparison(comparison, result_table):
    expected = flatten_dict_comparison(comparison)
    assert expected == result_table
