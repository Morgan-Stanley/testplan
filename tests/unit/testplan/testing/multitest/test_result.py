"""
Unit tests for the testplan.testing.multitest.result module.
"""

import collections
import copy
import hashlib
import inspect
import os
import re
import tempfile
from unittest import mock

import matplotlib
import matplotlib.pyplot as plot
import pytest

from testplan.common.report import Status
from testplan.common.utils import callable, comparison, match
from testplan.common.utils import path as path_utils
from testplan.common.utils import testing
from testplan.testing import result as result_mod
from testplan.testing.multitest import MultiTest
from testplan.testing.multitest.suite import testcase, testsuite

matplotlib.use("agg")


def get_code_context(obj, rel_pos):
    """
    Extracts code context based on object and relative position.
    """
    lines, start = inspect.getsourcelines(obj)
    return (start + rel_pos, lines[rel_pos].strip())


def helper(result, description=None):
    result.less(1, 2, description=description)


@result_mod.report_target
def intermediary(result, description=None):
    helper(result, description=description)


def test_group_no_marking():
    """
    Tests, at result object level, when code context is not enabled.
    """
    result = result_mod.Result()
    result.equal(1, 1)
    result_entry = result.entries.pop()
    assert result_entry.line_no == None
    assert result_entry.code_context == None


def test_group_marking():
    """
    Tests, at result object level, if marking works as expected.
    """
    result = result_mod.Result(_collect_code_context=True)
    result.equal(1, 1)
    result_entry = result.entries.pop()
    code_context = get_code_context(test_group_marking, 5)
    assert result_entry.line_no == code_context[0]
    assert result_entry.code_context == code_context[1]

    helper(result)
    result_entry = result.entries.pop()
    code_context = get_code_context(helper, 1)
    assert result_entry.line_no == code_context[0]
    assert result_entry.code_context == code_context[1]

    intermediary(result)
    result_entry = result.entries.pop()
    code_context = get_code_context(intermediary, 2)
    assert result_entry.line_no == code_context[0]
    assert result_entry.code_context == code_context[1]


@testsuite
class GroupMarking:
    @testcase
    def case(self, env, result):
        result.equal(1, 1, description="A")
        helper(result, description="B")
        intermediary(result, description="C")


@testsuite
class ParametrizedGroupMarking:
    @testcase(parameters=(0, 1))
    def case(self, env, result, val):
        result.equal(val, 1, description=f"A{val}")
        helper(result, description=f"B{val}")
        intermediary(result, description=f"C{val}")


def pre_fn(self, env, result):
    result.equal(1, 1, description="Pre")


def post_fn(self, env, result):
    result.equal(1, 1, description="Post")


@testsuite
class PrePostTestcaseMarking:
    @callable.pre(pre_fn)
    @callable.post(post_fn)
    @testcase
    def case(self, env, result):
        result.equal(1, 1, description="Case")


@pytest.mark.parametrize("flag", [True, False])
def test_group_marking_multitest(mockplan, flag):
    """
    Tests, at MultiTest-level, if marking works as expected.
    """
    test = MultiTest(
        name="GroupMarking",
        suites=[GroupMarking()],
        testcase_report_target=flag,
    )
    test.cfg.parent = mockplan.cfg
    test.cfg.collect_code_context = True
    test.run()
    assertions = {
        entry["description"]: entry
        for entry in test.report.flatten()
        if isinstance(entry, dict) and entry["meta_type"] == "assertion"
    }
    expected = {
        "A": get_code_context(GroupMarking.case, 2),
        "B": get_code_context(GroupMarking.case, 3)
        if flag
        else get_code_context(helper, 1),
        "C": get_code_context(intermediary, 2),
    }
    for desc, code_context in expected.items():
        assert assertions[desc]["line_no"] == code_context[0]
        assert assertions[desc]["code_context"] == code_context[1]


@pytest.mark.parametrize("flag", [True, False])
def test_parametrized_group_marking_multitest(mockplan, flag):
    """
    Tests, at MultiTest-level, if marking works as expected
    for parametrized testcases.
    """
    test = MultiTest(
        name="ParametrizedGroupMarking",
        suites=[ParametrizedGroupMarking()],
        testcase_report_target=flag,
    )
    test.cfg.parent = mockplan.cfg
    test.cfg.collect_code_context = True
    test.run()
    assertions = {
        entry["description"]: entry
        for entry in test.report.flatten()
        if isinstance(entry, dict) and entry["meta_type"] == "assertion"
    }
    expected = {
        "A0": get_code_context(ParametrizedGroupMarking.case, 2),
        "B0": get_code_context(ParametrizedGroupMarking.case, 3)
        if flag
        else get_code_context(helper, 1),
        "C0": get_code_context(intermediary, 2),
    }
    expected.update(
        {
            "A1": expected["A0"],
            "B1": expected["B0"],
            "C1": expected["C0"],
        }
    )
    for desc, code_context in expected.items():
        assert assertions[desc]["line_no"] == code_context[0]
        assert assertions[desc]["code_context"] == code_context[1]


