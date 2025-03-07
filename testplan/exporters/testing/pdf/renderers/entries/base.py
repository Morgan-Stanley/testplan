""" TODO """
import pprint

from PIL import Image as pil_image
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import Image
from testplan.common.exporters.pdf import (
    RowStyle,
    create_table,
    format_table_style,
    split_text,
)
from testplan.common.utils.convert import delta_decode_level
from testplan.common.utils.registry import Registry
from testplan.exporters.testing.pdf.renderers.base import SlicedParagraph
from testplan.testing.multitest.entries import base

from .. import constants
from ..base import BaseRowRenderer, RowData
from .baseUtils import export_plot_to_image, format_image, get_matlib_plot


class SerializedEntryRegistry(Registry):
    """
    Registry that is used for binding assertion classes to PDF renderers.

    Keep in mind that we pass around serialized version of assertion objects
    (generated via `multitest.entries.schemas`) meaning that lookup
    arguments will be dictionary representation instead of assertion object
    instances, hence the need to use class names instead of class objects
    for `data` keys.
    """

    def get_record_key(self, obj):
        return obj.__name__

    def get_lookup_key(self, obj):
        return obj["type"]

    def get_category(self, obj):
        return obj["meta_type"]


registry = SerializedEntryRegistry()


@registry.bind_default()
class SerializedEntryRenderer(BaseRowRenderer):
    """Default fallback for all serialized entries."""

    def get_header(self, source, depth, row_idx):
        """Display the description or type as the header."""
        styles = [
            RowStyle(
                font=(constants.FONT, constants.FONT_SIZE_SMALL),
                left_padding=constants.INDENT * depth,
            )
        ]
        header = split_text(
            source["description"] or source["type"],
            constants.FONT,
            constants.FONT_SIZE_SMALL,
            constants.PAGE_WIDTH - (depth * constants.INDENT),
        )
        return RowData(
            content=[header, "", "", ""], style=styles, start=row_idx
        )

    def get_row_content(self, source):
        """
        All entries will either have a description or type,
        we display whatever is available.
        """
        return [source["description"] or source["type"], "", "", ""]

    def get_row_data(self, source, depth, row_idx):
        """
        Most entries will be rendered as single rows, so we use
        `get_row_content` and `get_row_style` for simplicity.
        """
        result = RowData(
            content=self.get_row_content(source),
            style=self.get_row_style(source, depth),
            start=row_idx,
        )
        return result

    def get_row_style(self, source, depth, **kwargs):
        """Default styling for all serialized entries, with small font size."""
        return RowStyle(
            font=(constants.FONT, constants.FONT_SIZE_SMALL),
            left_padding=constants.INDENT * depth,
            **kwargs
        )

    def get_style(self, source):
        if "passed" in source and source["passed"] is False:
            return self.style.failing
        return self.style.passing

    def should_display(self, source):
        return self.get_style(source).display_assertion


@registry.bind(base.Log)
class LogRenderer(SerializedEntryRenderer):
    def get_header(self, source, depth, row_idx):
        """
        Display the description or the log message (if no description) as
        the header.
        """
        styles = [
            RowStyle(
                font=(constants.FONT, constants.FONT_SIZE_SMALL),
                left_padding=constants.INDENT * depth,
                span=(),
            )
        ]
        # log assertion is guaranteed to have description field
        header = source["description"]

        return RowData(
            content=[header, "", "", ""], style=styles, start=row_idx
        )

    def get_row_data(self, source, depth, row_idx):
        """
        Create a header and a detailed log message, only create a head if
        should display a string message without the description.
        """
        header = self.get_header(source, depth, row_idx)

        log_msg = (
            str(source["message"])
            if isinstance(source["message"], str)
            else pprint.pformat(source["message"], depth=6)
        )
        left_padding = constants.INDENT * (depth + 1)

        for para in SlicedParagraph(
            parts=(log_msg, "{}"),
            width=constants.PAGE_WIDTH - left_padding - 6,
        ):
            header = header + RowData(
                content=[para, "", "", ""],
                style=[RowStyle(left_padding=left_padding, span=tuple())],
                start=header.end,
            )

        return header


@registry.bind(base.Attachment)
class AttachmentRenderer(SerializedEntryRenderer):
    """Render an assertion of attaching file from a serialized entry."""

    def get_row_data(self, source, depth, row_idx):
        """Display path of attached file."""
        header = self.get_header(source, depth, row_idx)
        row_idx += 1

        return header + RowData(
            content=[source["source_path"], "", "", ""],
            style=[
                RowStyle(
                    font=(constants.FONT, constants.FONT_SIZE_SMALL),
                    left_padding=constants.INDENT * (depth + 1),
                    text_color=colors.black,
                )
            ],
            start=row_idx,
        )


@registry.bind(base.MatPlot)
class MatPlotRenderer(SerializedEntryRenderer):
    """Render a Matplotlib assertion from a serialized entry."""

    def get_row_data(self, source, depth, row_idx):
        """
        Load the Matplotlib graph from the saved image, set its height and width
        and add it to the row.
        """
        header = self.get_header(source, depth, row_idx)
        styles = [
            RowStyle(
                font=(constants.FONT, constants.FONT_SIZE_SMALL),
                left_padding=constants.INDENT * (depth + 1),
                text_color=colors.black,
            )
        ]

        p_img = pil_image.open(source["source_path"])
        dpi_w, dpi_h = p_img.info["dpi"]

        width = p_img.width / dpi_w * inch
        height = p_img.height / dpi_h * inch
        img = Image(source["source_path"], width, height)

        return header + RowData(
            content=[img, "", "", ""],
            start=header.end,
            style=styles,
        )


