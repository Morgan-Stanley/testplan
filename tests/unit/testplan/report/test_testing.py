import functools
import json
from collections import OrderedDict

import pytest
from boltons.iterutils import get_path

from testplan.common import entity
from testplan.common.report import (
    ReportCategories,
    RuntimeStatus,
    Status,
)
from testplan.common.report.log import LOGGER as report_logger
from testplan.common.utils.json import json_dumps, json_loads
from testplan.common.utils.testing import check_report, disable_log_propagation
from testplan.report.testing.base import (
    TestCaseReport,
    TestGroupReport,
    TestReport,
)
from testplan.report.testing.schemas import TestReportSchema
from testplan.testing.result import Result

DummyCaseReport = functools.partial(TestCaseReport, name="dummy")
DummyGroupReport = functools.partial(TestGroupReport, name="dummy")


@disable_log_propagation(report_logger)
def test_report_exception_logger():
    """
    `TestReportExceptionLogger` should set `status_override` to
    `TestReportStatus.FAILED` if `fail` argument is True.
    """
    rep = TestCaseReport(name="foo")
    assert rep.status_override is Status.NONE

    # should not change status_override
    with rep.logged_exceptions(fail=False):
        raise Exception("foo")

    assert rep.status_override is Status.NONE

    # should change status_override
    with rep.logged_exceptions():
        raise Exception("foo")

    assert rep.status_override is Status.ERROR


class TestTestGroupReport:
    def test_hash_merge(self):
        """
        Test that the hash is updated after new report entries are merged in.
        """
        parent = DummyGroupReport()
        child = DummyCaseReport(name="testcase")
        parent.append(child)
        orig_parent_hash = parent.hash

        parent2 = DummyGroupReport(uid=parent.uid)
        child2 = DummyCaseReport(name="testcase", uid=child.uid)
        child2.append({"name": "entry", "passed": True})
        parent2.append(child2)

        parent.merge(parent2)
        assert parent.hash != orig_parent_hash

    def test_merge_children_not_strict(self):
        """
        Not strict merge should append child entries and update
        the index if they do not exist in the parent.
        """
        child_clone_1 = DummyCaseReport(uid=10)
        child_clone_2 = DummyCaseReport(uid=20)
        parent_clone = DummyGroupReport(
            uid=1, entries=[child_clone_1, child_clone_2]
        )

        child_orig_1 = DummyCaseReport(uid=10)
        parent_orig = DummyGroupReport(uid=1, entries=[child_orig_1])

        parent_orig.merge(parent_clone, strict=False)
        assert parent_orig.entries == [child_orig_1, child_clone_2]

        # Merging a second time should give us the same results
        parent_orig.merge(parent_clone, strict=False)
        assert parent_orig.entries == [child_orig_1, child_clone_2]


class TestTestCaseReport:
    @pytest.mark.parametrize(
        "entries,expected_status",
        (
            ([], Status.UNKNOWN),
            ([{"foo": 2}, {"bar": 3}], Status.PASSED),
            ([{"foo": True}], Status.PASSED),
            ([{"passed": True}], Status.PASSED),
            ([{"passed": False}], Status.FAILED),
            ([{"passed": None}], Status.PASSED),
            ([{"passed": False}, {"passed": True}], Status.FAILED),
        ),
    )
    def test_status(self, entries, expected_status):
        """
        TestCaseReport status should be `Status.FAILED` if it has a
        `dict` entry with the key `passed` = `False`.
        """
        rep = TestCaseReport(name="foo", entries=entries)
        assert rep.status == expected_status

    @pytest.mark.parametrize(
        "entries,status_override",
        (
            ([], Status.PASSED),
            ([], Status.FAILED),
            ([{"passed": True}], Status.FAILED),
            ([{"passed": False}], Status.PASSED),
        ),
    )
    def test_status_override(self, entries, status_override):
        """
        TestCaseReport `status_override` should
        take precedence over `status` logic.
        """
        rep = TestCaseReport(name="foo", entries=entries)
        rep.status_override = status_override
        assert rep.status == status_override

    def test_merge(self):
        """
        `TestCaseReport.merge` should assign basic attributes
        (`status_override`, `logs`, `entries`) in place.
        """
        rep = TestCaseReport(uid=1, name="foo", entries=[1, 2, 3])
        rep.logs = [4, 5, 6]
        rep.status_override = Status.PASSED

        rep2 = TestCaseReport(uid=1, name="foo", entries=[10, 20, 30])
        rep2.logs = [40, 50, 60]
        rep2.status_override = Status.FAILED

        rep.merge(rep2)

        assert rep.status_override == rep2.status_override
        assert rep.logs == rep2.logs
        assert rep.entries == rep2.entries

    def test_hash(self):
        """Test that a consistent hash can be generated for a report object."""
        rep_1 = TestCaseReport(name="testcase1")
        rep_2 = TestCaseReport(name="testcase2")

        for rep in rep_1, rep_2:
            assert rep.hash == rep.hash

        assert rep_1.hash != rep_2.hash


