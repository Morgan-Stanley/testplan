import React from "react";
import PropTypes from "prop-types";
import TableBaseAssertion from "./TableBaseAssertion";

import {
  prepareTableLogColumnDefs,
  prepareTableLogRowData,
} from "./tableAssertionUtils";

/**
 * Component that are used to render TableLog assertion.
 */
export default function TableLogAssertion(props) {
  let columnDefs = prepareTableLogColumnDefs(
    props.assertion.columns,
    props.assertion.display_index
  );
  let rowData = prepareTableLogRowData(
    props.assertion.indices || [...Array(props.assertion.table.length).keys()],
    props.assertion.table,
    props.assertion.columns,
    props.assertion.display_index
  );

  return <TableBaseAssertion columns={columnDefs} rows={rowData} />;
}

TableLogAssertion.propTypes = {
  /** Assertion being rendered */
  assertion: PropTypes.object,
};
