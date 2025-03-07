import os
import sys
import atexit
import collections

from testplan import TestplanMock
from testplan.testing.multitest import MultiTest
from testplan.common.utils.comparison import compare
from interactive_helper import wait_for_interactive_start

THIS_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

ModuleInfo = collections.namedtuple(
    "ModuleInfo",
    "template_path module_path "
    "original_value updated_value original_report updated_report",
)

TEST_SUITE_MODULES = [
    # A module in the same directory with the main script.
    ModuleInfo(
        os.path.abspath(
            os.path.join(THIS_DIRECTORY, "basic_suite_template.txt")
        ),
        os.path.abspath(os.path.join(THIS_DIRECTORY, "basic_suite.py")),
        {"VALUE": "0"},
        {"VALUE": "1"},
        [
            {
                "type": "Equal",
                "meta_type": "assertion",
                "description": "Equal Assertion",
                "label": "==",
                "passed": False,
                "first": 1,
                "second": 0,
                "type_expected": "int",
                "type_actual": "int",
            }
        ],
        [
            {
                "type": "Equal",
                "meta_type": "assertion",
                "description": "Equal Assertion",
                "label": "==",
                "passed": True,
                "first": 1,
                "second": 1,
                "type_expected": "int",
                "type_actual": "int",
            }
        ],
    ),
    # A module in a package which is in the same directory as the main script.
    ModuleInfo(
        os.path.abspath(
            os.path.join(THIS_DIRECTORY, "tasks", "inner_suite_template.txt")
        ),
        os.path.abspath(
            os.path.join(THIS_DIRECTORY, "tasks", "inner_suite.py")
        ),
        {"IMPORT": "", "ANOTHER_CASE": "", "VALUE": "True"},
        {
            "IMPORT": "from .mod import VAL",
            "ANOTHER_CASE": (
                "    @testcase\n"
                "    def another_case(self, env, result):\n"
                '        result.false(VAL, description="Fallacy Assertion")\n'
            ),
            "VALUE": "False",
        },
        [
            {
                "type": "IsTrue",
                "meta_type": "assertion",
                "description": "Truth Assertion",
                "passed": True,
                "expr": True,
            }
        ],
        [
            {
                "type": "IsTrue",
                "meta_type": "assertion",
                "description": "Truth Assertion",
                "passed": True,
                "expr": True,
            },
            {
                "type": "IsFalse",
                "meta_type": "assertion",
                "description": "Fallacy Assertion",
                "passed": True,
                "expr": False,
            },
        ],
    ),
    # A module outside of the current directory where main script is placed.
    ModuleInfo(
        os.path.abspath(
            os.path.join(
                THIS_DIRECTORY,
                os.pardir,
                "extra_deps",
                "extra_suite_template.txt",
            )
        ),
        os.path.abspath(
            os.path.join(
                THIS_DIRECTORY, os.pardir, "extra_deps", "extra_suite.py"
            )
        ),
        {"ASSERTION": "fail", "RELATIVE_TOLERANCE": "0.01"},
        {"ASSERTION": "log", "RELATIVE_TOLERANCE": "0.1"},
        [
            {
                "type": "Fail",
                "meta_type": "assertion",
                "description": "Save a message into report",
                "passed": False,
                "message": "Save a message into report",
            },
            {
                "type": "IsClose",
                "meta_type": "assertion",
                "description": "Approximately Equal",
                "label": "~=",
                "passed": False,
                "first": 100,
                "second": 95,
                "rel_tol": 0.01,
                "abs_tol": 0,
            },
        ],
        [
            {
                "type": "Log",
                "meta_type": "entry",
                "description": "Save a message into report",
                "message": "Save a message into report",
            },
            {
                "type": "IsClose",
                "meta_type": "assertion",
                "description": "Approximately Equal",
                "label": "~=",
                "passed": True,
                "first": 100,
                "second": 95,
                "rel_tol": 0.1,
                "abs_tol": 0,
            },
        ],
    ),
    # A module which has a callable target and this target is defined in
    # "inner_suite.py" (no `template_path` needed here) and it will be
    # directly imported in main script
    ModuleInfo(
        "",
        "",
        {},
        {},
        [
            {
                "type": "IsFalse",
                "meta_type": "assertion",
                "description": "Fallacy Assertion",
                "passed": False,
                "expr": True,
            }
        ],
        [
            {
                "type": "IsFalse",
                "meta_type": "assertion",
                "description": "Fallacy Assertion",
                "passed": True,
                "expr": False,
            }
        ],
    ),
    # A module which has a callable target and will be scheduled as string
    # target. The module imports another module in another package.
    ModuleInfo(
        os.path.abspath(
            os.path.join(
                THIS_DIRECTORY, "tasks", "scheduled", "foo", "mod_template.txt"
            )
        ),
        os.path.abspath(
            os.path.join(THIS_DIRECTORY, "tasks", "scheduled", "foo", "mod.py")
        ),
        {"VALUE": "0"},
        {"VALUE": "1"},
        [
            {
                "type": "Equal",
                "meta_type": "assertion",
                "description": "Equal Assertion",
                "label": "==",
                "passed": False,
                "first": 1,
                "second": 0,
                "type_expected": "int",
                "type_actual": "int",
            }
        ],
        [
            {
                "type": "Equal",
                "meta_type": "assertion",
                "description": "Equal Assertion",
                "label": "==",
                "passed": True,
                "first": 1,
                "second": 1,
                "type_expected": "int",
                "type_actual": "int",
            }
        ],
    ),
    # A module which has a callable target and will be scheduled as string
    # target. The module imports another module in the parent package.
    ModuleInfo(
        os.path.abspath(
            os.path.join(
                THIS_DIRECTORY,
                "tasks",
                "scheduled",
                "foo",
                "bar",
                "suite_template.txt",
            )
        ),
        os.path.abspath(
            os.path.join(
                THIS_DIRECTORY, "tasks", "scheduled", "foo", "bar", "suite.py"
            )
        ),
        {"ANOTHER_CASE": ""},
        {
            "ANOTHER_CASE": (
                "    @testcase\n"
                "    def another_case(self, env, result):\n"
                '        result.log("Save a message into report")\n'
            )
        },
        [
            {
                "type": "NotEqual",
                "meta_type": "assertion",
                "description": "Not Equal Assertion",
                "label": "!=",
                "passed": False,
                "first": 0,
                "second": 0,
            }
        ],
        [
            {
                "type": "NotEqual",
                "meta_type": "assertion",
                "description": "Not Equal Assertion",
                "label": "!=",
                "passed": True,
                "first": 0,
                "second": 1,
            },
            {
                "type": "Log",
                "meta_type": "entry",
                "description": "Save a message into report",
                "message": "Save a message into report",
            },
        ],
    ),
]


