"""Base classes for all Tests"""
import functools
import os
import subprocess
import sys
import warnings
from datetime import timezone
from enum import Enum
from typing import (
    Callable,
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
    Union,
)

from schema import And, Or, Use

from testplan import defaults
from testplan.common.config import ConfigOption, validate_func
from testplan.common.entity import (
    Resource,
    ResourceStatus,
    ResourceTimings,
    Runnable,
    RunnableConfig,
    RunnableResult,
)
from testplan.common.remote.remote_driver import RemoteDriver
from testplan.common.report import ReportCategories, RuntimeStatus
from testplan.common.report import Status as ReportStatus
from testplan.common.utils import interface, strings, validation
from testplan.common.utils.composer import compose_contexts
from testplan.common.utils.context import render
from testplan.common.utils.process import (
    enforce_timeout,
    kill_process,
    subprocess_popen,
)
from testplan.common.utils.timing import format_duration, parse_duration
from testplan.report import TestCaseReport, TestGroupReport, test_styles
from testplan.testing import common, filtering, ordering, result, tagging
from testplan.testing.environment import TestEnvironment, parse_dependency
from testplan.testing.multitest.driver.connection import DriverConnectionGraph
from testplan.testing.multitest.entries.assertions import RawAssertion
from testplan.testing.multitest.entries.base import Attachment
from testplan.testing.multitest.test_metadata import TestMetadata

TEST_INST_INDENT = 2
SUITE_INDENT = 4
TESTCASE_INDENT = 6
ASSERTION_INDENT = 8


class ResourceHooks(str, Enum):
    # suite names
    ENVIRONMENT_START = "Environment Start"
    ENVIRONMENT_STOP = "Environment Stop"
    ERROR_HANDLER = "Error Handler"

    # case names
    STARTING = "Starting"
    STOPPING = "Stopping"
    BEFORE_START = "Before Start"
    AFTER_START = "After Start"
    BEFORE_STOP = "Before Stop"
    AFTER_STOP = "After Stop"

    def __str__(self) -> str:
        return self.value


def _test_name_sanity_check(name: str) -> bool:
    """
    Checks whether some of the reserved name components are used.

    :param name: name of the entry
    :return: True if no reserved components are in the name
    :raises ValueError: if any of the reserved components is in the name
    """
    for s in [" - part", ":"]:
        if s in name:
            raise ValueError(
                f'"{s}" is specially treated by Testplan, '
                "it cannot be used in Test names."
            )
    return True


class TestConfig(RunnableConfig):
    """Configuration object for :py:class:`~testplan.testing.base.Test`."""

    @classmethod
    def get_options(cls):
        start_stop_signature = Or(
            None, validate_func("env"), validate_func("env", "result")
        )

        return {
            "name": And(
                str,
                lambda s: len(s) <= defaults.MAX_TEST_NAME_LENGTH,
                _test_name_sanity_check,
            ),
            ConfigOption("description", default=None): Or(str, None),
            ConfigOption("environment", default=[]): Or(
                [Or(Resource, RemoteDriver)], validate_func()
            ),
            ConfigOption("dependencies", default=None): Or(
                None, Use(parse_dependency), validate_func()
            ),
            ConfigOption("initial_context", default={}): Or(
                dict, validate_func()
            ),
            ConfigOption("before_start", default=None): start_stop_signature,
            ConfigOption("after_start", default=None): start_stop_signature,
            ConfigOption("before_stop", default=None): start_stop_signature,
            ConfigOption("after_stop", default=None): start_stop_signature,
            ConfigOption("error_handler", default=None): start_stop_signature,
            ConfigOption("test_filter"): filtering.BaseFilter,
            ConfigOption("test_sorter"): ordering.BaseSorter,
            ConfigOption("stdout_style"): test_styles.Style,
            ConfigOption("skip_strategy"): Use(
                common.SkipStrategy.from_test_option
            ),
            ConfigOption("tags", default=None): Or(
                None, Use(tagging.validate_tag_value)
            ),
            ConfigOption(
                "result", default=result.Result
            ): validation.is_subclass(result.Result),
        }


class TestResult(RunnableResult):
    """
    Result object for
    :py:class:`~testplan.testing.base.Test` runnable
    test execution framework base class and all sub classes.

    Contains a test ``report`` object.
    """

    def __init__(self) -> None:
        super(TestResult, self).__init__()
        self.report = None


