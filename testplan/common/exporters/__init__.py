"""TODO."""
import traceback

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from testplan.common.config import Config, Configurable
from testplan.common.utils import strings
from testplan.common.utils.comparison import is_regex
from testplan.common.utils.timing import now
from testplan.report import TestReport


@dataclass
class ExporterResult:
    exporter: "BaseExporter"
    result: Dict = None
    traceback: str = None
    uid: str = strings.uuid4()
    start_time: datetime = now()
    end_time: datetime = None

    @property
    def success(self) -> bool:
        return not self.traceback

    @classmethod
    def run_exporter(self, exporter, source, type):
        "Putting this back for compatibility reasons"

        result = run_exporter(
            exporter=exporter,
            source=source,
            export_context=None,
        )
        return result


@dataclass
class ExportContext:
    """Dataclass for storing information about exporters."""

    results: List[ExporterResult] = field(default_factory=list)


class ExporterConfig(Config):
    """
    Configuration object for
    :py:class:`BaseExporter <testplan.common.exporters.BaseExporter>` object.
    """

    @classmethod
    def get_options(cls):
        return {"name": str}


class BaseExporter(Configurable):
    """Base exporter class."""

    CONFIG = ExporterConfig

    def __init__(self, name=None, **options):
        if name is None:
            name = self.__class__.__name__
        self._cfg = self.CONFIG(name=name, **options)
        super().__init__()

    def __str__(self):
        return f"{self.__class__.__name__}[{self.name}]"

    @property
    def name(self):
        return self.cfg.name

    @property
    def cfg(self):
        """Exporter configuration."""
        return self._cfg

    def export(
        self,
        source: TestReport,
        export_context: ExportContext,
    ) -> Optional[Dict]:
        """
        Pseudo export function.

        :param: source: Testplan report export
        :param: export_context: information about other exporters
        :return: dictionary containing the possible output
        """
        raise NotImplementedError("Exporter must define export().")


def verify_export_context(
    exporter: BaseExporter, export_context: Optional[ExportContext]
) -> ExportContext:
    """
    Verifies whether export context is present and creates an empty one if not.

    :param: exporter: actual exporter being run
    :param: export_context: information about other exporters
    :return: ExportContext object containing information about exporters
    """

    # TODO: Remove this function after the grace period
    if export_context is None:
        exporter.logger.warning(
            (
                "Exporter '%s' does not have keyword_argument 'export_context'! "
                "This will be prohibited in the future, please modify your custom exporter!"
            ),
            exporter,
        )
        return ExportContext()
    else:
        return export_context


def run_exporter(
    exporter: BaseExporter,
    source: TestReport,
    export_context: ExportContext,
) -> ExporterResult:
    """
    Wraps an exporter run and handles exceptions.

    :param exporter: exporter to run
    :param source: Testplan report to export
    :param export_context: ExportContext object for storing information about other exporters
    """

    exp_result = ExporterResult(exporter=exporter)
    result = None
    try:
        result = exporter.export(
            source=source,
            export_context=export_context,
        )
    except TypeError:
        # TODO: Remove this except section after the grace period
        exporter.logger.warning(
            (
                "Exporter '%s' does not have keyword_argument 'export_context'! "
                "This will be prohibited in the future, please modify your custom exporter!"
            ),
            exporter,
        )
        try:
            result = exporter.export(source)
        except Exception:
            exp_result.traceback = traceback.format_exc()
    except Exception:
        exp_result.traceback = traceback.format_exc()
    finally:
        exp_result.end_time = now()
        if not exp_result.success:
            exporter.logger.error(exp_result.traceback)
        if result:
            if not isinstance(result, dict):
                # TODO: Remove this block after the grace period
                # We have output but in the wrong format
                exporter.logger.warning(
                    (
                        "Exporter '%s' does not return with a dictionary object! "
                        "This will be prohibited in the future, please modify your custom exporter!"
                    ),
                    exporter,
                )
                exp_result.result = {"unknown": exp_result}
            else:
                exp_result.result = result
        export_context.results.append(exp_result)
        return exp_result


def format_cell_data(data, limit):
    """
    Change the str representation of values in data if they represent regex or
    lambda functions. Also limit the length of these strings.

    :param data: List of values to be formatted.
    :type data: ``list``
    :param limit: The number of characters allowed in each string.
    :type limit: ``int``
    :return: List of formatted and limited strings.
    :rtype: ``list``
    """
    for i, value in enumerate(data):
        if is_regex(value):
            data[i] = "REGEX('{}')".format(value.pattern)
        elif "lambda" in str(value):
            data[i] = "<lambda>"

    return _limit_cell_length(data, limit)


def _limit_cell_length(iterable, limit):
    """
    Limit the length of each string in the iterable.

    :param iterable: iterable object containing string values.
    :type iterable: ``list`` or ``tuple`` etc.
    :param limit: The number of characters allowed in each string
    :type limit: ``int``
    :return: The list of limited strings.
    :rtype: ``list`` of ``str``
    """
    return [
        val if len(str(val)) < limit else "{}...".format(str(val)[: limit - 3])
        for val in iterable
    ]
