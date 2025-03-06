"""
Module containing base classes that represent object entities that can accept
configuration, start/stop/run/abort, create results and have some state.
"""

import os
import signal
import sys
import threading
import time
import traceback
from collections import OrderedDict, deque
from contextlib import suppress
from typing import (
    Any,
    Callable,
    Deque,
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
    Union,
)

import psutil
from schema import Or

from testplan.common.config import Config, ConfigOption
from testplan.common.report import Status
from testplan.common.utils import logger
from testplan.common.utils.path import default_runpath, makedirs, makeemptydirs
from testplan.common.utils.strings import slugify, uuid4
from testplan.common.utils.thread import execute_as_thread, interruptible_join
from testplan.common.utils.timing import wait, Timer
from testplan.common.utils.validation import is_subclass


class ReportLink:
    """
    A recursive linkage that will be available to all Entity object.
    """

    def __init__(self, name: str):
        self.name = name
        self.timer = Timer()
        self.children: List["ReportLink"] = []


class Environment:
    """
    A collection of resources that can be started/stopped.

    :param parent: Reference to parent object.
    :type parent: :py:class:`Entity <testplan.common.entity.base.Entity>`
    """

    def __init__(self, parent: Optional["Entity"] = None):
        self.__dict__["parent"] = parent
        self.__dict__["_initial_context"] = {}
        self.__dict__["_resources"] = OrderedDict()
        self.__dict__["start_exceptions"] = OrderedDict()
        self.__dict__["stop_exceptions"] = OrderedDict()

    def add(self, item: "Resource", uid: Optional[str] = None) -> str:
        """
        Adds a :py:class:`Resource <testplan.common.entity.base.Resource>` to
        the Environment.

        :param item: Resource to be added.
        :type item: :py:class:`Resource <testplan.common.entity.base.Resource>`
        :param uid: Unique identifier.
        :type uid: ``str`` or ``NoneType``
        :return: Unique identifier assigned to item added.
        :rtype: ``str``
        """
        if uid is None:
            uid = item.uid()
        if uid in dir(self):
            raise ValueError(
                f'Identifier "{uid}" is reserved and cannot be used as UID.'
            )
        if uid in self._resources:
            raise RuntimeError(f'Uid "{uid}" already in environment.')

        item.context = self
        self._resources[uid] = item
        return uid

    def remove(self, uid: str) -> None:
        """
        Removes resource with the given uid from the environment.

        :param uid: Unique identifier.
        """
        del self._resources[uid]

    def first(self) -> str:
        """
        Returns the UID of the first resource of the environment.
        """
        return next(uid for uid in self._resources.keys())

    def get(self, key: str, default=None) -> "Resource":
        # For compatibility reason, acts like a dictionary which has
        # a `get` method that returns `None` if no attribute found.
        try:
            return self.__getitem__(key)
        except AttributeError:
            return default

    def __getattr__(self, name: str) -> "Resource":
        resources = self.__getattribute__("_resources")
        initial_context = self.__getattribute__("_initial_context")

        if name in resources:
            return resources[name]

        if name in initial_context:
            return initial_context[name]

        raise AttributeError(
            f'"{self.__class__.__name__}" object has no attribute "{name}"'
        )

    def __setattr__(self, name, value):
        if name in self.__dict__:
            self.__dict__[name] = value
        elif name in self.__getattribute__("_resources"):
            raise RuntimeError(
                f'Cannot modify resource "{name}" in environment.'
            )
        elif name in self.__getattribute__("_initial_context"):
            raise RuntimeError(
                f'Cannot modify attribute "{name}" in initial context.'
            )
        else:
            super(Environment, self).__setattr__(name, value)

    def __getitem__(self, item):
        return self.__getattr__(item)

    def __contains__(self, item):
        if item in self.__getattribute__(
            "_resources"
        ) or item in self.__getattribute__("_initial_context"):
            return True
        else:
            return False

    def __iter__(self) -> Iterator["Resource"]:
        return iter(self._resources.values())

    def __repr__(self):
        initial = {key: val for key, val in self._initial_context.items()}
        res = {key: val for key, val in self._resources.items()}
        initial.update(res)
        return f"{self.__class__.__name__}[{initial}]"

    def __len__(self):
        return len(self._resources)

    def items(self):
        return self._resources.items()

    def all_status(self, target) -> bool:
        """
        Checks whether all resources have target status.

        :param target: expected status
        :type target: ``str``
        """
        return all(
            self._resources[resource].status == target
            for resource in self._resources
        )

    def _record_resource_exception(self, message, resource, msg_store):
        fetch_msg = "\n".join(resource.fetch_error_log())

        msg = message.format(
            resource=resource,
            traceback_exc=traceback.format_exc(),
            fetch_msg=fetch_msg,
        )
        resource.logger.error(msg)
        msg_store[resource] = "ERROR: " + msg

    def start(self):
        """
        Starts all resources sequentially and log errors.
        """
        # Trigger start all resources
        resources_to_wait_for: List[Resource] = []
        for resource in self._resources.values():
            if not resource.auto_start:
                continue

            try:
                resource.start()
            except Exception:
                self._record_resource_exception(
                    message="While starting resource {resource}:\n"
                    "{traceback_exc}\n{fetch_msg}",
                    resource=resource,
                    msg_store=self.start_exceptions,
                )

                failover = resource.failover()
                if failover:
                    self._resources[resource.uid()] = failover
                else:
                    # Environment start failure. Won't start the rest.
                    break
            else:
                if resource.async_start:
                    resources_to_wait_for.append(resource)

        # Wait resources status to be STARTED.
        for resource in resources_to_wait_for:
            try:
                resource.wait(resource.STATUS.STARTED)
            except Exception:
                self._record_resource_exception(
                    message="While waiting for resource {resource} to start:\n"
                    "{traceback_exc}\n{fetch_msg}",
                    resource=resource,
                    msg_store=self.start_exceptions,
                )

                failover = resource.failover()
                if failover:
                    self._resources[resource.uid()] = failover
                else:
                    pass

            else:
                resource.logger.info("%s started", resource)

    def start_in_pool(self, pool):
        """
        Start all resources concurrently in thread pool.

        :param pool: thread pool
        :type pool: ``ThreadPool``
        """

        for resource in self._resources.values():
            if not resource.async_start:
                raise RuntimeError(
                    f"Cannot start resource {resource} in thread pool,"
                    " its `async_start` attribute is set to False"
                )

        # Trigger start all resources
        resources_to_wait_for = []
        for resource in self._resources.values():
            if not resource.auto_start:
                continue

            pool.apply_async(
                self._log_exception(
                    resource, resource.start, self.start_exceptions
                )
            )
            resources_to_wait_for.append(resource)

        # Wait resources status to be STARTED.
        for resource in resources_to_wait_for:
            if resource not in self.start_exceptions:
                resource.wait(resource.STATUS.STARTED)
                resource.logger.info("%s started", resource)

    def sync_stop_resource(self, resource: "Resource"):
        """
        Stop a resource and log exceptions.
        """
        if resource.status in (
            resource.STATUS.STOPPING,
            resource.STATUS.STOPPED,
        ):
            return

        resource.logger.info("Stopping %s", resource)
        try:
            resource.stop()
        except Exception:
            self._record_resource_exception(
                message="While stopping resource {resource}:\n"
                "{traceback_exc}\n{fetch_msg}",
                resource=resource,
                msg_store=self.stop_exceptions,
            )

            # Resource status should be STOPPED even it failed to stop
            resource.force_stop()
        else:
            if resource.async_start:
                resource.wait(resource.STATUS.STOPPED)
        resource.logger.info("%s stopped", resource)

    def stop(self, is_reversed: bool = False):
        """
        Stop all resources, optionally in reverse order, and log exceptions.

        :param is_reversed: flag whether to stop resources in reverse order
        """
        resources: List[Resource] = list(self._resources.values())
        if is_reversed is True:
            resources = resources[::-1]

        # Stop all resources
        resources_to_wait_for: List[Resource] = []
        for resource in resources:
            if resource.status in (
                resource.STATUS.STOPPING,
                resource.STATUS.STOPPED,
            ):
                continue
            try:
                resource.stop()
            except Exception:
                self._record_resource_exception(
                    message="While stopping resource {resource}"
                    ":\n{traceback_exc}\n{fetch_msg}",
                    resource=resource,
                    msg_store=self.stop_exceptions,
                )
                # Resource status should be STOPPED even it failed to stop
                resource.force_stop()
            else:
                if (
                    resource.async_start
                    and resource.status == resource.STATUS.STOPPING
                ):
                    # the 2nd clause to avoid StatusTransitionException: On status change from None to STOPPED
                    resources_to_wait_for.append(resource)

        # Wait resources status to be STOPPED.
        for resource in resources_to_wait_for:
            try:
                resource.wait(resource.STATUS.STOPPED)
            except Exception:
                self._record_resource_exception(
                    message="While waiting for resource {resource} to stop"
                    ":\n{traceback_exc}\n{fetch_msg}",
                    resource=resource,
                    msg_store=self.stop_exceptions,
                )
                # Resource status should be STOPPED even it failed to stop
                resource.force_stop()
            resource.logger.info("%s stopped", resource)

    def stop_in_pool(self, pool, is_reversed=False):
        """
        Stop all resources in reverse order and log exceptions.

        :param pool: thread pool
        :type pool: ``ThreadPool``
        :param is_reversed: flag whether to stop resources in reverse order
        :type is_reversed: ``bool``
        """
        resources = list(self._resources.values())
        if is_reversed is True:
            resources = resources[::-1]

        # Stop all resources
        resources_to_wait_for = []
        for resource in resources:
            if resource.status in (
                resource.STATUS.STOPPING,
                resource.STATUS.STOPPED,
            ):
                continue
            pool.apply_async(
                self._log_exception(
                    resource, resource.stop, self.stop_exceptions
                )
            )
            resources_to_wait_for.append(resource)

        # Wait resources status to be STOPPED.
        for resource in resources_to_wait_for:
            if resource not in self.stop_exceptions:
                if resource.async_start:
                    resource.wait(resource.STATUS.STOPPED)
                else:
                    # avoid post_stop being called twice
                    wait(
                        lambda: resource.status == resource.STATUS.STOPPED,
                        timeout=resource.cfg.status_wait_timeout,
                    )
                resource.logger.info("%s stopped", resource)
            else:
                # Resource status should be STOPPED even it failed to stop
                resource.force_stop()

    def _log_exception(self, resource, func, exception_record):
        """
        Decorator for logging an exception at resource and environment level.

        :param resource: resource to log the exception with
        :type resource: :py:class:`~testplan.common.entity.base.Resource`
        :param func: function to catch exception for
        :type func: ``Callable``
        :param exception_record: A dictionary that maps resource name to
            exception message during start or stop: `self.start_exception`
            for `start()` and `self.stop_exceptions` for `stop()`.
        :type exception_record: ``dict``
        """

        def wrapper(*args, **kargs):
            try:
                func(*args, **kargs)
            except Exception:
                msg = "While executing {} of resource [{}]\n{}".format(
                    func.__name__, resource.cfg.name, traceback.format_exc()
                )
                resource.logger.error(msg)
                exception_record[resource] = msg

        return wrapper

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class StatusTransitionException(Exception):
    """To be raised on illegal state transition attempt."""

    pass