def _compare_reports(expected_reports, actual_reports, ignore=None):
    # Compare the content of testcase reports
    assert len(expected_reports) == len(actual_reports)
    for expected_report, actual_report in zip(
        expected_reports, actual_reports
    ):
        assert len(expected_report) == len(actual_report)
        for expected_entry, actual_entry in zip(
            expected_report, actual_report
        ):
            assert (
                compare(expected_entry, actual_entry, ignore=ignore)[0] is True
            )


def _get_actual_reports(plan):
    # Generate a list test reports from Testplan for comparing
    return [
        [
            plan.interactive.test_case_report(
                test_uid="BasicTest",
                suite_uid="Suite",
                case_uid="case",
                serialized=True,
            )["entries"][0]["entries"][0]["entries"][0],
        ],
        [
            plan.interactive.test_case_report(
                test_uid="InnerTest",
                suite_uid="Suite",
                case_uid="case",
                serialized=True,
            )["entries"][0]["entries"][0]["entries"][0],
        ],
        [
            plan.interactive.test_case_report(
                test_uid="ExtraTest",
                suite_uid="Suite1",
                case_uid="case",
                serialized=True,
            )["entries"][0]["entries"][0]["entries"][0],
            plan.interactive.test_case_report(
                test_uid="ExtraTest",
                suite_uid="Suite2",
                case_uid="case",
                serialized=True,
            )["entries"][0]["entries"][0]["entries"][0],
        ],
        [
            plan.interactive.test_case_report(
                test_uid="CallableTarget",
                suite_uid="AnotherSuite",
                case_uid="case",
                serialized=True,
            )["entries"][0]["entries"][0]["entries"][0],
        ],
        [
            plan.interactive.test_case_report(
                test_uid="ScheduledTest1",
                suite_uid="Suite",
                case_uid="case",
                serialized=True,
            )["entries"][0]["entries"][0]["entries"][0],
        ],
        [
            plan.interactive.test_case_report(
                test_uid="ScheduledTest2",
                suite_uid="Suite",
                case_uid="case",
                serialized=True,
            )["entries"][0]["entries"][0]["entries"][0],
        ],
    ]


