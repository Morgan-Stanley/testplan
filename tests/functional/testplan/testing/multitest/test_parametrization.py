import sys
import logging
from contextlib import contextmanager
from unittest import mock
from importlib import reload

import pytest

from testplan.defaults import MAX_TEST_NAME_LENGTH
from testplan.testing.multitest import MultiTest, testsuite, testcase
from testplan.testing.multitest.parametrization import (
    MAX_METHOD_NAME_LENGTH,
    ParametrizationError,
)
from testplan.report import (
    TestReport,
    TestGroupReport,
    TestCaseReport,
    ReportCategories,
)
from testplan.common.utils.testing import check_report, warnings_suppressed
from testplan.common.utils.timing import Interval

LOGGER = logging.getLogger()


@contextmanager
def module_reloaded(mod):
    """
    If uncaught exception raised, Testplan process should abort. However,
    if the process is managed by PyTest for testing purpose, then the
    exception will be caught and execute the next testcase, but Testplan
    modules still exist in memory, some global variables need to be reset.
    """
    yield
    if mod in sys.modules:
        reload(sys.modules[mod])


def gen_testcase_report(group_report):
    for report in group_report.entries:
        if isinstance(report, TestGroupReport):
            for element in gen_testcase_report(report):
                yield element
        else:
            yield report


def check_parametrization(
    mockplan, suite_kls, report_entries, testcase_uids=None, tag_dict=None
):
    tag_dict = tag_dict or {}
    multitest = MultiTest(name="MyMultitest", suites=[suite_kls()])
    mockplan.add(multitest)
    mockplan.run()

    if testcase_uids:
        suite_report = mockplan.report.entries[0].entries[0]
        assert isinstance(suite_report, TestGroupReport)
        for testcase_report, uid in zip(
            gen_testcase_report(suite_report), testcase_uids
        ):
            assert testcase_report.uid == uid

    expected_report = TestReport(
        name="plan",
        entries=[
            TestGroupReport(
                name="MyMultitest",
                category=ReportCategories.MULTITEST,
                entries=[
                    TestGroupReport(
                        name="MySuite",
                        tags=tag_dict,
                        category=ReportCategories.TESTSUITE,
                        entries=report_entries,
                    )
                ],
            )
        ],
    )

    check_report(expected_report, mockplan.report)


def test_basic_parametrization(mockplan):
    @testsuite
    class MySuite:
        @testcase(parameters=((1, 2, 3), -1, (5, -5), {"a": 3, "expected": 4}))
        def test_add(self, env, result, a, b=1, expected=0):
            """Simple docstring"""
            result.equal(a + b, expected)

    parametrization_group = TestGroupReport(
        name="test_add",
        description="Simple docstring",
        category=ReportCategories.PARAMETRIZATION,
        entries=[
            TestCaseReport(
                name="test_add <a=1, b=2, expected=3>",
                description="Simple docstring",
                entries=[{"type": "Equal", "first": 3, "second": 3}],
            ),
            TestCaseReport(
                name="test_add <a=-1, b=1, expected=0>",
                description="Simple docstring",
                entries=[{"type": "Equal", "first": 0, "second": 0}],
            ),
            TestCaseReport(
                name="test_add <a=5, b=-5, expected=0>",
                description="Simple docstring",
                entries=[{"type": "Equal", "first": 0, "second": 0}],
            ),
            TestCaseReport(
                name="test_add <a=3, b=1, expected=4>",
                description="Simple docstring",
                entries=[{"type": "Equal", "first": 4, "second": 4}],
            ),
        ],
    )

    testcase_uids = [
        "test_add__a_1__b_2__expected_3",
        "test_add__0",
        "test_add__1",
        "test_add__a_3__b_1__expected_4",
    ]

    check_parametrization(
        mockplan, MySuite, [parametrization_group], testcase_uids
    )


