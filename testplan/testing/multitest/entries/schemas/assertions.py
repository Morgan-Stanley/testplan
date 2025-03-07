"""
Schema definitions for serializing Assertion objects. This will be a one-way
conversion, meaning that the reports and exports will be using the serialized
data directly.

The reason being some assertion classes may have attributes that
cannot be deserialized (processes, exception objects etc).
"""
from marshmallow import Schema, fields, post_dump

from testplan.common.serialization import fields as custom_fields
from testplan.common.utils.convert import delta_encode_level

from .base import BaseSchema, registry
from .. import assertions as asr

# pylint: disable=missing-docstring, abstract-method


@registry.bind_default(category="assertion")
class AssertionSchema(BaseSchema):
    passed = fields.Boolean()


@registry.bind(asr.RawAssertion)
class RawAssertionSchema(AssertionSchema):
    content = fields.String()


@registry.bind(
    asr.NotEqual,
    asr.Less,
    asr.LessEqual,
    asr.Greater,
    asr.GreaterEqual,
)
class FuncAssertionSchema(AssertionSchema):

    first = custom_fields.NativeOrPretty()
    second = custom_fields.NativeOrPretty()
    label = fields.String()


@registry.bind(asr.Equal)
class EqualSchema(FuncAssertionSchema):

    type_actual = fields.String()
    type_expected = fields.String()


@registry.bind(asr.Fail)
class FailSchema(AssertionSchema):
    message = fields.Raw()


@registry.bind(asr.IsClose)
class ApproximateEqualitySchema(AssertionSchema):

    first = custom_fields.NativeOrPretty()
    second = custom_fields.NativeOrPretty()
    rel_tol = custom_fields.NativeOrPretty()
    abs_tol = custom_fields.NativeOrPretty()
    label = fields.String()


@registry.bind(asr.IsTrue, asr.IsFalse)
class BooleanSchema(AssertionSchema):

    expr = custom_fields.NativeOrPretty()


@registry.bind(asr.Contain, asr.NotContain)
class MembershipSchema(AssertionSchema):

    member = custom_fields.NativeOrPretty()
    container = custom_fields.NativeOrPretty()


@registry.bind(
    asr.RegexMatch,
    asr.RegexMatchNotExists,
    asr.RegexSearch,
    asr.RegexSearchNotExists,
    asr.RegexMatchLine,
)
class RegexSchema(AssertionSchema):

    string = custom_fields.NativeOrPretty()
    pattern = custom_fields.NativeOrPretty()
    # flags = fields.Integer()  # NOTE: never set & used up to now
    match_indexes = fields.List(fields.List(fields.Integer()))


@registry.bind(asr.RegexFindIter)
class RegexFindIterSchema(RegexSchema):

    condition_match = fields.Boolean()
    condition = custom_fields.NativeOrPretty()


@registry.bind(asr.ExceptionRaised, asr.ExceptionNotRaised)
class ExceptionRaisedSchema(AssertionSchema):

    raised_exception = custom_fields.ExceptionField()
    expected_exceptions = fields.List(custom_fields.NativeOrPretty())

    pattern = custom_fields.Unicode(allow_none=True)
    func = fields.String(allow_none=True)

    exception_match = fields.Boolean()
    func_match = fields.Boolean()
    pattern_match = fields.Boolean()


@registry.bind(asr.EqualSlices, asr.EqualExcludeSlices)
class EqualSlicesSchema(AssertionSchema):
    # TODO: strip included_indices if of type EqualSlices

    data = fields.List(custom_fields.SliceComparisonField())
    included_indices = fields.List(fields.Integer())
    actual = fields.List(custom_fields.NativeOrPretty())
    expected = fields.List(custom_fields.NativeOrPretty())


@registry.bind(asr.LineDiff)
class LineDiffSchema(AssertionSchema):

    first = fields.List(custom_fields.NativeOrPretty())
    second = fields.List(custom_fields.NativeOrPretty())
    ignore_space_change = custom_fields.NativeOrPretty()
    ignore_whitespaces = custom_fields.NativeOrPretty()
    ignore_blank_lines = custom_fields.NativeOrPretty()
    unified = custom_fields.NativeOrPretty()
    context = custom_fields.NativeOrPretty()
    delta = fields.List(custom_fields.NativeOrPretty())