def main():
    # Create module files that contain test suite definition
    for module_info in TEST_SUITE_MODULES:
        if module_info.template_path and module_info.module_path:
            with open(module_info.template_path, "r") as fp_r, open(
                module_info.module_path, "w"
            ) as fp_w:
                fp_w.write(fp_r.read().format(**module_info.original_value))
            # module files will be removed after testing
            atexit.register(os.remove, module_info.module_path)

    # Import 3 test suites
    extra_path = os.path.abspath(os.path.join(THIS_DIRECTORY, os.pardir))
    sys.path.insert(0, extra_path)
    try:
        import basic_suite
        from tasks import inner_suite
        from extra_deps import extra_suite
    finally:
        sys.path.remove(extra_path)

    # Create an interactive Testplan
    plan = TestplanMock(
        name="MyPlan",
        interactive_port=0,
        interactive_block=False,
        extra_deps=[extra_suite],
    )

    # Add 2 MultiTest instances and trigger run of interactive executioner
    plan.add(MultiTest(name="BasicTest", suites=[basic_suite.Suite()]))
    plan.add(MultiTest(name="InnerTest", suites=[inner_suite.Suite()]))
    plan.add(
        MultiTest(
            name="ExtraTest",
            suites=[extra_suite.Suite1(), extra_suite.Suite2()],
        )
    )
    plan.schedule(target=inner_suite.make_mtest)
    plan.schedule(
        target="TaskManager.make_mtest",
        module="scheduled.suite",
        path="tasks",
        kwargs=dict(name="ScheduledTest1"),
    )
    plan.schedule(
        target="scheduled.foo.bar.suite.make_mtest",
        path="tasks",
        kwargs=dict(name="ScheduledTest2"),
    )
    plan.run()
    wait_for_interactive_start(plan)

    # Run tests
    plan.interactive.run_all_tests()

    # Check reports
    _compare_reports(
        expected_reports=[
            module_info.original_report for module_info in TEST_SUITE_MODULES
        ],
        actual_reports=_get_actual_reports(plan),
        ignore=["file_path", "line_no", "timestamp"],
    )
    assert plan.interactive.report.passed is False

    # Apply code changes, two testcase changed and one newly added
    for module_info in TEST_SUITE_MODULES:
        if module_info.template_path and module_info.module_path:
            with open(module_info.template_path, "r") as fp_r, open(
                module_info.module_path, "w"
            ) as fp_w:
                fp_w.write(fp_r.read().format(**module_info.updated_value))

    # Reload code from changed files and update report
    plan.interactive.reload(rebuild_dependencies=True)
    plan.interactive.reload_report()

    # Run tests again
    plan.interactive.run_all_tests()

    # 2 suites has new testcase added respectively
    actual_reports = _get_actual_reports(plan)
    actual_reports[1].append(
        plan.interactive.test_case_report(
            test_uid="InnerTest",
            suite_uid="Suite",
            case_uid="another_case",
            serialized=True,
        )["entries"][0]["entries"][0]["entries"][0]
    )
    actual_reports[5].append(
        plan.interactive.test_case_report(
            test_uid="ScheduledTest2",
            suite_uid="Suite",
            case_uid="another_case",
            serialized=True,
        )["entries"][0]["entries"][0]["entries"][0]
    )

    # Check reports
    _compare_reports(
        expected_reports=[
            module_info.updated_report for module_info in TEST_SUITE_MODULES
        ],
        actual_reports=actual_reports,
        ignore=["file_path", "line_no", "timestamp"],
    )

    assert plan.interactive.report.passed is True


if __name__ == "__main__":
    main()
