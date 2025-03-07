"""
Base classes go here.
"""
import os
import re
import datetime
import operator
import pprint
import shutil
import hashlib
import pathlib


from testplan.common.utils.convert import nested_groups
from testplan.common.utils.timing import now
from testplan.common.utils.table import TableEntry
from testplan.common.utils.reporting import fmt
from testplan.common.utils.convert import flatten_formatted_object
from testplan.common.utils.path import hash_file, traverse_dir, makedirs
from testplan import defaults


__all__ = ["BaseEntry", "Group", "Summary", "Log"]


# Will be used for default conversion like: NotEqual -> Not Equal
ENTRY_NAME_PATTERN = re.compile(r"([A-Z])")

DEFAULT_CATEGORY = "DEFAULT"
DEFAULT_FLAG = "DEFAULT"


def readable_name(class_name):
    """NotEqual -> Not Equal"""
    return ENTRY_NAME_PATTERN.sub(" \\1", class_name).strip()


class BaseEntry:
    """Base class for all entries, stores common context like time etc."""

    meta_type = "entry"

    def __init__(self, description, category=None, flag=None):
        self.timestamp = now()
        self.description = description
        self.category = category or DEFAULT_CATEGORY
        self.flag = flag or DEFAULT_FLAG

        # Will be set explicitly via containers
        self.line_no = None
        self.file_path = None
        self.code_context = None

    def __str__(self):
        return repr(self)

    def __bool__(self):
        return True

    @property
    def name(self):
        """MyClass -> My Class"""
        return readable_name(self.__class__.__name__)

    def serialize(self):
        """Shortcut method for serialization via schemas"""
        from .schemas.base import registry

        return registry.serialize(self)


class Group:

    # we treat Groups as assertions so we can render them with pass/fail context
    meta_type = "assertion"

    def __init__(self, entries, description=None):
        self.timestamp = now()
        self.description = description
        self.entries = entries

    def __bool__(self):
        return self.passed

    def __repr__(self):
        return "{}(entries={}, description='{}')".format(
            self.__class__.__name__, self.entries, self.description
        )

    @property
    def passed(self):
        """
        Empty groups are truthy AKA does not
        contain anything that is failing.
        """
        return (not self.entries) or all([bool(e) for e in self.entries])


class Summary(Group):
    """
    A meta assertion that stores a subset of given entries.
    Groups assertion data into a nested structure by category, assertion type
    and pass/fail status.

    If any of the entries is a Group, then its entries are expanded and
    the Group object is discarded.
    """

    def __init__(
        self,
        entries,
        description=None,
        num_passing=defaults.SUMMARY_NUM_PASSING,
        num_failing=defaults.SUMMARY_NUM_FAILING,
        key_combs_limit=defaults.SUMMARY_KEY_COMB_LIMIT,
    ):
        self.num_passing = num_passing
        self.num_failing = num_failing
        self.key_combs_limit = key_combs_limit

        super(Summary, self).__init__(
            entries=self._summarize(
                entries,
                num_passing=num_passing,
                num_failing=num_failing,
                key_combs_limit=key_combs_limit,
            ),
            description=description,
        )

    def _flatten(self, entries):
        """
        Recursively traverse entries and expand entries of groups.
        """

        def _flatten(items):
            result = []
            for item in items:
                if isinstance(item, Group) and not isinstance(item, Summary):
                    result.extend(_flatten(item.entries))
                else:
                    result.append(item)
            return result

        return _flatten(entries)

    def _summarize(self, entries, num_passing, num_failing, key_combs_limit):
        # Circular imports
        from .assertions import Assertion
        from .summarization import registry

        # Get rid of Groups (but leave summaries)
        entries = self._flatten(entries)
        summaries = [e for e in entries if isinstance(e, Summary)]

        # Create nested data of depth 3
        # Group by category, class name and pass/fail status
        groups = nested_groups(
            iterable=(e for e in entries if isinstance(e, Assertion)),
            key_funcs=[
                operator.attrgetter("category"),
                lambda obj: obj.__class__.__name__,
                operator.truth,
            ],
        )

        result = []
        limits = dict(
            num_passing=num_passing,
            num_failing=num_failing,
            key_combs_limit=key_combs_limit,
        )

        for category, category_grouping in groups:
            cat_group = Group(
                entries=[], description="Category: {}".format(category)
            )
            for class_name, assertion_grouping in category_grouping:
                asr_group = Group(
                    entries=[],
                    description="Assertion type: {}".format(
                        readable_name(class_name)
                    ),
                )
                for pass_status, assertion_entries in assertion_grouping:
                    # Apply custom grouping, otherwise just trim the
                    # list of entries via default summarization func.
                    summarizer = registry[class_name]
                    summary_group = summarizer(
                        category=category,
                        class_name=class_name,
                        passed=pass_status,
                        entries=assertion_entries,
                        limits=limits,
                    )
                    if len(summary_group.entries):
                        asr_group.entries.append(summary_group)
                cat_group.entries.append(asr_group)
            result.append(cat_group)
        return summaries + result


