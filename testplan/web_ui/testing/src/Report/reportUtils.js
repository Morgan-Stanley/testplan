/**
 * Report utility functions.
 */
import React from "react";
import { format, formatISO } from "date-fns";
import { TZDate } from "@date-fns/tz";
import _ from "lodash";
import AssertionPane from "../AssertionPane/AssertionPane";
import ResourcePanel from "../AssertionPane/ResourcePanel";
import Message from "../Common/Message";
import { formatMilliseconds } from "./../Common/utils";
import { VIEW_TYPE } from "../Common/defaults";

import { filterEntries } from "./reportFilter";

/**
 * Test if a given report entry is a leaf node, i.e. there is no report entry
 * among its children.
 *
 * While there is no type attribute on TestGroupReport shallow objects,
 * undefined !== "TestCaseReport" will still make it work here.
 *
 * @param {Object} entry - Report entry to be tested.
 * @returns {Boolean} - true if it is such leaf node.
 */
const isReportLeaf = (entry) => entry.type === "TestCaseReport";

/**
 * Merge two tag objects into a single tag object.
 *
 * @param {Object} tagsA - first tag object, contains simple & named tags.
 * @param {Object} tagsB - second tag object, contains simple & named tags.
 * @returns {Object} - merged tag object.
 * @private
 */
function _mergeTags(tagsA, tagsB) {
  // Don't edit one of the objects in place, copy to new object.
  let mergedTags = {};
  for (const tagName in tagsA) {
    if (tagsA.hasOwnProperty(tagName)) {
      mergedTags[tagName] = tagsA[tagName];
    }
  }

  // Merge object B into object A.
  for (const tagName in tagsB) {
    if (tagsB.hasOwnProperty(tagName)) {
      const tags = tagsB[tagName];
      if (tagsA.hasOwnProperty(tagName)) {
        let tagsArray = tags.concat(tagsA[tagName]);
        let tagsSet = _.uniq(tagsArray);
        mergedTags[tagName] = [...tagsSet];
      } else {
        mergedTags[tagName] = tags;
      }
    }
  }
  return mergedTags;
}

/**
 * Merge assertions and structure into main report.
 *
 * @param {Object} mainReport - Main report with meta data.
 * @param {Object} assertions - An object which contains all assertions.
 * @param {Array} structure - Report structure.
 * @returns {Object} - Merged report.
 * @private
 */
const MergeSplittedReport = (mainReport, assertions, structure) => {
  const _mergeStructure = (_structure, _assertions) => {
    _structure.forEach((element) => {
      if (isReportLeaf(element)) {
        element.entries = _assertions[element.uid] || [];
      } else {
        _mergeStructure(element.entries, _assertions);
      }
    });
  };
  _mergeStructure(structure, assertions);
  mainReport.entries = structure;
  return mainReport;
};

/**
 * Propagate indices through report to be utilised by filter box. A single entry
 * will contain:
 *   * tags - its & its ancestors tags.
 *   * tags_index - its, its ancestors & its descendents tags.
 *   * name_type_index - its, its ancestors & its descendents names & types.
 *   * uids - the entity uids from root to this entity
 *
 * @param {Array} entries - Array of Testplan report entries.
 * @param {Object|undefined} parentIndices - An entry's parent's tags_index &
 * name_type_index.
 * @returns {Object} - The indices for all of the entries in the "entries"
 * Array.
 * @private
 */
const propagateIndicesRecur = (entries, parentIndices) => {
  if (parentIndices === undefined) {
    parentIndices = {
      tags_index: {},
      name_type_index: [],
      uids: [],
    };
  }
  let indices = {
    tags_index: {},
    name_type_index: [],
  };

  for (let entry of entries) {
    let entryType = entry.category;
    // Initialize indices.
    let tagsIndex = {};
    const entryNameType = entry.name + "|" + entryType;
    let nameTypeIndex = _.uniq([
      entryNameType,
      ...parentIndices.name_type_index,
    ]);

    let tags = parentIndices.tags_index;
    if (entry.hasOwnProperty("tags")) {
      entry.tags = _mergeTags(entry.tags, parentIndices.tags_index);
      tags = entry.tags;
    }

    const uids = [...parentIndices.uids, entry.uid];
    if (!isReportLeaf(entry)) {
      // Propagate indices to children.
      let descendantsIndices = propagateIndicesRecur(entry.entries, {
        tags_index: tags,
        name_type_index: nameTypeIndex,
        uids,
      });
      tagsIndex = _mergeTags(tagsIndex, descendantsIndices.tags_index);
      nameTypeIndex = _.uniq([
        ...nameTypeIndex,
        ...descendantsIndices.name_type_index,
      ]);
    }

    // Set entry's indices.
    tagsIndex = _mergeTags(tagsIndex, tags);
    entry.tags_index = tagsIndex;
    entry.name_type_index = nameTypeIndex;
    entry.uids = uids;

    // Update Array of entries indices.
    indices.tags_index = _mergeTags(indices.tags_index, tagsIndex);
    indices.name_type_index = _.uniq([
      ...indices.name_type_index,
      ...nameTypeIndex,
    ]);
  }
  return indices;
};