def test_combinatorial_parametrization(mockplan):
    @testsuite
    class MySuite:
        @testcase(parameters={"a": [1, 2], "b": ("alpha", "beta")})
        def test_sample(self, env, result, a, b):
            result.true(True, "{} - {}".format(a, b))

    parametrization_group = TestGroupReport(
        name="test_sample",
        category=ReportCategories.PARAMETRIZATION,
        entries=[
            TestCaseReport(
                name="test_sample <a=1, b='alpha'>",
                entries=[{"type": "IsTrue", "description": "1 - alpha"}],
            ),
            TestCaseReport(
                name="test_sample <a=1, b='beta'>",
                entries=[{"type": "IsTrue", "description": "1 - beta"}],
            ),
            TestCaseReport(
                name="test_sample <a=2, b='alpha'>",
                entries=[{"type": "IsTrue", "description": "2 - alpha"}],
            ),
            TestCaseReport(
                name="test_sample <a=2, b='beta'>",
                entries=[{"type": "IsTrue", "description": "2 - beta"}],
            ),
        ],
    )

    testcase_uids = [
        "test_sample__a_1__b_alpha",
        "test_sample__a_1__b_beta",
        "test_sample__a_2__b_alpha",
        "test_sample__a_2__b_beta",
    ]

    check_parametrization(
        mockplan, MySuite, [parametrization_group], testcase_uids
    )


@pytest.mark.parametrize(
    "val, msg",
    (
        ([(1, 2, 3, 4)], "Should fail if tuple length is longer than args."),
        (
            1,
            "Should fail if shortcut notation is used while the testcase"
            " accepts multiple parametrization arguments.",
        ),
        ([(1,)], "Should fail if tuple is missing values for required args."),
        (
            tuple(),
            "Should fail for empty tuple / list (basic parametrization).",
        ),
        (
            [{"a": 1, "b": 2, "e": 3}],
            "Should fail if explicit value dict (tuple element)"
            " has extra keys.",
        ),
        ({}, "Should fail for empty dict (combinatorial parametrization)."),
        (
            {"a": [1, 2], "b": 3},
            "Should fail combinatorial parametrization"
            " for non-iterable dict values.",
        ),
        (
            {"a": [1, 2], "b": {"foo": "bar"}},
            "Should fail combinatorial parametrization"
            " for dicts as dict values.",
        ),
        (
            {"a": [2], "c": [5]},
            "Should fail combinatorial parametrization"
            " for missing dict keys for required args.",
        ),
        (
            {"a": [2], "b": [4], "e": [12]},
            "Should fail if combinatorial dict has extra keys.",
        ),
    ),
)
def test_invalid_parametrization(val, msg):
    """Correct arguments should be passed to parametrized testcases."""
    with pytest.raises(ParametrizationError):

        @testsuite
        class MySuite:
            @testcase(parameters=val)
            def sample_test(self, env, result, a, b, c=3):
                pass

        pytest.fail(msg)


def test_duplicate_parametrization_template_definition():
    """No duplicate name of testcase or parametrization template allowed."""
    with pytest.raises(ValueError):

        @testsuite
        class MySuite:
            @testcase
            def sample_test(self, env, result):
                pass

            @testcase(parameters=(1, 2, 3))
            def sample_test(self, env, result, val):
                pass

        pytest.fail('Duplicate testcase definition "sample_test" found')


def test_auto_resolve_name_conflict(mockplan):
    """make sure no name conflict of parametrized testcases."""

    @testsuite
    class MySuite:
        @testcase(parameters=(0, 1))
        def sample__test(self, env, result, val):
            pass

        @testcase
        def sample__test__val_1(self, env, result):
            pass

        @testcase(parameters=(0, 1))
        def sample(self, env, result, test__val):
            pass

    report_entries = [
        TestGroupReport(
            name="sample__test",
            category=ReportCategories.PARAMETRIZATION,
            entries=[
                TestCaseReport(name="sample__test <val=0>"),
                TestCaseReport(name="sample__test <val=1>"),
            ],
        ),
        TestCaseReport(name="sample__test__val_1", uid=""),
        TestGroupReport(
            name="sample",
            category=ReportCategories.PARAMETRIZATION,
            entries=[
                TestCaseReport(name="sample <test__val=0>"),
                TestCaseReport(name="sample <test__val=1>"),
            ],
        ),
    ]

    testcase_uids = [
        "sample__test__val_0__0",
        "sample__test__val_1__0",
        "sample__test__val_1",
        "sample__test__val_0__1",
        "sample__test__val_1__1",
    ]

    check_parametrization(mockplan, MySuite, report_entries, testcase_uids)


