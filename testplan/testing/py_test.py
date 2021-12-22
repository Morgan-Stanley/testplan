"""PyTest test runner."""
import collections
import inspect
import os
import re
import traceback

import pytest
from schema import Or

from testplan.common.utils import validation
from testplan.common.config import ConfigOption
from testplan.testing import base as testing
from testplan.testing import filtering
from testplan.testing.multitest.entries import assertions
from testplan.testing.multitest.entries import base as entries_base
from testplan.testing.multitest.result import Result as MultiTestResult
from testplan.testing.multitest.entries.schemas.base import (
    registry as schema_registry,
)
from testplan.testing.multitest.entries.stdout.base import (
    registry as stdout_registry,
)
from testplan.report import (
    TestGroupReport,
    TestCaseReport,
    ReportCategories,
    Status,
    RuntimeStatus,
)

# Regex for parsing suite and case name and case parameters
_SUITE_CASE_REGEX = re.compile(
    r"^(?P<suite_name>.*)::"
    r"(?P<case_name>[^\[]+)(?:\[(?P<case_params>.+)\])?$",
    re.DOTALL,
)
# Regex for parsing case name and case parameters
_CASE_REGEX = re.compile(
    r"^(?P<case_name>[^\[]+)(?:\[(?P<case_params>.+)\])?$",
    re.DOTALL,
)


class PyTestConfig(testing.TestConfig):
    """
    Configuration object for
    :py:class:`~testplan.testing.py_test.PyTest` test runner.
    """

    @classmethod
    def get_options(cls):
        return {
            "target": Or(str, [str]),
            ConfigOption("select", default=""): str,
            ConfigOption("extra_args", default=None): Or([str], None),
            ConfigOption(
                "result", default=MultiTestResult
            ): validation.is_subclass(MultiTestResult),
        }