def generate_dummy_testgroup():

    tag_data_1 = {"tagname": {"tag1", "tag2"}}
    tag_data_2 = {"other_tagname": {"tag4", "tag5"}}

    tc_1 = TestCaseReport(
        name="test_case_1",
        description="test case 1 description",
        tags=tag_data_1,
    )

    with tc_1.logged_exceptions():
        raise Exception("some error")

    tc_2 = TestCaseReport(
        name="test_case_2", description="test case 2 description", tags={}
    )

    tg_1 = TestGroupReport(
        name="Test Group 1",
        description="Test Group 1 description",
        category=ReportCategories.TESTGROUP,
        entries=[tc_1, tc_2],
        tags=tag_data_2,
    )

    tc_3 = TestCaseReport(
        name="test_case_3",
        description="test case 3 description",
        tags=tag_data_2,
    )

    tc_3.status_override = Status.PASSED

    return TestGroupReport(
        name="Test Group 2",
        description="Test Group 2 description",
        category=ReportCategories.TESTGROUP,
        entries=[tg_1, tc_3],
        tags={},
    )


@disable_log_propagation(report_logger)
@pytest.fixture
def dummy_test_plan_report():

    tg_2 = generate_dummy_testgroup()

    rep = TestReport(name="My Plan", entries=[tg_2], meta={"foo": "baz"})

    with rep.timer.record("foo"):
        pass

    return rep


@disable_log_propagation(report_logger)
@pytest.fixture
def dummy_test_plan_report_with_binary_asserts():

    tg_2 = generate_dummy_testgroup()

    res = Result()
    res.equal(1, 1, "IGNORE THIS")
    res.equal(b"\xF2", b"\xf2", "IGNORE THIS")
    res.equal(b"\x00\xb1\xC1", b"\x00\xB2\xc2", "IGNORE THIS")

    # dict match nicely produce tupples, list, maps within the serialized schema
    a_dict = OrderedDict(
        [
            (b"binarykey\xB1", "string value"),
            ("string_key", b"binary value\xB1"),
            ("key3", [b"binary\xB1", "in", "list"]),
            ("key4", (b"binary\xB1", "in", "tuple")),
        ]
    )
    res.dict.match(a_dict, a_dict, "IGNORE THIS")

    btc_1 = TestCaseReport(
        name="binary_test_case_1",
        description="binary test case 1 description",
        entries=res.serialized_entries,
    )

    btg_1 = TestGroupReport(
        name="Binary Test Group 2",
        description="Binary Test Group 1 description",
        category=ReportCategories.TESTGROUP,
        entries=[btc_1],
        tags={},
    )

    rep = TestReport(
        name="My Bin Plan",
        description="Plan executing binary assertions",
        entries=[tg_2, btg_1],
        meta={"foobin": "bazbin"},
    )

    with rep.timer.record("foobin"):
        pass

    return rep


def test_report_serialization(dummy_test_plan_report):
    """Serialized & deserialized reports should be equal."""

    data = dummy_test_plan_report.serialize()
    deserialized_report = TestReport.deserialize(data)
    check_report(actual=deserialized_report, expected=dummy_test_plan_report)


def test_report_serialize_attr_strip(dummy_test_plan_report):
    data = dummy_test_plan_report.serialize()

    def assert_report_entry(func, report):
        assert func(report)
        for entry in report["entries"]:
            assert_report_entry(func, entry)

    def check_attr(e):
        if ReportCategories.is_test_level(e["category"]):
            return "part" in e and "env_status" in e
        else:
            return "part" not in e and "env_status" not in e

    assert_report_entry(check_attr, data)


