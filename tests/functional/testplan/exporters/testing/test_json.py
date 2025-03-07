"""Test the JSON exporter."""
import copy
import json
import os
import pathlib
import tempfile

import testplan
from testplan import TestplanMock
from testplan.common.utils.testing import argv_overridden
from testplan.exporters.testing import JSONExporter
from testplan.exporters.testing.json import gen_attached_report_names
from testplan.testing import multitest


@multitest.testsuite
class Alpha:
    def setup(self, env, result):
        result.log("within suite setup...")

    @multitest.testcase
    def test_comparison(self, env, result):
        result.equal(1, 1, "equality description")

    @multitest.testcase(parameters=(1, 2, 3))
    def test_membership(self, env, result, arg):
        result.contain(1, [1, 2, 3])

    @multitest.testcase
    def test_attach(self, env, result):
        """Test attaching a file to the report."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmpfile:
            tmpfile.write("testplan\n" * 100)

        result.attach(tmpfile.name)

    @multitest.testcase
    def test_special_values(self, env, result):
        result.ne(float("nan"), float("nan"))
        result.lt(float("-inf"), float("inf"))


@multitest.testsuite
class Beta:
    @multitest.testcase
    def test_failure(self, env, result):
        result.equal(1, 2, "failing assertion")
        result.not_equal(5, 5)

    @multitest.testcase
    def test_error(self, env, result):
        raise Exception("foo")


def secondary_after_start(env, result):
    result.log("within after start...")


def test_split_and_merge(runpath):
    """
    Test static methods used for splitting and merging JSON report.
    """
    json_path = os.path.join(runpath, "report.json")
    plan = TestplanMock(
        "plan", exporters=JSONExporter(json_path=json_path), runpath=runpath
    )
    multitest_1 = multitest.MultiTest(name="Primary", suites=[Alpha()])
    multitest_2 = multitest.MultiTest(
        name="Secondary", suites=[Beta()], after_start=secondary_after_start
    )
    plan.add(multitest_1)
    plan.add(multitest_2)
    plan.run()

    assert os.path.exists(json_path)
    assert os.stat(json_path).st_size > 0

    with open(json_path) as json_file:
        report = json.load(json_file)
    del report["version"]

    meta, structure, assertions = JSONExporter.split_json_report(
        copy.deepcopy(report)
    )
    assert "information" in meta
    assert (
        dict(meta["information"])["testplan_version"] == testplan.__version__
    )
    assert meta["entries"] == []
    assert (
        JSONExporter.merge_json_report(meta, structure, assertions) == report
    )


def test_json_exporter(runpath):
    """
    JSON Exporter should generate a full json report at the given `json_path`.
    """
    json_path = os.path.join(runpath, "report.json")

    plan = TestplanMock(
        "plan", exporters=JSONExporter(json_path=json_path), runpath=runpath
    )
    multitest_1 = multitest.MultiTest(name="Primary", suites=[Alpha()])
    multitest_2 = multitest.MultiTest(
        name="Secondary", suites=[Beta()], after_start=secondary_after_start
    )
    plan.add(multitest_1)
    plan.add(multitest_2)
    plan.run()

    assert os.path.exists(json_path)
    assert os.stat(json_path).st_size > 0

    # Load the JSON file to validate it contains valid JSON.
    with open(json_path) as json_file:
        report = json.load(json_file)

    # Check that the expected text file is attached correctly.
    attachments_dir = os.path.join(os.path.dirname(json_path), "_attachments")
    assert os.path.isdir(attachments_dir)
    assert len(report["attachments"]) == 1

    dst_path = list(report["attachments"].keys())[0]
    attachment_filepath = os.path.join(attachments_dir, dst_path)
    assert os.path.isfile(attachment_filepath)

    with open(attachment_filepath) as f:
        attachment_file_contents = f.read()
    assert attachment_file_contents == "testplan\n" * 100


def test_json_exporter_generating_split_report(runpath):
    """
    JSON Exporter should generate a main json report at the given `json_path`.
    """
    json_path = os.path.join(runpath, "report.json")

    plan = TestplanMock(
        "plan",
        exporters=[JSONExporter(json_path=json_path, split_json_report=True)],
        runpath=runpath,
    )

    multitest_1 = multitest.MultiTest(name="Primary", suites=[Alpha()])
    multitest_2 = multitest.MultiTest(
        name="Secondary", suites=[Beta()], after_start=secondary_after_start
    )
    plan.add(multitest_1)
    plan.add(multitest_2)
    plan.run()

    assert os.path.exists(json_path)
    assert os.stat(json_path).st_size > 0

    # Load the JSON file to validate it contains valid JSON.
    with open(json_path) as json_file:
        report = json.load(json_file)

    assert report["version"] == 2

    # Check that the expected text file is attached correctly.
    attachments_dir = os.path.join(os.path.dirname(json_path), "_attachments")
    assert os.path.isdir(attachments_dir)
    assert len(report["entries"]) == 0
    assert len(report["attachments"]) == 3

    structure_filename, assertions_filename = gen_attached_report_names(
        pathlib.Path(json_path).resolve()
    )
    assert structure_filename in report["attachments"]
    assert assertions_filename in report["attachments"]
    assert report["structure_file"] == structure_filename
    assert report["assertions_file"] == assertions_filename

    structure_filepath = os.path.join(attachments_dir, structure_filename)
    assertions_filepath = os.path.join(attachments_dir, assertions_filename)
    assert os.path.isfile(structure_filepath)
    assert os.path.isfile(assertions_filepath)

    with open(structure_filepath) as f1, open(assertions_filepath) as f2:
        structure = json.loads(f1.read())
        assertions = json.loads(f2.read())

    assert len(structure) == 2  # 2 multitests
    assert structure[0]["name"] == "Primary"  # 1st multitest name
    assert len(structure[0]["entries"]) == 1  # one suite in 1st multitest
    assert structure[0]["entries"][0]["name"] == "Alpha"  # 1st suite name
    assert (
        len(structure[0]["entries"][0]["entries"]) == 5
    )  # 4 testcases, 1 synthesized
    assert (
        len(structure[0]["entries"][0]["entries"][2]["entries"]) == 3
    )  # 3 parametrized testcases

    assert structure[1]["name"] == "Secondary"  # 2nd multitest name
    assert (
        len(structure[1]["entries"]) == 2
    )  # one suite in 2nd multitest, 1 synthesized
    assert structure[1]["entries"][0]["name"] == "Environment Start"
    assert structure[1]["entries"][0]["entries"][0]["name"] == "After Start"
    assert len(structure[1]["entries"][0]["entries"]) == 1
    assert structure[1]["entries"][1]["name"] == "Beta"  # 1st suite name
    assert len(structure[1]["entries"][1]["entries"]) == 2  # 2 testcases

    assert len(assertions) == 10  # 10 cases in total
    # only one assertion in each testcase in suite `Alpha`
    assert assertions["test_comparison"][0]["type"] == "Equal"
    assert assertions["test_membership__arg_1"][0]["type"] == "Contain"
    assert assertions["test_membership__arg_2"][0]["type"] == "Contain"
    assert assertions["test_membership__arg_3"][0]["type"] == "Contain"
    assert assertions["test_attach"][0]["type"] == "Attachment"
    # 2 assertions in testcase `test_failure`
    assert assertions["test_failure"][0]["type"] == "Equal"
    assert assertions["test_failure"][1]["type"] == "NotEqual"
    # no assertion in testcase `test_error`
    assert len(assertions["test_error"]) == 0
    # 2 assertions in synthesized cases, i.e. custom hooks
    assert assertions["setup"][0]["type"] == "Log"
    assert assertions["After Start"][0]["type"] == "Log"

    # special values representation preserved
    # NOTE: these values are of type float in old impl,
    # NOTE: converted to js repr in cope with json lib change
    assert assertions["test_special_values"][0]["first"] == "NaN"
    assert assertions["test_special_values"][1]["first"] == "-Infinity"
    assert assertions["test_special_values"][1]["second"] == "Infinity"


def test_implicit_exporter_initialization(runpath):
    """
    An implicit JSON should be generated if `json_path` is available
    via cmdline args but no exporters were declared programmatically.
    """
    json_path = os.path.join(runpath, "report.json")

    with argv_overridden("--json", json_path):
        plan = TestplanMock(name="plan", parse_cmdline=True)
        multitest_1 = multitest.MultiTest(name="Primary", suites=[Alpha()])
        plan.add(multitest_1)
        plan.run()

    assert os.path.exists(json_path)
    assert os.stat(json_path).st_size > 0

    # Load the JSON file to validate it contains valid JSON.
    with open(json_path) as json_file:
        json.load(json_file)