@pytest.mark.parametrize("flag", [True, False])
def test_decorated_testcase_marking_multitest(mockplan, flag):
    """
    Tests, at MultiTest-level, if marking works as expected
    for testcase which is decorated by other functions.
    """
    test = MultiTest(
        name="PrePostTestcaseMarking",
        suites=[PrePostTestcaseMarking()],
        testcase_report_target=flag,
    )
    test.cfg.parent = mockplan.cfg
    test.cfg.collect_code_context = True
    test.run()
    assertions = {
        entry["description"]: entry
        for entry in test.report.flatten()
        if isinstance(entry, dict) and entry["meta_type"] == "assertion"
    }
    expected = {
        "Pre": get_code_context(pre_fn, 1),
        "Case": get_code_context(PrePostTestcaseMarking.case, 4),
        "Post": get_code_context(post_fn, 1),
    }
    for desc, code_context in expected.items():
        assert assertions[desc]["line_no"] == code_context[0]
        assert assertions[desc]["code_context"] == code_context[1]


@testsuite
class AssertionOrder:
    @testcase
    def case(self, env, result):
        summary = result.subresult()
        first = result.subresult()
        second = result.subresult()

        second.true(True, "AssertionSecond")

        result.true(True, "AssertionMain1")
        result.true(True, "AssertionMain2")

        first.true(True, "AssertionFirst1")
        first.true(True, "AssertionFirst2")

        summary.append(first)
        result.true(first.passed, "Report passed so far.")
        if first.passed:
            summary.append(second)

        result.prepend(summary)


def test_assertion_order(mockplan):
    """Verify ordered assertion entries in test report."""
    mtest = MultiTest(name="AssertionsOrder", suites=[AssertionOrder()])
    mtest.cfg.parent = mockplan.cfg
    mtest.run()

    expected = [
        "AssertionFirst1",
        "AssertionFirst2",
        "AssertionSecond",
        "AssertionMain1",
        "AssertionMain2",
        "Report passed so far.",
    ]
    # pylint: disable=invalid-sequence-index
    assertions = [
        entry
        for entry in mtest.report.flatten()
        if isinstance(entry, dict) and entry["meta_type"] == "assertion"
    ]

    for idx, desc in enumerate(expected):
        assert desc == assertions[idx]["description"]


@testsuite
class AssertionFail:
    @testcase
    def fail_with_description(self, env, result):
        result.fail(message="Invalid outcome", description="message not found")

    @testcase
    def fail_without_description(self, env, result):
        # Same message will be used for description
        result.fail(message="userid not found")


def test_assertion_fail(mockplan):
    """Verify ordered assertion entries in test report."""
    mtest = MultiTest(name="AssertionFail", suites=[AssertionFail()])
    mtest.cfg.parent = mockplan.cfg
    mtest.run()

    expected = [
        {
            "message": "Invalid outcome",
            "description": "message not found",
        },
        {
            "message": "userid not found",
            "description": "userid not found",
        },
    ]

    assertions = [
        entry
        for entry in mtest.report.flatten()
        if isinstance(entry, dict) and entry["meta_type"] == "assertion"
    ]

    for idx, item in enumerate(expected):
        assert item["description"] == assertions[idx]["description"]
        assert item["message"] == assertions[idx]["message"]


@testsuite
class AssertionExtraAttribute:
    @testcase
    def case(self, env, result):
        first = result.subresult()
        second = result.subresult()

        second.false(False, custom_style=None)
        second.false(False, custom_style={"border": 1, "margin": 2})

        first.true(True, custom_style={"color": "red", "bgcolor": "white"})
        first.true(True, custom_style={123: "foo", 456: "bar", 789: "baz"})

        result.log("Report passed so far.", custom_style={})
        result.prepend(first)
        result.append(second)


def test_assertion_extra_attribute(mockplan):
    """Test that required extra attribute correctly recorded in report."""
    mtest = MultiTest(
        name="AssertionExtraAttribute", suites=[AssertionExtraAttribute()]
    )
    mtest.cfg.parent = mockplan.cfg
    mtest.run()

    expected = [
        {"color": "red", "bgcolor": "white"},
        {"123": "foo", "456": "bar", "789": "baz"},
        {},
        {"border": "1", "margin": "2"},
    ]
    assertions = [
        entry
        for entry in mtest.report.flatten()
        if isinstance(entry, dict) and "custom_style" in entry
    ]

    for idx, custom_style in enumerate(expected):
        assert custom_style == assertions[idx]["custom_style"]


