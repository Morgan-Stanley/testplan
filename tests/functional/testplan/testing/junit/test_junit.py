"""Unit tests for the JUnit test runner."""
import os

import testplan.report
from testplan.testing import junit
from testplan.report import TestGroupReport, TestCaseReport
from testplan.common.utils.testing import check_report
from pytest_test_filters import skip_on_windows

CURRENT_PATH = os.path.dirname(os.path.abspath(__file__))
JUNIT_FAKE_BIN = os.path.join(CURRENT_PATH, "junit_mock.py")
REPORT_PATH = os.path.join(CURRENT_PATH, "build", "test-results", "test")


expect_report = TestGroupReport(
    name="My Junit",
    category="junit",
    description="Junit example test",
    entries=[
        TestGroupReport(
            name="com.gradle.example.application.ApplicationTests",
            category="testsuite",
            entries=[
                TestCaseReport(
                    name="contextLoads()",
                    entries=[
                        {
                            "content": "Testcase contextLoads() passed",
                            "passed": True,
                            "description": "Passed",
                            "meta_type": "assertion",
                            "type": "RawAssertion",
                        }
                    ],
                )
            ],
            tags=None,
        ),
        TestGroupReport(
            name="com.gradle.example.application.MessageServiceTest",
            category="testsuite",
            entries=[
                TestCaseReport(
                    name="testGet()",
                    entries=[
                        {
                            "passed": False,
                            "meta_type": "assertion",
                            "type": "Fail",
                        },
                        {
                            "language": "java",
                            "description": "stacktrace",
                            "meta_type": "entry",
                            "type": "CodeLog",
                        },
                    ],
                )
            ],
            tags=None,
        ),
        TestGroupReport(
            name="ProcessChecks",
            category="testsuite",
            entries=[
                TestCaseReport(
                    name="ExitCodeCheck",
                    entries=[
                        {
                            "passed": True,
                            "description": "Process exit code check",
                            "meta_type": "assertion",
                            "type": "RawAssertion",
                        },
                        {
                            "description": "Process stdout",
                            "meta_type": "entry",
                            "type": "Attachment",
                        },
                        {
                            "description": "Process stderr",
                            "meta_type": "entry",
                            "type": "Attachment",
                        },
                    ],
                )
            ],
            tags=None,
        ),
    ],
    tags=None,
)


@skip_on_windows(reason="JUnit is skipped on Windows.")
def test_run_test(mockplan):
    mockplan.add(
        junit.JUnit(
            name="My Junit",
            description="Junit example test",
            binary=JUNIT_FAKE_BIN,
            junit_args=["test"],
            results_dir=REPORT_PATH,
            proc_cwd=CURRENT_PATH,
        )
    )

    assert mockplan.run().run is True

    report = mockplan.report
    assert report.status == testplan.report.Status.FAILED

    mt_report = report.entries[0]
    assert len(mt_report.entries) == 3

    check_report(expect_report, mt_report)


def test_custom_args():
    pre_cmd = ["echo", '"Hi"']
    post_cmd = ["echo", '"Bye"']
    pre_cmds = pre_cmd + ["echo", "it's a pre arg"]
    post_cmds = post_cmd + ["echo", "it's a post arg"]

    default_runner = junit.JUnit(
        name="My Junit", binary=JUNIT_FAKE_BIN, results_dir=REPORT_PATH
    )

    assert default_runner.test_command() == default_runner._test_command()
    assert not default_runner.list_command()

    basic_runner = junit.JUnit(
        name="My Junit",
        binary=JUNIT_FAKE_BIN,
        results_dir=REPORT_PATH,
        pre_args=pre_cmd,
        post_args=post_cmd,
    )

    assert (
        basic_runner.test_command()[0:2]
        == basic_runner.cfg._options["pre_args"]
    )
    assert (
        basic_runner.test_command()[-2:]
        == basic_runner.cfg._options["post_args"]
    )
    assert not basic_runner.list_command()

    extra_runner = junit.JUnit(
        name="My Junit",
        binary=JUNIT_FAKE_BIN,
        results_dir=REPORT_PATH,
        pre_args=pre_cmds,
        post_args=post_cmds,
    )

    assert (
        extra_runner.test_command()[0:4]
        == extra_runner.cfg._options["pre_args"]
    )
    assert (
        extra_runner.test_command()[-4:]
        == extra_runner.cfg._options["post_args"]
    )
    assert not extra_runner.list_command()
