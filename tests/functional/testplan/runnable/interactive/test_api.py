"""Functional tests for interactive HTTP API."""
import functools
from unittest import mock

import pytest
import requests

import testplan
from testplan.common import entity
from testplan.common.utils import timing
from testplan.exporters.testing import XMLExporter
from testplan.report import RuntimeStatus, Status
from testplan.testing import multitest
from testplan.testing.multitest import driver
from tests.functional.testplan.runnable.interactive.interactive_helper import (
    wait_for_interactive_start,
)
from tests.unit.testplan.runnable.interactive import test_api


@multitest.testsuite
class ExampleSuite:
    """Example test suite."""

    def __init__(self, tmpfile):
        self._tmpfile = tmpfile

    @multitest.testcase
    def test_passes(self, env, result):
        """Testcase that passes."""
        result.true(True)

    @multitest.testcase
    def test_fails(self, env, result):
        """Testcase that fails."""
        result.true(False)

    @multitest.testcase
    def test_logs(self, env, result):
        """Testcase that makes a log."""
        result.log("Here I share my deepest thoughts")

    @multitest.testcase
    def test_attach(self, env, result):
        """Testcase that attaches a file."""
        result.attach(self._tmpfile)

    @multitest.testcase(parameters=[1, 2, 3])
    def test_parametrized(self, env, result, val):
        """Parametrized testcase."""
        result.log(val)
        result.gt(val, 0)
        result.lt(val, 10)


@pytest.fixture
def plan(tmpdir):
    """Yield an interactive testplan."""

    with mock.patch(
        "testplan.runnable.interactive.reloader.ModuleReloader"
    ) as MockReloader:
        MockReloader.return_value = None

        plan = testplan.TestplanMock(
            name="InteractiveAPITest",
            interactive_port=0,
            interactive_block=False,
            exporters=[XMLExporter(xml_dir=str(tmpdir / "xml_exporter"))],
        )

        logfile = tmpdir / "attached_log.txt"
        logfile.write_text(
            "This text will be written into the attached file.",
            encoding="utf-8",
        )

        plan.add(
            multitest.MultiTest(
                name="ExampleMTest",
                suites=[ExampleSuite(str(logfile))],
            )
        )
        plan.run()
        wait_for_interactive_start(plan)
        yield plan
        plan.abort()


class BadDriver(driver.Driver):
    """Driver that cannot start de to exception raised."""

    def __init__(self, name, **options):
        super(BadDriver, self).__init__(name=name, **options)

    def starting(self):
        super(BadDriver, self).starting()
        raise Exception("Failed to start with no reason")


@pytest.fixture
def plan2(tmpdir):
    """Yield an interactive testplan."""

    with mock.patch(
        "testplan.runnable.interactive.reloader.ModuleReloader"
    ) as MockReloader:
        MockReloader.return_value = None

        plan = testplan.TestplanMock(
            name="InteractiveAPITest",
            interactive_port=0,
            interactive_block=False,
            exporters=[XMLExporter(xml_dir=str(tmpdir / "xml_exporter"))],
        )

        logfile = tmpdir / "attached_log.txt"
        logfile.write_text(
            "This text will be written into the attached file.",
            encoding="utf-8",
        )

        plan.add(
            multitest.MultiTest(
                name="BrokenMTest",
                suites=[ExampleSuite(str(logfile))],
                environment=[BadDriver(name="BadDriver")],
            )
        )
        plan.run()
        wait_for_interactive_start(plan)
        yield plan
        plan.abort()


@multitest.testsuite(strict_order=True)
class StrictOrderSuite:
    """Example test suite."""

    def __init__(self, tmpfile):
        self._tmpfile = tmpfile

    @multitest.testcase
    def test_passes(self, env, result):
        """Testcase that passes."""
        result.true(True)

    @multitest.testcase
    def test_fails(self, env, result):
        """Testcase that fails."""
        result.true(False)

    @multitest.testcase
    def test_logs(self, env, result):
        """Testcase that makes a log."""
        result.log("Here I share my deepest thoughts")

    @multitest.testcase
    def test_attach(self, env, result):
        """Testcase that attaches a file."""
        result.attach(self._tmpfile)

    @multitest.testcase(parameters=[1, 2, 3])
    def test_parametrized(self, env, result, val):
        """Parametrized testcase."""
        result.log(val)
        result.gt(val, 0)
        result.lt(val, 10)


@pytest.fixture
def plan3(tmpdir):
    """
    Yield an interactive testplan. It only has one multitest instance with
    one test suite whose `strict_order` attribute is enabled.
    """

    with mock.patch(
        "testplan.runnable.interactive.reloader.ModuleReloader"
    ) as MockReloader:
        MockReloader.return_value = None

        plan = testplan.TestplanMock(
            name="InteractiveAPITest",
            interactive_port=0,
            interactive_block=False,
            exporters=[XMLExporter(xml_dir=str(tmpdir / "xml_exporter"))],
        )

        logfile = tmpdir / "attached_log.txt"
        logfile.write_text(
            "This text will be written into the attached file.",
            encoding="utf-8",
        )

        plan.add(
            multitest.MultiTest(
                name="ExampleMTest2",
                suites=[StrictOrderSuite(str(logfile))],
            )
        )
        plan.run()
        wait_for_interactive_start(plan)
        yield plan
        plan.abort()


