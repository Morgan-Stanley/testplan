import re

from testplan.report import (
    TestReport,
    TestGroupReport,
    TestCaseReport,
)
from testplan.common.report.base import RuntimeStatus, Status

testcase_report = TestCaseReport(
    name="ExitCodeCheck",
    entries=[
        {
            "type": "RawAssertion",
            "description": "Process exit code check",
            "passed": False,
        },
        {"type": "Attachment", "description": "Process stdout"},
        {"type": "Attachment", "description": "Process stderr"},
    ],
)

testcase_report.runtime_status = RuntimeStatus.FINISHED

my_test_report = TestGroupReport(
    name="MyTest",
    category="dummytest",
    entries=[
        TestGroupReport(
            name="ProcessChecks",
            category="testsuite",
            entries=[testcase_report],
        )
    ],
)

my_test_report.logs = [
    {
        "message": re.compile(
            r"RuntimeError: Timeout while"
            r" running DummyTest\[MyTest\] after 1 seconds\."
        )
    }
]

my_test_report.status_override = Status.ERROR

expected_report = TestReport(name="plan", entries=[my_test_report])
