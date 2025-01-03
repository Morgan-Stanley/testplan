"""
Http handler for interactive mode.
"""

import copy
import functools
import os
from typing import Dict, Optional
from urllib.parse import unquote_plus

import flask
import flask_restx
import flask_restx.fields
import marshmallow.exceptions
import werkzeug.exceptions
from cheroot import wsgi
from flask import request

import testplan
from testplan import defaults
from testplan.common import entity
from testplan.common.config import ConfigOption
from testplan.common.exporters import ExportContext, run_exporter
from testplan.report import (
    ReportCategories,
    RuntimeStatus,
    TestCaseReport,
    TestGroupReport,
    TestReport,
)


class OutOfOrderError(Exception):
    def __init__(self, msg):
        super(OutOfOrderError, self).__init__(msg)


def decode_uri_component(func):
    """Decode URI component before arguments passed to url route handler."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        new_kwargs = {key: unquote_plus(val) for key, val in kwargs.items()}
        return func(*args, **new_kwargs)

    return wrapper


def generate_interactive_api(ihandler):
    """Generates the interactive API using Flask."""
    build_directory = os.path.join(
        os.path.dirname(testplan.__file__), "web_ui", "testing", "build"
    )
    static_dir = os.path.join(build_directory, "static")

    api_prefix = "/api/v1/interactive"
    api_blueprint = flask.Blueprint("api", "testplan")
    api = flask_restx.Api(api_blueprint)
    app = flask.Flask("testplan", static_folder=static_dir)
    try:
        from flask_orjson import OrjsonProvider
    except ImportError:
        pass
    else:
        app.json = OrjsonProvider(app)
    app.register_blueprint(api_blueprint, url_prefix=api_prefix)

    post_export_model = api.model(
        "Save report",
        {
            "exporters": flask_restx.fields.List(
                flask_restx.fields.String(example="PDFExporter")
            )
        },
    )

    export_history = []

    @app.route("/interactive/")
    @app.route("/interactive/<path:subpath>")
    def interactive(subpath=None):
        """
        Main entry point for the interactive mode UI page. Serves the static
        index.html from the UI app's build directory. We serve the app at
        /interactive and not just at /index.html or at / because the same app
        is used for batch and interactive report, and the way it
        distinguishes between the two modes is by the URL.
        """
        return flask.send_from_directory(build_directory, "index.html")

    @app.route("/<path:filename>")
    def serve_static(filename):
        """
        Serve all static files (HTML, JS, CSS, images etc.) at the root path.
        """
        return flask.send_from_directory(build_directory, filename)

    @app.after_request
    def add_cache_control_headers(response):
        """
        Disable browser caching for all HTTP requests, so that the most
        up-to-date data is always returned.
        """
        response.headers["Cache-Control"] = "no-cache"
        return response

    @api.errorhandler(OutOfOrderError)
    def execution_out_of_order(err):
        """Return a custom message and 200 status code."""
        return {
            "errmsg": f"{err} Restart runtime environment"
            " to reset test report if necessary."
        }, 200

    @api.errorhandler(werkzeug.exceptions.HTTPException)
    def log_error(err):
        """Log exceptions that will lead to 4XX status code."""
        ihandler.target.logger.exception(err)
        return {"message": str(err)}, err.code

    @api.route("/report")
    class Report(flask_restx.Resource):
        """
        Interactive report endpoint. There is a single root report object
        for interactive mode.
        """

        def get(self):
            """Get the state of the root interactive report."""
            full = flask.request.args.get("full", "false").lower() == "true"
            with ihandler.report_mutex:
                return _serialize_report_entry(ihandler.report, full=full)

        def put(self):
            """Update the state of the root interactive report."""
            shallow_report = flask.request.json
            _validate_json_body(shallow_report)

            with ihandler.report_mutex:
                try:
                    new_report = _deserialize_report_entry(
                        shallow_report, ihandler.report
                    )
                except marshmallow.exceptions.ValidationError as e:
                    raise werkzeug.exceptions.BadRequest(str(e))

                _check_uids_match(ihandler.report.uid, new_report.uid)
                new_runtime_status = RuntimeStatus.from_json_compatible(
                    shallow_report.get("runtime_status")
                )

                if _should_reset(
                    ihandler.report.uid,
                    ihandler.report.runtime_status,
                    new_runtime_status,
                ):
                    ihandler.report.runtime_status = RuntimeStatus.WAITING
                    ihandler.reset_all_tests(await_results=False)
                elif _should_run(
                    ihandler.report.uid,
                    ihandler.report.runtime_status,
                    new_runtime_status,
                ):
                    _check_execution_order(ihandler.report)
                    filtered = "entries" in shallow_report
                    if filtered:
                        entries = _extract_entries(shallow_report)
                        ihandler.report.set_runtime_status_filtered(
                            RuntimeStatus.WAITING,
                            entries,
                        )
                    else:
                        ihandler.report.runtime_status = RuntimeStatus.WAITING
                    ihandler.run_all_tests(
                        shallow_report=shallow_report if filtered else None,
                        await_results=False,
                    )

                return _serialize_report_entry(ihandler.report)

    @api.route("/report/tests")
    class AllTests(flask_restx.Resource):
        """
        Tests endpoint. Represents all Test objects in the report. Read-only.
        """

        def get(self):
            """Get the UIDs of all tests defined in the testplan."""
            with ihandler.report_mutex:
                return [
                    _serialize_report_entry(test_report)
                    for test_report in ihandler.report
                ]

    @api.route("/report/tests/<string:test_uid>")
    class SingleTest(flask_restx.Resource):
        """
        Test endpoint. Represents a single Test object in the testplan with
        corresponding UID.
        """

        _ENV_TRANSITIONS = {
            entity.ResourceStatus.STOPPED: (
                entity.ResourceStatus.STARTING,
                ihandler.start_test_resources,
            ),
            entity.ResourceStatus.STARTED: (
                entity.ResourceStatus.STOPPING,
                ihandler.stop_test_resources,
            ),
        }

        @decode_uri_component
        def get(self, test_uid):
            """Get the state of a specific test from the testplan."""
            with ihandler.report_mutex:
                try:
                    return _serialize_report_entry(ihandler.report[test_uid])
                except KeyError:
                    raise werkzeug.exceptions.NotFound

        @decode_uri_component
        def put(self, test_uid):
            """Update the state of a specific test."""
            shallow_report = flask.request.json
            _validate_json_body(shallow_report)

            with ihandler.report_mutex:
                try:
                    current_test = ihandler.report[test_uid]
                except KeyError:
                    raise werkzeug.exceptions.NotFound

                try:
                    new_test = _deserialize_report_entry(
                        shallow_report, current_test
                    )
                except marshmallow.exceptions.ValidationError as e:
                    raise werkzeug.exceptions.BadRequest(str(e))

                _check_uids_match(current_test.uid, new_test.uid)
                new_runtime_status = RuntimeStatus.from_json_compatible(
                    shallow_report.get("runtime_status")
                )

                # Trigger a side-effect if either the report or environment
                # statuses have been updated.
                if _should_reset(
                    current_test.uid,
                    current_test.runtime_status,
                    new_runtime_status,
                ):
                    current_test.runtime_status = RuntimeStatus.WAITING
                    ihandler.reset_test(test_uid, await_results=False)
                elif _should_run(
                    current_test.uid,
                    current_test.runtime_status,
                    new_runtime_status,
                ):
                    _check_env_status_match(
                        current_test.env_status, new_test.env_status
                    )
                    _check_execution_order(ihandler.report, test_uid=test_uid)
                    filtered = "entries" in shallow_report
                    if filtered:
                        entries = _extract_entries(shallow_report)
                        current_test.set_runtime_status_filtered(
                            RuntimeStatus.WAITING,
                            entries,
                        )
                    else:
                        current_test.runtime_status = RuntimeStatus.WAITING
                    ihandler.run_test(
                        test_uid,
                        shallow_report=shallow_report if filtered else None,
                        await_results=False,
                    )
                else:
                    next_env_status, env_action = self._check_env_transition(
                        current_test.env_status, new_test.env_status
                    )
                    if env_action is not None:
                        if current_test.runtime_status in (
                            RuntimeStatus.RESETTING,
                            RuntimeStatus.RUNNING,
                            RuntimeStatus.WAITING,
                        ):
                            raise werkzeug.exceptions.BadRequest(
                                "Env status cannot change when test"
                                f" is {current_test.runtime_status}"
                            )
                        env_action(test_uid, await_results=False)

                    current_test.env_status = next_env_status
                    return _serialize_report_entry(current_test)

                return _serialize_report_entry(current_test)

        def _check_env_transition(self, current_state, new_state):
            """
            Validate the new environment state by comparing with the current
            state. Only updates which leave the environment status unchanged
            or which follow an allowed transition will be accepted.

            Returns an action if one is required, or else None.
            """
            if current_state == new_state:
                return None, None

            allowed_transition, action = self._ENV_TRANSITIONS.get(
                current_state, (None, None)
            )
            if allowed_transition is None or new_state != allowed_transition:
                raise werkzeug.exceptions.BadRequest(
                    "Cannot transition environment state"
                    f" from {current_state} to {new_state}"
                )

            return allowed_transition, action

    @api.route("/report/tests/<string:test_uid>/suites")
    class AllSuites(flask_restx.Resource):
        """
        Suites endpoint. Represents all test suites within a Test object.
        """

        @decode_uri_component
        def get(self, test_uid):
            """Get the UIDs of all test suites owned by a specific test."""
            with ihandler.report_mutex:
                try:
                    return [
                        _serialize_report_entry(entry)
                        for entry in ihandler.report[test_uid]
                    ]
                except KeyError:
                    raise werkzeug.exceptions.NotFound

    @api.route("/report/tests/<string:test_uid>/suites/<string:suite_uid>")
    class SingleSuite(flask_restx.Resource):
        """
        Suite endpoint. Represents a single test suite within a Test object
        with the matching test and suite UIDs.
        """

        @decode_uri_component
        def get(self, test_uid, suite_uid):
            """Get the state of a specific test suite."""
            with ihandler.report_mutex:
                try:
                    return _serialize_report_entry(
                        ihandler.report[test_uid][suite_uid]
                    )
                except KeyError:
                    raise werkzeug.exceptions.NotFound

        @decode_uri_component
        def put(self, test_uid, suite_uid):
            """Update the state of a specific test suite."""
            shallow_report = flask.request.json
            _validate_json_body(shallow_report)

            with ihandler.report_mutex:
                try:
                    test = ihandler.report[test_uid]
                    current_suite = test[suite_uid]
                except KeyError:
                    raise werkzeug.exceptions.NotFound

                try:
                    new_suite = _deserialize_report_entry(
                        shallow_report, current_suite
                    )
                except marshmallow.exceptions.ValidationError as e:
                    raise werkzeug.exceptions.BadRequest(str(e))

                _check_uids_match(current_suite.uid, new_suite.uid)
                new_runtime_status = RuntimeStatus.from_json_compatible(
                    shallow_report.get("runtime_status")
                )

                if _should_run(
                    current_suite.uid,
                    current_suite.runtime_status,
                    new_runtime_status,
                ):
                    _check_execution_order(
                        ihandler.report, test_uid=test_uid, suite_uid=suite_uid
                    )
                    filtered = "entries" in shallow_report
                    if filtered:
                        entries = _extract_entries(shallow_report)
                        current_suite.set_runtime_status_filtered(
                            RuntimeStatus.WAITING,
                            entries,
                        )
                    else:
                        current_suite.runtime_status = RuntimeStatus.WAITING
                    ihandler.run_test_suite(
                        test_uid,
                        suite_uid,
                        shallow_report=shallow_report if filtered else None,
                        await_results=False,
                    )

                return _serialize_report_entry(current_suite)

    @api.route(
        "/report/tests/<string:test_uid>/suites/<string:suite_uid>/testcases"
    )
    class AllTestcases(flask_restx.Resource):
        """
        Testcases endpoint. Represents all testcases within a test suite
        within a Test object, with the matching test and suite UIDs.
        """

        @decode_uri_component
        def get(self, test_uid, suite_uid):
            """Get the UIDs of all testcases defined on a suite."""
            with ihandler.report_mutex:
                try:
                    return [
                        _serialize_report_entry(entry)
                        for entry in ihandler.report[test_uid][suite_uid]
                    ]
                except KeyError:
                    raise werkzeug.exceptions.NotFound

    @api.route(
        "/report/tests/<string:test_uid>/suites/<string:suite_uid>/testcases"
        "/<string:case_uid>"
    )
    class SingleTestcase(flask_restx.Resource):
        """
        Testcases endpoint. Represents a single testcase within a test
        suite, within a Test object, with the matching test, suite and
        testcase UIDs.
        """

        @decode_uri_component
        def get(self, test_uid, suite_uid, case_uid):
            """Get the state of a specific testcase."""
            with ihandler.report_mutex:
                try:
                    report_entry = ihandler.report[test_uid][suite_uid][
                        case_uid
                    ]
                except KeyError:
                    raise werkzeug.exceptions.NotFound

                return _serialize_report_entry(report_entry)

        @decode_uri_component
        def put(self, test_uid, suite_uid, case_uid):
            """Update the state of a specific testcase."""
            shallow_report = flask.request.json
            _validate_json_body(shallow_report)

            with ihandler.report_mutex:
                suite = ihandler.report[test_uid][suite_uid]
                try:
                    current_case = suite[case_uid]
                except KeyError:
                    raise werkzeug.exceptions.NotFound

                try:
                    new_testcase = _deserialize_report_entry(
                        shallow_report, current_case
                    )
                except marshmallow.exceptions.ValidationError as e:
                    raise werkzeug.exceptions.BadRequest(str(e))

                _check_uids_match(current_case.uid, new_testcase.uid)
                new_runtime_status = RuntimeStatus.from_json_compatible(
                    shallow_report.get("runtime_status")
                )

                if _should_run(
                    current_case.uid,
                    current_case.runtime_status,
                    new_runtime_status,
                ):
                    _check_execution_order(
                        ihandler.report,
                        test_uid=test_uid,
                        suite_uid=suite_uid,
                        case_uid=case_uid,
                    )
                    filtered = "entries" in shallow_report
                    if filtered:
                        entries = _extract_entries(shallow_report)
                        current_case.set_runtime_status_filtered(
                            RuntimeStatus.WAITING,
                            entries,
                        )
                    else:
                        current_case.runtime_status = RuntimeStatus.WAITING
                    ihandler.run_test_case(
                        test_uid,
                        suite_uid,
                        case_uid,
                        shallow_report=shallow_report if filtered else None,
                        await_results=False,
                    )

                return _serialize_report_entry(current_case)

    @api.route(
        "/report/tests/<string:test_uid>/suites/<string:suite_uid>/testcases"
        "/<string:case_uid>/parametrizations"
    )
    class AllParametrizations(flask_restx.Resource):
        """
        Parametrizations endpoint. Represents all parametrizations of a single
        testcase.
        """

        @decode_uri_component
        def get(self, test_uid, suite_uid, case_uid):
            """Get the state of all parametrizations of a testcase."""
            with ihandler.report_mutex:
                try:
                    return [
                        _serialize_report_entry(entry)
                        for entry in ihandler.report[test_uid][suite_uid][
                            case_uid
                        ]
                    ]
                except KeyError:
                    raise werkzeug.exceptions.NotFound

    @api.route(
        "/report/tests/<string:test_uid>/suites/<string:suite_uid>/testcases"
        "/<string:case_uid>/parametrizations/<string:param_uid>"
    )
    class ParamatrizedTestCase(flask_restx.Resource):
        """
        Paramatrized testcase endpoint. Represents a single testcase within
        a paramatrization group, with a unique combination of parameters.
        """

        @decode_uri_component
        def get(self, test_uid, suite_uid, case_uid, param_uid):
            """Get the state of a specific paramatrized testcase."""
            with ihandler.report_mutex:
                try:
                    report_entry = ihandler.report[test_uid][suite_uid][
                        case_uid
                    ][param_uid]
                except KeyError:
                    raise werkzeug.exceptions.NotFound

                return _serialize_report_entry(report_entry)

        @decode_uri_component
        def put(self, test_uid, suite_uid, case_uid, param_uid):
            """Update the state of a specific parametrized testcase."""
            shallow_report = flask.request.json
            _validate_json_body(shallow_report)

            with ihandler.report_mutex:
                try:
                    param_group = ihandler.report[test_uid][suite_uid][
                        case_uid
                    ]
                    current_case = param_group[param_uid]
                except KeyError:
                    raise werkzeug.exceptions.NotFound

                try:
                    new_testcase = _deserialize_report_entry(
                        shallow_report, current_case
                    )
                except marshmallow.exceptions.ValidationError as e:
                    raise werkzeug.exceptions.BadRequest(str(e))

                _check_uids_match(current_case.uid, new_testcase.uid)
                new_runtime_status = RuntimeStatus.from_json_compatible(
                    shallow_report.get("runtime_status")
                )

                if _should_run(
                    current_case.uid,
                    current_case.runtime_status,
                    new_runtime_status,
                ):
                    _check_execution_order(
                        ihandler.report,
                        test_uid=test_uid,
                        suite_uid=suite_uid,
                        case_uid=case_uid,
                        param_uid=param_uid,
                    )
                    current_case.runtime_status = RuntimeStatus.WAITING
                    ihandler.run_test_case_param(
                        test_uid,
                        suite_uid,
                        case_uid,
                        param_uid,
                        await_results=False,
                    )

                return _serialize_report_entry(current_case)

    @api.route("/report/export")
    class ExportReport(flask_restx.Resource):
        """
        Interactive export endpoint. There is an API for exporting root
        report object.
        """

        def get(self):
            available_exporters = []
            with ihandler.report_mutex:
                for exporter in ihandler.exporters:
                    available_exporters.append(exporter.name)
            return {
                "available": available_exporters,
                "history": export_history,
            }

        @api.expect(post_export_model)
        def post(self) -> Optional[Dict]:
            request_data = request.json
            with ihandler.report_mutex:
                export_context = ExportContext()
                for exporter in ihandler.exporters:
                    if exporter.name in request_data.get("exporters", []):
                        report = copy.deepcopy(ihandler.report)
                        report.reset_uid()
                        exporter_run_result = run_exporter(
                            exporter=exporter,
                            source=report,
                            export_context=export_context,
                        )
                        export_information = {
                            "time": exporter_run_result.start_time.timestamp(),
                            "name": exporter_run_result.exporter.name,
                            "uid": exporter_run_result.uid,
                            "success": exporter_run_result.success,
                        }
                        request_result = exporter_run_result.result
                        if request_result:
                            if len(request_result) > 1:
                                export_information["message"] = "\n".join(
                                    [
                                        f"{k}: {v}"
                                        for k, v in request_result.items()
                                    ]
                                )
                            else:
                                export_information["message"] = list(
                                    request_result.values()
                                )[0]
                        else:
                            export_information["message"] = (
                                exporter_run_result.traceback or "No output."
                            )
                        export_history.append(export_information)
            return {"history": export_history}

    @api.route("/report/export/<string:uid>")
    class ExporterFile(flask_restx.Resource):
        """
        Interactive export download endpoint. There is an API for downloading
        report file.
        """

        def get(self, uid):
            for export in export_history:
                if export["uid"] == uid:
                    return flask.send_file(export["message"])
            raise werkzeug.exceptions.NotFound

    @api.route("/attachments")
    class AllAttachments(flask_restx.Resource):
        """
        Represents all files currently attached to the Testplan interactive
        report.
        """

        def get(self):
            """Return a list of all attachment UIDs."""
            with ihandler.report_mutex:
                return list(ihandler.report.attachments.keys())

    @api.route("/attachments/<path:attachment_uid>")
    class SingleAttachment(flask_restx.Resource):
        """
        Represents a specific file attached to the Testplan interactive report.
        """

        def get(self, attachment_uid):
            """Get a file attachment."""
            with ihandler.report_mutex:
                try:
                    filepath = ihandler.report.attachments[attachment_uid]
                except KeyError:
                    raise werkzeug.exceptions.NotFound

            return flask.send_file(filepath)

    @api.route("/reload")
    class ReloadCode(flask_restx.Resource):
        """
        Reload source code.
        """

        def get(self):
            if ihandler.report.runtime_status in (
                RuntimeStatus.RUNNING,
                RuntimeStatus.RESETTING,
                RuntimeStatus.WAITING,
            ):
                raise werkzeug.exceptions.BadRequest(
                    "Cannot reload code when any test is in execution"
                )

            with ihandler.report_mutex:
                # Occupy the mutex so that no other request will be handled
                try:
                    ihandler.reload(rebuild_dependencies=True)
                    ihandler.reload_report()
                except Exception as ex:
                    ihandler.logger.error("Reload failed! %s ", str(ex))
                    return {"errmsg": f"Reload failed! {ex}"}, 200
                return True

    @api.route("/abort")
    class AbortExecution(flask_restx.Resource):
        """
        Abort Testplan execution and notify client.
        """

        def get(self):
            try:
                ihandler.abort()
            except Exception as ex:
                ihandler.logger.error("Failed to abort Testplan! %s ", str(ex))
                return {"errmsg": f"Failed to abort Testplan! {ex}"}, 200
            return True

    return app, api


def _validate_json_body(json_body: Dict) -> None:
    """
    Validates the JSON body for PUT requests.

    :param json_body: decoded JSON
    :raises BadRequest: raised if JSON body is None
    """
    if json_body is None:
        raise werkzeug.exceptions.BadRequest("JSON body is required for PUT")

def _serialize_report_entry(report_entry, full=False):
    """
    Serialize a report entry representing a testcase or a test group.
    For a test group shallow serialization is used instead.
    """
    if isinstance(report_entry, TestCaseReport):
        return report_entry.serialize()
    elif isinstance(report_entry, (TestGroupReport, TestReport)):
        if full:
            return report_entry.serialize()
        else:
            return report_entry.shallow_serialize()
    else:
        raise TypeError(f"Unexpected report entry type: {type(report_entry)}")


def _deserialize_report_entry(serialized, curr_report_entry):
    """
    Deserialize an updated report entry which represents a testcase or
    a test group. We need to inspect the type of the current testcase
    object in order to decide how to deserialize the update.
    """
    if isinstance(curr_report_entry, TestCaseReport):
        return TestCaseReport.deserialize(serialized)
    elif isinstance(curr_report_entry, (TestGroupReport, TestReport)):
        return TestGroupReport.shallow_deserialize(
            serialized, curr_report_entry
        )
    else:
        raise TypeError(
            f"Unexpected report entry type {type(curr_report_entry)}"
        )


def _check_uids_match(current_uid, new_uid):
    """
    Check that the UID from the updated entry matches the current one.
    UIDs cannot be changed, so raise a BadRequest error if they do not
    match.
    """
    if new_uid != current_uid:
        raise werkzeug.exceptions.BadRequest(
            f'Cannot update UID of entry from "{current_uid}" to "{new_uid}"'
        )


def _check_env_status_match(current_status, new_status):
    """
    Check that the environment status from the updated entry matches the
    current one, raise a BadRequest error if they do not match.
    """
    if current_status != new_status:
        raise werkzeug.exceptions.BadRequest(
            f'Env status cannot change from "{current_status}"'
            f' to "{new_status}" when test status is changing'
        )


def _should_reset(uid, curr_status, new_status):
    """
    Check if any test(s) should be triggered to reset from a state update.

    The only allowed state transition on update is to set the status
    to RESETTING to trigger test(s) to reset. Any other state update
    (e.g. setting the state of a running/resetting test to PASSED) is
    not allowed - only the server can make those transitions.
    A BadRequest exception will be raised if the requested status is invalid.
    """
    if new_status == curr_status:
        return False
    elif new_status == RuntimeStatus.RESETTING:
        if curr_status not in (RuntimeStatus.RUNNING, RuntimeStatus.WAITING):
            return True
        else:
            raise werkzeug.exceptions.BadRequest(
                "Cannot update runtime status of entry"
                f' "{uid}" from "{curr_status}" to "{new_status}"'
            )
    return False


def _should_run(uid, curr_status, new_status):
    """
    Check if any test(s) should be triggered to run from a state update.

    The only allowed state transition on update is to set the status
    to RUNNING to trigger test(s) to run. Any other state update
    (e.g. setting the state of a running/resetting test to PASSED) is
    not allowed - only the server can make those transitions.
    A BadRequest exception will be raised if the requested status is invalid.
    """
    if new_status == curr_status:
        return False

    # test entry already triggered
    elif (
        new_status == RuntimeStatus.RUNNING
        and curr_status == RuntimeStatus.WAITING
    ):
        return False

    elif new_status == RuntimeStatus.RUNNING:

        if curr_status == RuntimeStatus.RESETTING:
            raise werkzeug.exceptions.BadRequest(
                "Cannot update runtime status of entry"
                f' "{uid}" from "{curr_status}" to "{new_status}"'
            )
        return True

    return False


def _check_execution_order(
    report, test_uid=None, suite_uid=None, case_uid=None, param_uid=None
):
    """
    Check that if `strict_order` is specified for a test entity then all of
    its children should run sequentially and the finished ones cannot run
    again unless report been reset. Will raise if violation found. Currently
    we only need to check execution order of testcases in a test suite.
    """

    def report_runtime_status(report, status):
        """
        Check that if a test entity is in specified status (all of its children
        should also be in the same status) by test report. "setup" & "teardown"
        are not included in this check.
        """
        if isinstance(report, TestCaseReport):
            return (
                report.category == ReportCategories.SYNTHESIZED
                or report.runtime_status == status
            )
        elif isinstance(report, TestGroupReport):
            return all(
                report_runtime_status(report_entry, status)
                for report_entry in report
            )

    ready = lambda rep: report_runtime_status(rep, RuntimeStatus.READY)
    finished = lambda rep: report_runtime_status(rep, RuntimeStatus.FINISHED)
    suite_reports = []

    for test_report in [report[test_uid]] if test_uid else report.entries:
        for suite_report in test_report.entries:
            if suite_uid:
                if suite_report.uid == suite_uid and suite_report.strict_order:
                    suite_reports.append(suite_report)
            elif suite_report.strict_order:
                suite_reports.append(suite_report)

    for suite_report in suite_reports:
        if case_uid:
            idx = suite_report._index[case_uid]
            if param_uid:
                param_report = suite_report[case_uid]
                sub_idx = param_report._index[param_uid]
                if not (
                    all(finished(rep) for rep in suite_report.entries[:idx])
                    and all(
                        finished(rep) for rep in param_report.entries[:sub_idx]
                    )
                    and all(
                        ready(rep) for rep in param_report.entries[sub_idx:]
                    )
                    and all(
                        ready(rep) for rep in suite_report.entries[idx + 1 :]
                    )
                ):
                    raise OutOfOrderError(
                        f'Should run testcase "{case_uid}"'
                        f' in parametrization group "{param_uid}"'
                        f' in test suite "{suite_report.uid}" sequentially.'
                    )
            else:
                if not (
                    all(finished(rep) for rep in suite_report.entries[:idx])
                    and all(ready(rep) for rep in suite_report.entries[idx:])
                ):
                    report_type = (
                        "testcase"
                        if isinstance(suite_report, TestCaseReport)
                        else "parametrization group"
                    )
                    raise OutOfOrderError(
                        f'Should run {report_type} "{case_uid}"'
                        f' in test suite "{suite_report.uid}" sequentially.'
                    )
        else:
            if not all(ready(rep) for rep in suite_report):
                raise OutOfOrderError(
                    "Should run all testcases"
                    f' in test suite "{suite_report.uid}" sequentially.'
                )


# NOTE: to drive behavior of runtime status setting between cases of
#            a filter being present or not, the entries field needs processing
def _extract_entries(entry: Dict) -> Dict:
    """
    Given a report entry, extracts all entry names into a tree structure.

    :param entry: report entry
    :return: dictionary representing the tree structure of entry names
    """
    entries = {}

    # FIXME:
    # by design, filtering out assertions has been properly done in frontend
    # code; following lines are still kept for possible corner cases, while
    # currently ``type`` field does not exist in ``Shallow*`` schemas...
    if entry.get("type") == TestCaseReport.__name__:
        return entries

    for child in entry.get("entries", []):
        entries[child["name"]] = _extract_entries(child)

    return entries


class TestRunnerHTTPHandlerConfig(entity.EntityConfig):
    """
    Configuration object for
    :py:class:`~testplan.runnable.interactive.http.TestRunnerHTTPHandler`
    entity.
    """

    @classmethod
    def get_options(cls):
        return {
            "ihandler": entity.Entity,
            ConfigOption("host", default=defaults.WEB_SERVER_HOSTNAME): str,
            ConfigOption("port", default=defaults.WEB_SERVER_PORT): int,
            ConfigOption(
                "pool_size", default=defaults.INTERACTIVE_POOL_SIZE
            ): int,
        }


class TestRunnerHTTPHandler(entity.Entity):
    """
    Server that invokes an interactive handler to perform dynamic operations.

    :param ihandler: Runnable interactive handler instance.
    :type ihandler: ``Entity``
    :param host: Host to bind to.
    :type host: ``str``
    :param port: Port to bind to.
    :type port: ``int``

    Also inherits all
    :py:class:`~testplan.common.entity.base.Entity` options.
    """

    CONFIG = TestRunnerHTTPHandlerConfig

    def __init__(self, **options):
        super(TestRunnerHTTPHandler, self).__init__(**options)
        self._server = None

    @property
    def bind_addr(self):
        """
        :return: Bound host and port of HTTP server, or None if not bound.
        :rtype: ``Optional[Tuple[str, int]]``
        """
        if self._server is None:
            return None, None
        else:
            return self._server.bind_addr

    def setup(self):
        """
        Generate the flask App and prepare the HTTP server.

        :return: server host and port tuple
        :rtype: ``Tuple[str, int]``
        """
        app, _ = generate_interactive_api(self.cfg.ihandler)
        self._server = wsgi.Server((self.cfg.host, self.cfg.port), app)
        self._server.prepare()

        return self._server.bind_addr

    def run(self):
        """
        Start serving requests. Will block until the server stops running.
        """
        if self._server is None:
            raise RuntimeError("Run setup() before run()")
        try:
            self._server.serve()
        finally:
            self._server = None

    def aborting(self):
        """Stopping http service."""
        if self._server is not None:
            try:
                self._server.stop()
            except Exception:
                pass