class Test(Runnable):
    """
    Base test instance class. Any runnable that runs a test
    can inherit from this class and override certain methods to
    customize functionality.

    :param name: Test instance name, often used as uid of test entity.
    :param description: Description of test instance.
    :param environment: List of
        :py:class:`drivers <testplan.testing.multitest.driver.base.Driver>` to
        be started and made available on tests execution. Can also take a
        callable that returns the list of drivers.
    :param dependencies: driver start-up dependencies as a directed graph,
        e.g {server1: (client1, client2)} indicates server1 shall start before
        client1 and client2. Can also take a callable that returns a dict.
    :param initial_context: key: value pairs that will be made available as
        context for drivers in environment. Can also take a callable that
        returns a dict.
    :param test_filter: Class with test filtering logic.
    :param test_sorter: Class with tests sorting logic.
    :param before_start: Callable to execute before starting the environment.
    :param after_start: Callable to execute after starting the environment.
    :param before_stop: Callable to execute before stopping the environment.
    :param after_stop: Callable to execute after stopping the environment.
    :param error_handler: Callable to execute when a step hits an exception.
    :param stdout_style: Console output style.
    :param tags: User defined tag value.
    :param result: Result class definition for result object made available
        from within the testcases.

    Also inherits all
    :py:class:`~testplan.common.entity.base.Runnable` options.
    """

    CONFIG = TestConfig
    RESULT = TestResult
    ENVIRONMENT = TestEnvironment

    # Base test class only allows Test (top level) filtering
    filter_levels = [filtering.FilterLevel.TEST]

    def __init__(
        self,
        name: str,
        description: str = None,
        environment: Union[list, Callable] = None,
        dependencies: Union[dict, Callable] = None,
        initial_context: Union[dict, Callable] = None,
        before_start: callable = None,
        after_start: callable = None,
        before_stop: callable = None,
        after_stop: callable = None,
        error_handler: callable = None,
        test_filter: filtering.BaseFilter = None,
        test_sorter: ordering.BaseSorter = None,
        stdout_style: test_styles.Style = None,
        tags: Union[str, Iterable[str]] = None,
        result: Type[result.Result] = result.Result,
        **options,
    ):
        options.update(self.filter_locals(locals()))
        super(Test, self).__init__(**options)

        if ":" in self.cfg.name:
            warnings.warn(
                "Multitest object contains colon in name: {self.cfg.name}"
            )

        self._test_context = None
        self._discover_path = None

        self._init_test_report()
        self._env_built = False

        self.log_testcase_status = functools.partial(
            self._log_status, indent=TESTCASE_INDENT
        )

    def __str__(self) -> str:
        return f"{self.__class__.__name__}[{self.name}]"

    def _log_status(self, report: TestGroupReport, indent: int) -> None:
        """Log the test status for a report at the given indent level."""
        self.logger.log_test_status(
            name=report.name, status=report.status, indent=indent
        )

    def _new_test_report(self) -> TestGroupReport:
        return TestGroupReport(
            name=self.cfg.name,
            description=self.cfg.description,
            category=self.__class__.__name__.lower(),
            tags=self.cfg.tags,
            env_status=ResourceStatus.STOPPED,
        )

    def _init_test_report(self) -> None:
        self.result.report = self._new_test_report()

    def get_tags_index(self) -> Union[str, Iterable[str], Dict]:
        """
        Return the tag index that will be used for filtering.
        By default, this is equal to the native tags for this object.

        However, subclasses may build larger tag indices
        by collecting tags from their children for example.
        """
        return self.cfg.tags or {}

    def get_filter_levels(self) -> List[filtering.FilterLevel]:
        if not self.filter_levels:
            raise ValueError(f"`filter_levels` is not defined by {self}")
        return self.filter_levels

    @property
    def name(self) -> str:
        """Instance name."""
        return self.cfg.name

    @property
    def description(self) -> str:
        return self.cfg.description

    @property
    def report(self) -> TestGroupReport:
        """Shortcut for the test report."""
        return self.result.report

    @property
    def stdout_style(self):
        """Stdout style input."""
        return self.cfg.stdout_style

    @property
    def test_context(self):
        if self._test_context is None:
            self._test_context = self.get_test_context()
        return self._test_context

    def reset_context(self) -> None:
        self._test_context = None

    def get_test_context(self):
        raise NotImplementedError

    def get_stdout_style(self, passed: bool):
        """Stdout style for status."""
        return self.stdout_style.get_style(passing=passed)

    def get_metadata(self) -> TestMetadata:
        return TestMetadata(self.name, self.description, [])

    def uid(self) -> str:
        """Instance name uid."""
        return self.cfg.name

    def should_run(self) -> bool:
        return (
            self.cfg.test_filter.filter(
                test=self,
                # Instance level shallow filtering is applied by default
                suite=None,
                case=None,
            )
            and self.test_context
        )

    def should_log_test_result(
        self, depth: int, test_obj, style
    ) -> Tuple[bool, int]:
        """
        Whether to log test result and if yes, then with what indent.

        :return: whether to log test results (Suite report, Testcase report, or
            result of assertions) and the indent that should be kept at start of lines
        :raises ValueError: if met with an unexpected test group category
        :raises TypeError: if meth with an unsupported test object
        """
        if isinstance(test_obj, TestGroupReport):
            if not depth:
                return style.display_test, TEST_INST_INDENT
            elif test_obj.category == ReportCategories.TESTSUITE:
                return style.display_testsuite, SUITE_INDENT
            elif test_obj.category == ReportCategories.SYNTHESIZED:
                # NOTE: keep logging style for sythesized suites for hooks
                return style.display_testsuite, SUITE_INDENT
            elif test_obj.category == ReportCategories.PARAMETRIZATION:
                return False, 0  # DO NOT display
            else:
                raise ValueError(
                    f"Unexpected test group category: {test_obj.category}"
                )
        elif isinstance(test_obj, TestCaseReport):
            return style.display_testcase, TESTCASE_INDENT
        elif isinstance(test_obj, dict):
            return style.display_assertion, ASSERTION_INDENT
        raise TypeError(f"Unsupported test object: {test_obj}")

    def log_test_results(self, top_down: bool = True):
        """
        Log test results. i.e. ProcessRunnerTest or PyTest.

        :param top_down: Flag logging test results using a top-down approach
            or a bottom-up approach.
        """
        report = self.result.report
        items = report.flatten(depths=True)
        entries = []  # Composed of (depth, report obj)

        def log_entry(depth, obj):
            name = obj["description"] if isinstance(obj, dict) else obj.name
            try:
                passed = obj["passed"] if isinstance(obj, dict) else obj.passed
            except KeyError:
                passed = True  # Some report entries (i.e. Log) always pass

            style = self.get_stdout_style(passed)
            display, indent = self.should_log_test_result(depth, obj, style)

            if display:
                if isinstance(obj, dict):
                    if obj["type"] == "RawAssertion":
                        header = obj["description"]
                        details = obj["content"]
                    elif "stdout_header" in obj and "stdout_details" in obj:
                        header = obj["stdout_header"]
                        details = obj["stdout_details"]
                    else:
                        return
                    if style.display_assertion:
                        self.logger.user_info(indent * " " + header)
                    if details and style.display_assertion_detail:
                        details = os.linesep.join(
                            (indent + 2) * " " + line
                            for line in details.split(os.linesep)
                        )
                        self.logger.user_info(details)
                else:
                    self.logger.log_test_status(
                        name, obj.status, indent=indent
                    )

        for depth, obj in items:
            if top_down:
                log_entry(depth, obj)
            else:
                while entries and depth <= entries[-1][0]:
                    log_entry(*(entries.pop()))
                entries.append((depth, obj))

        while entries:
            log_entry(*(entries.pop()))

    def propagate_tag_indices(self) -> None:
        """
        Basic step for propagating tag indices of the test report tree.
        This step may be necessary if the report tree is created
        in parts and then added up.
        """
        if len(self.report):
            self.report.propagate_tag_indices()

    def _init_context(self) -> None:
        if callable(self.cfg.initial_context):
            self.resources._initial_context = self.cfg.initial_context()
        else:
            self.resources._initial_context = self.cfg.initial_context

    def _build_environment(self) -> None:
        # build environment only once in interactive mode
        if self._env_built:
            return

        if callable(self.cfg.environment):
            drivers = self.cfg.environment()
        else:
            drivers = self.cfg.environment
        for driver in drivers:
            driver.parent = self
            driver.cfg.parent = self.cfg
            self.resources.add(driver)

        self._env_built = True

    def _set_dependencies(self) -> None:
        if callable(self.cfg.dependencies):
            deps = parse_dependency(self.cfg.dependencies())
        else:
            deps = self.cfg.dependencies
        self.resources.set_dependency(deps)

    def _start_resource(self) -> None:
        if len(self.resources) == 0:
            return
        case_report = self._create_case_or_override(
            ResourceHooks.ENVIRONMENT_START.value, ResourceHooks.STARTING
        )
        self.resources.start()
        if self.driver_info:
            self._record_driver_timing(
                ResourceTimings.RESOURCE_SETUP, case_report
            )
            self._record_driver_connection(case_report)
        case_report.pass_if_empty()

        if self.resources.start_exceptions:
            for msg in self.resources.start_exceptions.values():
                case_report.logger.error(msg)
            case_report.status_override = ReportStatus.ERROR
            case_report.runtime_status = RuntimeStatus.NOT_RUN
        else:
            case_report.runtime_status = RuntimeStatus.FINISHED
        pattern = f"{self.name}:{ResourceHooks.ENVIRONMENT_START}:{ResourceHooks.STARTING}"
        self._xfail(pattern, case_report)

    def _stop_resource(self, is_reversed=True) -> None:
        if len(self.resources) == 0:
            return
        case_report = self._create_case_or_override(
            ResourceHooks.ENVIRONMENT_STOP.value, ResourceHooks.STOPPING.value
        )
        self.resources.stop(is_reversed=is_reversed)
        if self.driver_info:
            self._record_driver_timing(
                ResourceTimings.RESOURCE_TEARDOWN, case_report
            )
        case_report.pass_if_empty()

        if self.resources.stop_exceptions:
            for msg in self.resources.stop_exceptions.values():
                case_report.logger.error(msg)
            case_report.status_override = ReportStatus.ERROR
        drivers = set(self.resources.start_exceptions.keys())
        drivers.update(self.resources.stop_exceptions.keys())
        for driver in drivers:
            if driver.cfg.report_errors_from_logs:
                error_log = os.linesep.join(driver.fetch_error_log())
                if error_log:
                    case_report.logger.error(error_log)
        pattern = f"{self.name}:{ResourceHooks.ENVIRONMENT_STOP}:{ResourceHooks.STOPPING}"
        self._xfail(pattern, case_report)

    def _finish_resource_report(self, suite_name):
        if self.result.report.has_uid(suite_name):
            self.result.report[
                suite_name
            ].runtime_status = RuntimeStatus.FINISHED

    def add_pre_resource_steps(self) -> None:
        """Runnable steps to be executed before environment starts."""
        self._add_step(self.timer.start, "setup")
        self._add_step(self._init_context)
        self._add_step(self._build_environment)
        self._add_step(self._set_dependencies)

    def add_start_resource_steps(self) -> None:
        self._add_step(
            self._run_resource_hook,
            hook=self.cfg.before_start,
            hook_name=ResourceHooks.BEFORE_START.value,
            suite_name=ResourceHooks.ENVIRONMENT_START.value,
        )

        self._add_step(self._start_resource)

        self._add_step(
            self._run_resource_hook,
            hook=self.cfg.after_start,
            hook_name=ResourceHooks.AFTER_START.value,
            suite_name=ResourceHooks.ENVIRONMENT_START.value,
        )

        self._add_step(
            self._finish_resource_report,
            suite_name=ResourceHooks.ENVIRONMENT_START.value,
        )

    def add_stop_resource_steps(self) -> None:
        self._add_step(
            self._run_resource_hook,
            hook=self.cfg.before_stop,
            hook_name=ResourceHooks.BEFORE_STOP.value,
            suite_name=ResourceHooks.ENVIRONMENT_STOP.value,
        )
        self._add_step(self._stop_resource, is_reversed=True)

        self._add_step(
            self._run_resource_hook,
            hook=self.cfg.after_stop,
            hook_name=ResourceHooks.AFTER_STOP.value,
            suite_name=ResourceHooks.ENVIRONMENT_STOP.value,
        )
        self._add_step(
            self._finish_resource_report,
            suite_name=ResourceHooks.ENVIRONMENT_STOP.value,
        )

    def add_pre_main_steps(self) -> None:
        """Runnable steps to run after environment started."""
        self._add_step(self.timer.end, "setup")

    def add_post_main_steps(self) -> None:
        """Runnable steps to run before environment stopped."""
        self._add_step(self.timer.start, "teardown")

    def add_post_resource_steps(self) -> None:
        """Runnable steps to run after environment stopped."""
        self._add_step(self._run_error_handler)
        self._add_step(self.timer.end, "teardown")

    def run_testcases_iter(
        self, testsuite_pattern: str = "*", testcase_pattern: str = "*"
    ) -> None:
        """
        For a Test to be run interactively, it must implement this method.

        It is expected to run tests iteratively and yield a tuple containing
        a testcase report and the list of parent UIDs required to merge the
        testcase report into the main report tree.

        If it is not possible or very inefficient to run individual testcases
        in an iteratie manner, this method may instead run all the testcases
        in a batch and then return an iterator for the testcase reports and
        parent UIDs.

        :param testsuite_pattern: Filter pattern for testsuite level.
        :param testcase_pattern: Filter pattern for testcase level.
        :yield: generate tuples containing testcase reports and a list of the
            UIDs required to merge this into the main report tree, starting
            with the UID of this test.
        """
        raise NotImplementedError

    def start_test_resources(self) -> None:
        """
        Start all test resources but do not run any tests. Used in the
        interactive mode when environments may be started/stopped on demand.
        The base implementation is very simple but may be overridden in sub-
        classes to run additional setup pre- and post-environment start.
        """
        # in case this is called more than once from interactive
        self.report.timer.clear()

        self._add_step(self.setup)
        self.add_pre_resource_steps()
        self.add_start_resource_steps()
        self.add_pre_main_steps()

        self._run()

    def stop_test_resources(self) -> None:
        """
        Stop all test resources. As above, this method is used for the
        interactive mode and is very simple in this base Test class, but may
        be overridden by sub-classes.
        """

        self.add_post_main_steps()
        self.add_stop_resource_steps()
        self.add_post_resource_steps()
        self._add_step(self.teardown)

        self._run()

    # TODO: this just for API compatibility
    # move RuntimeEnv to Test, or get rid of it?
    def _get_runtime_environment(self, testcase_name, testcase_report):
        return self.resources

    def _get_hook_context(self, case_report):
        return (
            case_report.timer.record("run"),
            case_report.logged_exceptions(),
        )

    def _run_error_handler(self) -> None:
        """
        This method runs error_handler hook.
        """

        if self.cfg.error_handler:
            self._run_resource_hook(
                self.cfg.error_handler,
                self.cfg.error_handler.__name__,
                ResourceHooks.ERROR_HANDLER,
            )

    def _get_suite_or_create(self, suite_name: str) -> TestGroupReport:
        if self.result.report.has_uid(suite_name):
            suite_report = self.result.report[suite_name]
        else:
            suite_report = TestGroupReport(
                name=suite_name,
                category=ReportCategories.SYNTHESIZED,
            )
            self.result.report.append(suite_report)
        return suite_report

    def _create_case_or_override(
        self, suite_name: str, case_name: str, description: str = ""
    ) -> TestCaseReport:
        suite_report = self._get_suite_or_create(suite_name)
        case_report = TestCaseReport(
            name=case_name,
            description=description,
            category=ReportCategories.SYNTHESIZED,
        )
        if suite_report.has_uid(case_name):
            suite_report.set_by_uid(case_name, case_report)
        else:
            suite_report.append(case_report)
        return case_report

    def _run_resource_hook(
        self, hook: Optional[Callable], hook_name: str, suite_name: str
    ) -> None:
        # TODO: env or env, result signature is mandatory not an "if"
        """
        This method runs post/pre_start/stop hooks. User can optionally make
        use of assertions if the function accepts both ``env`` and ``result``
        arguments.

        These functions are also run within report error logging context,
        meaning that if something goes wrong we will have the stack trace
        in the final report.
        """
        if not hook:
            return

        case_report = self._create_case_or_override(
            suite_name, hook_name, description=strings.get_docstring(hook)
        )

        case_result = self.cfg.result(
            stdout_style=self.stdout_style,
            _scratch=self.scratch,
            _collect_code_context=self.collect_code_context,
        )
        runtime_env = self._get_runtime_environment(
            testcase_name=hook_name,
            testcase_report=case_report,
        )
        case_report.pass_if_empty()
        try:
            interface.check_signature(hook, ["env", "result"])
            hook_args = (runtime_env, case_result)
        except interface.MethodSignatureMismatch:
            interface.check_signature(hook, ["env"])
            hook_args = (runtime_env,)
        with compose_contexts(*self._get_hook_context(case_report)):
            try:
                res = hook(*hook_args)
            except Exception as e:
                res = e
                raise

        case_report.extend(case_result.serialized_entries)
        case_report.attachments.extend(case_result.attachments)

        if self.get_stdout_style(case_report.passed).display_testcase:
            self.log_testcase_status(case_report)

        pattern = ":".join([self.name, suite_name, hook_name])
        self._xfail(pattern, case_report)
        case_report.runtime_status = RuntimeStatus.FINISHED

        if isinstance(res, Exception):
            raise res
        return res

    def _dry_run_resource_hook(
        self, hook: Optional[Callable], hook_name: str, suite_name: str
    ) -> None:
        if not hook:
            return
        self._create_case_or_override(
            suite_name, hook_name, description=strings.get_docstring(hook)
        )

    def _dry_run_testsuites(self) -> None:
        suites_to_run = self.test_context

        for testsuite, testcases in suites_to_run:
            testsuite_report = TestGroupReport(
                name=testsuite,
                category=ReportCategories.TESTSUITE,
            )

            for testcase in testcases:
                testcase_report = TestCaseReport(name=testcase)
                testsuite_report.append(testcase_report)

            self.result.report.append(testsuite_report)

    def dry_run(self) -> RunnableResult:
        """
        Return an empty report skeleton for this test including all
        testsuites, testcases etc. hierarchy. Does not run any tests.
        """

        self.result.report = self._new_test_report()

        for hook, hook_name, suite_name in (
            (
                self.cfg.before_start,
                ResourceHooks.BEFORE_START.value,
                ResourceHooks.ENVIRONMENT_START.value,
            ),
            (
                (lambda: None) if self.cfg.environment else None,
                ResourceHooks.STARTING.value,
                ResourceHooks.ENVIRONMENT_START.value,
            ),
            (
                self.cfg.after_start,
                ResourceHooks.AFTER_START.value,
                ResourceHooks.ENVIRONMENT_START.value,
            ),
        ):
            self._dry_run_resource_hook(hook, hook_name, suite_name)
        self._dry_run_testsuites()

        for hook, hook_name, suite_name in (
            (
                self.cfg.before_stop,
                ResourceHooks.BEFORE_STOP.value,
                ResourceHooks.ENVIRONMENT_STOP.value,
            ),
            (
                (lambda: None) if self.cfg.environment else None,
                ResourceHooks.STOPPING.value,
                ResourceHooks.ENVIRONMENT_STOP.value,
            ),
            (
                self.cfg.after_stop,
                ResourceHooks.AFTER_STOP.value,
                ResourceHooks.ENVIRONMENT_STOP.value,
            ),
        ):
            self._dry_run_resource_hook(hook, hook_name, suite_name)

        return self.result

    def set_discover_path(self, path: str) -> None:
        """
        If the Test is materialized from a task that is discovered outside pwd(),
        this might be needed for binary/library path derivation to work properly.
        :param path: the absolute path where the task has been discovered
        """

        self._discover_path = path

    def _xfail(self, pattern: str, report) -> None:
        """Utility xfail a report entry if found in xfail_tests"""
        if getattr(self.cfg, "xfail_tests", None):
            found = self.cfg.xfail_tests.get(pattern)
            if found:
                report.xfail(strict=found["strict"])

    def _record_driver_timing(
        self, setup_or_teardown: str, case_report: TestCaseReport
    ) -> None:
        import plotly.express as px

        case_result = self.cfg.result(
            stdout_style=self.stdout_style, _scratch=self.scratch
        )

        def _try_asutc(dt_or_none):
            if dt_or_none:
                return dt_or_none.astimezone(tz=timezone.utc)
            return None

        # input for tablelog
        table = [
            {
                "Driver Class": driver.__class__.__name__,
                "Driver Name": driver.name,
                "Start Time (UTC)": _try_asutc(
                    driver.timer.last(setup_or_teardown).start
                ),
                "Stop Time (UTC)": _try_asutc(
                    driver.timer.last(setup_or_teardown).end
                ),
                "Duration(seconds)": driver.timer.last(
                    setup_or_teardown
                ).elapsed,
            }
            for driver in self.resources
            if setup_or_teardown in driver.timer.keys()
        ]
        table.sort(key=lambda entry: entry["Start Time (UTC)"])

        # input for plotly
        px_input = {
            "Start Time (UTC)": [],
            "Stop Time (UTC)": [],
            "Driver Name": [],
        }
        for driver in table:
            if driver["Stop Time (UTC)"]:
                px_input["Driver Name"].append(driver["Driver Name"])
                px_input["Start Time (UTC)"].append(driver["Start Time (UTC)"])
                px_input["Stop Time (UTC)"].append(driver["Stop Time (UTC)"])

            # format tablelog entries to be human readable
            if driver["Start Time (UTC)"]:
                driver["Start Time (UTC)"] = driver[
                    "Start Time (UTC)"
                ].strftime("%H:%M:%S.%f")
            if driver["Stop Time (UTC)"]:
                driver["Stop Time (UTC)"] = driver["Stop Time (UTC)"].strftime(
                    "%H:%M:%S.%f"
                )

        case_result.table.log(
            table, description=f"Driver {setup_or_teardown.capitalize()} Info"
        )

        # values are arbitary
        padding = 150
        row_size = 25
        height = padding + row_size * len(px_input["Driver Name"])
        if height == padding:
            # min height
            height = padding + row_size
        fig = px.timeline(
            px_input,
            x_start="Start Time (UTC)",
            x_end="Stop Time (UTC)",
            y="Driver Name",
            height=height,
        )
        fig.update_yaxes(autorange="reversed", automargin=True)
        case_result.plotly(
            fig,
            description=f"Driver {setup_or_teardown.capitalize()} Timeline",
        )

        case_report.extend(case_result.serialized_entries)
        case_report.attachments.extend(case_result.attachments)

    def _record_driver_connection(self, case_report: TestCaseReport) -> None:
        case_result = self.cfg.result(
            stdout_style=self.stdout_style, _scratch=self.scratch
        )
        graph = DriverConnectionGraph(self.resources)
        for driver in self.resources:
            for conn_info in driver.get_connections():
                graph.add_connection(str(driver), conn_info)
        graph.set_nodes_and_edges()
        case_result.flow_chart(
            graph.nodes, graph.edges, description="Driver Connections"
        )
        case_report.extend(case_result.serialized_entries)

    @property
    def driver_info(self) -> bool:
        # handle possibly missing ``driver_info``
        if not hasattr(self.cfg, "driver_info"):
            return False
        return self.cfg.driver_info

    @property
    def collect_code_context(self) -> bool:
        """
        Collecting the file path, line number and code context of the assertions
        if enabled.
        """
        return getattr(self.cfg, "collect_code_context", False)


