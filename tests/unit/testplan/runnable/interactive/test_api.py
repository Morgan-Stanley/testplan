"""Test the interactive HTTP API."""

from unittest import mock

import pytest

from testplan import report
from testplan.common import entity
from testplan.runnable.interactive import base, http


class TestRunnerIHandlerConfig(base.TestRunnerIHandlerConfig):
    """Only for testing."""

    @classmethod
    def get_options(cls):
        return {
            "target": object,
        }


class TestRunnerIHandler(base.TestRunnerIHandler):
    """Only for testing."""

    CONFIG = TestRunnerIHandlerConfig


@pytest.fixture
def example_report():
    """Create a new report skeleton."""
    return report.TestReport(
        name="Interactive API Test",
        entries=[
            report.TestGroupReport(
                name="MTest1",
                category=report.ReportCategories.MULTITEST,
                env_status=entity.ResourceStatus.STOPPED,
                parent_uids=["Interactive API Test"],
                entries=[
                    report.TestGroupReport(
                        name="Suite1",
                        uid="MT1Suite1",
                        category=report.ReportCategories.TESTSUITE,
                        parent_uids=["Interactive API Test", "MTest1"],
                        entries=[
                            report.TestCaseReport(
                                name="TestCase1",
                                uid="MT1S1TC1",
                                parent_uids=[
                                    "Interactive API Test",
                                    "MTest1",
                                    "MT1Suite1",
                                ],
                            ),
                            report.TestGroupReport(
                                name="ParametrizedTestCase",
                                uid="MT1S1TC2",
                                category=(
                                    report.ReportCategories.PARAMETRIZATION
                                ),
                                parent_uids=[
                                    "Interactive API Test",
                                    "MTest1",
                                    "MT1Suite1",
                                ],
                                entries=[
                                    report.TestCaseReport(
                                        name="ParametrizedTestCase_0",
                                        uid="MT1S1TC2_0",
                                        parent_uids=[
                                            "Interactive API Test",
                                            "MTest1",
                                            "MT1Suite1",
                                            "MT1S1TC2",
                                        ],
                                    ),
                                    report.TestCaseReport(
                                        name="ParametrizedTestCase_1",
                                        uid="MT1S1TC2_1",
                                        parent_uids=[
                                            "Interactive API Test",
                                            "MTest1",
                                            "MT1Suite1",
                                            "MT1S1TC2",
                                        ],
                                    ),
                                    report.TestCaseReport(
                                        name="ParametrizedTestCase_2",
                                        uid="MT1S1TC2_2",
                                        parent_uids=[
                                            "Interactive API Test",
                                            "MTest1",
                                            "MT1Suite1",
                                            "MT1S1TC2",
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    report.TestGroupReport(
                        name="After Stop",
                        uid="MT1AS",
                        category=report.ReportCategories.SYNTHESIZED,
                        parent_uids=["Interactive API Test", "MTest1"],
                        entries=[
                            report.TestCaseReport(
                                name="after_stop_hook",
                                uid="MT1ASH",
                                category=report.ReportCategories.SYNTHESIZED,
                                parent_uids=[
                                    "Interactive API Test",
                                    "MTest1",
                                    "MT1AS",
                                ],
                            ),
                        ],
                    ),
                ],
            )
        ],
    )


@pytest.fixture()
def api_env(example_report):
    """
    Set up and yield a client object for the API and the interactive handler.
    """
    mock_target = mock.MagicMock()
    mock_target.cfg.name = "Interactive API Test"

    with mock.patch(
        "testplan.runnable.interactive.reloader.ModuleReloader"
    ) as MockReloader:
        MockReloader.return_value = None

        ihandler = TestRunnerIHandler(target=mock_target)
        ihandler._report = example_report
        ihandler.reset_all_tests = mock.MagicMock()
        ihandler.reset_test = mock.MagicMock()
        ihandler.run_all_tests = mock.MagicMock()
        ihandler.run_test = mock.MagicMock()
        ihandler.run_test_suite = mock.MagicMock()
        ihandler.run_test_case = mock.MagicMock()
        ihandler.run_test_case_param = mock.MagicMock()
        ihandler.start_test_resources = mock.MagicMock()
        ihandler.stop_test_resources = mock.MagicMock()

        # Add a couple of fake attachments.
        ihandler.report.attachments = {
            "attached_log.txt": "/path/to/attached_log.txt",
            "attached_image.png": "/path/to/attached_image.png",
        }

        app, _ = http.generate_interactive_api(ihandler)
        app.config["TESTING"] = True

        with app.test_client() as client:
            yield client, ihandler


class TestReport:
    """Test the Report resource."""

    def test_get(self, api_env):
        """Test reading the Report resource via GET."""
        client, ihandler = api_env

        json_report = ihandler.report.shallow_serialize()
        rsp = client.get("/api/v1/interactive/report")
        assert rsp.status_code == 200
        json_rsp = rsp.get_json()
        assert (
            json_rsp["runtime_status"]
            == report.RuntimeStatus.READY.to_json_compatible()
        )
        compare_json(json_rsp, json_report)

    def test_put(self, api_env):
        """Test updating the Report resource via PUT."""
        client, ihandler = api_env

        json_report = ihandler.report.shallow_serialize()
        json_report[
            "runtime_status"
        ] = report.RuntimeStatus.RUNNING.to_json_compatible()
        rsp = client.put("/api/v1/interactive/report", json=json_report)
        assert rsp.status_code == 200
        rsp_json = rsp.get_json()
        assert (
            rsp_json["runtime_status"]
            == report.RuntimeStatus.WAITING.to_json_compatible()
        )
        compare_json(rsp_json, json_report, ignored_keys=["runtime_status"])

        ihandler.run_all_tests.assert_called_once_with(
            shallow_report=None, await_results=False
        )

    def test_put_filtered(self, api_env):
        """Test updating the Report resource via PUT."""
        client, ihandler = api_env

        json_report = ihandler.report.serialize()
        json_report[
            "runtime_status"
        ] = report.RuntimeStatus.RUNNING.to_json_compatible()
        json_report["information"] = [
            list(t) for t in json_report["information"]
        ]
        rsp = client.put("/api/v1/interactive/report", json=json_report)
        assert rsp.status_code == 200

        ihandler.run_all_tests.assert_called_once_with(
            shallow_report=json_report,
            await_results=False,
        )

    def test_put_reset(self, api_env):
        """Test resetting the Report resource via PUT."""
        client, ihandler = api_env

        json_report = ihandler.report.shallow_serialize()
        json_report[
            "runtime_status"
        ] = report.RuntimeStatus.RESETTING.to_json_compatible()
        rsp = client.put("/api/v1/interactive/report", json=json_report)
        assert rsp.status_code == 200
        rsp_json = rsp.get_json()
        assert (
            rsp_json["runtime_status"]
            == report.RuntimeStatus.WAITING.to_json_compatible()
        )
        compare_json(rsp_json, json_report, ignored_keys=["runtime_status"])

        ihandler.reset_all_tests.assert_called_once_with(await_results=False)

    def test_put_validation(self, api_env):
        """Test that (400 if Werkzeug < 2.3.0 else 415) is returned for invalid PUT data."""
        client, ihandler = api_env
        api_url = "/api/v1/interactive/report"

        # JSON body is required.
        rsp = client.put(api_url)
        assert rsp.status_code in (400, 415)

        # "uid" field is required.
        rsp = client.put(api_url, json={"name": "ReportName"})
        assert rsp.status_code in (400, 415)

        # "uid" field cannot be changed.
        shallow_report = ihandler.report.shallow_serialize()
        shallow_report["uid"] = "I have changed"
        rsp = client.put(api_url, json=shallow_report)
        assert rsp.status_code in (400, 415)


class TestAllTests:
    """Test the AllTests resource."""

    def test_get(self, api_env):
        """Test reading the AllTests resource via GET."""
        client, ihandler = api_env
        rsp = client.get("/api/v1/interactive/report/tests")
        assert rsp.status_code == 200
        json_rsp = rsp.get_json()
        json_tests = [test.shallow_serialize() for test in ihandler.report]
        compare_json(json_rsp, json_tests)

    def test_put(self, api_env):
        """
        Test attempting to update the AllTests resource via PUT. This resource
        is read-only so PUT is not allowed.
        """
        client, _ = api_env
        rsp = client.put("/api/v1/interactive/report/tests")
        assert rsp.status_code == 405


class TestSingleTest:
    """Test the SingleTest resource."""

    def test_get(self, api_env):
        """Test reading the SingleTest resource via GET."""
        client, ihandler = api_env
        rsp = client.get("/api/v1/interactive/report/tests/MTest1")
        assert rsp.status_code == 200

        json_rsp = rsp.get_json()
        json_test = ihandler.report["MTest1"].shallow_serialize()
        compare_json(json_rsp, json_test)

    def test_put(self, api_env):
        """Test updating the SingleTest resource via PUT."""
        client, ihandler = api_env

        json_test = ihandler.report["MTest1"].shallow_serialize()
        json_test[
            "runtime_status"
        ] = report.RuntimeStatus.RUNNING.to_json_compatible()
        rsp = client.put(
            "/api/v1/interactive/report/tests/MTest1", json=json_test
        )
        assert rsp.status_code == 200
        json_rsp = rsp.get_json()
        assert (
            json_rsp["runtime_status"]
            == report.RuntimeStatus.WAITING.to_json_compatible()
        )
        compare_json(json_rsp, json_test, ignored_keys=["runtime_status"])

        ihandler.run_test.assert_called_once_with(
            "MTest1", shallow_report=None, await_results=False
        )

    def test_put_filtered(self, api_env):
        """Test updating the SingleTest resource via PUT."""
        client, ihandler = api_env

        json_test = ihandler.report["MTest1"].serialize()
        json_test[
            "runtime_status"
        ] = report.RuntimeStatus.RUNNING.to_json_compatible()
        rsp = client.put(
            "/api/v1/interactive/report/tests/MTest1", json=json_test
        )
        assert rsp.status_code == 200
        ihandler.run_test.assert_called_once_with(
            "MTest1", shallow_report=json_test, await_results=False
        )

    def test_put_reset(self, api_env):
        """Test resetting the Report resource via PUT."""
        client, ihandler = api_env

        json_test = ihandler.report["MTest1"].shallow_serialize()
        json_test[
            "runtime_status"
        ] = report.RuntimeStatus.RESETTING.to_json_compatible()
        rsp = client.put(
            "/api/v1/interactive/report/tests/MTest1", json=json_test
        )
        assert rsp.status_code == 200
        json_rsp = rsp.get_json()
        assert (
            json_rsp["runtime_status"]
            == report.RuntimeStatus.WAITING.to_json_compatible()
        )
        compare_json(json_rsp, json_test, ignored_keys=["runtime_status"])

        ihandler.reset_test.assert_called_once_with(
            "MTest1", await_results=False
        )

    def test_put_env(self, api_env):
        """Test starting and stopping a test environment via PUT."""
        client, ihandler = api_env

        json_test = ihandler.report["MTest1"].shallow_serialize()
        json_test["env_status"] = "STARTING"
        rsp = client.put(
            "/api/v1/interactive/report/tests/MTest1", json=json_test
        )
        assert rsp.status_code == 200
        compare_json(rsp.get_json(), json_test)

        ihandler.start_test_resources.assert_called_once_with(
            "MTest1", await_results=False
        )

        # Mark the environment as STARTED and then request for it to stop.
        ihandler.report["MTest1"].env_status = "STARTED"
        json_test["env_status"] = "STOPPING"
        rsp = client.put(
            "/api/v1/interactive/report/tests/MTest1", json=json_test
        )
        assert rsp.status_code == 200
        compare_json(rsp.get_json(), json_test)

        ihandler.stop_test_resources.assert_called_once_with(
            "MTest1", await_results=False
        )

        # Try requesting an invalid environment state change - should be
        # rejected.
        ihandler.report["MTest1"].env_status = "STARTING"
        json_test["env_status"] = "STOPPING"
        rsp = client.put(
            "/api/v1/interactive/report/tests/MTest1", json=json_test
        )
        assert rsp.status_code in (400, 415)

    def test_put_validation(self, api_env):
        """Test that (400 if Werkzeug < 2.3.0 else 415) is returned for invalid PUT data."""
        client, ihandler = api_env
        api_url = "/api/v1/interactive/report/tests/MTest1"

        # JSON body is required.
        rsp = client.put(api_url)
        assert rsp.status_code in (400, 415)

        # "uid" field is required.
        rsp = client.put(api_url, json={"name": "MTestName"})
        assert rsp.status_code in (400, 415)

        # "uid" field cannot be changed.
        json_test = ihandler.report["MTest1"].shallow_serialize()
        json_test["uid"] = "I have changed"
        rsp = client.put(api_url, json=json_test)
        assert rsp.status_code in (400, 415)

        # Cannot change status if test is already running/resetting/waiting
        json_test = ihandler.report["MTest1"].shallow_serialize()
        json_test[
            "runtime_status"
        ] = report.RuntimeStatus.RUNNING.to_json_compatible()
        rsp = client.put(api_url, json=json_test)
        assert rsp.status_code == 200
        rsp = client.put(api_url, json=json_test)
        assert rsp.status_code == 200
        json_rsp = rsp.get_json()
        assert (
            json_rsp["runtime_status"]
            == report.RuntimeStatus.WAITING.to_json_compatible()
        )


class TestAllSuites:
    """Test the AllSuites resource."""

    def test_get(self, api_env):
        """Test reading the AllSuites resource via GET."""
        client, ihandler = api_env
        rsp = client.get("/api/v1/interactive/report/tests/MTest1/suites")
        assert rsp.status_code == 200
        json_rsp = rsp.get_json()
        json_suites = [
            suite.shallow_serialize() for suite in ihandler.report["MTest1"]
        ]
        compare_json(json_rsp, json_suites)

    def test_put(self, api_env):
        """
        Test attempting to update the AllSuites resource via PUT. This resource
        is read-only so PUT is not allowed.
        """
        client, _ = api_env
        rsp = client.put("/api/v1/interactive/report/tests/MTest1/suites")
        assert rsp.status_code == 405


class TestSingleSuite:
    """Test the SingleSuite resource."""

    def test_get(self, api_env):
        """Test reading the SingleSuite resource via GET."""
        client, ihandler = api_env
        rsp = client.get(
            "/api/v1/interactive/report/tests/MTest1/suites/MT1Suite1"
        )
        assert rsp.status_code == 200

        json_rsp = rsp.get_json()
        suite_json = ihandler.report["MTest1"]["MT1Suite1"].shallow_serialize()
        compare_json(json_rsp, suite_json)

    def test_put(self, api_env):
        """Test updating the SingleSuite resource via PUT."""
        client, ihandler = api_env

        suite_json = ihandler.report["MTest1"]["MT1Suite1"].shallow_serialize()
        suite_json[
            "runtime_status"
        ] = report.RuntimeStatus.RUNNING.to_json_compatible()
        rsp = client.put(
            "/api/v1/interactive/report/tests/MTest1/suites/MT1Suite1",
            json=suite_json,
        )
        assert rsp.status_code == 200
        json_rsp = rsp.get_json()
        assert (
            json_rsp["runtime_status"]
            == report.RuntimeStatus.WAITING.to_json_compatible()
        )
        compare_json(json_rsp, suite_json, ignored_keys=["runtime_status"])

        ihandler.run_test_suite.assert_called_once_with(
            "MTest1", "MT1Suite1", shallow_report=None, await_results=False
        )

    def test_put_filtered(self, api_env):
        """Test updating the SingleSuite resource via PUT."""
        client, ihandler = api_env

        suite_json = ihandler.report["MTest1"]["MT1Suite1"].serialize()
        suite_json[
            "runtime_status"
        ] = report.RuntimeStatus.RUNNING.to_json_compatible()
        rsp = client.put(
            "/api/v1/interactive/report/tests/MTest1/suites/MT1Suite1",
            json=suite_json,
        )
        assert rsp.status_code == 200
        ihandler.run_test_suite.assert_called_once_with(
            "MTest1",
            "MT1Suite1",
            shallow_report=suite_json,
            await_results=False,
        )

    def test_put_validation(self, api_env):
        """Test that (400 if Werkzeug < 2.3.0 else 415) is returned for invalid PUT data."""
        client, ihandler = api_env
        api_url = "/api/v1/interactive/report/tests/MTest1/suites/MT1Suite1"

        # JSON body is required.
        rsp = client.put(api_url)
        assert rsp.status_code in (400, 415)

        # "uid" field is required.
        rsp = client.put(api_url, json={"name": "SuiteName"})
        assert rsp.status_code in (400, 415)

        # "uid" field cannot be changed.
        shallow_suite = ihandler.report["MTest1"][
            "MT1Suite1"
        ].shallow_serialize()
        shallow_suite["uid"] = "I have changed"
        rsp = client.put(api_url, json=shallow_suite)
        assert rsp.status_code in (400, 415)


class TestAllTestcases:
    """Test the Testcases resource."""

    def test_get(self, api_env):
        """Test reading the AllTestcases resource via GET."""
        client, ihandler = api_env
        rsp = client.get(
            "/api/v1/interactive/report/tests/MTest1/suites/MT1Suite1/testcases"
        )
        assert rsp.status_code == 200
        json_rsp = rsp.get_json()
        json_testcases = [
            serialize_testcase(testcase)
            for testcase in ihandler.report["MTest1"]["MT1Suite1"]
        ]
        compare_json(json_rsp, json_testcases)

    def test_put(self, api_env):
        """
        Test attempting to update the AllTestcases resource via PUT. This
        resource is read-only so PUT is not allowed.
        """
        client, _ = api_env
        rsp = client.put(
            "/api/v1/interactive/report/tests/MTest1/suites/MT1Suite1/testcases"
        )
        assert rsp.status_code == 405


class TestSingleTestcase:
    """Test the SingleTestcase resource."""

    @pytest.mark.parametrize("testcase_uid", ["MT1S1TC1", "MT1S1TC2"])
    def test_get(self, api_env, testcase_uid):
        """Test reading the SingleTestcase resource via GET."""
        client, ihandler = api_env
        rsp = client.get(
            "/api/v1/interactive/report/tests/MTest1/suites/MT1Suite1/"
            "testcases/{}".format(testcase_uid)
        )
        assert rsp.status_code == 200

        json_rsp = rsp.get_json()

        report_entry = ihandler.report["MTest1"]["MT1Suite1"][testcase_uid]

        if isinstance(report_entry, report.TestCaseReport):
            testcase_json = report_entry.serialize()
        elif isinstance(report_entry, report.TestGroupReport):
            testcase_json = report_entry.shallow_serialize()
        else:
            raise TypeError("Unexpected report type.")

        compare_json(json_rsp, testcase_json)

    @pytest.mark.parametrize("testcase_uid", ["MT1S1TC1", "MT1S1TC2"])
    def test_put(self, api_env, testcase_uid):
        """Test updating the SingleTestcase resource via PUT."""
        client, ihandler = api_env
        report_entry = ihandler.report["MTest1"]["MT1Suite1"][testcase_uid]

        if isinstance(report_entry, report.TestCaseReport):
            testcase_json = report_entry.serialize()
        elif isinstance(report_entry, report.TestGroupReport):
            testcase_json = report_entry.shallow_serialize()
        else:
            raise TypeError("Unexpected report type")

        testcase_json[
            "runtime_status"
        ] = report.RuntimeStatus.RUNNING.to_json_compatible()
        if "entries" in testcase_json:
            del testcase_json["entries"]
        rsp = client.put(
            "/api/v1/interactive/report/tests/MTest1/suites/MT1Suite1/"
            "testcases/{}".format(testcase_uid),
            json=testcase_json,
        )
        assert rsp.status_code == 200
        json_rsp = rsp.get_json()
        assert (
            json_rsp["runtime_status"]
            == report.RuntimeStatus.WAITING.to_json_compatible()
        )
        compare_json(json_rsp, testcase_json, ignored_keys=["runtime_status"])

        ihandler.run_test_case.assert_called_once_with(
            "MTest1",
            "MT1Suite1",
            testcase_uid,
            shallow_report=None,
            await_results=False,
        )

    def test_put_filtered(self, api_env):
        """Test updating the SingleTestcase resource via PUT."""
        client, ihandler = api_env
        report_entry = ihandler.report["MTest1"]["MT1Suite1"]["MT1S1TC1"]

        testcase_json = report_entry.serialize()
        testcase_json[
            "runtime_status"
        ] = report.RuntimeStatus.RUNNING.to_json_compatible()
        rsp = client.put(
            "/api/v1/interactive/report/tests/MTest1/suites/MT1Suite1/"
            "testcases/{}".format("MT1S1TC1"),
            json=testcase_json,
        )
        assert rsp.status_code == 200
        ihandler.run_test_case.assert_called_once_with(
            "MTest1",
            "MT1Suite1",
            "MT1S1TC1",
            shallow_report=testcase_json,
            await_results=False,
        )

    def test_put_filtered_parametrized(self, api_env):
        client, ihandler = api_env
        report_entry = ihandler.report["MTest1"]["MT1Suite1"]["MT1S1TC2"]

        testcase_json = report_entry.serialize()
        testcase_json[
            "runtime_status"
        ] = report.RuntimeStatus.RUNNING.to_json_compatible()
        rsp = client.put(
            "/api/v1/interactive/report/tests/MTest1/suites/MT1Suite1/"
            "testcases/{}".format("MT1S1TC2"),
            json=testcase_json,
        )
        assert rsp.status_code == 200
        ihandler.run_test_case.assert_called_once_with(
            "MTest1",
            "MT1Suite1",
            "MT1S1TC2",
            shallow_report=testcase_json,
            await_results=False,
        )

    def test_put_validation(self, api_env):
        """Test that (400 if Werkzeug < 2.3.0 else 415) is returned for invalid PUT data."""
        client, ihandler = api_env
        api_url = (
            "/api/v1/interactive/report/tests/MTest1/suites/MT1Suite1/"
            "testcases/MT1S1TC1"
        )

        # JSON body is required.
        rsp = client.put(api_url)
        assert rsp.status_code in (400, 415)

        # "uid" field is required.
        rsp = client.put(api_url, json={"name": "TestcaseName"})
        assert rsp.status_code in (400, 415)

        # "uid" field cannot be changed.
        serialized_testcase = ihandler.report["MTest1"]["MT1Suite1"][
            "MT1S1TC1"
        ].serialize()
        serialized_testcase["uid"] = "I have changed"
        rsp = client.put(api_url, json=serialized_testcase)
        assert rsp.status_code in (400, 415)


class TestAllParametrizations:
    """Test the AllParametrizations resource."""

    def test_get(self, api_env):
        """Test reading the AllParametrizations resource via GET."""
        client, ihandler = api_env
        rsp = client.get(
            "/api/v1/interactive/report/tests/MTest1/suites/MT1Suite1/"
            "testcases/MT1S1TC2/parametrizations"
        )
        assert rsp.status_code == 200
        json_rsp = rsp.get_json()
        json_parametrizations = [
            param.serialize()
            for param in ihandler.report["MTest1"]["MT1Suite1"]["MT1S1TC2"]
        ]
        compare_json(json_rsp, json_parametrizations)

    def test_put(self, api_env):
        """
        Test attempting to update the AllParametrizations resource via PUT.
        This resource is read-only so PUT is not allowed.
        """
        client, _ = api_env
        rsp = client.put(
            "/api/v1/interactive/report/tests/MTest1/suites/MT1Suite1/"
            "testcases/MT1S1TC2/parametrizations"
        )
        assert rsp.status_code == 405


class TestParametrizedTestCase:
    """Test the ParametrizedTestCase resource."""

    def test_get(self, api_env):
        """Test reading the ParametrizedTestCase resource via GET."""
        client, ihandler = api_env
        rsp = client.get(
            "/api/v1/interactive/report/tests/MTest1/suites/MT1Suite1/"
            "testcases/MT1S1TC2/parametrizations/MT1S1TC2_0"
        )
        assert rsp.status_code == 200
        json_rsp = rsp.get_json()

        report_entry = ihandler.report["MTest1"]["MT1Suite1"]["MT1S1TC2"][
            "MT1S1TC2_0"
        ]
        testcase_json = report_entry.serialize()
        compare_json(json_rsp, testcase_json)

    def test_put(self, api_env):
        """Test updating the ParametrizedTestCase resource via PUT."""
        client, ihandler = api_env
        report_entry = ihandler.report["MTest1"]["MT1Suite1"]["MT1S1TC2"][
            "MT1S1TC2_0"
        ]
        testcase_json = report_entry.serialize()
        if "entries" in testcase_json:
            del testcase_json["entries"]
        testcase_json[
            "runtime_status"
        ] = report.RuntimeStatus.RUNNING.to_json_compatible()
        rsp = client.put(
            "/api/v1/interactive/report/tests/MTest1/suites/MT1Suite1/"
            "testcases/MT1S1TC2/parametrizations/MT1S1TC2_0",
            json=testcase_json,
        )
        assert rsp.status_code == 200
        json_rsp = rsp.get_json()
        assert (
            json_rsp["runtime_status"]
            == report.RuntimeStatus.WAITING.to_json_compatible()
        )
        compare_json(json_rsp, testcase_json, ignored_keys=["runtime_status"])

        ihandler.run_test_case_param.assert_called_once_with(
            "MTest1",
            "MT1Suite1",
            "MT1S1TC2",
            "MT1S1TC2_0",
            await_results=False,
        )

    def test_put_validation(self, api_env):
        """Test that (400 if Werkzeug < 2.3.0 else 415) is returned for invalid PUT data."""
        client, ihandler = api_env
        api_url = (
            "/api/v1/interactive/report/tests/MTest1/suites/MT1Suite1/"
            "testcases/MT1S1TC2/parametrizations/MT1S1TC2_0"
        )

        # JSON body is required.
        rsp = client.put(api_url)
        assert rsp.status_code in (400, 415)

        # "uid" field is required.
        rsp = client.put(api_url, json={"name": "TestcaseName"})
        assert rsp.status_code in (400, 415)

        # "uid" field cannot be changed.
        serialized_testcase = ihandler.report["MTest1"]["MT1Suite1"][
            "MT1S1TC2"
        ]["MT1S1TC2_0"].serialize()
        serialized_testcase["uid"] = "I have changed"
        rsp = client.put(api_url, json=serialized_testcase)
        assert rsp.status_code in (400, 415)


class TestAllAttachments:
    """Test the AllAttachments resource."""

    def test_get(self, api_env):
        """
        Test that getting AllAttachments returns a list of the attachment UIDs.
        """
        client, _ = api_env
        rsp = client.get("/api/v1/interactive/attachments")
        assert rsp.status_code == 200
        assert rsp.get_json() == ["attached_log.txt", "attached_image.png"]

    def test_put(self, api_env):
        """
        Test attempting to update the AllAttachments resource via PUT.
        This resource is read-only so PUT is not allowed.
        """
        client, _ = api_env
        rsp = client.put("/api/v1/interactive/attachments")
        assert rsp.status_code == 405


class TestSingleAttachment:
    """Test the SingleAttachment resource."""

    @mock.patch("flask.send_file", return_value="texttexttext")
    def test_get(self, mock_send_file, api_env):
        """Test that a specific attachment can be retrieved."""
        client, _ = api_env
        rsp = client.get("/api/v1/interactive/attachments/attached_log.txt")
        assert rsp.status_code == 200
        assert rsp.get_json() == "texttexttext"
        mock_send_file.assert_called_once_with("/path/to/attached_log.txt")

    def test_put(self, api_env):
        """
        Test attempting to update the SingleAttachment resource via PUT.
        This resource is read-only so PUT is not allowed.
        """
        client, _ = api_env
        rsp = client.put("/api/v1/interactive/attachments/attached_log.txt")
        assert rsp.status_code == 405


def compare_json(actual, expected, ignored_keys=None):
    """
    Compare the actual and expected JSON returned from the API. Since the
    JSON contains a hash value we cannot predict, we cannot simply check
    for exact equality against a reference.
    """
    ignored_keys = ignored_keys or []
    if isinstance(actual, list):
        assert isinstance(expected, list)
        for actual_item, expected_item in zip(actual, expected):
            compare_json(actual_item, expected_item, ignored_keys)
    else:
        assert isinstance(actual, dict)
        assert isinstance(expected, dict)

        for key in expected:
            # Skip checking the "hash" key.
            if key != "hash" and key not in ignored_keys:
                assert actual[key] == expected[key]


def serialize_testcase(testcase):
    """
    Serialize a testcase.

    If the testcase contains parametrizations, it will be represented as a
    TestGroupReport in the report tree and should be shallow-serialized.
    Otherwise, for a regular testcase we serialize the whole thing including
    its entries.
    """
    if isinstance(testcase, report.TestCaseReport):
        return testcase.serialize()
    elif isinstance(testcase, report.TestGroupReport):
        return testcase.shallow_serialize()
    else:
        raise TypeError("Unexpected testcase type: {}".format(type(testcase)))
