"""
This module contains tests for test report merge functionality.

We will have parallel test runs for our multitests
(e.g. run different suites of a multitest in parallel,
in different environments)

or even parallel test runs for ourt suites
(e.g. run different testcases of the same
suite in parallel, in different environments.)

In all of these cases, the final multitest report
should be equal to the one that is generated by merging multiple ones.
"""

from testplan.common.utils.testing import check_report
from testplan.report import TestCaseReport, TestGroupReport


# TODO: Multitest/suite splitting is not supported yet,
# refactor these tests so that they actually
# run a testplan when it is implemented.


# Assume we have a test structure like
#
# MultiTest(name=MyMultiTest)
#   AlphaSuite
#       test_one
#       test_two
#   BetaSuite
#       test_one
#       test_two
#       test_param
#           test_param_0
#           test_param_1
#           test_param_2
#           test_param_3
#   GammaSuite
#       test_one
#       test_two
#

expected_report = TestGroupReport(
    name="MyMultiTest",
    category="multitest",
    uid=1,
    tags={"color": {"green"}},
    entries=[
        TestGroupReport(
            name="AlphaSuite",
            category="testsuite",
            uid=10,
            tags={"color": {"red"}},
            entries=[
                TestCaseReport(name="test_one", uid=100, entries=[], tags={}),
                TestCaseReport(
                    name="test_two",
                    uid=101,
                    entries=[],
                    tags={"environment": {"server"}},
                ),
            ],
        ),
        TestGroupReport(
            name="BetaSuite",
            category="testsuite",
            uid=11,
            tags={},
            entries=[
                TestCaseReport(
                    name="test_one",
                    uid=102,
                    entries=[],
                    tags={"color": {"blue"}},
                ),
                TestCaseReport(name="test_two", uid=103, entries=[], tags={}),
                TestGroupReport(
                    name="test_param",
                    category="parametrization",
                    uid=999,
                    tags={"environment": {"client"}},
                    entries=[
                        TestCaseReport(
                            name="test_param_0", uid=104, entries=[]
                        ),
                        TestCaseReport(
                            name="test_param_1", uid=105, entries=[]
                        ),
                        TestCaseReport(
                            name="test_param_2", uid=106, entries=[]
                        ),
                        TestCaseReport(
                            name="test_param_3", uid=107, entries=[]
                        ),
                    ],
                ),
            ],
        ),
        TestGroupReport(
            name="GammaSuite",
            category="testsuite",
            uid=12,
            tags={},
            entries=[
                TestCaseReport(
                    name="test_one",
                    uid=108,
                    entries=[],
                    tags={"environment": {"client"}},
                ),
                TestCaseReport(
                    name="test_two",
                    uid=109,
                    entries=[],
                    tags={"environment": {"server"}},
                ),
            ],
        ),
    ],
)


# Assume we split our test run so that
# All suites are run separately and parametrized
# testcases of BetaSuite is run separately as well

# Keep in mind that tag indexes differ for multitest reports
# as the propagated tag data won't be available for
# suites that have not been run.

mt_report_alpha = TestGroupReport(
    name="MyMultiTest",
    category="multitest",
    uid=1,
    tags={"color": {"green"}},
    entries=[
        TestGroupReport(
            name="AlphaSuite",
            category="testsuite",
            uid=10,
            tags={"color": {"red"}},
            entries=[
                TestCaseReport(name="test_one", uid=100, entries=[], tags={}),
                TestCaseReport(
                    name="test_two",
                    uid=101,
                    entries=[],
                    tags={"environment": {"server"}},
                ),
            ],
        )
    ],
)


mt_report_beta_1 = TestGroupReport(
    name="MyMultiTest",
    category="multitest",
    uid=1,
    tags={"color": {"green"}},
    entries=[
        TestGroupReport(
            name="BetaSuite",
            category="testsuite",
            uid=11,
            tags={},
            entries=[
                TestCaseReport(
                    name="test_one",
                    uid=102,
                    entries=[],
                    tags={"color": {"blue"}},
                ),
                TestCaseReport(name="test_two", uid=103, entries=[], tags={}),
            ],
        )
    ],
)

mt_report_beta_2 = TestGroupReport(
    name="MyMultiTest",
    category="multitest",
    uid=1,
    tags={"color": {"green"}},
    entries=[
        TestGroupReport(
            name="BetaSuite",
            category="testsuite",
            uid=11,
            tags={},
            entries=[
                TestGroupReport(
                    name="test_param",
                    category="parametrization",
                    uid=999,
                    tags={"environment": {"client"}},
                    entries=[
                        TestCaseReport(
                            name="test_param_0", uid=104, entries=[]
                        ),
                        TestCaseReport(
                            name="test_param_1", uid=105, entries=[]
                        ),
                        TestCaseReport(
                            name="test_param_2", uid=106, entries=[]
                        ),
                        TestCaseReport(
                            name="test_param_3", uid=107, entries=[]
                        ),
                    ],
                )
            ],
        )
    ],
)


mt_report_gamma = TestGroupReport(
    name="MyMultiTest",
    category="multitest",
    uid=1,
    tags={"color": {"green"}},
    entries=[
        TestGroupReport(
            name="GammaSuite",
            category="testsuite",
            uid=12,
            tags={},
            entries=[
                TestCaseReport(
                    name="test_one",
                    uid=108,
                    entries=[],
                    tags={"environment": {"client"}},
                ),
                TestCaseReport(
                    name="test_two",
                    uid=109,
                    entries=[],
                    tags={"environment": {"server"}},
                ),
            ],
        )
    ],
)


def test_merge():
    mt_report = TestGroupReport(
        name="MyMultiTest",
        category="multitest",
        uid=1,
        tags={"color": {"green"}},
    )

    mt_report.merge(mt_report_alpha, strict=False)
    mt_report.merge(mt_report_beta_1, strict=False)
    mt_report.merge(mt_report_beta_2, strict=False)
    mt_report.merge(mt_report_gamma, strict=False)

    check_report(actual=mt_report, expected=expected_report)