@testsuite
class SkipSuite:
    @testcase
    def skip_me(self, env, result):
        result.true(True)
        result.skip("call skip assertion")
        result.fail("skip me")

    @testcase(parameters=tuple(range(10)))
    def condition_skip(self, env, result, num):
        if num % 2 == 0:
            result.skip("This testcase is marked as skipped")
            result.fail("skip me")
        else:
            result.log("This is a log message")


def test_assertion_skip(mockplan):
    mtest = MultiTest(name="SkipAssertion", suites=[SkipSuite()])
    mtest.cfg.parent = mockplan.cfg
    mtest.run()

    skip_multitest = mtest.report.flatten()[0]
    skip_suite = skip_multitest.entries[0]
    skip_me_case = skip_suite.entries[0]
    assert skip_me_case.status == Status.SKIPPED
    assert skip_me_case.failed is False
    assert len(skip_me_case.entries) == 2

    for index, condition_skip_case in enumerate(skip_suite.entries[1]):
        if index % 2 == 0:
            assert condition_skip_case.status == Status.SKIPPED
        else:
            assert condition_skip_case.status == Status.PASSED
        assert len(condition_skip_case.entries) == 1


@pytest.fixture
def dict_ns():
    """Dict namespace with a mocked out result object."""
    mock_result = mock.MagicMock()
    mock_result.entries = collections.deque()
    return result_mod.DictNamespace(mock_result)


@pytest.fixture
def fix_ns():
    """FIX namespace with a mocked out result object."""
    mock_result = mock.MagicMock()
    mock_result.entries = collections.deque()
    return result_mod.FixNamespace(mock_result)


@pytest.fixture
def logfile_ns():
    mock_result = mock.MagicMock()
    mock_result.entries = collections.deque()
    return result_mod.LogfileNamespace(mock_result)


@pytest.fixture
def logfile_w_matcher():
    f = tempfile.NamedTemporaryFile(delete=False)
    f.close()

    def logline(self, s):
        self.write(s + os.linesep)

    try:
        fp = open(f.name, "r+")
        fp.logline = lambda x: logline(fp, x)
        yield fp, match.LogMatcher(f.name)
    finally:
        fp.close()
        os.unlink(f.name)


