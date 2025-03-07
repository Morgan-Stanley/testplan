"""
We'd like to use python's logging interface when we log messages through Report
objects. The most lightweight way to do it is to use a `logging.LoggingAdapter`
which is a thin wrapper around a `logging.Logger`.

We can then use a global mapping and a custom handler to append log messages
to the report object's `logs` list.
"""
import logging
import datetime
import weakref

from datetime import timezone
from testplan.common.utils import strings

LOGGER = logging.getLogger(__name__)

REPORT_MAP = weakref.WeakValueDictionary()


class ReportLogHandler(logging.Handler):
    """
    Log handler that uses the global report map for appending log messages to
    report objects.
    """

    def emit(self, record):
        if hasattr(record, "report_obj_id"):
            report = REPORT_MAP.get(record.report_obj_id)
            if report is not None:
                created = datetime.datetime.fromtimestamp(
                    record.created
                ).astimezone()
                report.logs.append(
                    {
                        "message": self.format(record),
                        "levelname": record.levelname,
                        "levelno": record.levelno,
                        "created": created,
                        "funcName": record.funcName,
                        "lineno": record.lineno,
                        "uid": strings.uuid4(),
                    }
                )


LOGGER.addHandler(ReportLogHandler())
LOGGER.propagate = False


def create_logging_adapter(report):
    """
    Create a new adapter and bind the report to global `REPORT_MAP` so handler
    can access it.
    """

    obj_id = id(report)

    if REPORT_MAP.get(obj_id) is None:
        REPORT_MAP[obj_id] = report

    return logging.LoggerAdapter(LOGGER, {"report_obj_id": obj_id})