# Expected JSON to be returned from each API resource at start of day, before
# any tests have been run.
EXPECTED_INITIAL_GET = [
    (
        "/report",
        {
            "attachments": {},
            "category": "testplan",
            "entry_uids": ["ExampleMTest"],
            "meta": {},
            "name": "InteractiveAPITest",
            "parent_uids": [],
            "status": "unknown",
            "runtime_status": "ready",
            "counter": {"failed": 0, "passed": 0, "total": 7, "unknown": 7},
            "tags_index": {},
            "timer": {},
            "uid": "InteractiveAPITest",
        },
    ),
    (
        "/report/tests",
        [
            {
                "category": "multitest",
                "description": None,
                "entry_uids": ["ExampleSuite"],
                "env_status": "STOPPED",
                "name": "ExampleMTest",
                "parent_uids": ["InteractiveAPITest"],
                "part": None,
                "status": "unknown",
                "runtime_status": "ready",
                "counter": {
                    "failed": 0,
                    "passed": 0,
                    "total": 7,
                    "unknown": 7,
                },
                "tags": {},
                "timer": {},
                "uid": "ExampleMTest",
            }
        ],
    ),
    (
        "/report/tests/ExampleMTest",
        {
            "category": "multitest",
            "description": None,
            "entry_uids": ["ExampleSuite"],
            "env_status": "STOPPED",
            "name": "ExampleMTest",
            "parent_uids": ["InteractiveAPITest"],
            "part": None,
            "status": "unknown",
            "runtime_status": "ready",
            "counter": {"failed": 0, "passed": 0, "total": 7, "unknown": 7},
            "tags": {},
            "timer": {},
            "uid": "ExampleMTest",
        },
    ),
    (
        "/report/tests/ExampleMTest/suites",
        [
            {
                "category": "testsuite",
                "description": "Example test suite.",
                "entry_uids": [
                    "test_passes",
                    "test_fails",
                    "test_logs",
                    "test_attach",
                    "test_parametrized",
                ],
                "name": "ExampleSuite",
                "parent_uids": ["InteractiveAPITest", "ExampleMTest"],
                "status": "unknown",
                "runtime_status": "ready",
                "counter": {
                    "failed": 0,
                    "passed": 0,
                    "total": 7,
                    "unknown": 7,
                },
                "tags": {},
                "timer": {},
                "uid": "ExampleSuite",
            }
        ],
    ),
    (
        "/report/tests/ExampleMTest/suites/ExampleSuite",
        {
            "category": "testsuite",
            "description": "Example test suite.",
            "entry_uids": [
                "test_passes",
                "test_fails",
                "test_logs",
                "test_attach",
                "test_parametrized",
            ],
            "name": "ExampleSuite",
            "parent_uids": ["InteractiveAPITest", "ExampleMTest"],
            "status": "unknown",
            "runtime_status": "ready",
            "counter": {"failed": 0, "passed": 0, "total": 7, "unknown": 7},
            "tags": {},
            "timer": {},
            "uid": "ExampleSuite",
        },
    ),
    (
        "/report/tests/ExampleMTest/suites/ExampleSuite/testcases",
        [
            {
                "category": "testcase",
                "description": "Testcase that passes.",
                "entries": [],
                "logs": [],
                "name": "test_passes",
                "parent_uids": [
                    "InteractiveAPITest",
                    "ExampleMTest",
                    "ExampleSuite",
                ],
                "status": "unknown",
                "runtime_status": "ready",
                "counter": {
                    "passed": 0,
                    "failed": 0,
                    "total": 1,
                    "unknown": 1,
                },
                "tags": {},
                "timer": {},
                "type": "TestCaseReport",
                "uid": "test_passes",
            },
            {
                "category": "testcase",
                "description": "Testcase that fails.",
                "entries": [],
                "logs": [],
                "name": "test_fails",
                "parent_uids": [
                    "InteractiveAPITest",
                    "ExampleMTest",
                    "ExampleSuite",
                ],
                "status": "unknown",
                "runtime_status": "ready",
                "counter": {
                    "passed": 0,
                    "failed": 0,
                    "total": 1,
                    "unknown": 1,
                },
                "tags": {},
                "timer": {},
                "type": "TestCaseReport",
                "uid": "test_fails",
            },
            {
                "category": "testcase",
                "description": "Testcase that makes a log.",
                "entries": [],
                "logs": [],
                "name": "test_logs",
                "parent_uids": [
                    "InteractiveAPITest",
                    "ExampleMTest",
                    "ExampleSuite",
                ],
                "status": "unknown",
                "runtime_status": "ready",
                "counter": {
                    "passed": 0,
                    "failed": 0,
                    "total": 1,
                    "unknown": 1,
                },
                "tags": {},
                "timer": {},
                "type": "TestCaseReport",
                "uid": "test_logs",
            },
            {
                "category": "testcase",
                "description": "Testcase that attaches a file.",
                "entries": [],
                "logs": [],
                "name": "test_attach",
                "parent_uids": [
                    "InteractiveAPITest",
                    "ExampleMTest",
                    "ExampleSuite",
                ],
                "status": "unknown",
                "runtime_status": "ready",
                "counter": {
                    "passed": 0,
                    "failed": 0,
                    "total": 1,
                    "unknown": 1,
                },
                "tags": {},
                "timer": {},
                "type": "TestCaseReport",
                "uid": "test_attach",
            },
            {
                "category": "parametrization",
                "counter": {
                    "passed": 0,
                    "failed": 0,
                    "total": 3,
                    "unknown": 3,
                },
                "description": "Parametrized testcase.",
                "entry_uids": [
                    "test_parametrized__val_1",
                    "test_parametrized__val_2",
                    "test_parametrized__val_3",
                ],
                "name": "test_parametrized",
                "parent_uids": [
                    "InteractiveAPITest",
                    "ExampleMTest",
                    "ExampleSuite",
                ],
                "runtime_status": "ready",
                "status": "unknown",
                "tags": {},
                "timer": {},
                "uid": "test_parametrized",
            },
        ],
    ),
    (
        "/report/tests/ExampleMTest/suites/ExampleSuite/testcases/test_passes",
        {
            "category": "testcase",
            "description": "Testcase that passes.",
            "entries": [],
            "logs": [],
            "name": "test_passes",
            "parent_uids": [
                "InteractiveAPITest",
                "ExampleMTest",
                "ExampleSuite",
            ],
            "status": "unknown",
            "runtime_status": "ready",
            "tags": {},
            "timer": {},
            "type": "TestCaseReport",
            "uid": "test_passes",
        },
    ),
    (
        "/report/tests/ExampleMTest/suites/ExampleSuite/testcases/"
        "test_parametrized/parametrizations",
        [
            {
                "category": "testcase",
                "description": "Parametrized testcase.",
                "entries": [],
                "logs": [],
                "name": "test_parametrized <val=1>",
                "parent_uids": [
                    "InteractiveAPITest",
                    "ExampleMTest",
                    "ExampleSuite",
                    "test_parametrized",
                ],
                "status": "unknown",
                "runtime_status": "ready",
                "tags": {},
                "timer": {},
                "type": "TestCaseReport",
                "uid": "test_parametrized__val_1",
            },
            {
                "category": "testcase",
                "description": "Parametrized testcase.",
                "entries": [],
                "logs": [],
                "name": "test_parametrized <val=2>",
                "parent_uids": [
                    "InteractiveAPITest",
                    "ExampleMTest",
                    "ExampleSuite",
                    "test_parametrized",
                ],
                "status": "unknown",
                "runtime_status": "ready",
                "tags": {},
                "timer": {},
                "type": "TestCaseReport",
                "uid": "test_parametrized__val_2",
            },
            {
                "category": "testcase",
                "description": "Parametrized testcase.",
                "entries": [],
                "logs": [],
                "name": "test_parametrized <val=3>",
                "parent_uids": [
                    "InteractiveAPITest",
                    "ExampleMTest",
                    "ExampleSuite",
                    "test_parametrized",
                ],
                "status": "unknown",
                "runtime_status": "ready",
                "tags": {},
                "timer": {},
                "type": "TestCaseReport",
                "uid": "test_parametrized__val_3",
            },
        ],
    ),
    (
        "/report/tests/ExampleMTest/suites/ExampleSuite/testcases/"
        "test_parametrized/parametrizations/test_parametrized__val_1",
        {
            "category": "testcase",
            "description": "Parametrized testcase.",
            "entries": [],
            "logs": [],
            "name": "test_parametrized <val=1>",
            "parent_uids": [
                "InteractiveAPITest",
                "ExampleMTest",
                "ExampleSuite",
                "test_parametrized",
            ],
            "status": "unknown",
            "runtime_status": "ready",
            "tags": {},
            "timer": {},
            "type": "TestCaseReport",
            "uid": "test_parametrized__val_1",
        },
    ),
]


