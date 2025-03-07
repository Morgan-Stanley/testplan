"""
  Base schemas for report serialization.
"""
import datetime

from marshmallow import Schema, fields, post_dump, post_load, pre_load
from marshmallow.utils import EXCLUDE

from testplan.common.report.base import (
    BaseReportGroup,
    Report,
    RuntimeStatus,
    Status,
)
from testplan.common.serialization import fields as custom_fields
from testplan.common.serialization import schemas
from testplan.common.utils import timing

__all__ = ["ReportLogSchema", "ReportSchema", "BaseReportGroupSchema"]

# pylint: disable=unused-argument


class IntervalSchema(Schema):
    """Schema for ``timer.Interval``"""

    start = fields.DateTime("timestamp")
    end = fields.DateTime("timestamp", allow_none=True)

    @pre_load
    def accept_old_isoformat(self, data, **kwargs):
        try:
            if data.get("start", None) and isinstance(data["start"], str):
                data["start"] = datetime.datetime.fromisoformat(
                    data["start"]
                ).timestamp()
            if data.get("end", None) and isinstance(data["end"], str):
                data["end"] = datetime.datetime.fromisoformat(
                    data["end"]
                ).timestamp()
            return data
        except ValueError as e:
            # no need to defer
            raise ValueError("Invalid value when loading Interval.") from e

    @post_load
    def make_interval(self, data, **kwargs):
        """Create an Interal object."""
        return timing.Interval(**data)


class TimerField(fields.Field):
    """
    Field for serializing ``timer.Timer`` objects, which is a ``dict``
    of ``timer.Interval``.
    """

    def _serialize(self, value, attr, obj, **kwargs):
        return {
            k: [IntervalSchema().dump(v) for v in l] for k, l in value.items()
        }

    def _deserialize(self, value, attr, data, **kwargs):
        return timing.Timer(
            {
                k: [IntervalSchema().load(v) for v in l]
                for k, l in value.items()
            }
        )


class ReportLinkSchema(Schema):
    """
    Field for serializing ``ReportLink`` objects, which is a recursive
    structure for report linkage.
    """

    name = fields.String()
    timer = TimerField()
    children = fields.List(fields.Nested(lambda: ReportLinkSchema()))


class ReportLogSchema(Schema):
    """Schema for log record data created by report stdout."""

    message = fields.String()
    levelname = fields.String()
    levelno = fields.Integer()
    created = fields.DateTime("timestamp")
    funcName = fields.String()
    lineno = fields.Integer()
    uid = fields.UUID()


class ReportSchema(schemas.TreeNodeSchema):
    """Schema for ``base.Report``."""

    class Meta:
        unknown = EXCLUDE

    source_class = Report

    name = fields.String()
    description = fields.String(allow_none=True)
    definition_name = fields.String(
        allow_none=True
    )  # otherwise new tpr cannot process old report
    uid = fields.String()
    entries = fields.List(custom_fields.NativeOrPretty())
    status_override = fields.Function(
        lambda x: x.status_override.to_json_compatible(),
        Status.from_json_compatible,
        allow_none=True,
    )
    status_reason = fields.String(allow_none=True)
    status = fields.Function(
        lambda x: x.status.to_json_compatible(),
        Status.from_json_compatible,
    )
    runtime_status = fields.Function(
        lambda x: x.runtime_status.to_json_compatible(),
        RuntimeStatus.from_json_compatible,
    )
    logs = fields.Nested(ReportLogSchema, many=True)
    hash = fields.Integer(dump_only=True)
    parent_uids = fields.List(fields.String())
    timer = TimerField(required=True)

    @post_load
    def make_report(self, data, **kwargs):
        """Create report object, attach log list."""

        # We can discard the type field since we know what kind of report we
        # are making.
        if "type" in data:
            data.pop("type")

        logs = data.pop("logs", [])
        timer = data.pop("timer")

        rep = self.get_source_class()(**data)

        rep.logs = logs
        rep.timer = timer
        return rep

    @post_dump
    def strip_none(self, data, **kwargs):
        if data["status_override"] is None:
            del data["status_override"]
        if data["status_reason"] is None:
            del data["status_reason"]
        return data


class BaseReportGroupSchema(ReportSchema):
    """Schema for ``base.BaseReportGroup``."""

    source_class = BaseReportGroup

    entries = custom_fields.GenericNested(
        schema_context={
            "Report": ReportSchema,
            "BaseReportGroup": lambda: BaseReportGroupSchema(),
        },
        many=True,
    )
    counter = fields.Dict(dump_only=True)
    children = fields.List(fields.Nested(ReportLinkSchema))

    @post_load
    def make_report(self, data, **kwargs):
        """Create report group object"""

        children = data.pop("children", [])
        host = data.pop("host", None)
        status = data.pop("status")
        runtime_status = data.pop("runtime_status")

        rep = super(BaseReportGroupSchema, self).make_report(data)
        rep.children = children
        rep.host = host
        rep.status = status
        rep.runtime_status = runtime_status

        return rep