class TestDictNamespace:
    """Unit testcases for the result.DictNamespace class."""

    def test_basic_match(self, dict_ns):
        """
        Test the match method against identical expected and actual dicts.
        """
        expected = {"key": 123}
        actual = expected.copy()

        assert dict_ns.match(
            actual,
            expected,
            description="Basic dictmatch of identical dicts passes",
        )

        assert dict_ns.match(
            actual,
            expected,
            description="Force type-check of values",
            value_cmp_func=comparison.COMPARE_FUNCTIONS["check_types"],
        )

        assert dict_ns.match(
            actual,
            expected,
            description="Convert values to strings before comparing",
            value_cmp_func=comparison.COMPARE_FUNCTIONS["stringify"],
        )

    def test_duck_match(self, dict_ns):
        """
        Test the match method by seting different types that can be compared.
        Due to duck-typing, ints and floats can be equal if they refer to the
        same numeric value - in this case, 123 == 123.0. However if
        type-checking is forced by use of the check_types comparison method
        the assertion will fail.
        """
        expected = {"key": 123}
        actual = {"key": 123.0}

        assert dict_ns.match(
            actual,
            expected,
            description="Dictmatch passes since the numeric values are equal.",
        )

        assert not dict_ns.match(
            actual,
            expected,
            description="Dictmatch fails when type comparison is forced.",
            value_cmp_func=comparison.COMPARE_FUNCTIONS["check_types"],
        )

        assert not dict_ns.match(
            actual,
            expected,
            description="Dictmatch with string conversion fails due to "
            "different string representations of int/float.",
            value_cmp_func=comparison.COMPARE_FUNCTIONS["stringify"],
        )

    def test_fail_match(self, dict_ns):
        """
        Test the match method for types that do not compare equal - in this
        case, 123 should not match "123".
        """
        expected = {"key": 123}
        actual = {"key": "123"}

        assert not dict_ns.match(
            actual, expected, description='Dictmatch fails because 123 != "123'
        )

        assert not dict_ns.match(
            actual,
            expected,
            description="Dictmatch fails due to type mismatch",
            value_cmp_func=comparison.COMPARE_FUNCTIONS["check_types"],
        )

        assert dict_ns.match(
            actual,
            expected,
            description="Dictmatch passes when values are converted to strings",
            value_cmp_func=comparison.COMPARE_FUNCTIONS["stringify"],
        )

    def test_custom_match(self, dict_ns):
        """Test a dict match using a user-defined comparison function."""
        expected = {"key": 174.24}
        actual = {"key": 174.87}

        tolerance = 1.0

        def cmp_with_tolerance(lhs, rhs):
            """Check that both values are within a given tolerance range."""
            return abs(lhs - rhs) < tolerance

        assert not dict_ns.match(
            actual, expected, description="Values are not exactly equal"
        )

        assert dict_ns.match(
            actual,
            expected,
            description="Values are equal within tolerance",
            value_cmp_func=cmp_with_tolerance,
        )

    def test_report_modes(self, dict_ns):
        """Test controlling report modes for a dict match."""
        expected = {"key{}".format(i): i for i in range(10)}
        actual = expected.copy()
        expected["wrong"] = "expected"
        actual["wrong"] = "actual"

        assert not dict_ns.match(
            actual, expected, description="Keep all comparisons by default"
        )
        assert len(dict_ns.result.entries) == 1
        dict_assert = dict_ns.result.entries.popleft()
        assert len(dict_assert.comparison) == 11

        assert dict_ns.match(
            actual,
            expected,
            description="Keep ignored comparisons",
            include_keys=["key{}".format(i) for i in range(3)],
        )

        assert len(dict_ns.result.entries) == 1
        dict_assert = dict_ns.result.entries.popleft()
        assert len(dict_assert.comparison) == 11

        assert dict_ns.match(
            actual,
            expected,
            description="Discard ignored comparisons",
            include_keys=["key{}".format(i) for i in range(3)],
            report_mode=comparison.ReportOptions.NO_IGNORED,
        )

        assert len(dict_ns.result.entries) == 1
        dict_assert = dict_ns.result.entries.popleft()
        assert len(dict_assert.comparison) == 3

        assert not dict_ns.match(
            actual,
            expected,
            report_mode=comparison.ReportOptions.FAILS_ONLY,
            description="Discard passing comparisons",
        )
        assert len(dict_ns.result.entries) == 1
        dict_assert = dict_ns.result.entries.popleft()
        assert len(dict_assert.comparison) == 1

    def test_flattened_comparison_result(self, dict_ns):
        """Test the comparison result in flattened entries."""
        expected = {
            "foo": 1,
            "bar": lambda val: val >= 1,
            "baz": [
                {
                    "apple": 3,
                    "pear": 4,
                    "bat": [
                        {"wine": "gin", "tea": re.compile(r"[a-z]{5}")},
                        {"wine": "vodka", "tea": "green"},
                    ],
                }
            ],
        }
        actual = copy.deepcopy(expected)
        actual["bar"] = 2
        actual["baz"][0]["pear"] = 5
        actual["baz"][0]["bat"][0]["wine"] = "lime"
        actual["baz"][0]["bat"][0]["tea"] = "oolong"
        actual["baz"][0]["bat"][1]["wine"] = "brandy"
        actual["baz"][0]["bat"][1]["tea"] = "black"
        assert dict_ns.match(
            actual,
            expected,
            description="complex dictionary comparison",
            exclude_keys=["pear", "wine", "tea"],
        )
        assert len(dict_ns.result.entries) == 1

        # Comparison result is a list of list items in below format:
        # [indent, key, result, (act_type, act_value), (exp_type, exp_value)]
        comp_result = dict_ns.result.entries[0].comparison
        bar = [item for item in comp_result if item[1] == "bar"][0]
        assert bar[0] == 0 and bar[4][0] == "func"
        baz = [item for item in comp_result if item[1] == "baz"][0]
        assert baz[0] == 0 and baz[2][0].lower() == comparison.Match.PASS
        bat = [item for item in comp_result if item[1] == "bat"][0]
        assert bat[0] == 1 and bat[2][0].lower() == comparison.Match.IGNORED
        tea_1, tea_2 = [item for item in comp_result if item[1] == "tea"]
        assert (
            tea_1[0] == tea_2[0] == 2
            and tea_1[2][0].lower() == comparison.Match.IGNORED
            and tea_2[2][0].lower() == comparison.Match.IGNORED
            and tea_1[4][0] == "REGEX"
        )