@pytest.mark.parametrize(
    "parameters, testcase_names, testcase_uids, msg",
    (
        (
            ("#@)$*@#%", "a-b"),
            ["sample_test <val='#@)$*@#%'>", "sample_test <val='a-b'>"],
            ["sample_test__0", "sample_test__1"],
            "Should use original method name + index fallback if"
            " generated names are not valid Python attribute names.",
        ),
        (
            ("a" * MAX_METHOD_NAME_LENGTH, "b" * MAX_METHOD_NAME_LENGTH),
            [
                "sample_test <val='{}'>".format("a" * MAX_METHOD_NAME_LENGTH),
                "sample_test <val='{}'>".format("b" * MAX_METHOD_NAME_LENGTH),
            ],
            ["sample_test__0", "sample_test__1"],
            "Should use original method name + index fallback if"
            " generated names are longer than {} characters.".format(
                MAX_METHOD_NAME_LENGTH
            ),
        ),
    ),
)
def test_param_name_func_fallback(
    mockplan, parameters, testcase_names, testcase_uids, msg
):
    """Testcase uid should be a valid python identifier and not too long."""
    LOGGER.info(msg)

    with warnings_suppressed():

        @testsuite
        class MySuite:
            @testcase(parameters=parameters)
            def sample_test(self, env, result, val):
                pass

    parametrization_group = TestGroupReport(
        name="sample_test",
        category=ReportCategories.PARAMETRIZATION,
        entries=[
            TestCaseReport(name=testcase_names[0]),
            TestCaseReport(name=testcase_names[1]),
        ],
    )

    testcase_uids = [testcase_uids[0], testcase_uids[1]]

    check_parametrization(
        mockplan, MySuite, [parametrization_group], testcase_uids
    )


def test_custom_name(mockplan):
    """
    User defined testcase name is saved into report instead of function name.
    """

    @testsuite
    class MySuite:
        @testcase(
            name="Sample Test", parameters=(("foo", "bar"), ("alpha", "beta"))
        )
        def sample_test(self, env, result, a, b):
            pass

    parametrization_group = TestGroupReport(
        name="Sample Test",
        category=ReportCategories.PARAMETRIZATION,
        entries=[
            TestCaseReport(name="Sample Test <a='foo', b='bar'>"),
            TestCaseReport(name="Sample Test <a='alpha', b='beta'>"),
        ],
    )

    testcase_uids = [
        "sample_test__a_foo__b_bar",
        "sample_test__a_alpha__b_beta",
    ]

    check_parametrization(
        mockplan, MySuite, [parametrization_group], testcase_uids
    )


@pytest.mark.parametrize(
    "name_func, testcase_names",
    (
        (
            lambda func_name, kwargs: "XXX_{a}_{b}_YYY".format(**kwargs),
            ("XXX_foo_bar_YYY", "XXX_alpha_beta_YYY"),
        ),
        (None, ("Sample Test 0", "Sample Test 1")),
    ),
)
def test_custom_name_func(mockplan, name_func, testcase_names):
    """`name_func` is used for generating display names of testcases."""

    @testsuite
    class MySuite:
        @testcase(
            parameters=(("foo", "bar"), ("alpha", "beta")),
            name="Sample Test",
            name_func=name_func,
        )
        def sample_test(self, env, result, a, b):
            pass

    parametrization_group = TestGroupReport(
        name="Sample Test",
        category=ReportCategories.PARAMETRIZATION,
        entries=[
            TestCaseReport(name=testcase_names[0]),
            TestCaseReport(name=testcase_names[1]),
        ],
    )

    testcase_uids = [
        "sample_test__a_foo__b_bar",
        "sample_test__a_alpha__b_beta",
    ]

    check_parametrization(
        mockplan, MySuite, [parametrization_group], testcase_uids
    )