/**
 * Propagate indices through report to be utilised by filter box. A single entry
 * will contain:
 *   * tags - its & its ancestors tags.
 *   * tags_index - its, its ancestors & its descendents tags.
 *   * name_type_index - its, its ancestors & its descendents names & types.
 *   * uids - the entity uids from root to this entity
 *
 * @param {Array} entries - A single Testplan report in an Array.
 * @returns {Array} - The Testplan report with indices, in an Array.
 */
const PropagateIndices = (report) => {
  propagateIndicesRecur([report], undefined);
  return report;
};

/**
 * Get the current report data, status and fetch message as required.
 */
const GetReportState = (state) => {
  // Handle the Testplan report if it has been fetched.
  if (!state.report) {
    // The Testplan report hasn't been fetched yet.
    return {
      reportStatus: null,
      reportFetchMessage: getReportFetchMessage(state),
    };
  } else {
    // The Testplan report has been fetched.
    return {
      reportStatus: state.report.status,
      reportFetchMessage: null,
    };
  }
};

/**
 * Get the component to display in the centre pane.
 */
const GetCenterPane = (
  state,
  reportFetchMessage,
  reportUid,
  selectedEntries,
  displayTime,
  UTCTime
) => {
  const selectedEntry = _.last(selectedEntries);
  const logs = selectedEntry?.logs || [];
  const selectedDescription = selectedEntries
    .slice(-1)
    .map((element) => {
      return element.description;
    })
    .filter((element) => {
      return element; // filter empty description
    });

  if (state.error) {
    return <Message message={`Error: ${state.error.message}`} />;
  }

  if (reportFetchMessage !== null) {
    return <Message message={reportFetchMessage} />;
  }

  if (state.currentPanelView === VIEW_TYPE.RESOURCE) {
    return <ResourcePanel key="resourcePanel" report={state.report} />;
  }

  const assertions = getAssertions(selectedEntries, displayTime, UTCTime);
  if (
    assertions.length > 0 ||
    logs.length > 0 ||
    selectedDescription.length > 0
  ) {
    return (
      <AssertionPane
        key={selectedEntry ? selectedEntry.hash || selectedEntry.uid : null}
        assertions={assertions}
        logs={logs}
        descriptionEntries={selectedDescription}
        left={state.navWidth}
        testcaseUid={selectedEntry.uid}
        filter={state.filter}
        displayPath={state.displayPath}
        reportUid={reportUid}
      />
    );
  }
  if (selectedEntry && selectedEntry.entries.length > 0) {
    return <Message message="Please select an entry." />;
  } else {
    return <Message message="No entries to be displayed." />;
  }
};