# Expected results of testcases.
EXPECTED_TESTCASE_RESULTS = [
    (
        "test_passes",
        Status.PASSED.to_json_compatible(),
        RuntimeStatus.FINISHED.to_json_compatible(),
    ),
    (
        "test_fails",
        Status.FAILED.to_json_compatible(),
        RuntimeStatus.FINISHED.to_json_compatible(),
    ),
    (
        "test_logs",
        Status.PASSED.to_json_compatible(),
        RuntimeStatus.FINISHED.to_json_compatible(),
    ),
    (
        "test_attach",
        Status.PASSED.to_json_compatible(),
        RuntimeStatus.FINISHED.to_json_compatible(),
    ),
    (
        "test_parametrized",
        Status.PASSED.to_json_compatible(),
        RuntimeStatus.FINISHED.to_json_compatible(),
    ),
]

# Expected results of parametrized testcases.
EXPECTED_PARAM_TESTCASE_RESULTS = [
    (
        "test_parametrized__val_1",
        Status.PASSED.to_json_compatible(),
        RuntimeStatus.FINISHED.to_json_compatible(),
    ),
    (
        "test_parametrized__val_2",
        Status.PASSED.to_json_compatible(),
        RuntimeStatus.FINISHED.to_json_compatible(),
    ),
    (
        "test_parametrized__val_3",
        Status.PASSED.to_json_compatible(),
        RuntimeStatus.FINISHED.to_json_compatible(),
    ),
]