@registry.bind(asr.ColumnContain)
class ColumnContainSchema(AssertionSchema):
    # XXX: if report_fails_only is False, strip row indices within data?

    # table = fields.List(custom_fields.NativeOrPrettyDict())
    values = fields.List(custom_fields.NativeOrPretty())
    column = fields.String()
    limit = fields.Integer()
    report_fails_only = fields.Boolean()
    data = fields.List(custom_fields.ColumnContainComparisonField())


@registry.bind(asr.TableMatch, asr.TableDiff)
class TableMatchSchema(AssertionSchema):
    # XXX: if report_fails_only is False, strip row indices within data?

    strict = fields.Boolean()

    columns = fields.List(fields.String(), attribute="display_columns")

    # Row data with diffs, errors, extra ctx for comparators
    data = fields.List(custom_fields.RowComparisonField())

    include_columns = fields.List(fields.String(), allow_none=True)
    exclude_columns = fields.List(fields.String(), allow_none=True)
    message = fields.String(allow_none=True)
    fail_limit = fields.Integer()
    report_fails_only = fields.Bool()


@registry.bind(asr.XMLCheck)
class XMLCheckSchema(AssertionSchema):

    xpath = fields.String()
    tags = fields.List(fields.String())

    xml = custom_fields.XMLElementField(attribute="element")

    namespaces = fields.Dict()
    data = fields.List(fields.List(custom_fields.NativeOrPretty()))
    message = fields.String()


@registry.bind(asr.DictCheck, asr.FixCheck)
class DictCheckSchema(AssertionSchema):

    has_keys = fields.List(custom_fields.NativeOrPretty())
    has_keys_diff = fields.List(custom_fields.NativeOrPretty())

    absent_keys = fields.List(custom_fields.NativeOrPretty())
    absent_keys_diff = fields.List(custom_fields.NativeOrPretty())


@registry.bind(asr.DictMatch, asr.FixMatch)
class DictMatchSchema(AssertionSchema):

    include_keys = fields.List(custom_fields.NativeOrPretty())
    exclude_keys = fields.List(custom_fields.NativeOrPretty())
    actual_description = fields.String()
    expected_description = fields.String()
    comparison = fields.Raw()

    @post_dump
    def compress_level(self, data, many, **kw):
        data["comparison"] = delta_encode_level(data["comparison"])
        return data


@registry.bind(asr.DictMatchAll, asr.FixMatchAll)
class DictMatchAllSchema(AssertionSchema):

    key_weightings = fields.Raw()
    matches = fields.Raw()

    @post_dump
    def compress_level(self, data, many, **kw):
        for d in data["matches"]:
            d["comparison"] = delta_encode_level(d["comparison"])
        return data


class LogfileMatchResultSchema(Schema):
    matched = fields.String(allow_none=True)
    pattern = fields.String()
    start_pos = fields.String()
    end_pos = fields.String()


class AtMostOneList(fields.List):
    def _serialize(self, value, attr, obj, **kwargs):
        if not isinstance(value, list) or len(value) > 1:
            raise TypeError(
                f"Unexpected value {value} passed to AtMostOneList field."
            )
        return super()._serialize(value, attr, obj, **kwargs)

    def _deserialize(self, value, attr, data, **kwargs):
        if not isinstance(value, list) or len(value) > 1:
            raise TypeError(
                f"Unexpected value {value} passed to AtMostOneList field."
            )
        return super()._deserialize(value, attr, data, **kwargs)


@registry.bind(asr.LogfileMatch)
class LogfileMatchSchema(AssertionSchema):
    timeout = fields.Float()
    results = fields.List(fields.Nested(LogfileMatchResultSchema()))
    failure = AtMostOneList(fields.Nested(LogfileMatchResultSchema()))

    # TODO: check if chained list having at least one elem