class Log(BaseEntry):
    """Log a str to the report."""

    def __init__(self, message, description=None, flag=None):
        if isinstance(message, str):
            self.message = message
        elif isinstance(message, bytes):
            self.message = message.decode()
        else:
            self.message = pprint.pformat(message)

        if not description:
            description = next((l for l in self.message.split("\n") if l), "")
            if len(description) > 80:
                description = description[0:80] + "..."

        super(Log, self).__init__(description=description, flag=flag)


class TableLog(BaseEntry):
    """Log a table to the report."""

    def __init__(self, table, display_index=False, description=None):

        as_list = TableEntry(table).as_list_of_list()
        self.columns, self.table = as_list[0], as_list[1:]
        # NOTE: we don't allow custom indices up to now
        # NOTE: we can add self.indices back if necessary
        # self.indices = range(len(self.table))
        self.display_index = display_index

        super(TableLog, self).__init__(description=description)


class DictLog(BaseEntry):
    """Log a dict object to the report."""

    def __init__(self, dictionary, description=None):
        formatted_obj = fmt(dictionary)
        if len(formatted_obj) != 2 or formatted_obj[0] != 2:
            raise TypeError("Require a formatted object of mapping type")
        self.flattened_dict = flatten_formatted_object(formatted_obj)

        super(DictLog, self).__init__(description=description)


class FixLog(DictLog):
    """Log a fix message to the report."""

    def __init__(self, msg, description=None):
        if not msg or not isinstance(msg, dict):
            raise TypeError("Invalid format of fix message")

        super(FixLog, self).__init__(msg, description=description)


class Graph(BaseEntry):
    """Create a graph for the report."""

    def __init__(
        self,
        graph_type,
        graph_data,
        description=None,
        series_options=None,
        graph_options=None,
    ):
        """
        NOTE:
        When adding functionality to Graph, VALID_GRAPH_TYPES,
        VALID_CHART_TYPES, VALID_GRAPH_OPTIONS and
        VALID_SERIES_OPTIONS must be kept updated
        """
        self.VALID_GRAPH_TYPES = [
            "Line",
            "Scatter",
            "Bar",
            "Whisker",
            "Contour",
            "Hexbin",
        ]
        self.VALID_CHART_TYPES = ["Pie"]
        self.VALID_GRAPH_OPTIONS = ["xAxisTitle", "yAxisTitle", "legend"]
        self.VALID_SERIES_OPTIONS = ["colour"]

        self.graph_type = graph_type
        self.graph_data = graph_data

        if series_options is not None:
            self.assert_valid_series_options(series_options, graph_data)
        self.series_options = series_options

        if graph_options is not None:
            self.assert_valid_graph_options(graph_options)
        self.graph_options = graph_options

        self.type = "Graph"
        if graph_type in self.VALID_CHART_TYPES:
            self.discrete_chart = True
        elif graph_type in self.VALID_GRAPH_TYPES:
            self.discrete_chart = False
        else:
            raise ValueError(
                "Graph of type {!r} cannot " "be rendered".format(graph_type)
            )

        super(Graph, self).__init__(description=description)

    def assert_valid_graph_options(self, graph_options):
        for option in graph_options:
            if option not in self.VALID_GRAPH_OPTIONS:
                raise ValueError(
                    "Graph option {!r} " "is not valid".format(option)
                )

    def assert_valid_series_options(self, series_options, graph_data):
        for series_name in series_options:
            if series_name not in graph_data:
                raise ValueError(
                    "Series {!r} cannot be found in "
                    "graph data, cannot "
                    "apply series options".format(series_name)
                )
            for series_option in series_options[series_name]:
                if series_option not in self.VALID_SERIES_OPTIONS:
                    raise ValueError(
                        "Series Option: {!r} is not "
                        "valid (found in series "
                        "{!r})".format(series_option, series_name)
                    )