def test_initial_get(plan):
    """
    Test GETting the report state through each of the API resources at the
    start of day, i.e. before any tests have been run.
    """
    host, port = plan.interactive.http_handler_info
    assert host == "0.0.0.0"

    for resource_path, expected_json in EXPECTED_INITIAL_GET:
        rsp = requests.get(
            "http://localhost:{port}/api/v1/interactive{resource}".format(
                port=port, resource=resource_path
            )
        )
        assert rsp.status_code == 200
        test_api.compare_json(rsp.json(), expected_json)


def test_environment_control(plan):
    """Test starting and stopping the environment."""
    host, port = plan.interactive.http_handler_info
    assert host == "0.0.0.0"

    mtest_url = (
        "http://localhost:{}/api/v1/interactive/report/tests/"
        "ExampleMTest".format(port)
    )
    rsp = requests.get(mtest_url)
    assert rsp.status_code == 200
    mtest_json = rsp.json()

    # Trigger the environment to start by setting the env_status to STARTING
    # and PUTting back the data.
    mtest_json["env_status"] = entity.ResourceStatus.STARTING
    rsp = requests.put(mtest_url, json=mtest_json)
    assert rsp.status_code == 200
    updated_json = rsp.json()
    test_api.compare_json(updated_json, mtest_json)
    assert updated_json["hash"] != mtest_json["hash"]

    # Wait for the environment to become STARTED.
    timing.wait(
        functools.partial(
            _check_env_status,
            mtest_url,
            entity.ResourceStatus.STARTED,
            updated_json["hash"],
        ),
        interval=0.2,
        timeout=60,
        raise_on_timeout=True,
    )

    # Now trigger the environment to stop by setting the env_status to STOPPING
    # and PUTting back the data.
    mtest_json = updated_json
    mtest_json["env_status"] = entity.ResourceStatus.STOPPING
    rsp = requests.put(mtest_url, json=mtest_json)
    assert rsp.status_code == 200
    updated_json = rsp.json()
    test_api.compare_json(updated_json, mtest_json, ignored_keys=["timer"])
    assert updated_json["hash"] != mtest_json["hash"]

    # Wait for the environment to become STOPPED.
    timing.wait(
        functools.partial(
            _check_env_status,
            mtest_url,
            entity.ResourceStatus.STOPPED,
            updated_json["hash"],
        ),
        interval=0.2,
        timeout=30,
        raise_on_timeout=True,
    )


def test_run_all_tests(plan):
    """
    Test running all tests.
    """
    host, port = plan.interactive.http_handler_info
    assert host == "0.0.0.0"

    report_url = "http://localhost:{}/api/v1/interactive/report".format(port)
    rsp = requests.get(report_url)
    assert rsp.status_code == 200
    report_json = rsp.json()
    last_hash = report_json["hash"]

    # Trigger all tests to run by updating the report status to RUNNING
    # and PUTting back the data.
    report_json["runtime_status"] = RuntimeStatus.RUNNING.to_json_compatible()
    rsp = requests.put(report_url, json=report_json)
    assert rsp.status_code == 200

    updated_json = rsp.json()
    assert updated_json["hash"] != last_hash
    assert (
        updated_json["runtime_status"]
        == RuntimeStatus.WAITING.to_json_compatible()
    )
    test_api.compare_json(
        updated_json, report_json, ignored_keys=["runtime_status"]
    )

    timing.wait(
        functools.partial(
            _check_test_status,
            report_url,
            Status.FAILED.to_json_compatible(),
            RuntimeStatus.FINISHED.to_json_compatible(),
            updated_json["hash"],
        ),
        interval=0.2,
        timeout=60,
        raise_on_timeout=True,
    )

    # After running all tests, check that we can retrieve the attached file.
    _test_attachments(port)