class EntityStatus:
    """
    Represents current status of an
    :py:class:`Entity <testplan.common.entity.base.Entity>` object.

    TODO: Utilise metadata to store information.
    """

    NONE = None
    PAUSING = "PAUSING"
    PAUSED = "PAUSED"
    RESUMING = "RESUMING"

    def __init__(self):
        """
        TODO
        """
        self._current: str = self.NONE
        self._metadata = OrderedDict()
        self._transitions = self.transitions()

    @property
    def tag(self):
        """
        Current status value.
        """
        return self._current

    def __eq__(self, other: Union[None, str, "EntityStatus"]) -> bool:
        if other is None or isinstance(other, str):
            return self._current == other

        return self._current == other._current

    @property
    def metadata(self):
        """
        TODO
        """
        return self._metadata

    def change(self, new):
        """
        Transition to new status.

        :param new: status to be set
        :type new: ``NoneType`` or ``str``
        """
        current = self._current
        try:
            if current == new or new in self._transitions[current]:
                self._current = new
            else:
                msg = f"On status change from {current} to {new}"
                raise StatusTransitionException(msg)
        except KeyError as exc:
            msg = f"On status change from {current} to {new} - {exc}"
            raise StatusTransitionException(msg)

    def reset(self):
        """
        Reset status as None.
        """
        self._current = self.NONE

    def update_metadata(self, **metadata):
        """
        Updates metadata.

        :param metadata: additional metadata
        :type metadata: ``OrderedDict``
        """
        self._metadata.update(metadata)

    def clear_metadata(self):
        """
        Re-initializes metadata as empty.
        """
        self._metadata = OrderedDict()

    def transitions(self):
        """
        Returns all legal transitions of the status of the
        :py:class:`Entity <testplan.common.entity.base.Entity>`.
        """
        return {self.PAUSING: {self.PAUSED}, self.PAUSED: {self.RESUMING}}