class TestFIXNamespace:
    """Unit testcases for the result.FixNamespace class."""

    def test_untyped_fixmatch(self, fix_ns):
        """Test FIX matches between untyped FIX messages."""
        expected = testing.FixMessage(
            ((35, "D"), (38, "1000000"), (44, "125.83"))
        )
        actual = expected.copy()

        assert fix_ns.match(actual, expected, description="Basic FIX match")

    def test_typed_fixmatch(self, fix_ns):
        """Test FIX matches between typed FIX messages."""
        expected = testing.FixMessage(
            ((35, "D"), (38, 1000000), (44, 125.83)), typed_values=True
        )
        actual = expected.copy()

        assert fix_ns.match(actual, expected, description="Basic FIX match")

        # Now change the type of the actual 38 key's value to str. The assert
        # should fail since we are performing a typed match.
        actual[38] = "1000000"
        assert not fix_ns.match(
            actual, expected, description="Failing str/int comparison"
        )

        # Change the type to a float. The match should still fail because of
        # the type difference, despite the numeric values being equal.
        actual[38] = 1000000.0
        assert not fix_ns.match(
            actual, expected, description="Failing float/int comparison"
        )

    def test_mixed_fixmatch(self, fix_ns):
        """Test FIX matches between typed and untyped FIX messages."""
        expected = testing.FixMessage(
            ((35, "D"), (38, "1000000"), (44, "125.83")), typed_values=False
        )
        actual = testing.FixMessage(
            ((35, "D"), (38, "1000000"), (44, 125.83)), typed_values=True
        )

        assert fix_ns.match(actual, expected, description="Mixed FIX match")

    def test_report_modes(self, fix_ns):
        """Test controlling report modes for FIX match."""
        expected = testing.FixMessage((i, (25 * i) - 4) for i in range(10))
        actual = expected.copy()
        expected["wrong"] = "expected"
        actual["wrong"] = "actual"

        assert not fix_ns.match(
            actual, expected, description="Keep all comparisons by default"
        )
        assert len(fix_ns.result.entries) == 1
        dict_assert = fix_ns.result.entries.popleft()
        assert len(dict_assert.comparison) == 11

        assert fix_ns.match(
            actual,
            expected,
            description="Keep ignored comparisons",
            include_tags=[0, 1, 2],
        )

        assert len(fix_ns.result.entries) == 1
        dict_assert = fix_ns.result.entries.popleft()
        assert len(dict_assert.comparison) == 11

        assert fix_ns.match(
            actual,
            expected,
            description="Discard ignored comparisons",
            include_tags=[0, 1, 2],
            report_mode=comparison.ReportOptions.NO_IGNORED,
        )

        assert len(fix_ns.result.entries) == 1
        dict_assert = fix_ns.result.entries.popleft()
        assert len(dict_assert.comparison) == 3

        assert not fix_ns.match(
            actual,
            expected,
            report_mode=comparison.ReportOptions.FAILS_ONLY,
            description="Discard passing comparisons",
        )
        assert len(fix_ns.result.entries) == 1
        dict_assert = fix_ns.result.entries.popleft()
        assert len(dict_assert.comparison) == 1

    def test_flattened_comparison_result(self, fix_ns):
        """Test the comparison result in flattened entries."""
        expected = {
            8: "FIX42",
            9: re.compile(r"[A-Za-z]{2}"),
            555: [
                {
                    600: "A",
                    601: "B",
                    687: [
                        {688: "opq", 689: "rst"},
                        {688: "uvw", 689: "xyz"},
                    ],
                }
            ],
        }
        actual = expected.copy()
        actual[9] = "AE"
        actual[555] = [{600: "A", 601: "C", 700: "D"}]
        assert not fix_ns.match(
            actual,
            expected,
            description="complex fix message comparison",
            include_tags=[9, 555, 600, 687],
        )
        assert len(fix_ns.result.entries) == 1

        # Comparison result is a list of list items in below format:
        # [indent, key, result, (act_type, act_value), (exp_type, exp_value)]
        comp_result = fix_ns.result.entries[0].comparison
        _8 = [item for item in comp_result if item[1] == 8][0]
        assert _8[0] == 0 and _8[2][0].lower() == comparison.Match.IGNORED
        _9 = [item for item in comp_result if item[1] == 9][0]
        assert (
            _9[0] == 0
            and _9[2][0].lower() == comparison.Match.PASS
            and _9[4][0] == "REGEX"
        )
        _555 = [item for item in comp_result if item[1] == 555][0]
        assert _555[0] == 0 and _555[2][0].lower() == comparison.Match.FAIL
        _600 = [item for item in comp_result if item[1] == 600][0]
        assert _600[0] == 1 and _600[2][0].lower() == comparison.Match.PASS
        _601 = [item for item in comp_result if item[1] == 601][0]
        assert _601[0] == 1 and _601[2][0].lower() == comparison.Match.IGNORED
        _687 = [item for item in comp_result if item[1] == 687][0]
        assert (
            _687[0] == 1
            and _687[2][0].lower() == comparison.Match.FAIL
            and _687[3] == (None, "ABSENT")  # key not found in actual data
        )
        _688_1, _688_2 = [item for item in comp_result if item[1] == 688]
        assert _688_1[0] == 2 and _688_1[2][0].lower() == comparison.Match.FAIL
        assert _688_2[0] == 2 and _688_2[2][0].lower() == comparison.Match.FAIL
        _689_1, _689_2 = [item for item in comp_result if item[1] == 689]
        assert _689_1[0] == 2 and _689_1[2][0].lower() == comparison.Match.FAIL
        assert _689_2[0] == 2 and _689_2[2][0].lower() == comparison.Match.FAIL
        _700 = [item for item in comp_result if item[1] == 700][0]
        assert (
            _700[0] == 1
            and _700[2][0].lower() == comparison.Match.IGNORED
            and _700[4] == (None, "ABSENT")  # key not found in expected data
        )

    def test_subset_of_tags_with_include_tags_true(self, fix_ns):
        """
        Test the comparison result when the expected FIX message with repeating groups is the subset of the actual
        while include_tags set to True.
        """

        expected = {
            35: "D",
            55: 2,
            555: [
                {
                    601: "A",
                    683: [
                        {689: "a"},
                        {689: "b"},
                    ],
                },
                {
                    601: "B",
                    683: [
                        {688: "c", 689: "c"},
                        {688: "d"},
                    ],
                },
            ],
        }

        actual = {
            35: "D",
            22: 5,
            55: 2,
            38: 5,
            555: [
                {
                    600: "A",
                    601: "A",
                    683: [
                        {688: "a", 689: "a"},
                        {688: "b", 689: "b"},
                    ],
                },
                {
                    600: "B",
                    601: "B",
                    55: 4,
                    683: [
                        {688: "c", 689: "c"},
                        {688: "d", 689: "d"},
                    ],
                },
            ],
        }

        assert fix_ns.match(
            actual=actual,
            expected=expected,
            description="complex fix message comparison",
            include_only_expected=True,
        )
        assert len(fix_ns.result.entries) == 1

        # Comparison result is a list of list items in below format:
        # [indent, key, result, (act_type, act_value), (exp_type, exp_value)]

        comp_result = fix_ns.result.entries[0].comparison

        _35 = [item for item in comp_result if item[1] == 35][0]
        assert _35[0] == 0 and _35[2][0].lower() == comparison.Match.PASS
        _22 = [item for item in comp_result if item[1] == 22][0]
        assert (
            _22[0] == 0
            and _22[2][0].lower() == comparison.Match.IGNORED
            and _22[3][1] == 5
            and _22[4][1] == "ABSENT"
        )
        _55_1, _55_2 = [item for item in comp_result if item[1] == 55]
        assert _55_1[0] == 0 and _55_1[2][0].lower() == comparison.Match.PASS
        assert (
            _55_2[0] == 1
            and _55_2[2][0].lower() == comparison.Match.IGNORED
            and _55_2[3][1] == 4
            and _55_2[4][1] == "ABSENT"
        )
        _38 = [item for item in comp_result if item[1] == 38][0]
        assert (
            _38[0] == 0
            and _38[2][0].lower() == comparison.Match.IGNORED
            and _38[3][1] == 5
            and _38[4][1] == "ABSENT"
        )
        _555 = [item for item in comp_result if item[1] == 555][0]
        assert _555[0] == 0 and _555[2][0].lower() == comparison.Match.PASS
        _600 = [item for item in comp_result if item[1] == 600][0]
        assert (
            _600[0] == 1
            and _600[2][0].lower() == comparison.Match.IGNORED
            and _600[3][1] == "A"
            and _600[4][1] == "ABSENT"
        )
        _601 = [item for item in comp_result if item[1] == 601][0]
        assert _601[0] == 1 and _601[2][0].lower() == comparison.Match.PASS
        _683 = [item for item in comp_result if item[1] == 683][0]
        assert _683[0] == 1 and _683[2][0].lower() == comparison.Match.PASS
        _688_1, _688_2, _688_3, _688_4 = [
            item for item in comp_result if item[1] == 688
        ]
        assert (
            _688_1[0] == 2
            and _688_1[2][0].lower() == comparison.Match.IGNORED
            and _688_1[3][1] == "a"
            and _688_1[4][1] == "ABSENT"
        )
        assert (
            _688_2[0] == 2
            and _688_2[2][0].lower() == comparison.Match.IGNORED
            and _688_2[3][1] == "b"
            and _688_2[4][1] == "ABSENT"
        )
        assert _688_3[0] == 2 and _688_3[2][0].lower() == comparison.Match.PASS
        assert _688_4[0] == 2 and _688_4[2][0].lower() == comparison.Match.PASS
        _689_1, _689_2, _689_3, _689_4 = [
            item for item in comp_result if item[1] == 689
        ]
        assert _689_1[0] == 2 and _689_1[2][0].lower() == comparison.Match.PASS
        assert _689_2[0] == 2 and _689_2[2][0].lower() == comparison.Match.PASS
        assert _689_3[0] == 2 and _689_3[2][0].lower() == comparison.Match.PASS
        assert (
            _689_4[0] == 2
            and _689_4[2][0].lower() == comparison.Match.IGNORED
            and _689_4[3][1] == "d"
            and _689_4[4][1] == "ABSENT"
        )