def test_run_and_reset_mtest(plan):
    """Test running a single MultiTest and then reset the test report."""
    host, port = plan.interactive.http_handler_info
    assert host == "0.0.0.0"

    mtest_url = (
        "http://localhost:{}/api/v1/interactive/report/tests/"
        "ExampleMTest".format(port)
    )
    rsp = requests.get(mtest_url)
    assert rsp.status_code == 200
    mtest_json = rsp.json()

    # Trigger multitest to run by updating the report status to RUNNING
    # and PUTting back the data.
    mtest_json["runtime_status"] = RuntimeStatus.RUNNING.to_json_compatible()
    rsp = requests.put(mtest_url, json=mtest_json)
    assert rsp.status_code == 200
    updated_json = rsp.json()
    assert updated_json["hash"] != mtest_json["hash"]
    assert (
        updated_json["runtime_status"]
        == RuntimeStatus.WAITING.to_json_compatible()
    )
    test_api.compare_json(
        updated_json, mtest_json, ignored_keys=["runtime_status"]
    )

    timing.wait(
        functools.partial(
            _check_test_status,
            mtest_url,
            Status.FAILED.to_json_compatible(),
            RuntimeStatus.FINISHED.to_json_compatible(),
            updated_json["hash"],
        ),
        interval=0.2,
        timeout=60,
        raise_on_timeout=True,
    )

    # Get the updated report
    rsp = requests.get(mtest_url)
    assert rsp.status_code == 200
    mtest_json = rsp.json()

    # Trigger multitest to run by updating the report status to RESETTING
    # and PUTting back the data.
    mtest_json["runtime_status"] = RuntimeStatus.RESETTING.to_json_compatible()
    rsp = requests.put(mtest_url, json=mtest_json)
    assert rsp.status_code == 200
    updated_json = rsp.json()
    assert updated_json["hash"] != mtest_json["hash"]
    assert (
        updated_json["runtime_status"]
        == RuntimeStatus.WAITING.to_json_compatible()
    )
    test_api.compare_json(
        updated_json, mtest_json, ignored_keys=["runtime_status", "env_status"]
    )

    timing.wait(
        functools.partial(
            _check_test_status,
            mtest_url,
            Status.UNKNOWN.to_json_compatible(),
            RuntimeStatus.READY.to_json_compatible(),
            updated_json["hash"],
        ),
        interval=0.2,
        timeout=60,
        raise_on_timeout=True,
    )

    rsp = requests.get(mtest_url)
    assert rsp.status_code == 200
    mtest_json = rsp.json()
    assert (
        mtest_json["runtime_status"]
        == RuntimeStatus.READY.to_json_compatible()
    )
    assert mtest_json["env_status"] == entity.ResourceStatus.STOPPED


def test_run_suite(plan):
    """Test running a single test suite."""
    host, port = plan.interactive.http_handler_info
    assert host == "0.0.0.0"

    suite_url = (
        "http://localhost:{}/api/v1/interactive/report/tests/ExampleMTest/"
        "suites/ExampleSuite".format(port)
    )
    rsp = requests.get(suite_url)
    assert rsp.status_code == 200
    suite_json = rsp.json()

    # Trigger test suite to run by updating the report status to RUNNING
    # and PUTting back the data.
    suite_json["runtime_status"] = RuntimeStatus.RUNNING.to_json_compatible()
    rsp = requests.put(suite_url, json=suite_json)
    assert rsp.status_code == 200
    updated_json = rsp.json()
    assert updated_json["hash"] != suite_json["hash"]
    assert (
        updated_json["runtime_status"]
        == RuntimeStatus.WAITING.to_json_compatible()
    )
    test_api.compare_json(
        updated_json, suite_json, ignored_keys=["runtime_status"]
    )

    timing.wait(
        functools.partial(
            _check_test_status,
            suite_url,
            Status.FAILED.to_json_compatible(),
            RuntimeStatus.FINISHED.to_json_compatible(),
            updated_json["hash"],
        ),
        interval=0.2,
        timeout=60,
        raise_on_timeout=True,
    )


def test_run_testcase(plan):
    """Test running a single testcase."""
    host, port = plan.interactive.http_handler_info
    assert host == "0.0.0.0"

    for (
        testcase_name,
        expected_status,
        expected_runtime_status,
    ) in EXPECTED_TESTCASE_RESULTS:
        testcase_url = (
            "http://localhost:{port}/api/v1/interactive/report/tests/"
            "ExampleMTest/suites/ExampleSuite/testcases/{testcase}".format(
                port=port, testcase=testcase_name
            )
        )

        rsp = requests.get(testcase_url)
        assert rsp.status_code == 200
        testcase_json = rsp.json()

        # Trigger testcase to run by updating the report status to RUNNING
        # and PUTting back the data.
        testcase_json[
            "runtime_status"
        ] = RuntimeStatus.RUNNING.to_json_compatible()
        if "entries" in testcase_json:
            del testcase_json["entries"]
        rsp = requests.put(testcase_url, json=testcase_json)
        assert rsp.status_code == 200
        updated_json = rsp.json()
        assert updated_json["hash"] != testcase_json["hash"]
        assert (
            updated_json["runtime_status"]
            == RuntimeStatus.WAITING.to_json_compatible()
        )
        test_api.compare_json(
            updated_json, testcase_json, ignored_keys=["runtime_status"]
        )

        timing.wait(
            functools.partial(
                _check_test_status,
                testcase_url,
                expected_status,
                expected_runtime_status,
                updated_json["hash"],
            ),
            interval=0.2,
            timeout=60,
            raise_on_timeout=True,
        )


