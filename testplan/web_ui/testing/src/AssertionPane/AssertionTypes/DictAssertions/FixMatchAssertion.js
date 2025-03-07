import React, { useState } from "react";
import PropTypes from "prop-types";
import DictBaseAssertion from "./DictBaseAssertion";
import DictButtonGroup from "./DictButtonGroup";
import FixCellRenderer from "./FixCellRenderer";
import {
  prepareDictColumnDefs,
  prepareDictRowData,
  sortFlattenedJSON,
  dictCellStyle,
  preprocessDictRows,
} from "./dictAssertionUtils";
import { SORT_TYPES, FILTER_OPTIONS } from "./../../../Common/defaults";

/**
 * Component that renders FixMatch assertion.
 *
 * The expected dictionary   | The actual dictionary matched
 * of the test:              | to the expected one:
 *
 * {                         | {
 *   'foo': {                |   'foo': {
 *     'alpha': 'blue',      |     'alpha': 'red',
 *     'beta': 'green',      |     'beta': 'green',
 *   }                       |   }
 *   'bar': true             |   'bar': true
 * }                         | }
 *
 *  ______________________________________
 * | Key        | Expected   | Value      |
 * |------------|------------|------------|
 * | *foo       |            |            |
 * |   *alpha   | blue       | red        |
 * |   *beta    | green      | green      |
 * | *bar       | true       | true       |
 * |____________|____________|____________|
 *
 * The grid consists of three columns: Key, Expected and Value.
 *  - Key: a key of the dictionary. Nested objects are displayed with indented
 *    keys.
 *  - Expected: expected value for the given key.
 *  - Value: Actual value for the given key.
 *
 */
export default function FixMatchAssertion(props) {
  const flattenedDict = sortFlattenedJSON(
    preprocessDictRows(props.assertion.comparison, true),
    0,
    false,
    true
  );
  const columns = prepareDictColumnDefs(dictCellStyle, FixCellRenderer, true);

  const [rowData, setRowData] = useState(flattenedDict);

  const buttonGroup = (
    <DictButtonGroup
      sortTypeList={[
        SORT_TYPES.ALPHABETICAL,
        SORT_TYPES.REVERSE_ALPHABETICAL,
        SORT_TYPES.BY_STATUS,
      ]}
      filterOptionList={[
        FILTER_OPTIONS.FAILURES_ONLY,
        FILTER_OPTIONS.EXCLUDE_IGNORABLE,
      ]}
      flattenedDict={flattenedDict}
      setRowData={setRowData}
      defaultSortType={SORT_TYPES.BY_STATUS}
      defaultFilterOptions={[]}
    />
  );

  return (
    <DictBaseAssertion
      buttons={buttonGroup}
      columns={columns}
      rows={prepareDictRowData(rowData)}
    />
  );
}

FixMatchAssertion.propTypes = {
  /** Assertion being rendered */
  assertion: PropTypes.object.isRequired,
};