def test_report_json_serialization(dummy_test_plan_report):
    """JSON Serialized & deserialized reports should be equal."""

    test_plan_schema = TestReportSchema()
    data = json_dumps(test_plan_schema.dump(dummy_test_plan_report))
    deserialized_report = test_plan_schema.load(json_loads(data))
    check_report(actual=deserialized_report, expected=dummy_test_plan_report)


def test_report_json_binary_serialization(
    dummy_test_plan_report_with_binary_asserts,
):
    """JSON Serialized & deserialized reports should be equal."""
    test_plan_schema = TestReportSchema()
    data = test_plan_schema.dumps(dummy_test_plan_report_with_binary_asserts)

    j = json.loads(data)

    # passing assertion
    hx_1_1 = get_path(j, "entries.1.entries.0.entries.1.first")
    hx_1_2 = get_path(j, "entries.1.entries.0.entries.1.second")
    assert str(b"\xF2") == hx_1_1 == hx_1_2

    # failing assertion
    hx_2_1 = get_path(j, "entries.1.entries.0.entries.2.first")
    hx_2_2 = get_path(j, "entries.1.entries.0.entries.2.second")
    assert str(b"\x00\xb1\xC1") == hx_2_1
    assert str(b"\x00\xB2\xC2") == hx_2_2

    # dict.match the schema for that producing list of tuples

    KEY_INDEX = 0
    FIRST_INDEX = 2
    SECOND_INDEX = 3

    comps = get_path(j, "entries.1.entries.0.entries.3.comparison")
    assert comps[0][KEY_INDEX] == str(b"binarykey\xB1")
    assert comps[1][FIRST_INDEX][1] == str(b"binary value\xB1")
    assert comps[1][SECOND_INDEX][1] == str(b"binary value\xB1")
    assert comps[3][FIRST_INDEX][1] == str(b"binary\xB1")
    assert comps[3][SECOND_INDEX][1] == str(b"binary\xB1")
    assert comps[7][FIRST_INDEX][1] == str(b"binary\xB1")
    assert comps[7][SECOND_INDEX][1] == str(b"binary\xB1")