def test_run_param_testcase(plan):
    """Test running a single parametrized testcase."""
    host, port = plan.interactive.http_handler_info
    assert host == "0.0.0.0"

    for (
        param_name,
        expected_status,
        expected_runtime_status,
    ) in EXPECTED_PARAM_TESTCASE_RESULTS:
        testcase_url = (
            "http://localhost:{port}/api/v1/interactive/report/tests/"
            "ExampleMTest/suites/ExampleSuite/testcases/test_parametrized/"
            "parametrizations/{param}".format(port=port, param=param_name)
        )

        rsp = requests.get(testcase_url)
        assert rsp.status_code == 200
        testcase_json = rsp.json()

        # Trigger testcase to run by updating the report status to RUNNING
        # and PUTting back the data.
        testcase_json[
            "runtime_status"
        ] = RuntimeStatus.RUNNING.to_json_compatible()
        rsp = requests.put(testcase_url, json=testcase_json)
        assert rsp.status_code == 200
        updated_json = rsp.json()
        assert updated_json["hash"] != testcase_json["hash"]
        assert (
            updated_json["runtime_status"]
            == RuntimeStatus.WAITING.to_json_compatible()
        )
        test_api.compare_json(
            updated_json, testcase_json, ignored_keys=["runtime_status"]
        )

        timing.wait(
            functools.partial(
                _check_test_status,
                testcase_url,
                expected_status,
                expected_runtime_status,
                updated_json["hash"],
            ),
            interval=0.2,
            timeout=60,
            raise_on_timeout=True,
        )


def test_export_report(plan):
    """Test exporting report."""
    host, port = plan.interactive.http_handler_info
    assert host == "0.0.0.0"
    export_url = (
        "http://localhost:{port}/api/v1/interactive/report/export".format(
            port=port
        )
    )
    rsp = requests.get(export_url)
    assert rsp.status_code == 200
    result = rsp.json()
    assert len(result["history"]) == 0
    assert "XML exporter" in result["available"]

    rsp = requests.post(export_url, json={"exporters": ["XML exporter"]})
    assert rsp.status_code == 200
    result = rsp.json()
    assert len(result["history"]) == 1


def test_cannot_start_environment(plan2):
    """Test starting the environment but fails."""
    host, port = plan2.interactive.http_handler_info
    assert host == "0.0.0.0"

    mtest_url = (
        "http://localhost:{}/api/v1/interactive/report/tests/"
        "BrokenMTest".format(port)
    )
    rsp = requests.get(mtest_url)
    assert rsp.status_code == 200
    mtest_json = rsp.json()

    # Trigger the environment to start by setting the env_status to STARTING
    # and PUTting back the data.
    mtest_json["env_status"] = entity.ResourceStatus.STARTING
    rsp = requests.put(mtest_url, json=mtest_json)
    assert rsp.status_code == 200
    updated_json = rsp.json()
    test_api.compare_json(updated_json, mtest_json)
    assert updated_json["hash"] != mtest_json["hash"]

    # Wait for the environment to become STOPPED.
    timing.wait(
        functools.partial(
            _check_env_status,
            mtest_url,
            entity.ResourceStatus.STOPPED,
            updated_json["hash"],
        ),
        interval=0.2,
        timeout=60,
        raise_on_timeout=True,
    )

    # Check the error message
    mtest_url = (
        "http://localhost:{}/api/v1/interactive/report/tests/"
        "BrokenMTest/suites/Environment%2520Start/testcases"
    ).format(port)

    rsp = requests.get(mtest_url)
    assert rsp.status_code == 200
    mtest_json = rsp.json()
    assert len(mtest_json[0]["logs"]) == 1
    assert (
        "Failed to start with no reason" in mtest_json[0]["logs"][0]["message"]
    )