class PyTest(testing.Test):
    """
    PyTest plugin for Testplan. Allows tests written for PyTest to be run from
    Testplan, with the test results logged and included in the Testplan report.

    :param name: Test instance name, often used as uid of test entity.
    :type name: ``str``
    :param target: Target of PyTest configuration.
    :type target: ``str`` or ``list`` of ``str``
    :param description: Description of test instance.
    :type description: ``str``
    :param select: Selection of PyTest configuration.
    :type select: ``str``
    :param extra_args: Extra arguments passed to pytest.
    :type extra_args: ``NoneType`` or ``list`` of ``str``
    :param result: Result that contains assertion entries.
    :type result: :py:class:`~testplan.testing.multitest.result.Result`

    Also inherits all :py:class:`~testplan.testing.base.Test` options.
    """

    CONFIG = PyTestConfig

    # PyTest allows deep filtering
    filter_levels = [
        filtering.FilterLevel.TEST,
        filtering.FilterLevel.TESTSUITE,
        filtering.FilterLevel.TESTCASE,
    ]

    def __init__(
        self,
        name,
        target,
        description=None,
        select="",
        extra_args=None,
        result=MultiTestResult,
        **options,
    ):
        options.update(self.filter_locals(locals()))
        super(PyTest, self).__init__(**options)

        # Initialise a seperate plugin object to pass to PyTest. This avoids
        # namespace clashes with the PyTest object, since PyTest will scan for
        # methods that look like hooks in the plugin.
        quiet = not self._debug_logging_enabled
        self._pytest_plugin = _ReportPlugin(self, self.report, quiet)
        self._collect_plugin = _CollectPlugin(quiet)
        self._pytest_args = self._build_pytest_args()

        # Map from testsuite/testcase name to nodeid. Filled out after
        # tests are collected via dry_run().
        self._nodeids = None

    def main_batch_steps(self):
        """Specify the test steps: run the tests, then log the results."""
        self._add_step(self.run_tests)
        self._add_step(self.log_test_results, top_down=False)

    def setup(self):
        """Setup the PyTest plugin for the suite."""
        self._pytest_plugin.setup()

    def run_tests(self):
        """Run pytest and wait for it to terminate."""
        # Execute pytest with self as a plugin for hook support
        pytest_args = []
        for suite_name, testcases_to_run in self.test_context:
            pytest_args.extend(
                f"{suite_name}::{case_name}" for case_name in testcases_to_run
            )
        if pytest_args:
            pytest_args.extend(self._build_extra_args())

        with self.report.timer.record("run"):
            return_code = pytest.main(
                pytest_args or self._pytest_args, plugins=[self._pytest_plugin]
            )

            if return_code == 5:
                self.result.report.status_override = Status.UNSTABLE
                self.logger.warning("No tests were run")
            elif return_code != 0:
                self.result.report.status_override = Status.FAILED
                self.logger.error(
                    "pytest exited with return code %d", return_code
                )

    def _collect_tests(self):
        """Collect test items but do not run any."""

        # We shall restore sys.path after calling pytest.main
        # as it might prepend test rootdir in sys.path
        # but this has other problem (helper package)
        return_code = pytest.main(
            self._pytest_args + ["--collect-only"],
            plugins=[self._collect_plugin],
        )

        if return_code not in (0, 5):  # rc 5: no tests were run
            raise RuntimeError(
                f"Collection failure, exit code = {return_code}"
            )

        return self._collect_plugin.collected

    def get_test_context(self):
        """
        Inspect the test suites and cases by running PyTest with the
        --collect-only flag and passing in our collection plugin.

        :return: List containing pairs of suite name and testcase names.
        :rtype: List[Tuple[str, List[str]]]
        """
        try:
            collected = self._collect_tests()
        except RuntimeError:
            self.result.report.status_override = Status.ERROR
            self.logger.exception("Failed to collect tests.")
            return []

        # The plugin will handle converting PyTest tests into suites and
        # testcase names (with parameters).
        suites = collections.defaultdict(list)
        param_groups = collections.defaultdict(dict)
        for item in collected:
            suite_name, case_name, case_params = _case_parse(item)
            if case_params:
                case_full_name = f"{case_name}[{case_params}]"
                suites[suite_name].append(case_full_name)
                param_groups[suite_name].setdefault(case_name, []).append(
                    case_full_name
                )
            else:
                suites[suite_name].append(case_name)

        ctx = []
        for suite_name in self.cfg.test_sorter.sorted_testsuites(
            list(suites.keys())
        ):
            testcase_to_template = {
                case_name: param_template
                for param_template, cases in param_groups[suite_name].items()
                for case_name in cases
            }
            testcases_to_run = [
                case_name
                for case_name in self.cfg.test_sorter.sorted_testcases(
                    suite_name, suites[suite_name], param_groups[suite_name]
                )
                if self.cfg.test_filter.filter(
                    test=self, suite=suite_name, case=case_name
                )
                or case_name in testcase_to_template
                and self.cfg.test_filter.filter(
                    test=self,
                    suite=suite_name,
                    case=testcase_to_template[case_name],
                )
            ]
            if testcases_to_run:
                ctx.append((suite_name, testcases_to_run))

        return ctx

    def dry_run(self):
        """
        Collect tests and build a report tree skeleton, but do not run any
        tests.
        """
        self.result.report = self._new_test_report()
        self._nodeids = {
            "testsuites": {},
            "testcases": collections.defaultdict(dict),
        }

        for suite, testcases in self.test_context:
            for testcase in testcases:
                _add_empty_testcase_report(
                    suite, testcase, self.result.report, self._nodeids
                )

        return self.result

    def run_testcases_iter(self, testsuite_pattern="*", testcase_pattern="*"):
        """
        Run testcases matching the given patterns and yield testcase reports.

        :param testsuite_pattern: Filter pattern for testsuite level.
        :type testsuite_pattern: ``str``
        :param testcase_pattern: Filter pattern for testcase level.
        :type testsuite_pattern: ``str``
        :yield: generate tuples containing testcase reports and a list of the
            UIDs required to merge this into the main report tree, starting
            with the UID of this test.
        """
        if not self._nodeids:
            # Need to collect the tests so we know the nodeids for each
            # testsuite/case.
            self.dry_run()

        test_report = self._new_test_report()
        quiet = not self._debug_logging_enabled
        pytest_plugin = _ReportPlugin(self, test_report, quiet)
        pytest_plugin.setup()

        pytest_args, current_uids = self._build_iter_pytest_args(
            testsuite_pattern, testcase_pattern
        )
        # Will call `pytest.main` to run all testcases as a whole, accordingly,
        # runtime status of all these testcases will be set at the same time.
        yield {"runtime_status": RuntimeStatus.RUNNING}, current_uids

        self.logger.debug("Running PyTest with args: %r", pytest_args)
        return_code = pytest.main(pytest_args, plugins=[pytest_plugin])
        self.logger.debug("PyTest exit code: %d", return_code)

        for suite_report in test_report:
            for child_report in suite_report:
                if isinstance(child_report, TestCaseReport):
                    yield (
                        child_report,
                        [test_report.uid, suite_report.uid],
                    )
                elif isinstance(child_report, TestGroupReport):
                    if (
                        child_report.category
                        != ReportCategories.PARAMETRIZATION
                    ):
                        raise RuntimeError(
                            "Unexpected report category:"
                            f" {child_report.category}"
                        )

                    for testcase_report in child_report:
                        yield (
                            testcase_report,
                            [
                                test_report.uid,
                                suite_report.uid,
                                child_report.uid,
                            ],
                        )
                else:
                    raise TypeError(
                        f"Unexpected report type: {type(child_report)}"
                    )

    def _build_iter_pytest_args(self, testsuite_pattern, testcase_pattern):
        """
        Build the PyTest args for running a particular set of testsuites and
        testcases as specified.
        """
        if self._nodeids is None:
            raise RuntimeError("Need to call dry_run() first")

        if testsuite_pattern == "*" and testcase_pattern == "*":
            if isinstance(self.cfg.target, str):
                pytest_args = [self.cfg.target]
            else:
                pytest_args = self.cfg.target[:]
            current_uids = [self.uid()]
        elif testcase_pattern == "*":
            pytest_args = [self._nodeids["testsuites"][testsuite_pattern]]
            current_uids = [self.uid(), testsuite_pattern]
        else:
            pytest_args = [
                self._nodeids["testcases"][testsuite_pattern][testcase_pattern]
            ]
            suite_name, case_name, case_params = _split_nodeid(pytest_args[0])
            if case_params:
                current_uids = [
                    self.uid(),
                    suite_name,
                    case_name,
                    f"{case_name}[{case_params}]",
                ]
            else:
                current_uids = [self.uid(), suite_name, case_name]

        if self.cfg.extra_args:
            pytest_args.extend(self.cfg.extra_args)

        return pytest_args, current_uids

    def _build_pytest_args(self):
        """
        :return: A list of the args to be passed to PyTest
        :rtype: List[str]
        """
        if isinstance(self.cfg.target, str):
            pytest_args = [self.cfg.target]
        else:
            pytest_args = self.cfg.target[:]

        pytest_args.extend(self._build_extra_args())

        return pytest_args

    def _build_extra_args(self):
        """
        :return: A list of additional args to be passed to PyTest
        :rtype: List[str]
        """
        extra_args = []

        if self.cfg.select:
            extra_args.extend(["-k", self.cfg.select])

        if self.cfg.extra_args:
            extra_args.extend(self.cfg.extra_args)

        return extra_args