@pytest.mark.parametrize(
    "name_func, msg, err",
    (
        (
            5,
            "Should fail if name_func is not a callable.",
            ParametrizationError,
        ),
        (
            lambda foo, bar: "",
            "Should fail if `name_func` arg names"
            " does not match `func_name` and `kwargs`.",
            ParametrizationError,
        ),
        (
            lambda func_name, kwargs, foo: "",
            "Should fail if `name_func` arg names do not accept 2 arguments.",
            ParametrizationError,
        ),
        (
            lambda func_name, kwargs: "",
            "Should fail if `name_func` returns an empty string.",
            ValueError,
        ),
        (
            lambda func_name, kwargs: 999,
            "Should fail if return type of `name_func` is not string.",
            ValueError,
        ),
    ),
)
def test_invalid_name_func(name_func, msg, err):
    """Custom naming function should be correctly defined."""
    with pytest.raises(err):

        @testsuite
        class MySuite:
            @testcase(parameters=(1, 2), name_func=name_func)
            def sample_test(self, env, result, val):
                pass

        pytest.fail(msg)


def test_unwanted_testcase_name(mockplan):
    """Custom naming function should return a valid non-empty string."""
    with mock.patch("warnings.warn", return_value=None) as mock_warn:

        long_string = "c" * (MAX_TEST_NAME_LENGTH + 1)

        @testsuite
        class MySuite:
            @testcase(
                parameters=(1,),
                name_func=lambda func_name, kwargs: long_string,
            )
            def sample_test(self, env, result, val):
                pass

        multitest = MultiTest(name="MyMultitest", suites=[MySuite()])
        mockplan.add(multitest)
        mockplan.run()

    mock_warn.assert_called_once()


def test_custom_wrapper():
    """Custom wrappers should be applied to each generated testcase."""

    def add_label(value):
        def wrapper(func):
            func.label = value
            return func

        return wrapper

    @testsuite
    class MySuite:
        @testcase(
            parameters=((1, 2, 3), (3, 3, 6)), custom_wrappers=add_label("foo")
        )
        def adder_test(self, env, result, a, b, expected):
            result.equal(actual=a + b, expected=expected)

        # custom_wrappers should work for non-parametrized case as well
        @testcase(custom_wrappers=add_label("bar"))
        def non_param_case(self, env, result):
            result.equal(actual=1, expected=1)

    assert MySuite.adder_test__a_1__b_2__expected_3.label == "foo"
    assert MySuite.adder_test__a_3__b_3__expected_6.label == "foo"
    assert MySuite.non_param_case.label == "bar"


@pytest.mark.parametrize(
    "tag_func, expected_tags, expected_tags_index",
    (
        (
            lambda kwargs: kwargs["product"],
            {"simple": {"productA"}},
            {"simple": {"foo", "productA"}},
        ),
        (
            lambda kwargs: {"product": kwargs["product"]},
            {"product": {"productA"}},
            {"product": {"productA"}, "simple": {"foo"}},
        ),
    ),
)
def test_tag_func(tag_func, expected_tags, expected_tags_index):
    @testsuite
    class MySuite:
        @testcase(
            parameters=(dict(product="productA", category="dummyCategory"),),
            tags="foo",
            tag_func=tag_func,
        )
        def adder_test(self, env, result, product, category):
            pass

    assert (
        MySuite.adder_test__product_productA__category_dummyCategory.__tags__
        == expected_tags
    )
    assert (
        MySuite.adder_test__product_productA__category_dummyCategory.__tags_index__
        == expected_tags_index
    )


@pytest.mark.parametrize(
    "docstring_func, expected_docstring",
    (
        # By default, generated testcases inherit the docstring from the
        # template method.
        (None, "Original docstring"),
        (lambda docstring, kwargs: "foo", "foo"),
        (
            lambda docstring, kwargs: "{docstring} "
            "- {first} - {second}".format(docstring=docstring, **kwargs),
            "Original docstring - foo - bar",
        ),
    ),
)
def test_docstring_func(docstring_func, expected_docstring):
    @testsuite
    class MySuite:
        @testcase(parameters=(("foo", "bar"),), docstring_func=docstring_func)
        def adder_test(self, env, result, first, second):
            """Original docstring"""
            pass

    assert (
        MySuite.adder_test__first_foo__second_bar.__doc__ == expected_docstring
    )