class Attachment(BaseEntry):
    """Entry representing a file attached to the report."""

    def __init__(
        self, filepath, description=None, dst_path=None, scratch_path=None
    ):

        self.source_path = filepath
        self.orig_filename = os.path.basename(filepath)
        self.filesize = os.path.getsize(filepath)

        if dst_path is None:
            basename, ext = os.path.splitext(self.orig_filename)
            hash = hash_file(self.source_path)
            # To avoid file name collision
            self.dst_path = f"{basename}-{hash}-{self.filesize}{ext}"
        else:
            self.dst_path = dst_path

        if scratch_path:
            # will best effort make a copy of the file
            try:
                copy_of_file = os.path.join(scratch_path, self.dst_path)
                shutil.copyfile(filepath, copy_of_file)
            except Exception:
                pass
            else:
                self.source_path = copy_of_file

        super(Attachment, self).__init__(description=description)


class MatPlot(Attachment):
    """Display a MatPlotLib graph in the report."""

    def __init__(
        self, pyplot, image_file_path, width, height, description=None
    ):

        if width:
            pyplot.gcf().set_figwidth(float(width))
        if height:
            pyplot.gcf().set_figheight(float(height))

        pyplot.savefig(
            image_file_path, dpi=96, pad_inches=0, transparent=False
        )

        pyplot.close()
        super(MatPlot, self).__init__(
            filepath=image_file_path, description=description
        )


class Plotly(Attachment):
    def __init__(self, fig, data_file_path, style=None, description=None):
        import plotly.io

        fig_json = plotly.io.to_json(fig)
        pathlib.Path(data_file_path).resolve().parent.mkdir(
            parents=True, exist_ok=True
        )
        with open(data_file_path, "w") as f:
            f.write(fig_json)

        super(Plotly, self).__init__(
            filepath=data_file_path, description=description
        )
        self.style = style


class Directory(BaseEntry):
    """
    Entry representing a bunch of files under a directory which will be
    attached to the report.
    """

    def __init__(
        self,
        dirpath,
        description=None,
        ignore=None,
        only=None,
        recursive=False,
        dst_path=None,
        scratch_path=None,
    ):

        self.source_path = dirpath
        self.ignore = ignore
        self.only = only
        self.recursive = recursive
        self.dst_path = (
            dst_path
            or hashlib.md5(self.source_path.encode("utf-8")).hexdigest()
        )
        self.file_list = traverse_dir(
            self.source_path,
            topdown=True,
            ignore=ignore,
            only=only,
            recursive=recursive,
            include_subdir=False,
        )

        if scratch_path:
            # will best effort make a copy of the file
            for fpath in self.file_list:
                src_path = os.path.join(self.source_path, fpath)
                dst_path = os.path.join(scratch_path, self.dst_path, fpath)
                makedirs(os.path.dirname(dst_path))
                try:
                    shutil.copyfile(src_path, dst_path)
                except Exception:
                    break
            else:
                self.source_path = os.path.join(scratch_path, self.dst_path)

        super(Directory, self).__init__(description=description)


class CodeLog(BaseEntry):
    """Save source code to the report."""

    def __init__(self, code, language="python", description=None):
        if isinstance(code, str):
            self.code = code
        elif isinstance(code, bytes):
            self.code = code.decode()
        else:
            raise TypeError("Code must be a string")
        self.language = language
        super(CodeLog, self).__init__(description=description)


class Markdown(BaseEntry):
    """Save markdown to the report."""

    def __init__(self, message, description=None, escape=True):
        if isinstance(message, str):
            self.message = message
        elif isinstance(message, bytes):
            self.message = message.decode()
        else:
            raise ValueError("Message must be a string")
        self.escape = escape

        super(Markdown, self).__init__(description=description)


class FlowChart(BaseEntry):
    """Log a flowchart object that consists of nodes and edges to the report"""

    def __init__(self, nodes: list, edges: list, description=None):
        self.nodes = nodes
        self.edges = edges
        super().__init__(description=description)
