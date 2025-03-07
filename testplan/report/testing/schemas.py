"""Schema classes for test Reports."""

import functools
import math

from boltons.iterutils import is_scalar, remap
from marshmallow import Schema, fields, post_load, post_dump, pre_load
from marshmallow.utils import EXCLUDE

from testplan.common.report.base import ReportCategories
from testplan.common.report.schemas import (
    BaseReportGroupSchema,
    ReportLinkSchema,
    ReportLogSchema,
    ReportSchema,
    TimerField,
)
from testplan.common.serialization import fields as custom_fields
from testplan.common.serialization.schemas import load_tree_data
from testplan.common.utils.json import json_dumps
from testplan.report.testing.base import (
    TestCaseReport,
    TestGroupReport,
    TestReport,
)

__all__ = ["TestCaseReportSchema", "TestGroupReportSchema", "TestReportSchema"]

# pylint: disable=unused-argument


# NOTE: old format data doesn't come with timezone attr, this info ought to be
# NOTE: extracted from timer fields or maybe machine_time from serialized
# NOTE: assertions, but unfortunately we use utc in timer fields back then, and
# NOTE: the presentence of serialized assertions is not guaranteed
_IANA_UTC = "Etc/UTC"


class TagField(fields.Field):
    """Field for serializing tag data, which is a ``dict`` of ``set``."""

    def _serialize(self, value, attr, obj, **kwargs):
        return {
            tag_name: list(tag_values)
            for tag_name, tag_values in value.items()
        }

    def _deserialize(self, value, attr, data, **kwargs):
        return {
            tag_name: set(tag_values) for tag_name, tag_values in value.items()
        }


class EntriesField(fields.Field):
    """
    Handle encoding problems gracefully
    """

    @staticmethod
    def _json_serializable(v):
        try:
            json_dumps(v)
        except (UnicodeDecodeError, TypeError):
            return False
        else:
            return True

    def _serialize(self, value, attr, obj, **kwargs):
        # we don't need a _deserialize() here as we don't (and can't)
        # convert str back to non-json-serializable.
        def visit(parent, key, _value):
            """
            return
                True - keep the node unchange
                False - remove the node
                tuple - update the node data.
            """
            if is_scalar(_value):
                if isinstance(_value, float):
                    if math.isnan(_value):
                        return key, "NaN"
                    elif math.isinf(_value):
                        if _value > 0:
                            return key, "Infinity"
                        return key, "-Infinity"
                elif not self._json_serializable(_value):
                    return key, str(_value)
            return True

        return remap(value, visit=visit)


class TestCaseReportSchema(ReportSchema):
    """Schema for ``testing.TestCaseReport``"""

    source_class = TestCaseReport

    entries = fields.List(EntriesField())
    category = fields.String()
    counter = fields.Dict(dump_only=True)
    tags = TagField()

    @post_load
    def make_report(self, data, **kwargs):
        """
        Create the report object, assign ``timer`` &
        ``status_override`` attributes explicitly
        """
        status = data.pop("status")
        runtime_status = data.pop("runtime_status")

        rep = super(TestCaseReportSchema, self).make_report(data)

        rep.status = status
        rep.runtime_status = runtime_status
        return rep


class TestGroupReportSchema(BaseReportGroupSchema):
    """
    Schema for ``testing.TestGroupReportSchema``, supports tree serialization.
    """

    source_class = TestGroupReport

    part = fields.List(fields.Integer, allow_none=True)
    env_status = fields.String(allow_none=True)
    strict_order = fields.Bool(allow_none=True)
    timezone = fields.String(load_default=_IANA_UTC)

    category = fields.String()
    tags = TagField()

    entries = custom_fields.GenericNested(
        schema_context={
            TestCaseReport: TestCaseReportSchema,
            TestGroupReport: lambda: TestGroupReportSchema(),
        },
        many=True,
    )

    # # abolished
    # fix_spec_path = fields.String(allow_none=True, load_only=True)
    # host = fields.String(allow_none=True, load_only=True)

    @post_load
    def make_report(self, data, **kwargs):
        """
        Propagate tag indices after deserialization
        """
        rep = super(TestGroupReportSchema, self).make_report(data)
        rep.propagate_tag_indices()
        return rep

    @post_dump
    def strip_none_by_category(self, data, **kwargs):
        if not ReportCategories.is_test_level(data["category"]):
            del data["part"]
            del data["env_status"]
            del data["timezone"]
        if data["category"] != ReportCategories.TESTSUITE:
            del data["strict_order"]
        return data


