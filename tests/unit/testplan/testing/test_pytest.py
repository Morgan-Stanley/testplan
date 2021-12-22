"""Unit tests for PyTest runner."""
import os
import collections

import pytest

from testplan.testing import py_test as pytest_runner
from testplan.testing import ordering
from testplan.testing import filtering
from testplan import defaults
from testplan import report

from tests.unit.testplan.testing import pytest_expected_data

PYTEST_DEFAULT_PARAMS = {
    "test_filter": filtering.Filter(),
    "test_sorter": ordering.NoopSorter(),
    "stdout_style": defaults.STDOUT_STYLE,
}


@pytest.fixture
def pytest_test_inst(repo_root_path):
    """Return a PyTest test instance, with the example tests as its target."""
    # For testing purposes, we want to run the pytest example at
    # examples/PyTest/pytest_tests.py.
    example_path = os.path.join(
        repo_root_path, "examples", "PyTest", "pytest_tests.py"
    )

    # We need to explicitly set the stdout_style in UT, normally it is inherited
    # from the parent object but that doesn't work when testing PyTest in
    # isolation.
    return pytest_runner.PyTest(
        name="My PyTest",
        description="PyTest example test",
        target=example_path,
        extra_args=["--rootdir", repo_root_path],
        **PYTEST_DEFAULT_PARAMS
    )


def test_dry_run(pytest_test_inst):
    """
    Test the dry_run() method returns the expected report skeleton.
    """
    result = pytest_test_inst.dry_run()
    assert result.report == pytest_expected_data.EXPECTED_DRY_RUN_REPORT


def test_run_tests(pytest_test_inst):
    """Test running all tests in batch mode."""
    pytest_test_inst.setup()
    pytest_test_inst.run_tests()

    assert pytest_test_inst.report.status == report.Status.FAILED
    _check_all_testcounts(pytest_test_inst.report.counter)


def test_run_testcases_iter_all(pytest_test_inst):
    """Test running all tests iteratively."""
    all_results = list(pytest_test_inst.run_testcases_iter())
    assert len(all_results) == 13

    report_attributes, current_uids = all_results[0]
    assert current_uids == ["My PyTest"]
    assert report_attributes["runtime_status"] == report.RuntimeStatus.RUNNING

    counter = collections.Counter()
    for testcase_report, _ in all_results[1:]:
        counter[testcase_report.status] += 1

    _check_all_testcounts(counter)


def test_run_testcases_iter_testsuite(pytest_test_inst):
    """Test running a single testsuite iteratively."""
    all_results = list(
        pytest_test_inst.run_testcases_iter(
            testsuite_pattern="examples/PyTest/pytest_tests.py::TestPytestBasics"
        )
    )
    assert len(all_results) == 6

    report_attributes, current_uids = all_results[0]
    assert current_uids == [
        "My PyTest",
        "examples/PyTest/pytest_tests.py::TestPytestBasics",
    ]
    assert report_attributes["runtime_status"] == report.RuntimeStatus.RUNNING

    counter = collections.Counter()
    for testcase_report, _ in all_results[1:]:
        counter[testcase_report.status] += 1
        counter["total"] += 1

    assert counter["total"] == 5
    assert counter["passed"] == 4
    assert counter["failed"] == 1
    assert counter["skipped"] == 0


def test_run_testcases_iter_testcase(pytest_test_inst):
    """Test running a single testcase iteratively."""
    all_results = list(
        pytest_test_inst.run_testcases_iter(
            testsuite_pattern="examples/PyTest/pytest_tests.py::TestPytestBasics",
            testcase_pattern="test_success",
        )
    )
    assert len(all_results) == 2

    report_attributes, current_uids = all_results[0]
    assert current_uids == [
        "My PyTest",
        "examples/PyTest/pytest_tests.py::TestPytestBasics",
        "test_success",
    ]
    assert report_attributes["runtime_status"] == report.RuntimeStatus.RUNNING

    testcase_report, parent_uids = all_results[1]
    assert testcase_report.status == report.Status.PASSED
    assert parent_uids == [
        "My PyTest",
        "examples/PyTest/pytest_tests.py::TestPytestBasics",
    ]