def test_parametrization_tagging(mockplan):
    """
    Parametrization report group should include tags generated by
    `tag_func` and native suite tags in `tag_index` attribute.
    """

    @testsuite(tags="foo")
    class MySuite:
        @testcase(
            parameters=("red", "blue", "green"),
            tags="alpha",
            tag_func=lambda kwargs: {"color": kwargs["color"]},
        )
        def dummy_test(self, env, result, color):
            pass

    parametrization_group = TestGroupReport(
        name="dummy_test",
        category=ReportCategories.PARAMETRIZATION,
        tags={"simple": {"alpha"}},
        entries=[
            TestCaseReport(
                name="dummy_test <color='red'>", tags={"color": {"red"}}
            ),
            TestCaseReport(
                name="dummy_test <color='blue'>", tags={"color": {"blue"}}
            ),
            TestCaseReport(
                name="dummy_test <color='green'>", tags={"color": {"green"}}
            ),
        ],
    )

    check_parametrization(
        mockplan,
        MySuite,
        [parametrization_group],
        tag_dict={"simple": {"foo"}},
    )


def test_order_of_parametrization_report(mockplan):
    """
    In test suite report, parametrization report group should be
    placed at the correct position according to the order it is
    defined in source code.
    """

    @testsuite
    class MySuite:
        @testcase(parameters=("red", "blue", "green"))
        def dummy_test_1(self, env, result, color):
            pass

        @testcase
        def dummy_test_2(self, env, result):
            pass

        @testcase(parameters=("circle", "square", "triangle"))
        def dummy_test_3(self, env, result, shape):
            pass

        @testcase
        def dummy_test_4(self, env, result):
            pass

        @testcase(parameters=("fragrant", "stinky", "musty"))
        def dummy_test_5(self, env, result, smell):
            pass

    report_entries = [
        TestGroupReport(
            name="dummy_test_1",
            category=ReportCategories.PARAMETRIZATION,
            entries=[
                TestCaseReport(name="dummy_test_1 <color='red'>"),
                TestCaseReport(name="dummy_test_1 <color='blue'>"),
                TestCaseReport(name="dummy_test_1 <color='green'>"),
            ],
        ),
        TestCaseReport(name="dummy_test_2"),
        TestGroupReport(
            name="dummy_test_3",
            category=ReportCategories.PARAMETRIZATION,
            entries=[
                TestCaseReport(name="dummy_test_3 <shape='circle'>"),
                TestCaseReport(name="dummy_test_3 <shape='square'>"),
                TestCaseReport(name="dummy_test_3 <shape='triangle'>"),
            ],
        ),
        TestCaseReport(name="dummy_test_4"),
        TestGroupReport(
            name="dummy_test_5",
            category=ReportCategories.PARAMETRIZATION,
            entries=[
                TestCaseReport(name="dummy_test_5 <smell='fragrant'>"),
                TestCaseReport(name="dummy_test_5 <smell='stinky'>"),
                TestCaseReport(name="dummy_test_5 <smell='musty'>"),
            ],
        ),
    ]

    check_parametrization(mockplan, MySuite, report_entries)


def test_timing_info_of_parametrized_group_report(mockplan):
    @testsuite
    class SampleTest(object):
        @testcase(
            parameters=(
                (5, 5, 10),
                (3, 2, 5),
                (0, 0, 0),
                ("foo", "bar", "foobar"),
            )
        )
        def addition(self, env, result, a, b, expected):
            result.equal(a + b, expected)

        @testcase(parameters=(2, 4, 6, 8), execution_group="is even")
        def is_even(self, env, result, value):
            result.equal(value % 2, 0)

    multitest = MultiTest(name="Primary", suites=[SampleTest()])

    mockplan.add(multitest)
    mockplan.run()

    serial_group_report_timer = (
        mockplan.report.entries[0].entries[0].entries[0].timer
    )
    parallel_group_report_timer = (
        mockplan.report.entries[0].entries[0].entries[1].timer
    )

    assert "run" in serial_group_report_timer.keys()
    assert "run" in parallel_group_report_timer.keys()

    assert isinstance(serial_group_report_timer.last(key="run"), Interval)
    assert isinstance(parallel_group_report_timer.last(key="run"), Interval)
