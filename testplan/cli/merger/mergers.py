"""
Implements test report combiners.
"""
from typing import Iterable

from testplan.report import TestReport


# TODO: as of current implementation "_heading" depends on "merge" (linebreak)
#       which reduces this to a single function in principle
class SimpleCombiner:
    """
    Combiner class that puts test reports next to each other under a testplan.
    """

    RESULT_DESCRIPTION_HEADER = "Merged report"

    @staticmethod
    def _heading(text: str, underline_char: str = "="):
        """
        Generates header components from header text, underline, and linebreak.

        :param text: header text
        :param underline_char: character to use for underlining header text
        """
        # The empty string is to be used in a "\n".join(...) and serves as a
        # linebreak
        return [text, underline_char * len(text), ""]

    def merge(self, reports: Iterable[TestReport]) -> TestReport:
        """
        Merges reports in a single test plan.

        :param reports: testplan reports to merge
        """
        result = TestReport(name="Combined Report")

        description = self._heading(self.RESULT_DESCRIPTION_HEADER)

        for report in reports:
            result.attachments.update(report.attachments)
            result.extend(report.entries)
            result.logs.extend(report.logs)

            result.information.extend(report.information)
            description.extend(self._heading(report.name))
            if report.description:
                description.append(f"{report.description}\n")

            # TODO: what to do with meta, tags_index
            # TODO: timer & timezone
        result.description = "\n".join(description)

        return result