class _ReportPlugin:
    """
    Plugin object passed to PyTest. Contains hooks used to update the Testplan
    report with the status of testcases.
    """

    def __init__(self, parent, report, quiet):
        self._parent = parent
        self._report = report
        self._quiet = quiet

        # Collection of suite reports - will be initialised by the setup()
        # method.
        self._suite_reports = None

        # The current working testcase report. It needs to be stored on this
        # object since it is set and read by different callback hooks.
        self._current_case_report = None

        # Result object which supports various assertions like in MultiTest.
        # Its entries will later be added to current testcase report.
        self._current_result_obj = None

        # Create fixture function for interface
        self._fixtures_init()

    def _fixtures_init(self):
        """
        Register fixtures with pytest.
        """

        @pytest.fixture
        def result():
            """
            Return the result object for the current test case.

            :return: the result object for the current test case
            :rtype: ``Result``
            """
            return self._current_result_obj

        @pytest.fixture
        def env():
            """
            Return the testing environment.

            :return: the testing environment
            :rtype: ``Environment``
            """
            return self._parent.resources

        # PyTest picks up fixtures from all files it loads (including plugins)
        self.result = result
        self.env = env

    def setup(self):
        """Set up environment as required."""
        self._suite_reports = collections.defaultdict(collections.OrderedDict)

    def case_report(self, suite_name, case_name, case_params):
        """
        Return the case report for the specified suite and case name, creating
        it first if necessary.

        :param suite_name: the suite name to get the report for
        :type suite_name: ``str``
        :param case_name: the case name to get the report for
        :type case_name: ``str``
        :param case_params: the case parameters to get the report for
        :type case_params: ``str`` or ``NoneType``
        :return: the case report
        :rtype: :py:class:`testplan.report.testing.TestCaseReport`
        """
        if case_params is None:
            report = self._suite_reports[suite_name].get(case_name)
            if report is None:
                report = TestCaseReport(case_name, uid=case_name)
                self._suite_reports[suite_name][case_name] = report
            return report

        else:
            group_report = self._suite_reports[suite_name].get(case_name)
            if group_report is None:
                # create group report for parametrized testcases
                group_report = TestGroupReport(
                    name=case_name,
                    uid=case_name,
                    category=ReportCategories.PARAMETRIZATION,
                )
                self._suite_reports[suite_name][case_name] = group_report

            case_name = f"{case_name}[{case_params}]"
            try:
                report = group_report.get_by_uid(case_name)
            except:
                # create report of parametrized testcase
                report = TestCaseReport(name=case_name, uid=case_name)
                group_report.append(report)
            return report

    def pytest_runtest_setup(self, item):
        """
        Hook called by pytest to set up a test.

        :param item: the test item to set up (see pytest documentation)
        """
        # Extract suite name, case name and parameters
        suite_name, case_name, case_params = _case_parse(item)
        report = self.case_report(suite_name, case_name, case_params)

        try:
            func_doc = item.function.__doc__
        except AttributeError:
            func_doc = None

        if func_doc is not None:
            report.description = os.linesep.join(
                f"    {line}"
                for line in inspect.getdoc(item.function).split(os.linesep)
            )

        self._current_case_report = report
        self._current_result_obj = self._parent.cfg.result(
            stdout_style=self._parent.stdout_style,
            _scratch=self._parent.scratch,
        )

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtest_makereport(self, item, call):
        """
        Hook called to create a TestReport for each of the setup, call
        and teardown runtest phases of a test item.

        :param item: the test item to tear down (see pytest documentation)
        :param call: the ``CallInfo`` for the phase (see pytest documentation)
        """
        outcome = yield
        report = outcome.get_result()
        # Update `report.nodeid` which contains relative path of test source
        # as prefix, this information might be used later, e.g. for a skipped
        # testcase, `pytest_runtest_setup` will not be called, therefore, we
        # create testcase report in `pytest_runtest_logreport`. However, the
        # report's `nodeid` may need to be modified here (called right before
        # `pytest_runtest_logreport`) because the `nodeid` does not always
        # have the correct path of test source, if:
        #   1> multi "pytest.ini" is found in nested directories
        #   2> test source file is out of pytest root directory
        suite_name, case_name, case_params = _case_parse(item)
        report.nodeid = "::".join(
            [
                suite_name,
                f"{case_name}[{case_params}]" if case_params else case_name,
            ]
        )

    def pytest_runtest_logreport(self, report):
        """
        Hook called by pytest to report on the result of a test.

        :param report: the test report for the item just tested (see pytest
                       documentation)
        """
        if isinstance(report, list):
            report = report[0]

        if report.when == "setup":
            if report.skipped:
                if self._current_case_report is None:
                    suite_name, case_name, case_params = _split_nodeid(
                        report.nodeid
                    )
                    testcase_report = self.case_report(
                        suite_name, case_name, case_params
                    )
                else:
                    testcase_report = self._current_case_report

                # Status set to be SKIPPED if testcase is marked skip or xfail
                # lower versioned PyTest does not support this feature
                testcase_report.status_override = Status.SKIPPED
                testcase_report.runtime_status = RuntimeStatus.FINISHED

        elif report.when == "call":
            if self._current_case_report is None:
                raise RuntimeError(
                    "Cannot store testcase results to report: no report "
                    "object was created."
                )

            if self._current_result_obj.entries:
                # Add the assertion entry to the case report
                for entry in self._current_result_obj.entries:
                    stdout_renderer = stdout_registry[entry]()
                    stdout_header = stdout_renderer.get_header(entry)
                    stdout_details = stdout_renderer.get_details(entry) or ""

                    # Add 'stdout_header' and 'stdout_details' attributes to
                    # serialized entries for standard output later
                    serialized_entry = schema_registry.serialize(entry)
                    serialized_entry.update(
                        stdout_header=stdout_header,
                        stdout_details=stdout_details,
                    )
                    self._current_case_report.append(serialized_entry)

                self._current_case_report.attachments.extend(
                    self._current_result_obj.attachments
                )

            if report.failed:
                self._current_case_report.status_override = Status.FAILED
            else:
                self._current_case_report.pass_if_empty()
            self._current_case_report.runtime_status = RuntimeStatus.FINISHED

        elif report.when == "teardown":
            pass

    def pytest_runtest_teardown(self, item):
        """
        Hook called by pytest to tear down a test.

        :param item: the test item to tear down (see pytest documentation)
        """
        self._current_case_report = None
        self._current_result_obj = None

    def pytest_exception_interact(self, node, call, report):
        """
        Hook called when an exception raised and it can be handled. This hook
        is only called if the exception is not an PyTest internal exception.

        :param node: PyTest Function or Module object
        :param call: PyTest CallInfo object
        :param report: PyTest TestReport or CollectReport object
        """
        if call.when in ("memocollect", "collect"):
            # Failed to collect tests: log to console and mark the report as
            # ERROR.
            self._report.logger.error(
                "".join(
                    traceback.format_exception(
                        call.excinfo.type, call.excinfo.value, call.excinfo.tb
                    )
                )
            )
            self._report.status_override = Status.ERROR

        elif self._current_case_report is not None:
            # Log assertion errors or exceptions in testcase report
            trace = call.excinfo.traceback[-1]
            message = (
                getattr(call.excinfo.value, "message", None)
                or getattr(call.excinfo.value, "msg", None)
                or getattr(call.excinfo.value, "args", None)
                or ""
            )
            if isinstance(message, (tuple, list)):
                message = message[0]

            header = (
                (
                    "Assertion - Fail"
                    if call.excinfo.typename == "AssertionError"
                    else "Exception raised"
                )
                if call.when == "call"
                else f"{call.when} - Fail"
            )
            details = (
                (
                    f"File: {trace.path}\n"
                    f"Line: {trace.lineno + 1}\n"
                    f"{call.excinfo.typename}: {message}"
                )
                if call.excinfo.typename == "AssertionError"
                else (
                    report.longreprtext
                    if hasattr(report, "longreprtext")
                    else str(report.longrepr)
                )
            )

            assertion_obj = assertions.RawAssertion(
                description=header, content=details, passed=False
            )
            serialized_obj = schema_registry.serialize(assertion_obj)
            self._current_case_report.append(serialized_obj)
            self._current_case_report.status_override = Status.FAILED

            for capture, description in (
                ("caplog", "Captured Log"),
                ("capstdout", "Captured Stdout"),
                ("capstderr", "Captured Stderr"),
            ):
                message = getattr(report, capture)
                if message:
                    assertion_obj = entries_base.Log(
                        message, description=description
                    )
                    serialized_obj = schema_registry.serialize(assertion_obj)
                    self._current_case_report.append(serialized_obj)

        else:
            self._report.logger.error(
                "Exception occured outside of a testcase: during %s", call.when
            )
            self._report.logger.error(
                "".join(
                    traceback.format_exception(
                        call.excinfo.type, call.excinfo.value, call.excinfo.tb
                    )
                )
            )

    @pytest.hookimpl(trylast=True)
    def pytest_configure(self, config):
        """
        Hook called by pytest upon startup. Disable output to terminal.

        :param config: pytest config object
        """
        if self._quiet:
            config.pluginmanager.unregister(name="terminalreporter")

    def pytest_unconfigure(self, config):
        """
        Hook called by pytest before exiting. Collate suite reports.

        :param config: pytest config object
        """
        # Collate suite reports
        for suite_name, cases in self._suite_reports.items():
            suite_report = TestGroupReport(
                name=suite_name,
                uid=suite_name,
                category=ReportCategories.TESTSUITE,
            )

            for case in cases.values():
                suite_report.append(case)

            self._report.append(suite_report)