class EntityConfig(Config):
    """
    Configuration object for
    :py:class:`Entity <testplan.common.entity.base.Entity>` object.

    All classes that inherit
    :py:class:`Entity <testplan.common.entity.base.Entity>` can define a
    configuration that inherits this one's schema.
    """

    @classmethod
    def get_options(cls):
        """
        Config options for base Entity class.
        """
        return {
            ConfigOption("runpath"): Or(None, str, callable),
            ConfigOption("path_cleanup", default=False): bool,
            ConfigOption("status_wait_timeout", default=600): int,
            ConfigOption("abort_wait_timeout", default=300): int,
            ConfigOption("active_loop_sleep", default=0.005): float,
        }


class Entity(logger.Loggable):
    """
    Base class for :py:class:`Entity <testplan.common.entity.base.Entity>`
    and :py:class:`Resource <testplan.common.entity.base.Resource>` objects
    providing common functionality like runpath creation, abort policy
    and common attributes.

    :param runpath: Path to be used for temp/output files by entity.
    :type runpath: ``str`` or ``NoneType`` callable that returns ``str``
    :param path_cleanup: Remove previous runpath created dirs/files.
    :type path_cleanup: ``bool``
    :param status_wait_timeout: Timeout for wait status events.
    :type status_wait_timeout: ``int``
    :param abort_wait_timeout: Timeout for entity abort.
    :type abort_wait_timeout: ``int``
    :param active_loop_sleep: Sleep time on busy waiting loops.
    :type active_loop_sleep: ``float``
    """

    CONFIG = EntityConfig
    STATUS = EntityStatus

    def __init__(self, **options):
        super(Entity, self).__init__()
        self._cfg = self.__class__.CONFIG(**options)
        self._status = self.__class__.STATUS()
        self._wait_handlers = {}
        self._runpath = None
        self._scratch = None
        self._parent = None
        self._uid = None
        self._should_abort = False
        self._aborted = False
        self._report = None

    def __str__(self):
        return f"{self.__class__.__name__}[{self.uid()}]"

    @property
    def cfg(self):
        """
        Configuration object.
        """
        return self._cfg

    @property
    def status(self):
        """
        Status object.
        """
        return self._status

    @property
    def aborted(self):
        """
        Returns if entity was aborted.
        """
        return self._aborted

    @property
    def active(self):
        """
        Entity not aborting/aborted.
        """
        return self._should_abort is False and self._aborted is False

    @property
    def runpath(self):
        """
        Path to be used for temp/output files by entity.
        """
        return self._runpath

    @property
    def scratch(self):
        """
        Path to be used for temp files by entity.
        """
        return self._scratch

    @property
    def parent(self):
        """
        Returns parent :py:class:`Entity <testplan.common.entity.base.Entity>`.
        """
        return self._parent

    @parent.setter
    def parent(self, value):
        """
        Reference to parent object.
        """
        self._parent = value

    @property
    def report(self):
        """
        A handle to access the report via recursive parent
        """
        if not self._report:
            self._report = ReportLink(name=str(self))
            if self.parent and hasattr(self.parent, "report"):
                # don't always have parent in test
                # ChildLoop doesn't have report
                self.parent.report.children.append(self._report)
            else:
                # will just have a dangling child
                # but the timer won't be collected to report
                self.logger.debug("dangling report")

        return self._report

    @property
    def timer(self):
        return self.report.timer

    def pause(self):
        """
        Pauses entity execution.
        """
        self.status.change(self.STATUS.PAUSING)
        self.pausing()

    def resume(self):
        """
        Resumes entity execution.
        """
        self.status.change(self.STATUS.RESUMING)
        self.resuming()

    def abort(self):
        """
        Default abort policy. First abort all dependencies and then itself.
        """
        if not self.active:
            return

        self._should_abort = True
        for dep in self.abort_dependencies():
            self._abort_entity(dep)

        self.logger.info("Aborting %s", self)
        self.aborting()
        self._aborted = True
        self.report.status_override = Status.INCOMPLETE
        self.logger.info("Aborted %s", self)

    def abort_dependencies(self):
        """
        Returns an empty generator.
        """
        return
        yield

    def _abort_entity(self, entity, wait_timeout=None):
        """
        Method to abort an entity and log exceptions.

        :param entity: entity to abort
        :type entity: :py:class:`Entity <testplan.common.entity.base.Entity>`
        :param wait_timeout: timeout in seconds
        :type wait_timeout: ``int`` or ``NoneType``
        """
        timeout = (
            wait_timeout
            if wait_timeout is not None
            else self.cfg.abort_wait_timeout
        )
        try:
            entity.abort()  # Here entity can be a function and will raise
        except Exception as exc:
            self.logger.error(traceback.format_exc())
            self.logger.error("Exception on aborting %s - %s", entity, exc)
        else:
            if (
                wait(
                    predicate=lambda: entity.aborted is True,
                    timeout=timeout,
                    raise_on_timeout=False,  # continue even if some entity timeout
                )
                is False
            ):
                self.logger.error(
                    "Timeout on waiting to abort %s after %d seconds.",
                    entity,
                    timeout,
                )

    def aborting(self):
        """
        Aborting logic for self.
        """
        self.logger.debug(
            "Abort logic not implemented for {}[{}]".format(
                self.__class__.__name__, self.uid()
            )
        )

    def pausing(self):
        raise NotImplementedError()

    def resuming(self):
        raise NotImplementedError()

    def wait(self, target_status, timeout=None):
        """
        Wait until objects status becomes target status.

        :param target_status: expected status
        :type target_status: ``str``
        :param timeout: timeout in seconds
        :type timeout: ``int`` or ``NoneType``
        """
        timeout = (
            timeout if timeout is not None else self.cfg.status_wait_timeout
        )
        if target_status in self._wait_handlers:
            self._wait_handlers[target_status](timeout=timeout)
        else:
            wait(lambda: self.status == target_status, timeout=timeout)

    def uid(self):
        """
        Unique identifier of self.
        """
        if not self._uid:
            self._uid = uuid4()
        return self._uid

    def define_runpath(self):
        """
        Define runpath directory based on parent object and configuration.
        """
        # local config has highest precedence
        runpath = self.cfg.get_local("runpath")
        if runpath:
            self._runpath = runpath(self) if callable(runpath) else runpath
        # else get container's runpath and append uid
        elif self.parent and self.parent.runpath:
            self._runpath = os.path.join(
                self.parent.runpath, slugify(self.uid())
            )
        else:
            self._runpath = default_runpath(self)

    def make_runpath_dirs(self):
        """
        Creates runpath related directories.
        """
        self.define_runpath()
        if self._runpath is None:
            raise RuntimeError(
                f"{self.__class__.__name__} runpath cannot be None"
            )

        self._scratch = os.path.join(self._runpath, "scratch")

        self.logger.info(
            "%s has %s runpath and pid %d", self, self.runpath, os.getpid()
        )

        if self.cfg.path_cleanup is False:
            makedirs(self._runpath)
            makedirs(self._scratch)
        else:
            makeemptydirs(self._runpath)
            makeemptydirs(self._scratch)

    @classmethod
    def filter_locals(cls, local_vars):
        """
        Filter out init params of None value, they will take default value
        defined in its ConfigOption object; also filter out special vars that
        are not init params from local_vars.

        :param local_vars:
        :type local_vars:
        """
        EXCLUDE = ("cls", "self", "kwargs", "options", "__class__", "__dict__")
        return {
            key: value
            for key, value in local_vars.items()
            if key not in EXCLUDE and value is not None
        }

    def context_input(self, exclude: list = None) -> Dict[str, Any]:
        """All attr of self in a dict for context resolution"""
        ctx = {}
        exclude = exclude or []
        for attr in dir(self):
            if attr in exclude:
                continue
            ctx[attr] = getattr(self, attr)
        return ctx


