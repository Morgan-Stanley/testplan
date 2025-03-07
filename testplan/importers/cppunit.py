"""
Implements three-phase importer for CppUnit format.
"""
import datetime
import socket
from typing import List

from lxml import objectify, etree
from lxml.builder import E
from lxml.objectify import Element

from testplan.common.utils.strings import uuid4
from testplan.importers.base import ThreePhaseFileImporter, T
from testplan.importers.suitesresults import SuitesResult
from testplan.report import (
    TestGroupReport,
    ReportCategories,
    TestCaseReport,
    RuntimeStatus,
)
from testplan.testing.multitest.entries.assertions import RawAssertion
from testplan.testing.multitest.entries.schemas.base import registry


CPPUNIT_TO_JUNIT_XSL = b"""<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="xml" indent="yes"/>
    <xsl:template match="/">
        <testsuites>
            <xsl:attribute name="name">All Tests</xsl:attribute>
            <testsuite>
                <xsl:attribute name="errors">
                    <xsl:value-of select="TestRun/Statistics/Errors"/>
                </xsl:attribute>
                <xsl:attribute name="failures">
                    <xsl:value-of select="TestRun/Statistics/Failures"/>
                </xsl:attribute>
                <xsl:attribute name="tests">
                    <xsl:value-of select="TestRun/Statistics/Tests"/>
                </xsl:attribute>
                <xsl:attribute name="name"></xsl:attribute>
                <xsl:apply-templates/>
            </testsuite>
        </testsuites>
    </xsl:template>
    <xsl:template match="/TestRun/SuccessfulTests/Test">
        <testcase>
            <xsl:attribute name="classname" ><xsl:value-of select="substring-before(Name, '::')"/></xsl:attribute>
            <xsl:attribute name="name"><xsl:value-of select="substring-after(Name, '::')"/></xsl:attribute>
        </testcase>
    </xsl:template>
    <xsl:template match="/TestRun/FailedTests/FailedTest">
        <testcase>
            <xsl:attribute name="classname" ><xsl:value-of select="substring-before(Name, '::')"/></xsl:attribute>
            <xsl:attribute name="name"><xsl:value-of select="substring-after(Name, '::')"/></xsl:attribute>
            <error>
                <xsl:attribute name="message">
                    <xsl:value-of select=" normalize-space(Message)"/>
                </xsl:attribute>
                <xsl:attribute name="type">
                    <xsl:value-of select="FailureType"/>
                </xsl:attribute>
                <xsl:value-of select="Message"/>
File: <xsl:value-of select="Location/File"/>
Line: <xsl:value-of select="Location/Line"/>
            </error>
        </testcase>
    </xsl:template>
    <xsl:template match="text()|@*"/>
</xsl:stylesheet>
"""


def _set_node_classname(name: str, element: etree.Element) -> None:
    """
    Sets classname attribute of testsuite/testcase if missing or incomplete.

    :param name: name of Cppunit which will be used as package name.
    :param element: XML element on which classname is set (recursively).
    """
    if element.tag == "testcase":
        for key, value in element.items():
            if key == "classname":
                if "." not in value:
                    element.set(key, f"{name}.{value}")
                break
        else:
            element.set("classname", f"{name}.{name}")
    else:
        if element.tag == "testsuite":
            element.set("name", name)
        for child in element.getchildren():
            _set_node_classname(name, child)


class CPPUnitImportedResult(SuitesResult):
    """ """

    REPORT_CATEGORY = ReportCategories.CPPUNIT


class CPPUnitResultImporter(ThreePhaseFileImporter[Element]):
    """
    Three-phase file importer class for handling CppUnit format.
    """

    _DEFAULT_SUITE_NAME = "All Tests"

    def _read_data(self, path: str) -> Element:
        """
        Parses a CppUnit XML report and returns root. Assumes xUnit format.

        :param path: path to source file
        :return: root node of parsed raw test data
        """
        with open(path) as report_file:
            return objectify.fromstring(
                self.cppunit_to_junit(
                    report_file.read(), self._DEFAULT_SUITE_NAME
                )
            )

    def _process_data(self, data: Element) -> List[TestGroupReport]:
        """
        Processes data read from the source file.

        :param data: raw data as read by the importer
        """
        # NOTE: XML output contains skipped testcases which are ignored.
        result = []

        for suite in data.getchildren():
            suite_name = suite.attrib["name"]
            suite_report = TestGroupReport(
                name=suite_name,
                category=ReportCategories.TESTSUITE,
            )

            for testcase in suite.getchildren():
                if testcase.tag != "testcase":
                    continue

                testcase_classname = testcase.attrib["classname"]
                testcase_name = testcase.attrib["name"]
                testcase_prefix = testcase_classname.split(".")[-1]
                testcase_report = TestCaseReport(
                    name="{}::{}".format(testcase_prefix, testcase_name),
                )

                if not testcase.getchildren():
                    assertion_obj = RawAssertion(
                        description="Passed",
                        content=f"Testcase {testcase_name} passed",
                        passed=True,
                    )
                    testcase_report.append(registry.serialize(assertion_obj))
                else:
                    for entry in testcase.getchildren():
                        assertion_obj = RawAssertion(
                            description=entry.tag,
                            content=entry.text,
                            passed=entry.tag not in ("failure", "error"),
                        )
                        testcase_report.append(
                            registry.serialize(assertion_obj)
                        )

                testcase_report.runtime_status = RuntimeStatus.FINISHED
                suite_report.append(testcase_report)

            if len(suite_report) > 0:
                result.append(suite_report)

        return result

    def _create_result(
        self, raw_data: Element, processed_data: List[TestGroupReport]
    ) -> CPPUnitImportedResult:
        """
        Creates in-memory imported result from processed data.

        :param raw_data: raw data as read by the importer
        :param processed_data: list of data as processed by the importer
        """
        return CPPUnitImportedResult(
            name=self.name,
            results=processed_data,
            description=self.description,
        )

    # TODO: can be moved to `testplan.common.util.xml module` if we add more
    #       similar functions that are needed by unit test binaries.
    @staticmethod
    def cppunit_to_junit(report: str, name: str) -> str:
        """
        Transforms CppUnit XML report into JUnit XML format.

        :param report: CppUnit test report in string format
        :param name: name of CppUnit which is used to set classname on XML
            elements recursively.
        """
        if isinstance(report, str):
            report = report.encode("utf-8")

        transform = etree.XSLT(etree.XML(CPPUNIT_TO_JUNIT_XSL))
        cppunit_report = etree.XML(report)
        junit_report = transform(cppunit_report)
        _set_node_classname(name, junit_report.getroot().getchildren()[0])

        for testsuite in junit_report.xpath("//testsuite"):
            if not testsuite.xpath("/properties"):
                testsuite.insert(0, E.properties())
            if not testsuite.xpath("/system-out"):
                testsuite.append(etree.Element("system-out"))
            if not testsuite.xpath("/system-err"):
                testsuite.append(etree.Element("system-err"))
            if testsuite.get("timestamp") is None:
                testsuite.set(
                    "timestamp",
                    datetime.datetime.now(tz=datetime.timezone.utc)
                    .isoformat()
                    .split(".")[0],
                )
            if testsuite.get("hostname") is None:
                testsuite.set("hostname", socket.gethostname())
            if testsuite.get("time") is None:
                testsuite.set("time", "0")

        for testcase in junit_report.xpath("//testsuite/testcase"):
            if testcase.get("time") is None:
                testcase.set("time", "0")

        return etree.tostring(junit_report)