def test_cannot_run_mtest(plan2):
    """Test running a single MultiTest and then reset the test report."""
    host, port = plan2.interactive.http_handler_info
    assert host == "0.0.0.0"

    mtest_url = (
        "http://localhost:{}/api/v1/interactive/report/tests/"
        "BrokenMTest".format(port)
    )
    rsp = requests.get(mtest_url)
    assert rsp.status_code == 200
    mtest_json = rsp.json()

    # Trigger multitest to run by updating the report status to RUNNING
    # and PUTting back the data.
    mtest_json["runtime_status"] = RuntimeStatus.RUNNING.to_json_compatible()
    rsp = requests.put(mtest_url, json=mtest_json)
    assert rsp.status_code == 200
    updated_json = rsp.json()
    assert updated_json["hash"] != mtest_json["hash"]
    assert (
        updated_json["runtime_status"]
        == RuntimeStatus.WAITING.to_json_compatible()
    )
    test_api.compare_json(
        updated_json, mtest_json, ignored_keys=["runtime_status"]
    )

    timing.wait(
        functools.partial(
            _check_test_status,
            mtest_url,
            Status.ERROR.to_json_compatible(),
            RuntimeStatus.READY.to_json_compatible(),
            updated_json["hash"],
        ),
        interval=0.2,
        timeout=60,
        raise_on_timeout=True,
    )

    # Check the error message
    ts_url = (
        "http://localhost:{}/api/v1/interactive/report/tests/"
        "BrokenMTest/suites/Environment%2520Start/testcases"
    ).format(port)
    rsp = requests.get(ts_url)
    assert rsp.status_code == 200
    ts_json = rsp.json()
    assert len(ts_json[0]["logs"]) == 1
    assert "Failed to start with no reason" in ts_json[0]["logs"][0]["message"]


def test_run_testcases_sequentially(plan3):
    """Test running a single testcase."""
    host, port = plan3.interactive.http_handler_info
    assert host == "0.0.0.0"

    suite_url = (
        "http://localhost:{}/api/v1/interactive/report/tests/"
        "ExampleMTest2/suites/StrictOrderSuite".format(port)
    )
    case_url = (
        "http://localhost:{port}/api/v1/interactive/report/tests/"
        "ExampleMTest2/suites/StrictOrderSuite/testcases/{testcase}"
    )
    param_case_url = (
        "http://localhost:{port}/api/v1/interactive/report/tests/"
        "ExampleMTest2/suites/StrictOrderSuite/testcases/test_parametrized/"
        "parametrizations/{param}"
    )

    # Run the 1st and 2nd testcases
    for (
        testcase_name,
        expected_status,
        expected_runtime_status,
    ) in EXPECTED_TESTCASE_RESULTS[:2]:
        testcase_url = case_url.format(port=port, testcase=testcase_name)
        rsp = requests.get(testcase_url)
        assert rsp.status_code == 200
        testcase_json = rsp.json()
        testcase_json[
            "runtime_status"
        ] = RuntimeStatus.RUNNING.to_json_compatible()
        if "entries" in testcase_json:
            del testcase_json["entries"]
        rsp = requests.put(testcase_url, json=testcase_json)
        assert rsp.status_code == 200
        updated_json = rsp.json()

        timing.wait(
            functools.partial(
                _check_test_status,
                testcase_url,
                expected_status,
                expected_runtime_status,
                updated_json["hash"],
            ),
            interval=0.2,
            timeout=60,
            raise_on_timeout=True,
        )

    # Skip the 3rd testcase and run the 4th, it is not allowed
    testcase_name, _, _ = EXPECTED_TESTCASE_RESULTS[3]
    testcase_url = case_url.format(port=port, testcase=testcase_name)
    rsp = requests.get(testcase_url)
    assert rsp.status_code == 200
    testcase_json = rsp.json()
    testcase_json[
        "runtime_status"
    ] = RuntimeStatus.RUNNING.to_json_compatible()
    rsp = requests.put(testcase_url, json=testcase_json)
    assert rsp.status_code == 200
    testcase_json = rsp.json()
    assert (
        "errmsg" in testcase_json
        and "reset test report if necessary" in testcase_json["errmsg"]
    )

    # Run the 3rd and 4th testcases sequentially again and this time it is OK
    for (
        testcase_name,
        expected_status,
        expected_runtime_status,
    ) in EXPECTED_TESTCASE_RESULTS[2:4]:
        testcase_url = case_url.format(port=port, testcase=testcase_name)
        rsp = requests.get(testcase_url)
        assert rsp.status_code == 200
        testcase_json = rsp.json()
        testcase_json[
            "runtime_status"
        ] = RuntimeStatus.RUNNING.to_json_compatible()
        if "entries" in testcase_json:
            del testcase_json["entries"]
        rsp = requests.put(testcase_url, json=testcase_json)
        assert rsp.status_code == 200
        updated_json = rsp.json()

        timing.wait(
            functools.partial(
                _check_test_status,
                testcase_url,
                expected_status,
                expected_runtime_status,
                updated_json["hash"],
            ),
            interval=0.2,
            timeout=60,
            raise_on_timeout=True,
        )

    # Run the 1st testcase in param group
    for (
        param_name,
        expected_status,
        expected_runtime_status,
    ) in EXPECTED_PARAM_TESTCASE_RESULTS[:1]:
        testcase_url = param_case_url.format(port=port, param=param_name)
        rsp = requests.get(testcase_url)
        assert rsp.status_code == 200
        testcase_json = rsp.json()
        testcase_json[
            "runtime_status"
        ] = RuntimeStatus.RUNNING.to_json_compatible()
        rsp = requests.put(testcase_url, json=testcase_json)
        assert rsp.status_code == 200
        updated_json = rsp.json()

        timing.wait(
            functools.partial(
                _check_test_status,
                testcase_url,
                expected_status,
                expected_runtime_status,
                updated_json["hash"],
            ),
            interval=0.2,
            timeout=60,
            raise_on_timeout=True,
        )

    # Skip the 2nd testcase in param group and run the 3rd, it is not allowed
    (
        param_name,
        expected_status,
        expected_runtime_status,
    ) = EXPECTED_PARAM_TESTCASE_RESULTS[2]
    testcase_url = param_case_url.format(port=port, param=param_name)
    rsp = requests.get(testcase_url)
    assert rsp.status_code == 200
    testcase_json = rsp.json()
    testcase_json[
        "runtime_status"
    ] = RuntimeStatus.RUNNING.to_json_compatible()
    rsp = requests.put(testcase_url, json=testcase_json)
    assert rsp.status_code == 200
    testcase_json = rsp.json()
    assert (
        "errmsg" in testcase_json
        and "reset test report if necessary" in testcase_json["errmsg"]
    )

    # Run the 2nd and 3rd testcases sequentially in param group again
    for (
        param_name,
        expected_status,
        expected_runtime_status,
    ) in EXPECTED_PARAM_TESTCASE_RESULTS[1:]:
        testcase_url = param_case_url.format(port=port, param=param_name)
        rsp = requests.get(testcase_url)
        assert rsp.status_code == 200
        testcase_json = rsp.json()
        testcase_json[
            "runtime_status"
        ] = RuntimeStatus.RUNNING.to_json_compatible()
        rsp = requests.put(testcase_url, json=testcase_json)
        assert rsp.status_code == 200
        updated_json = rsp.json()

        timing.wait(
            functools.partial(
                _check_test_status,
                testcase_url,
                expected_status,
                expected_runtime_status,
                updated_json["hash"],
            ),
            interval=0.2,
            timeout=60,
            raise_on_timeout=True,
        )

    # The testcases in that "strict_order" test suite already run so we
    # cannot run this suite again.
    rsp = requests.get(suite_url.format(port))
    assert rsp.status_code == 200
    suite_json = rsp.json()
    suite_json["runtime_status"] = RuntimeStatus.RUNNING.to_json_compatible()
    rsp = requests.put(suite_url, json=suite_json)
    assert rsp.status_code == 200
    suite_json = rsp.json()
    assert (
        "errmsg" in suite_json
        and "reset test report if necessary" in suite_json["errmsg"]
    )