@registry.bind(base.Plotly)
class PlotlyRenderer(SerializedEntryRenderer):
    """Render a Plotly assertion from a serialized entry."""

    def get_row_data(self, source, depth, row_idx):
        # TODO Add PDF render
        # https://plotly.com/python/static-image-export/
        # require kaleido which not support rhel6
        return super(PlotlyRenderer, self).get_row_data(source, depth, row_idx)

        #
        # header = self.get_header(source, depth, row_idx)
        # styles = [
        #     RowStyle(
        #         font=(constants.FONT, constants.FONT_SIZE_SMALL),
        #         left_padding=constants.INDENT * (depth + 1),
        #         text_color=colors.black,
        #     )
        # ]
        #
        # fig = plotly.io.read_json(source["source_path"])
        #
        # img_file = str(pathlib.Path(source["source_path"]).with_suffix(".jpg"))
        # plotly.io.write_image(fig, img_file)
        # p_img = pil_image.open(img_file)
        # dpi_w, dpi_h = p_img.info["dpi"]
        #
        # width = p_img.width / dpi_w * inch
        # height = p_img.height / dpi_h * inch
        #
        # img = Image(img_file, width, height)
        #
        # return header + RowData(
        #     content=[img, "", "", ""],
        #     start=header.end,
        #     style=styles,
        # )


@registry.bind(base.Directory)
class DirectoryRenderer(SerializedEntryRenderer):
    """Render an assertion of attaching directory from a serialized entry."""

    def get_row_data(self, source, depth, row_idx):
        """Display path of attached directory."""
        header = self.get_header(source, depth, row_idx)
        row_idx += 1

        header += RowData(
            content=[source["source_path"], "", "", ""],
            style=[
                RowStyle(
                    font=(constants.FONT, constants.FONT_SIZE_SMALL),
                    left_padding=constants.INDENT * (depth + 1),
                    text_color=colors.black,
                )
            ],
            start=row_idx,
        )
        row_idx += 1

        for idx, fpath in enumerate(source["file_list"]):
            header += RowData(
                content=[fpath, "", "", ""],
                style=[
                    RowStyle(
                        font=(constants.FONT, constants.FONT_SIZE_SMALL),
                        left_padding=constants.INDENT * (depth + 2),
                        text_color=colors.black,
                    )
                ],
                start=row_idx + idx,
            )

        return header


@registry.bind(base.TableLog)
class TableLogRenderer(SerializedEntryRenderer):
    """Render a Table from a serialized entry."""

    def get_row_data(self, source, depth, row_idx):
        """
        Reformat the rows from the serialized data into a format ReportLab
        accepts. Create a header and a ReportLab table and add it to the row.
        """
        header = self.get_header(source, depth, row_idx)
        row_style = [RowStyle(left_padding=constants.INDENT * (depth + 1))]
        table_style = format_table_style(constants.DISPLAYED_TABLE_STYLE)

        max_width = constants.PAGE_WIDTH - (depth * constants.INDENT)
        table = create_table(
            table=source["table"],
            columns=source["columns"],
            row_indices=list(range(len(source["table"]))),
            display_index=source["display_index"],
            max_width=max_width,
            style=table_style,
        )

        return header + RowData(
            content=table, start=header.end, style=row_style
        )


@registry.bind(base.DictLog, base.FixLog)
class DictLogRenderer(SerializedEntryRenderer):
    """Render a mapping object from a serialized entry."""

    def get_row_data(self, source, depth, row_idx):
        """
        Reformat the rows from the serialized data into a format ReportLab
        accepts. Create a header and rows of flattened mapping object.
        """
        header = self.get_header(source, depth, row_idx)
        row_idx += 1
        flattened_dict = delta_decode_level(source["flattened_dict"])

        if len(flattened_dict) == 0:
            return header + RowData(
                content=["(empty)", "", "", ""],
                style=[
                    RowStyle(
                        text_color=colors.black,
                        font=(constants.FONT, constants.FONT_SIZE_SMALL),
                        left_padding=constants.INDENT * (depth + 1),
                    )
                ],
                start=row_idx,
            )

        for idx, row in enumerate(flattened_dict):
            offset, key, val = row
            header += RowData(
                content=[
                    key,
                    "<{}> {}".format(val[0], val[1])
                    if isinstance(val, (tuple, list))
                    else "",
                    "",
                    "",
                ],
                style=[
                    RowStyle(
                        text_color=colors.black,
                        font=(constants.FONT, constants.FONT_SIZE_SMALL),
                        left_padding=constants.INDENT * (depth + offset + 1),
                    )
                ],
                start=row_idx + idx,
            )

        return header


@registry.bind(base.Graph)
class GraphRenderer(SerializedEntryRenderer):
    def get_row_data(self, source, depth, row_idx):
        """
        Load the graph as a static image using MatPlotLib
        """
        header = self.get_header(source, depth, row_idx)
        styles = [
            RowStyle(
                font=(constants.FONT, constants.FONT_SIZE_SMALL),
                left_padding=20,
                text_color=colors.black,
            )
        ]

        graph_plot = get_matlib_plot(source)

        if graph_plot is None:
            image = "Unable to render " + source["graph_type"]
            return header + RowData(
                content=image, start=header.end, style=styles
            )
        else:
            image = export_plot_to_image(graph_plot)
            image = format_image(image)

        # graph_plot must be cleared for next graph to render correctly
        graph_plot.clf()
        graph_plot.cla()
        graph_plot.close()

        return header + RowData(
            content=[image, "", "", ""], start=header.end, style=styles
        )