class RunnableStatus(EntityStatus):
    """
    Status of a
    :py:class:`Runnable <testplan.common.entity.base.Runnable>` entity.
    """

    EXECUTING = "EXECUTING"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    PAUSING = "PAUSING"
    PAUSED = "PAUSED"

    def transitions(self):
        """
        Defines the status transitions of a
        :py:class:`Runnable <testplan.common.entity.base.Runnable>` entity.
        """
        transitions = super(RunnableStatus, self).transitions()
        overrides = {
            self.NONE: {self.RUNNING},
            self.RUNNING: {self.FINISHED, self.EXECUTING, self.PAUSING},
            self.EXECUTING: {self.RUNNING},
            self.PAUSING: {self.PAUSED},
            self.PAUSED: {self.RESUMING},
            self.RESUMING: {self.RUNNING},
            self.FINISHED: {self.RUNNING},
        }
        transitions.update(overrides)
        return transitions


class RunnableConfig(EntityConfig):
    """
    Configuration object for
    :py:class:`~testplan.common.entity.base.Runnable` entity.
    """

    @classmethod
    def get_options(cls):
        """
        Runnable specific config options.
        """
        return {
            # IHandler explicitly enables interactive mode of runnable
            ConfigOption("interactive_port", default=None): Or(None, int),
            ConfigOption("pre_start_environments", default=None): Or(
                None, list
            ),
            ConfigOption(
                "interactive_block",
                default=hasattr(sys.modules["__main__"], "__file__"),
            ): bool,
        }


class RunnableResult:
    """
    Result object of a
    :py:class:`~testplan.common.entity.base.Runnable` entity.
    """

    def __init__(self):
        self.step_results = OrderedDict()
        self.run = False

    def __repr__(self):
        return f"{self.__class__.__name__}[{vars(self)}]"