class TestReportTags:
    def get_reports(self):
        tc_report_1 = TestCaseReport(
            name="My Test Case", tags={"simple": {"baz"}}
        )

        tc_report_2 = TestCaseReport(
            name="My Test Case 2", tags={"simple": {"bat"}}
        )

        tg_report_3 = TestGroupReport(
            name="My Group 3", category=ReportCategories.TESTGROUP, tags={}
        )

        tg_report_2 = TestGroupReport(
            name="My Group 2",
            category=ReportCategories.TESTGROUP,
            tags={"simple": {"bar"}},
            entries=[tc_report_1, tc_report_2],
        )

        tg_report_1 = TestGroupReport(
            name="My Group",
            category=ReportCategories.TESTGROUP,
            tags={"simple": {"foo"}},
            entries=[tg_report_2, tg_report_3],
        )

        return tg_report_1, tg_report_2, tg_report_3, tc_report_1, tc_report_2

    def test_tag_propagation_on_init(self):
        """
        Tag propagation should update tag indices
        of the children/parents recursively.
        """
        tg_rep_1, tg_rep_2, tg_rep_3, tc_rep_1, tc_rep_2 = self.get_reports()

        assert tg_rep_1.tags_index == {"simple": {"foo", "bar", "baz", "bat"}}
        assert tg_rep_1.tags == {"simple": {"foo"}}

        assert tg_rep_2.tags_index == {"simple": {"foo", "bar", "baz", "bat"}}
        assert tg_rep_2.tags == {"simple": {"bar"}}

        assert tg_rep_3.tags_index == {"simple": {"foo"}}
        assert tg_rep_3.tags == {}

        assert tc_rep_1.tags_index == {"simple": {"foo", "bar", "baz"}}
        assert tc_rep_1.tags == {"simple": {"baz"}}

        assert tc_rep_2.tags_index == {"simple": {"foo", "bar", "bat"}}
        assert tc_rep_2.tags == {"simple": {"bat"}}

    def test_tag_propagation_on_append(self):
        """
        After append operation, tag propagation should
        be triggered from the target node.
        """
        tg_rep_1, tg_rep_2, tg_rep_3, tc_rep_1, tc_rep_2 = self.get_reports()

        tc_report_3 = TestCaseReport(
            name="My Test Case 3", tags={"color": {"blue"}}
        )

        # root node
        tg_rep_1.append(tc_report_3)

        assert tg_rep_1.tags_index == {
            "simple": {"foo", "bar", "baz", "bat"},
            "color": {"blue"},
        }

        assert tc_report_3.tags_index == {"simple": {"foo"}, "color": {"blue"}}

    def test_tag_propagation_on_filter(self):
        """
        Tag indices should be updated after filter operations
        (starting with the original node that is getting filtered).
        """

        def filter_func(obj):
            """
            Keep all test groups, discard testcase
            report with name `My Test Case 2`
            """
            return isinstance(obj, TestGroupReport) or (
                isinstance(obj, TestCaseReport)
                and obj.name != "My Test Case 2"
            )

        tg_rep_1, tg_rep_2, tg_rep_3, tc_rep_1, tc_rep_2 = self.get_reports()

        new_tg_rep_1 = tg_rep_1.filter(filter_func)

        new_tg_rep_2, new_tg_rep_3 = new_tg_rep_1
        new_tc_rep_1 = new_tg_rep_2.entries[0]

        assert new_tc_rep_1.name == "My Test Case"

        assert new_tg_rep_1.tags_index == {"simple": {"foo", "bar", "baz"}}
        assert new_tg_rep_2.tags_index == {"simple": {"foo", "bar", "baz"}}
        assert new_tg_rep_3.tags_index == {"simple": {"foo"}}

        # tag indices from the original should have stayed same
        assert tg_rep_1.tags_index == {"simple": {"foo", "bar", "baz", "bat"}}
        assert tg_rep_2.tags_index == {"simple": {"foo", "bar", "baz", "bat"}}
        assert tg_rep_3.tags_index == {"simple": {"foo"}}
        assert tc_rep_1.tags_index == {"simple": {"foo", "bar", "baz"}}
        assert tc_rep_2.tags_index == {"simple": {"foo", "bar", "bat"}}


def test_env_status_hash():
    """
    Test updating the env_status of a TestGroupReport object - this should
    cause the hash to change.
    """
    report_group = TestGroupReport(
        name="MTest1",
        category=ReportCategories.MULTITEST,
        description="MTest1 description",
        env_status=entity.ResourceStatus.STOPPED,
    )

    orig_hash = report_group.hash
    report_group.env_status = entity.ResourceStatus.STARTED

    assert report_group.hash != orig_hash


def iter_report_entries(report):
    for entry in report.entries:
        yield entry
        if report.entries:
            yield from iter_report_entries(entry)


def test_runtime_status_setting(dummy_test_plan_report):
    for status in list(RuntimeStatus)[:-1]:
        dummy_test_plan_report.runtime_status = status
        assert dummy_test_plan_report.runtime_status == status
        for entry in iter_report_entries(dummy_test_plan_report):
            assert entry.runtime_status == status


def test_runtime_status_setting_filtered(dummy_test_plan_report):
    filtered_entries = {
        "Test Group 2": {
            "Test Group 1": {
                "test_case_1": {},
                "test_case_2": {},
            }
        }
    }
    flattened_filtered_entries = [
        "Test Group 2",
        "Test Group 1",
        "test_case_1",
        "test_case_2",
    ]
    for status in list(RuntimeStatus)[:-1]:
        dummy_test_plan_report.set_runtime_status_filtered(
            status, filtered_entries
        )
        # Due to precedence logic, as soon as we hit NOT_RUN and FINISHED
        # the not run entry's READY status will be returned in the getter.
        # This is expected behavior.
        if status in list(RuntimeStatus)[:-3]:
            assert (
                dummy_test_plan_report["Test Group 2"].runtime_status == status
            )
        else:
            assert (
                dummy_test_plan_report["Test Group 2"].runtime_status
                == RuntimeStatus.READY
            )
        # For all entries the underlying _runtime_status should be set explicitly
        # and not derived through precedence and other entries.
        for entry in iter_report_entries(dummy_test_plan_report):
            if entry.name in flattened_filtered_entries:
                assert entry._runtime_status == status