class TestLogfileNamespace:
    """Unit testcases for the result.LogfileNamespace class."""

    def test_match(self, logfile_ns, logfile_w_matcher):
        f, lm = logfile_w_matcher
        f.logline("chai")
        f.flush()

        logfile_ns.match(lm, r"chai", timeout=0)
        assert len(logfile_ns.result.entries) == 1
        assert logfile_ns.result.entries[0]
        e = logfile_ns.result.entries[0]
        assert len(e.results) == 1
        assert e.results[0].pattern == "chai" == e.results[0].matched
        assert e.results[0].start_pos == "<BOF>"
        if os.name == "posix":
            assert e.results[0].end_pos == "<position {}>".format(
                len("chai\n")
            )

    def test_seek_eof_match(self, logfile_ns, logfile_w_matcher):
        f, lm = logfile_w_matcher
        f.logline("coffee")
        f.flush()

        drinks = [
            "green tea",
            "black tea",
            "oolong tea",
            "whisky",
            "rum",
            "vodka",
        ]

        logfile_ns.seek_eof(lm)
        for d in drinks:
            f.logline(d)
        f.flush()
        logfile_ns.match(lm, r"vodka", timeout=0.1)

        assert len(logfile_ns.result.entries) == 2
        assert logfile_ns.result.entries[1]
        e = logfile_ns.result.entries[1]
        assert len(e.results) == 1
        assert all(
            map(
                lambda x: x.start_pos.startswith("<position")
                and x.end_pos.startswith("<position"),
                e.results,
            )
        )
        pattern_s = set(map(lambda x: x.pattern, e.results))
        matched_s = set(map(lambda x: x.matched, e.results))
        assert pattern_s == {"vodka"} == matched_s
        assert e.timeout == 0.1

    def test_expect(self, logfile_ns, logfile_w_matcher):
        f, lm = logfile_w_matcher
        f.logline("whisky regions:")
        f.flush()

        regions = [
            "speyside",
            "highland",
            "lowland",
            "campbeltown",
            "islay",
        ]

        with logfile_ns.expect(lm, r"lowland"):
            for r in regions:
                f.logline(r)
            f.flush()
        assert len(logfile_ns.result.entries) == 1

        assert logfile_ns.result.entries[0]
        m_res = logfile_ns.result.entries[0].results
        assert len(m_res) == 1 and m_res[0].pattern == "lowland"
        assert m_res[0].start_pos.startswith("<position")
        assert m_res[0].end_pos.startswith("<position")

        with logfile_ns.expect(lm, r"irish", timeout=0.1):
            f.logline("some other whiskeys:")
            f.logline("bourbon")
            f.flush()

        assert not logfile_ns.result.entries[1]
        m_fai = logfile_ns.result.entries[1].failure
        assert len(m_fai) == 1 and m_fai[0].pattern == "irish"
        assert m_fai[0].start_pos.startswith("<position")
        assert m_fai[0].end_pos.startswith("<position")