def test_run_testcases_iter_param(pytest_test_inst):
    """Test running all parametrizations of a testcase iteratively."""
    all_results = list(
        pytest_test_inst.run_testcases_iter(
            testsuite_pattern="examples/PyTest/pytest_tests.py::TestPytestBasics",
            testcase_pattern="test_parametrization",
        )
    )
    assert len(all_results) == 4

    report_attributes, current_uids = all_results[0]
    assert current_uids == [
        "My PyTest",
        "examples/PyTest/pytest_tests.py::TestPytestBasics",
        "test_parametrization",
    ]
    assert report_attributes["runtime_status"] == report.RuntimeStatus.RUNNING

    counter = collections.Counter()
    for testcase_report, parent_uids in all_results[1:]:
        assert parent_uids == [
            "My PyTest",
            "examples/PyTest/pytest_tests.py::TestPytestBasics",
            "test_parametrization",
        ]
        counter[testcase_report.status] += 1
        counter["total"] += 1

    assert counter["total"] == 3
    assert counter["passed"] == 3
    assert counter["failed"] == 0
    assert counter["skipped"] == 0


def test_capture_stdout(mockplan, pytest_test_inst):
    """Test running a single testcase iteratively."""
    pytest_test_inst.cfg.parent = mockplan.cfg
    all_results = list(
        pytest_test_inst.run_testcases_iter(
            testsuite_pattern="examples/PyTest/pytest_tests.py::TestPytestBasics",
            testcase_pattern="test_failure",
        )
    )
    assert all_results[0][0]["runtime_status"] == report.RuntimeStatus.RUNNING
    assert all_results[1][0].entries[1]["message"] == "test output\n"


def test_sorting(pytest_test_inst):
    """Test sorting test suites, testcases (including parametrizations)."""
    pytest_test_inst.cfg._options[
        "test_sorter"
    ] = ordering.AlphanumericSorter()
    result = pytest_test_inst.dry_run()
    assert result.report == pytest_expected_data.EXPECTED_SORTED_REPORT


def test_filtering(pytest_test_inst):
    """Test filtering test suites, testcases (including parametrizations)."""
    pytest_test_inst.cfg._options["test_filter"] = filtering.Pattern(
        "*::*TestPy*::*"
    )
    result = pytest_test_inst.dry_run()
    assert result.report == pytest_expected_data.EXPECTED_FILTERED_REPORT_1

    pytest_test_inst.cfg._options["test_filter"] = filtering.Pattern(
        "*::*Marks::test_s*"
    )
    # Config of parent has changed so force to update test context
    pytest_test_inst._test_context = pytest_test_inst.get_test_context()
    result = pytest_test_inst.dry_run()
    assert result.report == pytest_expected_data.EXPECTED_FILTERED_REPORT_2

    # Apply test sorter as well as test filter
    pytest_test_inst.cfg._options["test_filter"] = filtering.Pattern(
        "*::*::test_p*"
    )
    pytest_test_inst.cfg._options[
        "test_sorter"
    ] = ordering.AlphanumericSorter()
    # Config of parent has changed so force to update test context
    pytest_test_inst._test_context = pytest_test_inst.get_test_context()
    result = pytest_test_inst.dry_run()
    assert result.report == pytest_expected_data.EXPECTED_FILTERED_REPORT_3


def _check_all_testcounts(counter):
    """Check the pass/fail/skip counts after running all tests."""
    # One testcase is conditionally skipped when not running on a posix OS, so
    # we have to take this into account when checking the pass/fail/skip counts.
    if os.name == "posix":
        assert counter["passed"] == 7
        assert counter["skipped"] == 1
    else:
        assert counter["passed"] == 6
        assert counter["skipped"] == 2

    assert counter["failed"] == 4
