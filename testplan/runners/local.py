"""Basic local executor."""
import threading
import time
from typing import List

from testplan.common.utils import selector
from testplan.report import ReportCategories, Status, TestGroupReport
from testplan.runners.base import Executor
from testplan.runners.pools import tasks
from testplan.testing.base import Test, TestResult


class LocalRunner(Executor):
    """
    Basic local execution that inherits
    :py:class:`Executor <testplan.runners.base.Executor>`
    and accepts all
    :py:class:`ExecutorConfig <testplan.runners.base.ExecutorConfig>`
    options.
    """

    def __init__(self, uid="local_runner", **options) -> None:
        super(LocalRunner, self).__init__(**options)
        self._uid = uid

        # ``_loop`` & ``discard_pending_tasks`` are triggered in different
        # threads
        self._curr_runnable_lock = threading.Lock()
        self._curr_runnable = None

    def execute(self, uid: str) -> TestResult:
        """Execute item implementation."""
        # First retrieve the input from its UID.
        target = self._input[uid]

        if self._discard_pending:
            # to skip materialize, should be disposed immediately
            return TestResult()

        with self._curr_runnable_lock:
            # Inspect the input type. Tasks must be materialized before
            # they can be run.
            if isinstance(target, Test):
                runnable = target
            elif isinstance(target, tasks.Task):
                runnable = target.materialize()
            elif callable(target):
                runnable = target()
            else:
                raise TypeError(
                    f"Cannot execute target of type {type(target)}"
                )

            if not isinstance(runnable, Test):
                raise TypeError(
                    f"Cannot execute target of type {type(runnable)}"
                )
            if not runnable.parent:
                runnable.parent = self
                runnable.cfg.parent = self.cfg
            self._curr_runnable = runnable

        result = self._curr_runnable.run()

        with self._curr_runnable_lock:
            self._curr_runnable = None

        return result

    def _loop(self) -> None:
        """Execution loop implementation for local runner."""
        while self.active:
            if self.status == self.status.STARTING:
                self.status.change(self.status.STARTED)
            elif self.status == self.status.STARTED:
                try:
                    next_uid = self.ongoing[0]
                except IndexError:
                    pass
                else:
                    try:
                        result = self.execute(next_uid)
                    except Exception as exc:
                        result = TestResult()
                        result.report = TestGroupReport(
                            name=next_uid, category=ReportCategories.ERROR
                        )
                        result.report.status_override = Status.ERROR
                        result.report.logger.exception(
                            "Exception for %s on %s execution: %s",
                            next_uid,
                            self,
                            exc,
                        )
                    finally:
                        with self._curr_runnable_lock:
                            if not self._discard_pending:
                                # otherwise result from aborted test is used
                                self._results[next_uid] = result
                                self.ongoing.pop(0)

                    if self.cfg.skip_strategy.should_skip_rest_tests(
                        result.report.status
                    ):
                        self.bubble_up_discard_tasks(
                            selector.Not(selector.Eq(self.uid())),
                            report_reason="per skip strategy",
                        )
                        self.discard_pending_tasks(
                            report_reason="per skip strategy"
                        )

            elif self.status == self.status.STOPPING:
                self.status.change(self.status.STOPPED)
                return
            time.sleep(self.cfg.active_loop_sleep)

    def starting(self) -> None:
        """Starting the local runner."""
        if self.parent:
            self._runpath = self.parent.runpath
        super(LocalRunner, self).starting()  # start the loop
        self.status.change(self.status.STARTED)  # Start is async

    def stopping(self) -> None:
        """Stopping the local runner."""
        super(LocalRunner, self).stopping()  # stop the loop
        self.status.change(self.status.STOPPED)  # Stop is async

    def aborting(self) -> None:
        """Aborting logic."""
        self.discard_pending_tasks(
            report_status=Status.INCOMPLETE,
            report_reason=f"due to {self} aborted",
        )

    def discard_pending_tasks(
        self,
        report_status: Status = Status.INCOMPLETE,
        report_reason: str = "",
    ):
        with self._curr_runnable_lock:
            self._discard_pending = True
            if self._curr_runnable:
                self._curr_runnable.abort()

            self.logger.warning("Discard pending tasks of %s.", self)
            while self.ongoing:
                uid = self.ongoing.pop(0)
                try:
                    result = self.added_items[uid].result
                    result.report.status_override = report_status
                except (KeyError, AttributeError):
                    result = TestResult()
                    result.report = TestGroupReport(
                        name=uid,
                        category=ReportCategories.ERROR,
                    )
                    result.report.status_override = report_status
                else:
                    result.report.logger.warning(
                        "Test[%s] discarded%s.",
                        uid,
                        " " + report_reason if report_reason else "",
                    )
                    self._results[uid] = result

                if report_reason:
                    self.logger.warning(
                        "Discarding Test[%s] %s.", uid, report_reason
                    )

    def get_current_status_for_debug(self) -> List[str]:
        """
        Get current status of ``LocalRunner`` for debugging.

        :return: Status of ``LocalRunner``.
        :rtype: ``List[str]``
        """
        msgs = [f"{self.class_name} status: {self.status.tag}"]
        msgs.extend(super().get_current_status_for_debug())
        return msgs