class TestResultBaseNamespace:
    """Test assertions and other methods in the base result.* namespace."""

    def test_graph_assertion(self):
        """Unit testcase for the result.graph method."""
        result = result_mod.Result()
        graph_assertion = result.graph(
            "Line",
            {
                "Data Name": [
                    {"x": 0, "y": 8},
                    {"x": 1, "y": 5},
                    {"x": 2, "y": 4},
                    {"x": 3, "y": 9},
                    {"x": 4, "y": 1},
                    {"x": 5, "y": 7},
                    {"x": 6, "y": 6},
                    {"x": 7, "y": 3},
                    {"x": 8, "y": 2},
                    {"x": 9, "y": 0},
                ]
            },
            description="Line Graph",
            series_options={"Data Name": {"colour": "red"}},
            graph_options=None,
        )

        assert bool(graph_assertion) is True
        assert len(result.entries) == 1
        assert result.entries[0].graph_type is "Line"
        assert type(result.entries[0].graph_data) is dict
        assert type(result.entries[0].series_options) is dict
        assert result.entries[0].graph_options is None

    def test_attach(self, tmpdir):
        """UT for result.attach method."""
        tmpfile = str(tmpdir.join("attach_me.txt"))
        with open(tmpfile, "w") as f:
            f.write("testplan\n" * 1000)

        result = result_mod.Result(_scratch=str(tmpdir))
        hash = path_utils.hash_file(tmpfile)

        assert result.attach(tmpfile, description="Attach a text file")
        assert len(result.entries) == 1
        attachment_entry = result.entries[0]

        assert attachment_entry.source_path == os.path.join(
            os.path.dirname(tmpfile), attachment_entry.dst_path
        )
        assert hash in attachment_entry.dst_path
        assert attachment_entry.orig_filename == "attach_me.txt"
        assert attachment_entry.filesize == os.path.getsize(tmpfile)

        # The expected destination path depends on the exact hash and filesize
        # of the file we wrote.
        expected_dst_path = "attach_me-{hash}-{filesize}.txt".format(
            hash=hash, filesize=attachment_entry.filesize
        )
        assert attachment_entry.dst_path == expected_dst_path

    def test_attach_in_result_group(self, tmpdir):
        """UT for result.attach method."""
        tmpfile = str(tmpdir.join("attach_me.txt"))
        with open(tmpfile, "w") as f:
            f.write("testplan\n" * 1000)

        size = os.path.getsize(tmpfile)
        description = "Attach a text file at level: {}"

        result = result_mod.Result(_scratch=str(tmpdir))

        assert result.attach(tmpfile, description=description.format(0))
        assert len(result.entries) == 1

        with result.group("subgroup") as subgroup:
            assert subgroup.attach(tmpfile, description=description.format(1))
            assert len(subgroup.entries) == 1

            with subgroup.group("subgroup") as subsubgroup:
                assert subsubgroup.attach(
                    tmpfile, description=description.format(2)
                )
                assert len(subsubgroup.entries) == 1

            assert len(subgroup.entries) == 2
            assert len(subgroup.attachments) == 2
        assert len(result.entries) == 2
        assert len(result.attachments) == 3

        for idx, attachment in enumerate(result.attachments):
            assert attachment.source_path == os.path.join(
                os.path.dirname(tmpfile), attachment.dst_path
            )
            assert attachment.orig_filename == "attach_me.txt"
            assert attachment.filesize == size
            assert attachment.description == description.format(idx)

    def test_matplot(self, tmpdir):
        result_dir = str(tmpdir)
        result = result_mod.Result(_scratch=result_dir)

        x = range(0, 10)
        y = range(0, 10)
        plot.plot(x, y)

        result.matplot(plot, width=4, height=4, description="Matplot")

        assert len(result.entries) == 1
        assert len(result.attachments) == 1

        with result.group(description="subgroup") as subgroup:
            x = range(0, 10)
            y = range(0, 10)
            plot.plot(x, y)

            subgroup.matplot(plot, width=3, height=3, description="Matplot")

        assert len(result.entries) == 2
        assert len(result.attachments) == 2

        # two different file, with same content on the same directory
        assert (
            result.attachments[0].source_path
            != result.attachments[1].source_path
        )
        assert result.attachments[0].filesize > result.attachments[1].filesize
        assert result.attachments[0].source_path.startswith(result_dir)
        assert result.attachments[1].source_path.startswith(result_dir)

    def test_attach_dir(self, tmpdir):
        """UT for result.attach method."""
        path_utils.makeemptydirs(str(tmpdir.join("subdir")))

        tmpfile1 = str(tmpdir.join("1.txt"))
        with open(tmpfile1, "w") as f:
            f.write("testplan\n" * 10)

        tmpfile2 = str(tmpdir.join("2.txt"))
        with open(tmpfile2, "w") as f:
            f.write("testplan\n")

        tmpfile3 = str(tmpdir.join("subdir").join("3.txt"))
        with open(tmpfile3, "w") as f:
            f.write("testplan\n" * 100)

        tmpfile4 = str(tmpdir.join("subdir").join("4.txt"))
        with open(tmpfile4, "w") as f:
            f.write("testplan\n" * 1000)

        result = result_mod.Result()

        assert result.attach(str(tmpdir), description="Attach a directory")
        assert len(result.entries) == 1
        directory_entry = result.entries[0]

        assert directory_entry.source_path == str(tmpdir)
        assert (
            directory_entry.dst_path
            == hashlib.md5(
                directory_entry.source_path.encode("utf-8")
            ).hexdigest()
        )
        assert sorted(directory_entry.file_list) == ["1.txt", "2.txt"]

        assert result.attach(
            str(tmpdir),
            description="Attach a directory with filters",
            ignore=["2.*"],
            only=["*.txt"],
            recursive=True,
        )
        assert len(result.entries) == 2
        directory_entry = result.entries[1]

        assert directory_entry.source_path == str(tmpdir)
        assert (
            directory_entry.dst_path
            == hashlib.md5(
                directory_entry.source_path.encode("utf-8")
            ).hexdigest()
        )
        assert sorted(
            [file.replace("\\", "/") for file in directory_entry.file_list]
        ) == [
            "1.txt",
            "subdir/3.txt",
            "subdir/4.txt",
        ]

    def test_bool(self):
        result = result_mod.Result()
        assert result
        assert len(result) == 0
        assert result.passed

        first = result.subresult()
        second = result.subresult()

        first.true(True, "AssertionFirst")
        second.true(True, "AssertionSecond")

        result.append(first)
        result.append(second)

        assert len(result) == 2
        assert result.passed

        third = result.subresult()
        third.true(False, "AssertionThird")
        result.append(third)

        assert len(result) == 3
        assert not result.passed
