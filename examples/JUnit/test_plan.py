#!/usr/bin/env python
"""Example to demonstrate Junit integration with Testplan."""

import os
import sys
from testplan import test_plan
from testplan.testing import junit


# You need to create a gradle project.
CURRENT_PATH = os.path.dirname(os.path.abspath(__file__))
GRADLE_BIN = os.path.join(CURRENT_PATH, "gradle_mock.py")
REPORT_PATH = os.path.join(CURRENT_PATH, "build", "test-results", "test")


@test_plan(name="JUnit Example", description="JUnit test example")
def main(plan):
    # Now we are inside a function that will be passed a plan object, we
    # can add tests to this plan. Here we will add a QUnit suite, made up
    # of a single TestCase defined above.
    plan.add(
        junit.JUnit(
            name="My JUnit",
            description="JUnit example testcase",
            junit_args=["test"],
            results_dir=REPORT_PATH,
            binary=GRADLE_BIN,
            proc_cwd=CURRENT_PATH,
        )
    )


# Finally we trigger our main function when the script is run, and
# set the return status.
if __name__ == "__main__":
    res = main()
    sys.exit(res.exit_code)
