import re

from testplan.report import (
    TestReport,
    TestGroupReport,
    TestCaseReport,
    RuntimeStatus,
    Status,
)

testcase_report = TestCaseReport(
    name="ExitCodeCheck",
    entries=[
        {
            "type": "RawAssertion",
            "description": "Process exit code check",
            "passed": False,
        },
        {"type": "Attachment", "description": "Process stdout"},
        {"type": "Attachment", "description": "Process stderr"},
    ],
)

testcase_report.runtime_status = RuntimeStatus.FINISHED

expected_report = TestReport(
    name="plan",
    entries=[
        TestGroupReport(
            name="MyTest",
            category="dummytest",
            entries=[
                TestGroupReport(
                    name="ProcessChecks",
                    category="testsuite",
                    entries=[testcase_report],
                )
            ],
        )
    ],
)


expected_report_with_failing_driver_and_driver_info_flag = TestReport(
    name="plan",
    entries=[
        TestGroupReport(
            name="MyTest",
            category="multitest",
            entries=[
                TestGroupReport(
                    name="Environment Start",
                    category="synthesized",
                    entries=[
                        TestCaseReport(
                            name="Starting",
                            uid="Starting",
                            description="",
                            status_override=Status.ERROR,
                            entries=[
                                {
                                    "type": "TableLog",
                                    "display_index": False,
                                    "columns": [
                                        "Driver Class",
                                        "Driver Name",
                                        "Start Time (UTC)",
                                        "Stop Time (UTC)",
                                        "Duration(seconds)",
                                    ],
                                    "table": [
                                        [
                                            "FailingDriver",
                                            "driver",
                                            re.compile(
                                                r"\d{2}:\d{2}:\d{2}.\d{6}"
                                            ),
                                            None,
                                            None,
                                        ]
                                    ],
                                    "description": "Driver Setup Info",
                                    "meta_type": "entry",
                                },
                                {
                                    "style": None,
                                    "type": "Plotly",
                                    "filesize": lambda x: isinstance(x, int),
                                    "dst_path": re.compile(r".*\.json"),
                                    "source_path": re.compile(r".*\.json"),
                                    "orig_filename": re.compile(r".*\.json"),
                                    "description": "Driver Setup Timeline",
                                    "meta_type": "entry",
                                },
                                {
                                    "type": "FlowChart",
                                    "description": "Driver Connections",
                                    "nodes": [
                                        {
                                            "id": "FailingDriver[driver]",
                                            "style": {
                                                "border": "1px solid #FF0000"
                                            },
                                            "data": {
                                                "label": "FailingDriver\n[driver]"
                                            },
                                        },
                                    ],
                                    "edges": [],
                                },
                            ],
                        )
                    ],
                    tags=None,
                ),
                TestGroupReport(
                    name="Environment Stop",
                    category="synthesized",
                    entries=[
                        TestCaseReport(
                            name="Stopping",
                            uid="Stopping",
                            description="",
                            entries=[
                                {
                                    "type": "TableLog",
                                    "display_index": False,
                                    "columns": [
                                        "Driver Class",
                                        "Driver Name",
                                        "Start Time (UTC)",
                                        "Stop Time (UTC)",
                                        "Duration(seconds)",
                                    ],
                                    "table": [
                                        [
                                            "FailingDriver",
                                            "driver",
                                            re.compile(
                                                r"\d{2}:\d{2}:\d{2}.\d{6}"
                                            ),
                                            re.compile(
                                                r"\d{2}:\d{2}:\d{2}.\d{6}"
                                            ),
                                            lambda x: isinstance(x, float),
                                        ]
                                    ],
                                    "description": "Driver Teardown Info",
                                    "meta_type": "entry",
                                },
                                {
                                    "style": None,
                                    "type": "Plotly",
                                    "filesize": lambda x: isinstance(x, int),
                                    "dst_path": re.compile(r".*\.json"),
                                    "source_path": re.compile(r".*\.json"),
                                    "orig_filename": re.compile(r".*\.json"),
                                    "description": "Driver Teardown Timeline",
                                    "meta_type": "entry",
                                },
                            ],
                        )
                    ],
                    tags=None,
                ),
            ],
        ),
    ],
)
