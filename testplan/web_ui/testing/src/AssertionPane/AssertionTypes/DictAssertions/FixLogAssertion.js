import React, { useState } from "react";
import PropTypes from "prop-types";
import DictBaseAssertion from "./DictBaseAssertion";
import DictButtonGroup from "./DictButtonGroup";
import FixCellRenderer from "./FixCellRenderer";
import {
  prepareDictColumnDefs,
  prepareDictRowData,
  dictCellStyle,
  preprocessDictRows,
} from "./dictAssertionUtils";
import { SORT_TYPES } from "./../../../Common/defaults";

/**
 * Component that renders FixLog assertion.
 *
 * The actual dictionary of the test:
 *
 * {
 *   'foo': {
 *     'alpha': 'blue',
 *     'beta': 'green',
 *   }
 *   'bar': true
 * }
 *
 *  _________________________
 * | Key        | Value      |
 * |------------|------------|
 * | *foo       |            |
 * |   *alpha   | blue       |
 * |   *beta    | green      |
 * | *bar       | true       |
 * |____________|____________|
 *
 * The grid consists of two columns: Key and Value.
 *  - Key: a key of the dictionary. Nested objects are displayed with indented
 *    keys.
 *  - Value: Actual value for the given key.
 *
 */
export default function FixLogAssertion(props) {
  const flattenedDict = preprocessDictRows(
    props.assertion.flattened_dict,
    false
  );
  const columns = prepareDictColumnDefs(dictCellStyle, FixCellRenderer);

  const [rowData, setRowData] = useState(flattenedDict);

  const buttonGroup = (
    <DictButtonGroup
      sortTypeList={[
        SORT_TYPES.ALPHABETICAL,
        SORT_TYPES.REVERSE_ALPHABETICAL,
        SORT_TYPES.NONE,
      ]}
      flattenedDict={flattenedDict}
      setRowData={setRowData}
      defaultSortType={SORT_TYPES.NONE}
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

FixLogAssertion.propTypes = {
  /** Assertion being rendered */
  assertion: PropTypes.object.isRequired,
};
