"""
Test report browser which opens a local http web server and
displays the test result.
"""
import os
import webbrowser

from testplan import defaults
from testplan.common.utils.thread import interruptible_join
from testplan.common.utils.timing import wait
from testplan.common.utils.networking import get_hostname_access_url
from testplan.common.utils.logger import TESTPLAN_LOGGER

from .web_app import WebServer, TESTPLAN_UI_STATIC_DIR


class WebUIServer(object):
    """
    A tool for viewing test report in web browser.
    """

    def __init__(
        self,
        json_path,
        ui_port=defaults.WEB_SERVER_PORT,
        web_server_startup_timeout=defaults.WEB_SERVER_TIMEOUT,
    ):
        self._json_path = json_path
        self._ui_port = ui_port
        self._web_server_startup_timeout = web_server_startup_timeout
        self._web_server_thread = None
        self._report_url = None

    @property
    def report_url(self):
        return self._report_url

    @property
    def web_server_thread(self):
        return self._web_server_thread

    @property
    def ui_installed(self):
        """
        Check if the UI is installed. Just check that the build dir exists
        at the expected path.
        """
        build_path = os.path.join(TESTPLAN_UI_STATIC_DIR, "testing", "build")
        return os.path.isdir(build_path)

    def browse(self):
        """Display the JSON report in Testplan UI."""
        # NOTE: not being used
        self.display()

        if self._report_url:
            webbrowser.open(self._report_url)
            self.wait_for_kb_interrupt()

    def display(self):
        """Start a web server locally for JSON report."""
        if self._web_server_thread and self._web_server_thread.ready:
            TESTPLAN_LOGGER.user_info(
                "The JSON report is already served at: %s", self._report_url
            )
            return

        if not self.ui_installed:
            TESTPLAN_LOGGER.warning(
                "Cannot display web UI for report locally since"
                " the Testplan UI is not installed.\n"
                "Install the UI by running `install-testplan-ui`"
            )
            self._report_url = None
            return

        data_path = os.path.dirname(self._json_path)
        report_name = os.path.basename(self._json_path)

        self._web_server_thread = WebServer(
            port=self._ui_port, data_path=data_path, report_name=report_name
        )

        self._web_server_thread.start()
        wait(
            self._web_server_thread.ready,
            self._web_server_startup_timeout,
            raise_on_timeout=True,
        )

        (host, port) = self._web_server_thread.server.bind_addr
        self._report_url = f"http://localhost:{port}/testplan/local"

        TESTPLAN_LOGGER.user_info(
            "View the JSON report in the browser: %s",
            get_hostname_access_url(port, "/testplan/local"),
        )

    def wait_for_kb_interrupt(self):
        try:
            interruptible_join(self._web_server_thread)
        except KeyboardInterrupt:
            self._web_server_thread.stop()
        finally:
            self._web_server_thread = None
            self._report_url = None