def _test_attachments(port):
    """
    Test retrieving an attached file. The test_attach testcase needs to have
    been run first.
    """
    all_attachments_url = (
        "http://localhost:{port}/api/v1/interactive/attachments".format(
            port=port
        )
    )

    rsp = requests.get(all_attachments_url)
    assert rsp.status_code == 200
    attachments = rsp.json()
    assert len(attachments) == 1
    assert attachments[0].startswith("attached_log")

    attachment_uid = attachments[0]
    single_attachment_url = all_attachments_url + "/" + attachment_uid

    rsp = requests.get(single_attachment_url)
    assert rsp.status_code == 200
    assert rsp.text == "This text will be written into the attached file."


def _check_test_status(
    test_url, expected_status, expected_runtime_status, last_hash
):
    """
    Check the test status by polling the report resource. If the test is
    still running, return False. Otherwise assert that the status matches
    the expected status and return True.
    """
    rsp = requests.get(test_url)
    assert rsp.status_code == 200
    report_json = rsp.json()

    if report_json["runtime_status"] in (
        RuntimeStatus.RUNNING.to_json_compatible(),
        RuntimeStatus.RESETTING.to_json_compatible(),
        RuntimeStatus.WAITING.to_json_compatible(),
    ):
        # when running a test entity, the whole test report can be reset by
        # `dry_run` and `runtime_status` is changed to "ready".
        return False
    else:
        assert report_json["status"] == expected_status
        assert report_json["runtime_status"] == expected_runtime_status
        assert report_json["hash"] != last_hash
        return True


def _check_env_status(test_url, expected_status, last_hash):
    """
    Check the environment status by polling the report resource. Return
    True if the status matches the expected status, False otherwise.
    """
    rsp = requests.get(test_url)
    assert rsp.status_code == 200
    report_json = rsp.json()

    if report_json["env_status"] == expected_status:
        assert report_json["hash"] != last_hash
        return True
    else:
        return False
