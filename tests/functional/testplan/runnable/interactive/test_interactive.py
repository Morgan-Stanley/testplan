"""Interactive mode tests."""

import json
import os
from pathlib import Path

import requests
from pytest_test_filters import skip_on_windows

from testplan import TestplanMock
from testplan.common import entity
from testplan.common.utils.comparison import compare
from testplan.common.utils.context import context
from testplan.common.utils.logger import USER_INFO
from testplan.common.utils.timing import wait
from testplan.environment import LocalEnvironment
from testplan.testing.multitest import MultiTest, testcase, testsuite
from testplan.testing.multitest.driver.tcp import TCPClient, TCPServer
from tests.functional.testplan.runnable.interactive.interactive_helper import (
    wait_for_interactive_start,
)

THIS_DIRECTORY = os.path.dirname(os.path.abspath(__file__))


def load_from_json(path: Path) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def dump_to_file(data, path, ignore):
    """
    utility for dumping data from updated schema,
    we'd better leave it here
    """

    def _(d):
        for k, v in d.items():
            if isinstance(v, dict):
                if k in ignore:
                    d[k] = {}
                else:
                    d[k] = _(v)
            elif isinstance(v, list):
                if k in ignore:
                    d[k] = []
                else:
                    d[k] = list(
                        map(lambda x: _(x) if isinstance(x, dict) else x, v)
                    )
            elif k in ignore:
                d[k] = type(v)()
        return d

    data = _(data)
    with open(path, "w") as f:
        json.dump(data, f, sort_keys=True, indent=4)


class InteractivePlan:
    def __init__(self, **kwargs):
        self._kwargs = kwargs

    def __enter__(self):
        self._plan = TestplanMock(**self._kwargs)
        return self._plan

    def __exit__(self, *args):
        self._plan.abort()


@testsuite
class BasicSuite:
    @testcase(parameters=range(3))
    def basic_case(self, env, result, arg):
        result.equal(1, 1, description="Passing assertion")


@testsuite(name=lambda cls_name, suite: "Custom_{}".format(suite.arg))
class TCPSuite:
    def __init__(self, arg):
        self.arg = arg

    @testcase
    def send_and_receive_msg(self, env, result):
        """
        Client sends a message, server received and responds back.
        """
        bytes_sent = env.client.send_text("hello")
        received = env.server.receive_text(size=bytes_sent)
        result.equal(received, "hello", "Server received")

        bytes_sent = env.server.send_text("world")
        received = env.client.receive_text(size=bytes_sent)
        result.equal(received, "world", "Client received")


def make_multitest(idx=""):
    def accept_connection(env):
        # Server accepts client connection.
        env.server.accept_connection()

    return MultiTest(
        name="Test{}".format(idx),
        suites=[BasicSuite(), TCPSuite(0), TCPSuite(1)],
        environment=[
            TCPServer(name="server"),
            TCPClient(
                name="client",
                host=context("server", "{{host}}"),
                port=context("server", "{{port}}"),
            ),
        ],
        after_start=accept_connection,
    )