class TestReportSchema(BaseReportGroupSchema):
    """Schema for test report root, ``testing.TestReport``."""

    class Meta:
        unknown = EXCLUDE

    source_class = TestReport

    category = fields.String(dump_only=True)
    meta = fields.Dict()
    label = fields.String(allow_none=True)
    tags_index = TagField(dump_only=True)
    information = fields.List(fields.Tuple([fields.String(), fields.String()]))
    resource_meta_path = fields.String(dump_only=True, allow_none=True)
    counter = fields.Dict(dump_only=True)
    timezone = fields.String(load_default=_IANA_UTC)

    attachments = fields.Dict()
    timeout = fields.Integer(allow_none=True)

    entries = custom_fields.GenericNested(
        schema_context={TestGroupReport: TestGroupReportSchema}, many=True
    )

    @post_load
    def make_report(self, data, **kwargs):
        """Create report object & deserialize sub trees."""
        load_tree = functools.partial(
            load_tree_data,
            node_schema=TestGroupReportSchema,
            leaf_schema=TestCaseReportSchema,
        )

        entry_data = data.pop("entries")

        rep = super(TestReportSchema, self).make_report(data)
        rep.entries = [load_tree(c_data) for c_data in entry_data]
        rep.propagate_tag_indices()

        return rep


class ShallowTestGroupReportSchema(Schema):
    """Schema for shallow serialization of ``TestGroupReport``."""

    class Meta:
        unknown = EXCLUDE

    name = fields.String(required=True)
    description = fields.String(allow_none=True)
    uid = fields.String(required=True)
    category = fields.String()
    timer = TimerField(required=True)
    part = fields.List(fields.Integer, allow_none=True)

    status_override = fields.Function(
        lambda x: x.status_override.to_json_compatible(), allow_none=True
    )
    status = fields.Function(lambda x: x.status.to_json_compatible())
    runtime_status = fields.Function(
        lambda x: x.runtime_status.to_json_compatible()
    )
    counter = fields.Dict(dump_only=True)
    tags = TagField()
    timezone = fields.String(load_default=_IANA_UTC)

    entry_uids = fields.List(fields.String(), dump_only=True)
    parent_uids = fields.List(fields.String())
    logs = fields.Nested(ReportLogSchema, many=True)
    hash = fields.Integer(dump_only=True)
    env_status = fields.String(allow_none=True)
    strict_order = fields.Bool(allow_none=True)
    children = fields.List(fields.Nested(ReportLinkSchema))

    # # abolished
    # fix_spec_path = fields.String(allow_none=True, load_only=True)

    @post_load
    def make_testgroup_report(self, data, **kwargs):
        children = data.pop("children", [])
        timer = data.pop("timer")
        logs = data.pop("logs", [])

        group_report = TestGroupReport(**data)
        group_report.propagate_tag_indices()

        group_report.timer = timer
        group_report.logs = logs
        group_report.children = children

        return group_report

    @post_dump
    def strip_none_by_category(self, data, **kwargs):
        if not ReportCategories.is_test_level(data["category"]):
            del data["part"]
            del data["env_status"]
            del data["timezone"]
        if data["category"] != ReportCategories.TESTSUITE:
            del data["strict_order"]
        return data


class ShallowTestReportSchema(Schema):
    """Schema for shallow serialization of ``TestReport``."""

    class Meta:
        unknown = EXCLUDE

    name = fields.String(required=True)
    description = fields.String(allow_none=True)
    uid = fields.String(required=True)
    category = fields.String(dump_only=True)
    timezone = fields.String(load_default=_IANA_UTC)
    timer = TimerField(required=True)
    meta = fields.Dict()
    status = fields.Function(lambda x: x.status.to_json_compatible())
    runtime_status = fields.Function(
        lambda x: x.runtime_status.to_json_compatible()
    )
    information = fields.List(fields.List(fields.String()))
    tags_index = TagField(dump_only=True)
    status_override = fields.Function(
        lambda x: x.status_override.to_json_compatible(), allow_none=True
    )
    counter = fields.Dict(dump_only=True)
    attachments = fields.Dict()
    entry_uids = fields.List(fields.String(), dump_only=True)
    parent_uids = fields.List(fields.String())
    logs = fields.Nested(ReportLogSchema, many=True)
    hash = fields.Integer(dump_only=True)

    @post_load
    def make_test_report(self, data, **kwargs):
        timer = data.pop("timer")
        logs = data.pop("logs", [])

        test_plan_report = TestReport(**data)
        test_plan_report.propagate_tag_indices()

        test_plan_report.timer = timer
        test_plan_report.logs = logs

        return test_plan_report