class Runnable(Entity):
    """
    An object that defines steps, a run method to execute the steps and
    provides results with the
    :py:class:`~testplan.common.entity.base.RunnableResult`
    object.

    It contains an
    :py:class:`~testplan.common.entity.base.Environment`
    object of
    :py:class:`~testplan.common.entity.base.Resource` objects
    that can be started/stopped and utilized by the steps defined.

    :param interactive_port: Enable interactive execution mode on a port.
    :type interactive_port: ``int`` or ``NoneType``
    :param interactive_block: Block on run() on interactive mode.
    :type interactive_block: ``bool``

    Also inherits all
    :py:class:`~testplan.common.entity.base.Entity` options.
    """

    CONFIG = RunnableConfig
    STATUS = RunnableStatus
    RESULT = RunnableResult
    ENVIRONMENT = Environment

    def __init__(self, **options):
        super(Runnable, self).__init__(**options)
        self._environment: Environment = self.__class__.ENVIRONMENT(
            parent=self
        )
        self.result: RunnableResult = self.__class__.RESULT()
        self._steps: Deque[Tuple[Callable, List, Dict]] = deque()
        self._ihandler = None

    @property
    def resources(self) -> Environment:
        """
        Returns the
        :py:class:`Environment <testplan.common.entity.base.Environment>`
        of :py:class:`Resources <testplan.common.entity.base.Resource>`.
        """
        return self._environment

    @property
    def interactive(self):
        return self._ihandler

    # Shortcut for interactive handler
    i = interactive

    def add_resource(self, resource: "Resource", uid: Optional[str] = None):
        """
        Adds a :py:class:`resource <testplan.common.entity.base.Resource>`
        in the runnable environment.

        :param resource: Resource to be added.
        :type resource: Subclass of
            :py:class:`~testplan.common.entity.base.Resource`
        :param uid: Optional input resource uid.
        :type uid: ``str`` or ``NoneType``
        :return: Resource uid assigned.
        :rtype:  ``str``
        """
        resource.parent = self
        resource.cfg.parent = self.cfg
        return self.resources.add(resource, uid=uid or uuid4())

    def _add_step(self, step: Callable, *args, **kwargs):
        """
        Adds a step to the queue.
        """
        self._steps.append((step, args, kwargs))

    def pre_step_call(self, step):
        """
        Callable to be invoked before each step.
        """
        pass

    def skip_step(self, step):
        """
        Callable to determine if step should be skipped.
        """
        return False

    def post_step_call(self, step):
        """
        Callable to be invoked after each step.
        """
        pass

    def _run(self):
        """
        Runs the runnable object by executing a step.
        """

        self.logger.user_info("Running %s", self)
        self.status.change(RunnableStatus.RUNNING)
        while self.active:
            if self.status == RunnableStatus.RUNNING:
                try:
                    func, args, kwargs = self._steps.popleft()
                    self.pre_step_call(func)
                    if self.skip_step(func) is False:
                        self.logger.debug(
                            "Executing step of %s - %s", self, func.__name__
                        )
                        start_time = time.time()
                        self._execute_step(func, *args, **kwargs)
                        self.logger.debug(
                            "Finished step of %s - %s. Took %ds",
                            self,
                            func.__name__,
                            round(time.time() - start_time, 5),
                        )
                    else:
                        self.logger.debug(
                            "Skipping step of %s - %s", self, func.__name__
                        )
                    self.post_step_call(func)
                except IndexError:
                    self.status.change(RunnableStatus.FINISHED)
                    break
            time.sleep(self.cfg.active_loop_sleep)

    def _run_batch_steps(self):
        """
        Runs the runnable object by executing a batch of steps.
        """
        start_threads, start_procs = self._get_process_info()

        self._add_step(self.setup)
        self.add_pre_resource_steps()
        self.add_start_resource_steps()
        self.add_pre_main_steps()

        self.add_main_batch_steps()

        self.add_post_main_steps()
        self.add_stop_resource_steps()
        self.add_post_resource_steps()
        self._add_step(self.teardown)

        self._run()

        self._post_run_checks(start_threads, start_procs)

    @staticmethod
    def _get_process_info(recursive=False):
        """
        :return: lists of threads and child processes, to be passed to the
            _post_run_checks method after the run has finished.
        """
        threads = threading.enumerate()
        current_proc = psutil.Process()
        children = current_proc.children(recursive)

        return threads, children

    def _post_run_checks(self, start_threads, start_procs):
        """
        Compare the current running threads and processes to those that were
        alive before we were run. If there are any differences that indicates
        we have either gained or lost threads or processes during the run,
        which may indicate insufficient cleanup. Warnings will be logged.

        :param start_threads: threads before run
        :type start_threads: ``list`` of ``Thread``
        :param start_procs: processes before run
        :type start_procs: ``list`` of ``Process``
        """
        # XXX: do we want to suppress process/thread check for tests?
        end_threads = threading.enumerate()
        if start_threads != end_threads:
            new_threads = [
                thr.name for thr in end_threads if thr not in start_threads
            ]
            self.logger.warning(
                "New threads are still alive after run: %s", new_threads
            )
            dead_threads = [
                thr.name for thr in start_threads if thr not in end_threads
            ]
            self.logger.warning(
                "Threads have died during run: %s", dead_threads
            )

        current_proc = psutil.Process()
        end_procs = current_proc.children()
        if start_procs != end_procs:
            new_procs = [proc for proc in end_procs if proc not in start_procs]
            self.logger.warning(
                "New processes are still alive after run: %s", new_procs
            )
            dead_procs = [
                proc for proc in start_procs if proc not in end_procs
            ]
            self.logger.warning(
                "Child processes have died during run: %s", dead_procs
            )

    def _execute_step(self, step, *args, **kwargs):
        """
        Executes a particular step.

        :param step: step to execute
        :type step: ``Callable``
        """
        res = None
        try:
            res = step(*args, **kwargs)
        except Exception as exc:
            self.logger.error(
                "Exception on %s, step %s - %s",
                self,
                step.__name__,
                str(exc),
            )
            self.logger.error(traceback.format_exc())
            res = exc
        finally:
            self.result.step_results[step.__name__] = res
            self.status.update_metadata(**{str(step): res})

    def add_pre_resource_steps(self):
        """
        Runnable steps to run before environment started.
        """
        pass

    def add_start_resource_steps(self):
        """
        Runnable steps to start environment
        """
        self._add_step(self.resources.start)

    def add_pre_main_steps(self):
        """
        Runnable steps to run after environment started.
        """
        pass

    def add_main_batch_steps(self):
        """
        Runnable steps to be executed while environment is running.
        """
        pass

    def add_post_main_steps(self):
        """
        Runnable steps to run before environment stopped.
        """
        pass

    def add_stop_resource_steps(self):
        """
        Runnable steps to stop environment
        """
        self._add_step(self.resources.stop, is_reversed=True)

    def add_post_resource_steps(self):
        """
        Runnable steps to run after environment stopped.
        """
        pass

    def pausing(self):
        """
        Pauses the resource.
        """
        for resource in self.resources:
            resource.pause()
        self.status.change(RunnableStatus.PAUSED)

    def resuming(self):
        """
        Resumes the resource.
        """
        for resource in self.resources:
            resource.resume()
        self.status.change(RunnableStatus.RUNNING)

    def abort_dependencies(self):
        """
        Yield all dependencies to be aborted before self abort.
        """
        for resource in self.resources:
            yield resource

    def setup(self):
        """
        Setup step to be executed first.
        """
        pass

    def teardown(self):
        """
        Teardown step to be executed last.
        """
        pass

    def should_run(self):
        """
        Determines if current object should run.
        """
        return True

    def run(self):
        """
        Executes the defined steps and populates the result object.
        """
        try:
            if self.cfg.interactive_port is not None:

                from testplan.runnable.interactive.base import (
                    TestRunnerIHandler,
                )

                if self._ihandler is not None:
                    raise RuntimeError(
                        f"{self} already has an active {self._ihandler}"
                    )

                self.logger.user_info("Starting %s in interactive mode", self)
                handler_class = (
                    self.cfg.interactive_handler or TestRunnerIHandler
                )
                self._ihandler = handler_class(
                    target=self,
                    http_port=self.cfg.interactive_port,
                    pre_start_environments=self.cfg.pre_start_environments,
                )
                thread = threading.Thread(target=self._ihandler)
                # Testplan should exit even if interactive handler thread stuck
                thread.daemon = True
                thread.start()

                # Check if we are on interactive session.
                if self.cfg.interactive_block:
                    while self._ihandler.active:
                        time.sleep(self.cfg.active_loop_sleep)
                    else:
                        # TODO: need some rework
                        # if we abort from ui, the ihandler.abort executes in http thread
                        # if we abort by ^C, ihandler.abort is called in main thread
                        # anyway this join will not be blocked
                        interruptible_join(
                            thread, timeout=self.cfg.abort_wait_timeout
                        )
                        # if we abort from ui, we abort ihandler first, then testrunner
                        # this abort will wait ihandler to be aborted
                        # if we abort by ^C, testrunner.abort is already called, this will be noop
                        self.abort()
                return self._ihandler
            else:
                self._run_batch_steps()
        except Exception as exc:
            self.result.run = exc
            self.logger.error(traceback.format_exc())
        else:
            # TODO fix swallow exceptions in self.result.step_results.values()
            self.result.run = (
                self.status == RunnableStatus.FINISHED
                and self.run_result() is True
            )
        return self.result

    def run_result(self):
        """
        Returns if a run was successful.
        """
        return all(
            not isinstance(val, Exception) and val is not False
            for val in self.result.step_results.values()
        )

    def dry_run(self):
        """
        A testing process that creates result for each step.
        """
        raise NotImplementedError()


