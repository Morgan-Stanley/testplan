"""Executor base classes."""

import threading

from collections import OrderedDict
from typing import List

from testplan.common.config import ConfigOption
from testplan.common.entity import Resource, ResourceConfig
from testplan.common.utils.thread import interruptible_join


class ExecutorConfig(ResourceConfig):
    """
    Configuration object for
    :py:class:`Executor <testplan.runners.base.Executor>` resource.

    Inherits all
    :py:class:`~testplan.common.entity.base.ResourceConfig`
    options.
    """


class Executor(Resource):
    """
    Receives items, executes them and create results.

    Subclasses must implement the ``Executor._loop`` and
    ``Executor._execute`` logic to execute the input items.
    """

    CONFIG = ExecutorConfig
    _STOP_TIMEOUT = 10

    def __init__(self, **options):
        super(Executor, self).__init__(**options)
        self._loop_handler = None
        self._input = OrderedDict()
        self._results = OrderedDict()
        self.ongoing = []

    @property
    def name(self):
        return self.__class__.__name__

    @property
    def results(self):
        """Items results."""
        return self._results

    @property
    def added_items(self):
        """Returns added items."""
        return self._input

    def added_item(self, uid):
        """Returns the added item."""
        return self._input[uid]

    def add(self, item, uid):
        """
        Adds an item for execution.

        :param item: To be executed and create a result.
        :type item: ``object``
        :param uid: Unique id.
        :type uid: ``str``
        """
        if self.active:
            self._input[uid] = item
            # `NoRunpathPool` adds item after calling `_prepopulate_runnables`
            # so the following step is still needed
            if uid not in self.ongoing:
                self.ongoing.append(uid)

    def get(self, uid):
        """Get item result by uid."""
        return self._results[uid]

    def _loop(self):
        raise NotImplementedError()

    def _execute(self, uid):
        raise NotImplementedError()

    def _prepopulate_runnables(self):
        # If we are to apply test_sorter, it would be here
        # but it's not easy to implement a reasonable behavior
        # as _input could be a mixture of runnable/task/callable
        self.ongoing = list(self._input.keys())

    def starting(self):
        """Starts the execution loop."""
        self._prepopulate_runnables()
        self._loop_handler = threading.Thread(target=self._loop)
        self._loop_handler.daemon = True
        self._loop_handler.start()

    def stopping(self):
        """Stop the executor."""
        if self._loop_handler:
            interruptible_join(self._loop_handler, timeout=self._STOP_TIMEOUT)

    def abort_dependencies(self):
        """Abort items running before aborting self."""
        for uid in self.ongoing:
            yield self._input[uid]

    @property
    def is_alive(self):
        """Poll the loop handler thread to check it is running as expected."""
        if self._loop_handler:
            return self._loop_handler.is_alive()
        else:
            return False

    def pending_work(self):
        """Resource has pending work."""
        return len(self.ongoing) > 0

    def get_current_status(self) -> List[str]:
        """
        Get current status of Executor. Subclasses can override this method and
        implement a well suited method to get their current status.
        """
        msgs = []
        if self.added_items:
            msgs.append(f"{self.name} {self.cfg.name} added items:")
            for item in self.added_items:
                msgs.append(f"\t{item}")
        else:
            msgs.append(f"No added items in {self.name}")

        if self.ongoing:
            msgs.append(f"{self.name} {self.cfg.name} pending items:")
            for item in self.ongoing:
                msgs.append(f"\t{item}")
        else:
            msgs.append(f"No pending items in {self.name}")

        return msgs