class ProcessRunnerTestConfig(TestConfig):
    """
    Configuration object for
    :py:class:`~testplan.testing.base.ProcessRunnerTest`.
    """

    @classmethod
    def get_options(cls):
        return {
            "binary": str,
            ConfigOption("proc_env", default=None): Or(dict, None),
            ConfigOption("proc_cwd", default=None): Or(str, None),
            ConfigOption("timeout", default=None): Or(
                None, float, int, Use(parse_duration)
            ),
            ConfigOption("ignore_exit_codes", default=[]): [int],
            ConfigOption("pre_args", default=[]): list,
            ConfigOption("post_args", default=[]): list,
        }


class ProcessRunnerTest(Test):
    """
    A test runner that runs the tests in a separate subprocess.
    This is useful for running 3rd party testing frameworks (e.g. JUnit, GTest)

    Test report will be populated by parsing the generated report output file
    (report.xml file by default.)

    :param name: Test instance name, often used as uid of test entity.
    :param binary: Path to the application binary or script.
    :param description: Description of test instance.
    :param proc_env: Environment overrides for ``subprocess.Popen``;
        context value (when referring to other driver) and jinja2 template (when
        referring to self) will be resolved.
    :param proc_cwd: Directory override for ``subprocess.Popen``.
    :param timeout: Optional timeout for the subprocess. If a process
                    runs longer than this limit, it will be killed
                    and test will be marked as ``ERROR``.

                    String representations can be used as well as
                    duration in seconds. (e.g. 10, 2.3, '1m 30s', '1h 15m')
    :param ignore_exit_codes: When the test process exits with nonzero status
                    code, the test will be marked as ``ERROR``.
                    This can be disabled by providing a list of
                    numbers to ignore.
    :param pre_args: List of arguments to be prepended before the
        arguments of the test runnable.
    :param post_args: List of arguments to be appended before the
        arguments of the test runnable.

    Also inherits all
    :py:class:`~testplan.testing.base.Test` options.
    """

    CONFIG = ProcessRunnerTestConfig

    # Some process runners might not have a simple way to list
    # suites/testcases or might not even have the concept of test suites. If
    # no list_command is specified we will store all testcase results in a
    # single suite, with a default name.
    _DEFAULT_SUITE_NAME = "All Tests"
    _VERIFICATION_SUITE_NAME = "ProcessChecks"
    _VERIFICATION_TESTCASE_NAME = "ExitCodeCheck"
    _MAX_RETAINED_LOG_SIZE = 4096

    def __init__(self, **options) -> None:
        super(ProcessRunnerTest, self).__init__(**options)

        self._test_context = None
        self._test_process = None  # will be set by `self.run_tests`
        self._test_process_retcode = None  # will be set by `self.run_tests`
        self._test_process_killed = False
        self._test_has_run = False
        self._resolved_bin = None  # resolved binary path

    @property
    def stderr(self) -> Optional[str]:
        if self._runpath:
            return os.path.join(self._runpath, "stderr")

    @property
    def stdout(self) -> Optional[str]:
        if self._runpath:
            return os.path.join(self._runpath, "stdout")

    @property
    def timeout_log(self) -> Optional[str]:
        if self._runpath:
            return os.path.join(self._runpath, "timeout.log")

    @property
    def report_path(self) -> Optional[str]:
        if self._runpath:
            return os.path.join(self._runpath, "report.xml")

    @property
    def resolved_bin(self) -> str:
        if not self._resolved_bin:
            self._resolved_bin = self.prepare_binary()

        return self._resolved_bin

    def prepare_binary(self) -> str:
        """
        Resolve the real binary path to run
        """
        # Need to use the binary's absolute path if `proc_cwd` is specified,
        # otherwise won't be able to find the binary.
        if self.cfg.proc_cwd:
            return os.path.abspath(self.cfg.binary)
        # use user-specified binary as-is, override if more sophisticated binary resolution is needed.
        else:
            return self.cfg.binary

    def test_command(self) -> List[str]:
        """
        Add custom arguments before and after the executable if they are defined.
        :return: List of commands to run before and after the test process,
            as well as the test executable itself.
        """
        cmd = self._test_command()

        if self.cfg.pre_args:
            cmd = self.cfg.pre_args + cmd
        if self.cfg.post_args:
            cmd = cmd + self.cfg.post_args
        return cmd

    def _test_command(self) -> List[str]:
        """
        Override this to add extra options to the test command.

        :return: Command to run test process
        """
        return [self.resolved_bin]

    def list_command(self) -> Optional[List[str]]:
        """
        List custom arguments before and after the executable if they are defined.
        :return: List of commands to run before and after the test process,
            as well as the test executable itself.
        """
        cmd = self._list_command()
        if cmd:
            if self.cfg.pre_args:
                cmd = self.cfg.pre_args + cmd
            if self.cfg.post_args:
                cmd = cmd + self.cfg.post_args
        return cmd

    def _list_command(self) -> Optional[List[str]]:
        """
        Override this to generate the shell command that will cause the
        testing framework to list the tests available on stdout.

        :return: Command to list tests
        """
        return []

    def get_test_context(self, list_cmd=None):
        """
        Run the shell command generated by `list_command` in a subprocess,
        parse and return the stdout generated via `parse_test_context`.

        :param list_cmd: Command to list all test suites and testcases
        :type list_cmd: ``str``
        :return: Result returned by `parse_test_context`.
        :rtype: ``list`` of ``list``
        """

        cmd = list_cmd or self.list_command()
        if not cmd:
            # TODO: this is not a list of lists, it is a list of a tuple of str and tuple
            return [(self._DEFAULT_SUITE_NAME, ())]

        proc = subprocess_popen(
            cmd,
            cwd=self.cfg.proc_cwd,
            env=self.get_proc_env(),
            stdout=subprocess.PIPE,
        )
        test_list_output = proc.communicate()[0]

        # with python3, stdout is bytes so need to decode.
        if not isinstance(test_list_output, str):
            test_list_output = test_list_output.decode(sys.stdout.encoding)

        return self.parse_test_context(test_list_output)

    def parse_test_context(self, test_list_output: bytes) -> List[List]:
        """
        Override this to generate a nested list of test suite and test case
        context. Only required if `list_command` is overridden to return a
        command.

        The result will later on be used by test listers to generate the
        test context output for this test instance.

        Sample output:

        .. code-block:: python

          [
              ['SuiteAlpha', ['testcase_one', 'testcase_two'],
              ['SuiteBeta', ['testcase_one', 'testcase_two'],
          ]

        :param test_list_output: stdout from the list command
        :return: Parsed test context from command line
                 output of the 3rd party testing library.
        """
        raise NotImplementedError

    def timeout_callback(self):
        """
        Callback function that will be called by the daemon thread if a timeout
        occurs (e.g. process runs longer than specified timeout value).

        :raises RuntimeError:
        """

        self._test_process_killed = True
        with self.result.report.logged_exceptions():
            raise RuntimeError(
                "Timeout while running {instance} after {timeout}.".format(
                    instance=self, timeout=format_duration(self.cfg.timeout)
                )
            )

    def get_proc_env(self) -> Dict:
        """
        Fabricate the env var for subprocess.
        Precedence: user-specified > hardcoded > system env
        """

        # start with system env
        env = os.environ.copy()

        # override with hardcoded values
        if self.runpath:
            json_ouput = os.path.join(self.runpath, "output.json")
            self.logger.debug("Json output: %s", json_ouput)
            env["JSON_REPORT"] = json_ouput

        for driver in self.resources:
            driver_name = driver.uid()
            for attr in dir(driver):
                value = getattr(driver, attr)
                if attr.startswith("_") or callable(value):
                    continue
                env[
                    "DRIVER_{}_ATTR_{}".format(
                        strings.slugify(driver_name).replace("-", "_"),
                        strings.slugify(attr).replace("-", "_"),
                    ).upper()
                ] = str(value)

        # override with user specified values
        if isinstance(self.cfg.proc_env, dict):
            proc_env = {
                key.upper(): render(
                    val, self.context_input(exclude=["test_context"])
                )
                for key, val in self.cfg.proc_env.items()
            }
            env.update(proc_env)

        return env

    def run_tests(self) -> None:
        """
        Run the tests in a subprocess, record stdout & stderr on runpath.
        Optionally enforce a timeout and log timeout related messages in
        the given timeout log path.

        :raises ValueError: upon invalid test command
        """
        with self.report.timer.record("run"):
            with self.report.logged_exceptions(), open(
                self.stderr, "w"
            ) as stderr, open(self.stdout, "w") as stdout:

                test_cmd = self.test_command()
                if not test_cmd:
                    raise ValueError(
                        f"Invalid test command generated for: {self}"
                    )

                self.report.logger.info(
                    "Running {} - Command: {}".format(self, test_cmd)
                )
                self._test_process = subprocess_popen(
                    test_cmd,
                    stderr=stderr,
                    stdout=stdout,
                    cwd=self.cfg.proc_cwd,
                    env=self.get_proc_env(),
                )

                if self.cfg.timeout:
                    with open(self.timeout_log, "w") as timeout_log:
                        timeout_checker = enforce_timeout(
                            process=self._test_process,
                            timeout=self.cfg.timeout,
                            output=timeout_log,
                            callback=self.timeout_callback,
                        )
                        self._test_process_retcode = self._test_process.wait()
                        timeout_checker.join()
                else:
                    self._test_process_retcode = self._test_process.wait()

                self._test_has_run = True

    def read_test_data(self):
        """
        Parse output generated by the 3rd party testing tool, and then
        the parsed content will be handled by ``process_test_data``.

        You should override this function with custom logic to parse
        the contents of generated file.
        """
        raise NotImplementedError

    def process_test_data(self, test_data):
        """
        Process raw test data that was collected and return a list of
        entries (e.g. TestGroupReport, TestCaseReport) that will be
        appended to the current test instance's report as children.

        :param test_data: Root node of parsed raw test data
        :type test_data: ``xml.etree.Element``
        :return: List of sub reports
        :rtype: ``list`` of ``TestGroupReport`` / ``TestCaseReport``
        """
        raise NotImplementedError

    def get_process_check_report(
        self, retcode: int, stdout: str, stderr: str
    ) -> TestGroupReport:
        """
        When running a process fails (e.g. binary crash, timeout etc)
        we can still generate dummy testsuite / testcase reports with
        a certain hierarchy compatible with exporters and XUnit conventions.
        And logs of stdout & stderr can be saved as attachment.
        """
        assertion_content = "\n".join(
            [f"Process: {self.resolved_bin}", f"Exit code: {retcode}"]
        )

        passed = retcode == 0 or retcode in self.cfg.ignore_exit_codes

        testcase_report = TestCaseReport(
            name=self._VERIFICATION_TESTCASE_NAME,
            category=ReportCategories.SYNTHESIZED,
            entries=[
                RawAssertion(
                    description="Process exit code check",
                    content=assertion_content,
                    passed=passed,
                ).serialize()
            ],
        )

        if stdout and os.path.isfile(stdout):
            stdout_attachment = Attachment(
                filepath=os.path.abspath(stdout), description="Process stdout"
            )
            testcase_report.attachments.append(stdout_attachment)
            testcase_report.append(stdout_attachment.serialize())

        if stderr and os.path.isfile(stderr):
            stderr_attachment = Attachment(
                filepath=os.path.abspath(stderr), description="Process stderr"
            )
            testcase_report.attachments.append(stderr_attachment)
            testcase_report.append(stderr_attachment.serialize())

        testcase_report.runtime_status = RuntimeStatus.FINISHED

        suite_report = TestGroupReport(
            name=self._VERIFICATION_SUITE_NAME,
            category=ReportCategories.TESTSUITE,
            entries=[testcase_report],
        )

        return suite_report

    def update_test_report(self) -> None:
        """
        Update current instance's test report with generated sub reports from
        raw test data. Skip report updates if the process was killed.

        :raises ValueError: in case the test report already has children
        """
        if self._test_process_killed or not self._test_has_run:
            # Return code is `None` if process was killed or test has not run
            self.result.report.append(
                self.get_process_check_report(
                    self._test_process_retcode, self.stdout, self.stderr
                )
            )
            return

        if len(self.result.report):
            for suite in self.result.report:
                if suite.name not in [
                    member.value for member in ResourceHooks
                ]:
                    raise ValueError(
                        f"Cannot update test report, it already has a children: {self.result.report}"
                    )

        with self.result.report.logged_exceptions():
            self.result.report.extend(
                self.process_test_data(self.read_test_data())
            )

        # Check process exit code as last step, as we don't want to create
        # an error log if the report was populated
        # (with possible failures) already
        self.result.report.append(
            self.get_process_check_report(
                self._test_process_retcode, self.stdout, self.stderr
            )
        )

    def apply_xfail_tests(self) -> None:
        """
        Apply xfail tests specified via --xfail-tests or @test_plan(xfail_tests=...).
        """

        test_report = self.result.report
        pattern = f"{test_report.name}:*:*"
        self._xfail(pattern, test_report)

        for suite_report in test_report.entries:
            pattern = f"{test_report.name}:{suite_report.name}:*"
            self._xfail(pattern, suite_report)

            for case_report in suite_report.entries:
                pattern = f"{test_report.name}:{suite_report.name}:{case_report.name}"
                self._xfail(pattern, case_report)

    def add_pre_resource_steps(self) -> None:
        """Runnable steps to be executed before environment starts."""
        super(ProcessRunnerTest, self).add_pre_resource_steps()
        self._add_step(self.make_runpath_dirs)

    def add_post_resource_steps(self) -> None:
        """Runnable steps to run after environment stopped."""
        self._add_step(self.apply_xfail_tests)
        super(ProcessRunnerTest, self).add_post_resource_steps()

    def add_main_batch_steps(self) -> None:
        """Runnable steps to be executed while environment is running."""
        self._add_step(self.run_tests)
        self._add_step(self.update_test_report)
        self._add_step(self.propagate_tag_indices)
        self._add_step(self.log_test_results, top_down=False)

    def aborting(self) -> None:
        if self._test_process is not None:
            kill_process(self._test_process)
            self._test_process_killed = True

    def _dry_run_testsuites(self) -> None:

        super(ProcessRunnerTest, self)._dry_run_testsuites()

        testcase_report = TestCaseReport(
            name=self._VERIFICATION_TESTCASE_NAME,
            category=ReportCategories.SYNTHESIZED,
        )
        testsuite_report = TestGroupReport(
            name=self._VERIFICATION_SUITE_NAME,
            category=ReportCategories.SYNTHESIZED,
            entries=[testcase_report],
        )
        self.result.report.append(testsuite_report)

    def run_testcases_iter(
        self,
        testsuite_pattern: str = "*",
        testcase_pattern: str = "*",
        shallow_report: Dict = None,
    ) -> Generator:
        """
        Runs testcases as defined by the given filter patterns and yields
        testcase reports. A single testcase report is made for general checks
        of the test process, including checking the exit code and logging
        stdout and stderr of the process. Then, testcase reports are generated
        from the output of the test process.

        For efficiency, we run all testcases in a single subprocess rather than
        running each testcase in a seperate process. This reduces the total
        time taken to run all testcases, however it will mean that testcase
        reports will not be generated until all testcases have finished
        running.

        :param testsuite_pattern: pattern to match for testsuite names
        :param testcase_pattern: pattern to match for testcase names
        :param shallow_report: shallow report entry
        :return: generator yielding testcase reports and UIDs for merge step
        """
        self.make_runpath_dirs()

        list_cmd = self.list_command_filter(
            testsuite_pattern, testcase_pattern
        )
        self.logger.debug("list_cmd = %s", list_cmd)

        suites_to_run = self.get_test_context(list_cmd)

        for testsuite, testcases in suites_to_run:
            if testcases:
                for testcase in testcases:
                    testcase_report = self.report[testsuite][testcase]
                    yield {"runtime_status": RuntimeStatus.RUNNING}, [
                        self.uid(),
                        testsuite,
                        testcase,
                    ]
            else:
                # Unlike `MultiTest`, `ProcessRunnerTest` may have some suites
                # without any testcase after initializing test report, but will
                # get result of testcases after run. So we should not filter
                # them out, e.g. Hobbes-test can run in unit of test suite.
                yield {"runtime_status": RuntimeStatus.RUNNING}, [
                    self.uid(),
                    testsuite,
                ]

        yield {"runtime_status": RuntimeStatus.RUNNING}, [
            self.uid(),
            self._VERIFICATION_SUITE_NAME,
            self._VERIFICATION_TESTCASE_NAME,
        ]

        test_cmd = self.test_command_filter(
            testsuite_pattern, testcase_pattern
        )
        self.logger.debug("test_cmd = %s", test_cmd)

        with open(self.stdout, mode="w+") as stdout, open(
            self.stderr, mode="w+"
        ) as stderr:
            exit_code = subprocess.call(
                test_cmd,
                stderr=stderr,
                stdout=stdout,
                cwd=self.cfg.proc_cwd,
                env=self.get_proc_env(),
            )

        process_report = self.get_process_check_report(
            exit_code, self.stdout, self.stderr
        )
        exit_code_report = process_report[self._VERIFICATION_TESTCASE_NAME]

        try:
            group_reports = self.process_test_data(self.read_test_data())
        except Exception as exc:
            exit_code_report.logger.exception(exc)
            for testsuite, _ in suites_to_run:
                self.report[testsuite].runtime_status = RuntimeStatus.NOT_RUN
        else:
            for suite_report in group_reports:
                for testcase_report in suite_report:
                    yield testcase_report, [self.uid(), suite_report.uid]

        yield exit_code_report, [self.uid(), process_report.uid]

    def test_command_filter(
        self, testsuite_pattern: str, testcase_pattern: str
    ):
        """
        Return the base test command with additional filtering to run a
        specific set of testcases. To be implemented by concrete subclasses.
        """
        raise NotImplementedError

    def list_command_filter(
        self, testsuite_pattern: str, testcase_pattern: str
    ):
        """
        Return the base list command with additional filtering to list a
        specific set of testcases. To be implemented by concrete subclasses.
        """
        raise NotImplementedError