class FailedAction:
    """
    Simple falsy container that can be used for
    returning results of certain failed async actions.

    The `error_msg` can later on be used for enriching the error messages.
    """

    def __init__(self, error_msg):
        self.error_msg = error_msg

    def __bool__(self):
        return False


ActionResult = Union[bool, FailedAction]


class ResourceConfig(EntityConfig):
    """
    Configuration object for
    :py:class:`~testplan.common.entity.base.Resource` entity.
    """

    @classmethod
    def get_options(cls):
        """
        Resource specific config options.
        """
        return {
            ConfigOption("async_start", default=True): bool,
            ConfigOption("auto_start", default=True): bool,
            ConfigOption("pre_start", default=None): Or(callable, None),
            ConfigOption("post_start", default=None): Or(callable, None),
            ConfigOption("pre_stop", default=None): Or(callable, None),
            ConfigOption("post_stop", default=None): Or(callable, None),
        }


class ResourceStatus(EntityStatus):
    """
    Status of a
    :py:class:`Resource <testplan.common.entity.base.Resource>` entity.
    """

    STARTING = "STARTING"
    STARTED = "STARTED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"

    def transitions(self):
        """
        Defines the status transitions of a
        :py:class:`Resource <testplan.common.entity.base.Resource>` entity.
        """
        transitions = super(ResourceStatus, self).transitions()
        overrides = {
            self.NONE: {self.STARTING},
            self.STARTING: {self.STARTED, self.STOPPING},
            self.STARTED: {self.PAUSING, self.STOPPING},
            self.PAUSING: {self.PAUSED},
            self.PAUSED: {self.RESUMING, self.STOPPING},
            self.RESUMING: {self.STARTED},
            self.STOPPING: {self.STOPPED},
            self.STOPPED: {self.STARTING},
        }
        transitions.update(overrides)
        return transitions


class ResourceTimings:
    RESOURCE_SETUP = "setup"
    RESOURCE_TEARDOWN = "teardown"


