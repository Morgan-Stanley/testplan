"""
Base classes / logic for marshalling go here.
"""
from marshmallow import Schema, fields, post_dump

from testplan.common.serialization import fields as custom_fields
from testplan.common.serialization.schemas import SchemaRegistry
from testplan.common.utils.convert import delta_encode_level
from testplan.testing.multitest.entries.base import (
    DEFAULT_CATEGORY,
    DEFAULT_FLAG,
)

from .. import base


class AssertionSchemaRegistry(SchemaRegistry):
    def get_category(self, obj):
        return obj.meta_type


registry = AssertionSchemaRegistry()


class GenericEntryList(fields.Field):
    def _serialize(self, value, attr, obj, **kwargs):
        return [registry.serialize(entry) for entry in value]


@registry.bind_default()
class BaseSchema(Schema):
    type = custom_fields.ClassName()
    meta_type = fields.String()
    timestamp = fields.DateTime("timestamp")
    description = custom_fields.Unicode()
    category = fields.String()
    flag = fields.String()
    custom_style = fields.Dict(keys=fields.String(), values=fields.String())

    # optional
    line_no = fields.Integer(allow_none=True)
    file_path = fields.String(allow_none=True)
    code_context = fields.String(allow_none=True)

    # # deprecated, but this is a dump_only schema
    # utc_time = custom_fields.UTCDateTime(allow_none=True, load_only=True)
    # machine_time = custom_fields.LocalDateTime(allow_none=True, load_only=True)

    def load(self, *args, **kwargs):
        raise NotImplementedError("Only serialization is supported.")

    @post_dump
    def streamline(self, data, **kwargs):
        # since source code is always available,
        # none-test on file_path should be reliable
        if data["file_path"] is None:
            del data["line_no"]
            del data["file_path"]
            del data["code_context"]
        if data["category"] == DEFAULT_CATEGORY:
            del data["category"]
        if data["flag"] == DEFAULT_FLAG:
            del data["flag"]
        return data


@registry.bind(base.Group, base.Summary)
class GroupSchema(Schema):
    type = custom_fields.ClassName()
    timestamp = fields.DateTime("timestamp")
    passed = fields.Boolean()
    meta_type = fields.String()
    description = custom_fields.Unicode(allow_none=True)
    entries = GenericEntryList(allow_none=True)

    # # deprecated, but this is a dump_only schema
    # utc_time = custom_fields.UTCDateTime(allow_none=True, load_only=True)

    def load(self, *args, **kwargs):
        raise NotImplementedError("Only serialization is supported.")


@registry.bind(base.Log)
class LogSchema(BaseSchema):
    message = fields.Raw()


@registry.bind(base.CodeLog)
class CodeLogSchema(BaseSchema):
    code = fields.String()
    language = fields.String()


@registry.bind(base.Markdown)
class MarkdownSchema(BaseSchema):
    message = fields.String()
    escape = fields.Boolean()


@registry.bind(base.TableLog)
class TableLogSchema(BaseSchema):
    table = fields.List(fields.List(custom_fields.NativeOrPretty()))
    display_index = fields.Boolean()
    columns = fields.List(fields.String(), allow_none=False)


@registry.bind(base.DictLog, base.FixLog)
class DictLogSchema(BaseSchema):
    flattened_dict = fields.Raw()

    @post_dump
    def compress_level(self, data, many, **kw):
        data["flattened_dict"] = delta_encode_level(data["flattened_dict"])
        return data


@registry.bind(base.Graph)
class GraphSchema(BaseSchema):
    graph_type = fields.String()
    graph_data = fields.Dict(
        keys=fields.String(), values=fields.List(fields.Dict())
    )
    series_options = fields.Dict(
        keys=fields.String(), values=fields.Dict(), allow_none=True
    )
    type = fields.String()
    graph_options = fields.Dict(allow_none=True)
    discrete_chart = fields.Bool()


@registry.bind(base.Attachment, base.MatPlot)
class AttachmentSchema(BaseSchema):
    source_path = fields.String()
    orig_filename = fields.String()
    filesize = fields.Integer()
    dst_path = fields.String()


@registry.bind(base.Plotly)
class PlotlySchema(AttachmentSchema):
    style = fields.Dict(allow_none=True)


@registry.bind(base.Directory)
class DirectorySchema(BaseSchema):
    source_path = fields.String()
    dst_path = fields.String()
    ignore = fields.List(fields.String(), allow_none=True)
    only = fields.List(fields.String(), allow_none=True)
    recursive = fields.Boolean()
    file_list = fields.List(fields.String())


class EdgeSchema(Schema):
    id = fields.String()
    source = fields.String()
    target = fields.String()
    startLabel = fields.String()
    label = fields.String()
    endLabel = fields.String()


class NodeSchema(Schema):
    id = fields.String()
    data = fields.Dict(keys=fields.String(), values=fields.String())
    style = fields.Dict(keys=fields.String(), values=fields.String())


@registry.bind(base.FlowChart)
class FlowChartSchema(BaseSchema):
    nodes = fields.Nested(NodeSchema, many=True)
    edges = fields.Nested(EdgeSchema, many=True)