def test_top_level_tests():
    with InteractivePlan(
        name="InteractivePlan",
        interactive_port=0,
        interactive_block=False,
        parse_cmdline=False,
        logger_level=USER_INFO,
    ) as plan:
        plan.add(make_multitest("1"))
        plan.add(make_multitest("2"))
        plan.run()
        wait_for_interactive_start(plan)
        assert isinstance(plan.interactive.test("Test1"), MultiTest)
        assert isinstance(plan.interactive.test("Test2"), MultiTest)

        # TESTS AND ASSIGNED RUNNERS
        assert list(plan.interactive.all_tests()) == ["Test1", "Test2"]

        plan.interactive.start_test_resources("Test2")  # START

        for resource in plan.interactive.test("Test2").resources:
            assert resource.status == resource.STATUS.STARTED

        plan.interactive.stop_test_resources("Test2")  # STOP
        for resource in plan.interactive.test("Test2").resources:
            assert resource.status == resource.STATUS.STOPPED

        # RESET REPORTS
        plan.interactive.reset_all_tests()

        BTLReset = load_from_json(
            Path(__file__).parent / "reports" / "basic_top_level_reset.data"
        )
        res = compare(
            BTLReset,
            plan.interactive.report.serialize(),
            ignore=["hash", "information", "timezone"],
        )
        assert res[0] is True

        # RUN ALL TESTS
        plan.interactive.run_all_tests()

        BTLevel = load_from_json(
            Path(__file__).parent / "reports" / "basic_top_level.data"
        )
        res = compare(
            BTLevel,
            plan.interactive.report.serialize(),
            ignore=[
                "hash",
                "information",
                "timer",
                "timestamp",
                "timezone",
            ],
        )
        assert res[0] is True

        # RESET REPORTS
        plan.interactive.reset_all_tests()
        res = compare(
            BTLReset,
            plan.interactive.report.serialize(),
            ignore=["hash", "information", "timezone"],
        )
        assert res[0] is True

        # RUN SINGLE TESTSUITE (CUSTOM NAME)
        plan.interactive.run_test_suite("Test2", "Custom_1")

        BRSTest2 = load_from_json(
            Path(__file__).parent / "reports" / "basic_run_suite_test2.data"
        )
        res = compare(
            BRSTest2,
            plan.interactive.test_report("Test2"),
            ignore=[
                "hash",
                "timer",
                "timestamp",
                "timezone",
            ],
        )
        assert res[0] is True

        # RUN SINGLE TESTCASE
        plan.interactive.run_test_case("Test1", "*", "basic_case__arg_1")

        BRCTest1 = load_from_json(
            Path(__file__).parent / "reports" / "basic_run_case_test1.data"
        )
        res = compare(
            BRCTest1,
            plan.interactive.test_report("Test1"),
            ignore=[
                "hash",
                "timer",
                "timestamp",
                "timezone",
            ],
        )
        assert res[0] is True


def test_top_level_environment():
    with InteractivePlan(
        name="InteractivePlan",
        interactive_port=0,
        interactive_block=False,
        parse_cmdline=False,
        logger_level=USER_INFO,
    ) as plan:
        plan.add_environment(
            LocalEnvironment(
                "env1",
                [
                    TCPServer(name="server"),
                    TCPClient(
                        name="client",
                        host=context("server", "{{host}}"),
                        port=context("server", "{{port}}"),
                    ),
                ],
            )
        )
        plan.run()
        wait_for_interactive_start(plan)

        assert len(plan.resources.environments.envs) == 1
        env_uid = "env1"

        env = plan.interactive.get_environment(env_uid)
        assert isinstance(env, entity.Environment)
        resources = [res.uid() for res in env]
        assert resources == ["server", "client"]
        for resource in env:
            assert resource.status == resource.STATUS.NONE
        plan.interactive.start_environment(env_uid)  # START

        # INSPECT THE CONTEXT WHEN STARTED
        env_context = plan.interactive.get_environment_context(env_uid)
        for resource in [res.uid() for res in env]:
            res_context = plan.interactive.environment_resource_context(
                env_uid, resource_uid=resource
            )
            assert env_context[resource] == res_context
            assert isinstance(res_context["host"], str)
            assert isinstance(res_context["port"], int)
            assert res_context["port"] > 0

        # CUSTOM RESOURCE OPERATIONS
        plan.interactive.environment_resource_operation(
            env_uid, "server", "accept_connection"
        )
        plan.interactive.environment_resource_operation(
            env_uid, "client", "send_text", msg="hello"
        )
        received = plan.interactive.environment_resource_operation(
            env_uid, "server", "receive_text"
        )
        assert received == "hello"
        plan.interactive.environment_resource_operation(
            env_uid, "server", "send_text", msg="worlds"
        )
        received = plan.interactive.environment_resource_operation(
            env_uid, "client", "receive_text"
        )
        assert received == "worlds"

        for resource in env:
            assert resource.status == resource.STATUS.STARTED
        plan.interactive.stop_environment(env_uid)  # STOP
        for resource in env:
            assert resource.status == resource.STATUS.STOPPED


def put_request(url, data):
    headers = {"content-type": "application/json"}
    return requests.put(url, headers=headers, json=data)