class Resource(Entity):
    """
    An object that can be started/stopped and expose its context
    object of key/value pair information.

    A Resource is usually part of an
    :py:class:`~testplan.common.entity.base.Environment`
    object of a
    :py:class:`~testplan.common.entity.base.Runnable` object.

    :param async_start: Resource can start asynchronously.
    :type async_start: ``bool``
    :param auto_start: Enables the Environment to start the Resource
        automatically.
    :type auto_start: ``bool``

    Also inherits all
    :py:class:`~testplan.common.entity.base.Entity` options.
    """

    CONFIG = ResourceConfig
    STATUS = ResourceStatus

    def __init__(self, **options):
        super(Resource, self).__init__(**options)
        self._context = None
        self._failovers = []  # failover resources if start fails
        self._wait_handlers.update(
            {
                self.STATUS.STARTED: self._wait_started,
                self.STATUS.STOPPED: self._wait_stopped,
            }
        )

    @property
    def context(self):
        """
        Key/value pair information of a Resource.
        """
        return self._context

    @context.setter
    def context(self, context):
        """
        Set the Resource context.
        """
        self._context = context

    @property
    def async_start(self):
        """
        If True, the resource's parent will take the responsibility
        to check that the resource has already STARTED or STOPPED.
        """
        return self.cfg.async_start

    @property
    def auto_start(self):
        """
        If False, the resource will not be automatically started by its parent
        (generally, a `Environment` object) while the parent is starting.
        """
        return self.cfg.auto_start

    def start(self):
        """
        Triggers the start logic of a Resource by executing
        :py:meth:
        `Resource.starting <testplan.common.entity.base.Resource.starting>`
        method.
        """
        if not self.active:
            self.logger.warning("Start %s but it is aborting / aborted", self)
            return

        if (
            self.status == self.STATUS.STARTING
            or self.status == self.STATUS.STARTED
        ):
            self.logger.debug(
                "start() has been called on %s, skip starting", self
            )
            return

        self.timer.start("lifespan")

        self.logger.info("Starting %s", self)
        self.timer.start(ResourceTimings.RESOURCE_SETUP)
        self.status.change(self.STATUS.STARTING)
        self.pre_start()
        if self.cfg.pre_start:
            self.cfg.pre_start(self)
        self.starting()

        if not self.async_start:
            self.wait(self.STATUS.STARTED)
            self.logger.info("%s started", self)

    def stop(self):
        """
        Triggers the stop logic of a Resource by executing
        :py:meth:
        `Resource.stopping <testplan.common.entity.base.Resource.stopping>`
        method.
        """
        if self.aborted:
            self.logger.warning("Stop %s but it has already aborted", self)

        if self.status == self.STATUS.NONE:
            self.logger.info("%s not started, skip stopping", self)
            return

        if (
            self.status == self.STATUS.STOPPING
            or self.status == self.STATUS.STOPPED
        ):
            self.logger.info(
                "stop() has been called on %s, skip stopping", self
            )
            return

        self.logger.info("Stopping %s", self)
        self.timer.start(ResourceTimings.RESOURCE_TEARDOWN)
        self.status.change(self.STATUS.STOPPING)
        self.pre_stop()
        if self.cfg.pre_stop:
            self.cfg.pre_stop(self)
        self.stopping()

        if not self.async_start:
            self.wait(self.STATUS.STOPPED)
            self.logger.info("%s stopped", self)
        self.timer.end("lifespan")

    def pre_start(self):
        """
        Steps to be executed right before resource starts.
        """
        pass

    def post_start(self):
        """
        Steps to be executed right after resource is started.
        """
        pass

    def pre_stop(self):
        """
        Steps to be executed right before resource stops.
        """
        pass

    def post_stop(self):
        """
        Steps to be executed right after resource is stopped.
        """
        pass

    def fetch_error_log(self) -> List[str]:
        """
        Override this method in Resource subclasses to automatically add any
        useful logs into the report, in case of startup/shutdown exception.

        :return: text from log files
        """
        return []

    def _wait_started(self, timeout: Optional[float] = None):
        """
        Changes status to STARTED, if possible.

        :param timeout: timeout in seconds
        """
        self._after_started()

    def _after_started(self):
        """
        Common logic after a successful Resource start.
        """
        self.status.change(self.STATUS.STARTED)
        try:
            self.timer.end(ResourceTimings.RESOURCE_SETUP)
        except KeyError as err:
            # wait has been called already, timing already recorded
            self.logger.debug(
                "Key error raised on recording %s setup time, likely due to wait being called twice",
                self,
            )
        self.post_start()
        if self.cfg.post_start:
            self.cfg.post_start(self)

    def _wait_stopped(self, timeout: Optional[float] = None):
        """
        Changes status to STOPPED, if possible.

        :param timeout: timeout in seconds
        """
        self._mark_stopped()

    def _mark_stopped(self):
        """
        Common logic after a successful Resource stop.
        """
        self.status.change(self.STATUS.STOPPED)
        try:
            self.timer.end(ResourceTimings.RESOURCE_TEARDOWN)
        except KeyError as err:
            # wait has been called already, timing already recorded
            self.logger.debug(
                "Key error raised on recording %s teardown time, likely due to wait being called twice",
                self,
            )
        self.post_stop()
        if self.cfg.post_stop:
            self.cfg.post_stop(self)

    def starting(self):
        """
        Start logic for Resource that also sets the status to *STARTED*.
        """
        raise NotImplementedError()

    def stopping(self):
        """
        Stop logic for Resource that also sets the status to *STOPPED*.
        """
        raise NotImplementedError()

    def pausing(self):
        """
        Pause the resource.
        """
        self.status.change(self.STATUS.PAUSED)

    def resuming(self):
        """
        Resume the resource.
        """
        self.status.change(self.STATUS.STARTED)

    def restart(self):
        """
        Stop and start the resource.
        """
        self.stop()
        if self.async_start:
            self.wait(self.STATUS.STOPPED)

        self.start()
        if self.async_start:
            self.wait(self.STATUS.STARTED)

    def force_stop(self):
        """
        Change the status to STOPPED (e.g. exception raised).
        """
        self.status.change(self.STATUS.STOPPED)

    def force_started(self):
        """
        Change the status to STARTED (e.g. exception raised).
        """
        self.status.change(self.STATUS.STARTED)

    def __enter__(self):
        self.start()
        if self.async_start:
            self.wait(self.STATUS.STARTED)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        if self.async_start:
            self.wait(self.STATUS.STOPPED)

    @property
    def is_alive(self):
        """
        Called to periodically poll the resource health. Default implementation
        assumes the resource is always healthy.
        """
        return True

    def pending_work(self):
        """
        Resource has pending work.
        """
        return False

    def register_failover(self, klass: Entity, params: dict) -> None:
        """
        Register a failover class to instantiate if resource start fails.

        :param klass: failover class
        :param params: parameters for failover class __init__ method
        """
        self._failovers.append({"klass": klass, "params": params})

    def failover(self) -> None:
        """
        API to create the failover resource, to be implemented in derived class
        """
        return None