class _CollectPlugin:
    """
    PyTest plugin used when collecting tests. Provides access to the collected
    test suites and testcases via the `collected` property.
    """

    def __init__(self, quiet):
        self._quiet = quiet
        self.collected = None

    @pytest.hookimpl(trylast=True)
    def pytest_configure(self, config):
        """
        Hook called by pytest upon startup. Disable output to terminal.

        :param config: pytest config object
        """
        if self._quiet:
            config.pluginmanager.unregister(name="terminalreporter")

    def pytest_collection_finish(self, session):
        """
        PyTest hook, called after collection is finished.
        """
        self.collected = session.items


def _case_parse(item):
    """
    Parse a nodeid of a pytest item into a shortened URL-safe suite name,
    case name, and case parameters.

    :param item: the pytest item
    :type item: ``object``
    :raises ValueError: if nodeid of pytest item is invalid
    :return: a tuple consisting of (suite name, case name, case parameters)
    :rtype: ``tuple``
    """
    suite_name, case_name, case_params = _split_nodeid(item.nodeid)
    # `suite_name` could be one of the following values:
    #   - "/path/to/test_source.py::TestSuite"
    #   - "/path/to/test_source.py"
    #   - "::TestSuite"
    #   - ""
    # the part before symbol :: (if any) or the whole `suite_name` will be
    # replaced by relative path of the test source
    return (
        "::".join([os.path.relpath(item.path)] + suite_name.split("::")[1:]),
        case_name,
        case_params,
    )


