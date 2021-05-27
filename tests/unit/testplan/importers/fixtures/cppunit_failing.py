from pathlib import Path

from testplan.report import TestReport, TestGroupReport, TestCaseReport
from tests.unit.testplan.importers.fixtures import (
    ImporterTestFixture,
)

fixture = ImporterTestFixture(
    Path(__file__).with_suffix(".xml"),
    TestReport(
        name="CPPUnit Result",
        description="CPPUnit Import",
        entries=[
            TestGroupReport(
                name="CPPUnit Result",
                category="cppunit",
                description="CPPUnit Import",
                entries=[
                    TestGroupReport(
                        name="All Tests",
                        category="testsuite",
                        entries=[
                            TestCaseReport(
                                name="Comparison::testEqual",
                                entries=[
                                    {"type": "RawAssertion", "passed": False}
                                ],
                            ),
                            TestCaseReport(
                                name="LogicalOp::testAnd",
                                entries=[
                                    {"type": "RawAssertion", "passed": False}
                                ],
                            ),
                            TestCaseReport(
                                name="Comparison::testGreater",
                                entries=[
                                    {"type": "RawAssertion", "passed": True}
                                ],
                            ),
                            TestCaseReport(
                                name="Comparison::testLess",
                                entries=[
                                    {"type": "RawAssertion", "passed": True}
                                ],
                            ),
                            TestCaseReport(
                                name="Comparison::testMisc",
                                entries=[
                                    {"type": "RawAssertion", "passed": True}
                                ],
                            ),
                            TestCaseReport(
                                name="LogicalOp::testOr",
                                entries=[
                                    {"type": "RawAssertion", "passed": True}
                                ],
                            ),
                            TestCaseReport(
                                name="LogicalOp::testNot",
                                entries=[
                                    {"type": "RawAssertion", "passed": True}
                                ],
                            ),
                            TestCaseReport(
                                name="LogicalOp::testXor",
                                entries=[
                                    {"type": "RawAssertion", "passed": True}
                                ],
                            ),
                        ],
                    ),
                ],
            )
        ],
    ),
)