DEFAULT_RUNNABLE_ABORT_SIGNALS = [signal.SIGINT, signal.SIGTERM]


class RunnableManagerConfig(EntityConfig):
    """
    Configuration object for
    :py:class:`RunnableManager <testplan.common.entity.base.RunnableManager>`
    entity.
    """

    @classmethod
    def get_options(cls):
        """
        RunnableManager specific config options.
        """
        return {
            ConfigOption("parse_cmdline", default=True): bool,
            ConfigOption("runnable", default=Runnable): is_subclass(Runnable),
            ConfigOption("resources", default=[]): [Resource],
            ConfigOption(
                "abort_signals", default=DEFAULT_RUNNABLE_ABORT_SIGNALS
            ): [int],
        }


class RunnableManager(Entity):
    """
    Executes a
    :py:class:`Runnable <testplan.common.entity.base.Runnable>` entity
    in a separate thread and handles the abort signals.

    :param parse_cmdline: Parse command line arguments.
    :type parse_cmdline: ``bool``
    :param runnable: Test runner.
    :type runnable: :py:class:`~testplan.runnable.TestRunner`
    :param resources: Initial resources.
    :type resources:
        ``list`` of :py:class:`Resources <testplan.common.entity.base.Resource>`
    :param abort_signals: Signals to catch and trigger abort.
    :type abort_signals: ``list`` of signals

    Also inherits all
    :py:class:`~testplan.common.entity.base.Entity` options.
    """

    CONFIG = RunnableManagerConfig

    def __init__(self, **options):
        super(RunnableManager, self).__init__(**options)

        self._default_options = options
        if self._cfg.parse_cmdline is True:
            options = self.enrich_options(self._default_options)

        self._runnable: Runnable = self._initialize_runnable(**options)
        for resource in self._cfg.resources:
            self._runnable.add_resource(resource)

    @property
    def aborted(self):
        return self._runnable.aborted

    def enrich_options(self, options):
        """
        Enrich the options using parsed command line arguments.
        Override this method to add extra argument processing logic.
        The result dictionary is used to initialize the configuration.

        :param options:
        :type options:
        """
        return options

    def _initialize_runnable(self, **options):
        """
        Instantiates runnable object as per configuration options.

        :param options: configuration to pass to constructor
        :type options: ``Mapping``
        """
        runnable_class = self._cfg.runnable
        return runnable_class(**options)

    @property
    def report(self):
        return self.runnable.report

    def __getattr__(self, item):
        try:
            return self.__getattribute__(item)
        except AttributeError:
            if "_runnable" in self.__dict__:
                return getattr(self._runnable, item)
            raise

    @property
    def runnable(self):
        """
        Runnable instance.
        """
        return self._runnable

    @property
    def runpath(self):
        """
        Expose the runnable runpath.
        """
        return self._runnable.runpath

    @property
    def cfg(self):
        """
        Expose the runnable configuration object.
        """
        return self._runnable.cfg

    @property
    def status(self):
        """
        Expose the runnable status.
        """
        return self._runnable.status

    @property
    def active(self):
        """
        Expose the runnable active attribute.
        """
        return self._runnable.active

    def run(self):
        """
        Executes target runnable defined in configuration in a separate thread.

        :return: Runnable result object.
        :rtype: :py:class:
            `RunnableResult <testplan.common.entity.base.RunnableResult>`
        """
        with suppress(ValueError):
            # best effort signal handling
            for sig in self._cfg.abort_signals:
                signal.signal(sig, self._handle_abort)

        execute_as_thread(
            self._runnable.run,
            daemon=True,
            join=True,
            break_join=lambda: self.aborted is True,
        )
        if self._runnable.interactive is not None:
            # for testing purpose
            if self.cfg.interactive_block is False:
                return self._runnable.interactive
        if isinstance(self._runnable.result, Exception):
            raise self._runnable.result
        return self._runnable.result

    def _handle_abort(self, signum, frame):
        for sig in self._cfg.abort_signals:
            signal.signal(sig, signal.SIG_IGN)
        self.logger.debug(
            "Signal handler called for signal %d from %s",
            signum,
            threading.current_thread(),
        )

        self.abort()

    def pausing(self):
        """
        Pause the runnable execution.
        """
        self._runnable.pause()

    def resuming(self):
        """
        Resume the runnable execution.
        """
        self._runnable.resume()

    def abort_dependencies(self):
        """
        Dependencies to be aborted first.
        """
        yield self._runnable

    def aborting(self):
        """
        Suppressing not implemented debug log by parent class.
        """
        pass
