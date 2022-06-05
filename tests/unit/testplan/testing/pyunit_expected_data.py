"""Expected data for the PyUnit test."""

import testplan.report


EXPECTED_DRY_RUN_REPORT = testplan.report.TestGroupReport(
    name="My PyUnit",
    description="PyUnit example test",
    uid="My PyUnit",
    category="pyunit",
    entries=[
        testplan.report.TestGroupReport(
            name="Passing",
            uid="Passing",
            category="testsuite",
            entries=[
                testplan.report.TestCaseReport(
                    name="PyUnit test results", uid="PyUnit test results"
                )
            ],
        ),
        testplan.report.TestGroupReport(
            name="Failing",
            uid="Failing",
            category="testsuite",
            entries=[
                testplan.report.TestCaseReport(
                    name="PyUnit test results", uid="PyUnit test results"
                )
            ],
        ),
    ],
)