@skip_on_windows(reason="Failing on windows, disable for now")
def test_env_operate():
    with InteractivePlan(
        name="InteractivePlan",
        interactive_port=0,
        interactive_block=False,
        parse_cmdline=False,
        logger_level=USER_INFO,
    ) as plan:

        plan.add(make_multitest("1"))
        plan.add(make_multitest("2"))

        plan.run()
        wait_for_interactive_start(plan)
        addr = "http://{}:{}".format(*plan.interactive.http_handler_info)

        response = requests.get(f"{addr}/api/v1/interactive/report/tests")
        assert response.ok

        current_report = response.json()
        assert len(current_report) == 2

        for resource in plan.interactive.test("Test2").resources:
            assert resource.status == resource.STATUS.NONE

        test2_report = current_report[1].copy()
        assert test2_report["name"] == "Test2"

        # Start env
        test2_report["env_status"] = entity.ResourceStatus.STARTING
        response = put_request(
            url=f"{addr}/api/v1/interactive/report/tests/Test2",
            data=test2_report,
        )
        assert response.ok

        current_test2_report = plan.interactive.report["Test2"]
        assert current_test2_report.env_status in (
            entity.ResourceStatus.STARTING,
            entity.ResourceStatus.STARTED,
        )

        wait(
            lambda: plan.interactive.report["Test2"].env_status
            == entity.ResourceStatus.STARTED,
            5,
            raise_on_timeout=True,
        )

        response = requests.get(
            f"{addr}/api/v1/interactive/report/tests/Test2"
        )
        assert response.ok
        test2_report = response.json()
        assert test2_report["env_status"] == entity.ResourceStatus.STARTED

        # Stop env
        test2_report["env_status"] = entity.ResourceStatus.STOPPING
        response = put_request(
            url=f"{addr}/api/v1/interactive/report/tests/Test2",
            data=test2_report,
        )
        assert response.ok

        current_test2_report = plan.interactive.report["Test2"]
        assert current_test2_report.env_status in (
            entity.ResourceStatus.STOPPING,
            entity.ResourceStatus.STOPPED,
        )
        wait(
            lambda: plan.interactive.report["Test2"].env_status
            == entity.ResourceStatus.STOPPED,
            5,
            raise_on_timeout=True,
        )

        response = requests.get(
            f"{addr}/api/v1/interactive/report/tests/Test2"
        )
        assert response.ok
        test2_report = response.json()
        assert test2_report["env_status"] == entity.ResourceStatus.STOPPED


def test_abort_handler():
    with InteractivePlan(
        name="InteractivePlan",
        interactive_port=0,
        interactive_block=False,
        parse_cmdline=False,
        logger_level=USER_INFO,
    ) as plan:
        multitest = make_multitest("1")
        plan.add(multitest)
        plan.run()
        # NOTE: wait until the HTTP handler is available
        wait_for_interactive_start(plan)

        plan.interactive.start_test_resources("Test1")
        for resource in multitest.resources:
            wait(
                lambda: resource.status == resource.STATUS.STARTED,
                timeout=5,
                raise_on_timeout=True,
            )
        # NOTE: triggering abortion for the interactive handler mocking API
        plan.interactive.abort()
        for resource in multitest.resources:
            wait(
                lambda: resource.status == resource.STATUS.STOPPED,
                timeout=5,
                raise_on_timeout=True,
            )


def test_restart_multitest_w_dependencies():
    s = TCPServer(name="server")
    c = TCPClient(
        name="client",
        host=context("server", "{{host}}"),
        port=context("server", "{{port}}"),
    )
    mt = MultiTest(
        name="Test",
        suites=[TCPSuite(0)],
        environment=[s, c],
        dependencies={s: c},
        after_start=lambda env: env.server.accept_connection(),
    )

    with InteractivePlan(
        name="InteractivePlan",
        interactive_port=0,
        interactive_block=False,
        parse_cmdline=False,
        logger_level=USER_INFO,
    ) as plan:
        plan.add(mt)
        plan.run()
        wait_for_interactive_start(plan)

        plan.interactive.start_test_resources("Test")
        plan.interactive.run_test("Test")
        assert plan.interactive.test(
            "Test"
        ).run_result(), "no exceptions in steps"
        assert plan.interactive.report[
            "Test"
        ].unknown, "env stop remain unknown"
        plan.interactive.stop_test_resources("Test")
        assert plan.interactive.report["Test"].passed, "env stop succeeded"

        plan.interactive.reset_all_tests()

        plan.interactive.start_test_resources("Test")
        plan.interactive.run_test("Test")
        assert plan.interactive.test(
            "Test"
        ).run_result(), "no exceptions in steps"
        assert plan.interactive.report[
            "Test"
        ].unknown, "env stop remain unknown"
        plan.interactive.stop_test_resources("Test")
        assert plan.interactive.report["Test"].passed, "env stop succeeded"