def _split_nodeid(nodeid):
    """
    Split a nodeid into its full suite name, case name, and case parameters.

    :param nodeid: the test nodeid
    :type nodeid: ``str``
    :raises ValueError: if nodeid is invalid
    :return: a tuple consisting of (suite name, case name, case parameters)
    :rtype: ``tuple``
    """
    match = _SUITE_CASE_REGEX.match(nodeid.replace("::()::", "::"))

    if match is None:
        raise ValueError(f"Invalid nodeid: {nodeid}")

    suite_name, case_name, case_params = match.groups()

    return suite_name, case_name, case_params


def _add_empty_testcase_report(suite_name, case_name, test_report, nodeids):
    """Add an empty testcase report to the test report."""
    case_name, case_params = _CASE_REGEX.match(case_name).groups()

    try:
        suite_report = test_report[suite_name]
    except KeyError:
        suite_report = TestGroupReport(
            name=suite_name,
            uid=suite_name,
            category=ReportCategories.TESTSUITE,
        )
        test_report.append(suite_report)
        nodeids["testsuites"][suite_name] = suite_name

    if case_params:
        try:
            param_report = suite_report[case_name]
        except KeyError:
            param_report = TestGroupReport(
                name=case_name,
                uid=case_name,
                category=ReportCategories.PARAMETRIZATION,
            )
            suite_report.append(param_report)
            nodeids["testcases"][suite_name][
                case_name
            ] = f"{suite_name}::{case_name}"

        param_case_name = f"{case_name}[{case_params}]"
        param_report.append(
            TestCaseReport(name=param_case_name, uid=param_case_name)
        )
        nodeids["testcases"][suite_name][
            param_case_name
        ] = f"{suite_name}::{case_name}[{case_params}]"
    else:
        suite_report.append(TestCaseReport(name=case_name, uid=case_name))
        nodeids["testcases"][suite_name][
            case_name
        ] = f"{suite_name}::{case_name}"