/** TODO */
const getAssertions = (selectedEntries, displayTime, UTCTime) => {
  // get timezone from nearest (test-level) report
  const IANAtz = selectedEntries.find((e) => e.timezone)?.timezone || ""; // default to utc

  // get all assertions from groups and list them sequentially in an array
  const getAssertionsRecursively = (links, entries) => {
    for (let i = 0; i < entries.length; ++i) {
      if (entries[i].type === "Group") {
        getAssertionsRecursively(links, entries[i].entries);
      } else {
        links.push(entries[i]);
      }
    }
  };

  const createTimeInfoString = (entry, UTCTime) => {
    // new entry structure
    if (entry.timestamp) {
      let d = new TZDate(entry.timestamp * 1000, IANAtz);
      let rep = UTCTime ? formatISO(d.withTimeZone("UTC")) : formatISO(d);
      return rep.split("T")[1];
    }

    // old entry structure
    let timestamp = UTCTime ? entry.utc_time : entry.machine_time;
    if (!timestamp) {
      return "";
    }
    let label = UTCTime ? "Z" : timestamp.substring(26, 32);
    timestamp = timestamp.substring(0, 26);
    return format(new Date(timestamp), "HH:mm:ss.SSS") + label;
  };

  const getTimeDelta = (prevEntry, currentEntry) => {
    if (prevEntry.utc_time && currentEntry.utc_time) {
      const previousEntryTime = new Date(prevEntry.utc_time).getTime();
      const currentEntryTime = new Date(currentEntry.utc_time).getTime();
      return formatMilliseconds(currentEntryTime - previousEntryTime);
    } else if (prevEntry.timestamp && currentEntry.timestamp) {
      return formatMilliseconds(
        (currentEntry.timestamp - prevEntry.timestamp) * 1000
      );
    }
    return "Unknown";
  };

  const selectedEntry = selectedEntries[selectedEntries.length - 1];
  if (selectedEntry && isReportLeaf(selectedEntry)) {
    let links = [];
    getAssertionsRecursively(links, selectedEntry.entries);

    // get time information of each assertion if needed
    if (displayTime) {
      // add time information to the array in a human readable format
      for (let i = 0; i < links.length; ++i) {
        // links[i].timeInfoArray = [index, start_time, duration]
        links[i].timeInfoArray = [i, createTimeInfoString(links[i], UTCTime)];
      }
      // calculate the time elapsed between assertions
      for (let i = links.length - 1; i > 0; --i) {
        let duration = `(+${getTimeDelta(links[i - 1], links[i])})`;
        links[i].timeInfoArray.push(duration);
      }
      if (links.length > 0) {
        let duration = "Unknown";
        if (selectedEntry.timer && selectedEntry.timer.run) {
          if (links[0].utc_time) {
            const previousEntryTime = new Date(
              selectedEntry.timer.run.at(-1).start
            );
            const currentEntryTime = new Date(links[0].utc_time);
            duration = formatMilliseconds(currentEntryTime - previousEntryTime);
          } else if (links[0].timestamp) {
            const previousEntryTime = selectedEntry.timer.run.at(-1).start;
            const currentEntryTime = links[0].timestamp;
            duration = formatMilliseconds(
              (currentEntryTime - previousEntryTime) * 1000
            );
          }
        }
        duration = "(+" + duration + ")";
        links[0].timeInfoArray.push(duration);
      }
    } else {
      for (let i = 0; i < links.length; ++i) {
        links[i].timeInfoArray = [];
      }
    }
    return selectedEntry.entries;
  } else {
    return [];
  }
};

/**
 * Get a message relating to the progress of fetching the testplan report.
 */
const getReportFetchMessage = (state) => {
  if (state.loading) {
    return "Fetching Testplan report...";
  } else {
    return "Waiting to fetch Testplan report...";
  }
};

/**
 * Get the selected entries in the report, from their UIDs.
 */
const GetSelectedEntries = (selectedUIDs, report) => {
  const [headSelectedUID, ...tailSelectedUIDs] = selectedUIDs;
  if (!headSelectedUID || !report) {
    return [];
  }

  if (tailSelectedUIDs.length > 0) {
    const childEntry = report.entries.find(
      (entry) => entry.uid === tailSelectedUIDs[0]
    );
    return [report, ...GetSelectedEntries(tailSelectedUIDs, childEntry)];
  } else {
    return [report];
  }
};

/**
 * Auto-select the first failed entry in the report when it is first loaded.
 * @param {reportNode} reportEntry - the current report entry to select from.
 * @return {Array[string]} List of UIDs of the currently selected entries.
 */
const findFirstFailure = (reportEntry) => {
  if (isReportLeaf(reportEntry) || reportEntry.entries.length === 0) {
    return [reportEntry.uid];
  } else {
    for (let entry in reportEntry.entries) {
      if (
        reportEntry.entries[entry].status === "failed" ||
        reportEntry.entries[entry].status === "error"
      ) {
        return [reportEntry.uid].concat(
          findFirstFailure(reportEntry.entries[entry])
        );
      }
    }
  }
};

const filterReport = (report, filter) => {
  if (filter.filters === null) {
    return { filter, report };
  }

  return {
    filter,
    report: {
      ...report,
      entries: filterEntries(report.entries, filter.filters),
    },
  };
};

const isValidSelection = (selection, entry) => {
  if (selection.length === 0) return true;

  const next_element = _.find(
    entry.entries,
    (entry) => entry.uid === _.head(selection)
  );
  return next_element
    ? isValidSelection(_.tail(selection), next_element)
    : false;
};

const getSelectedUIDsFromPath = ({ uid, selection }, uidDecoder) => {
  const uids = [uid, ...(selection ? selection.split("/") : [])];
  return uidDecoder ? uids.map((uid) => (uid ? uidDecoder(uid) : uid)) : uids;
};

export {
  isReportLeaf,
  PropagateIndices,
  GetReportState,
  GetCenterPane,
  GetSelectedEntries,
  MergeSplittedReport,
  findFirstFailure,
  filterReport,
  isValidSelection,
  getSelectedUIDsFromPath,
};
