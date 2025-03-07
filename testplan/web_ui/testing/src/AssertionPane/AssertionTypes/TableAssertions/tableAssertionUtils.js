/** @module tableAssertionUtils */

import React from "react";
import { useParams, Link } from "react-router-dom";
import _ from "lodash";
import { css, StyleSheet } from "aphrodite";
import {
  domToString,
  generateURLWithParameters,
} from "./../../../Common/utils";

// Small component for rendering TableLogLinkCell.
function LinkRender(props) {
  const { uid } = useParams();
  if (props.inner) {
    const link = generateURLWithParameters(
      window.location,
      props.link.startsWith("/")
        ? `/testplan/${uid}${props.link}`
        : `/testplan/${uid}/${props.link}`
    );
    return <Link to={link}>{props.title || props.link}</Link>;
  } else {
    return (
      <a
        rel="noreferrer"
        href={props.link}
        target={props.new_window ? "_blank" : "_self"}
      >
        {props.title || props.link}
      </a>
    );
  }
}

// The cell of link.
class TableLogLinkCell {
  constructor(cell) {
    this.cell = cell;
    this.value = cell.title || cell.link;
  }

  render() {
    return <LinkRender {...this.cell} />;
  }

  compare(linkB) {
    if (linkB instanceof TableLogLinkCell) {
      return this.value >= linkB.value ? 1 : -1;
    } else {
      return this.value >= String(linkB) ? 1 : -1;
    }
  }
  getValue() {
    return this.value;
  }
}

// The cell of formattedValue.
class FormattedValueCell {
  constructor(cell) {
    this.cell = cell;
  }

  render() {
    return <>{this.cell.display}</>;
  }
  compare(valueB) {
    if (valueB instanceof FormattedValueCell) {
      return this.cell.value >= valueB.cell.value ? 1 : -1;
    } else {
      return this.cell.value >= String(valueB) ? 1 : -1;
    }
  }
  getValue() {
    return this.cell.display;
  }
}

// The cell of default data type
class DefaultCell {
  constructor(cell) {
    this.cell = cell;
  }

  render() {
    return <>{this.cell}</>;
  }
  compare(cellB) {
    return this.cell >= cellB.cell ? 1 : -1;
  }
  getValue() {
    return this.cell;
  }
}

/**
 * Factory to create TableLog cell based on the values in ag-grid.
 *
 * @param {object} cellValue
 * @returns {object}
 * @private
 */
function tableLogCellType(cellValue) {
  if (!_.isNil(cellValue) && typeof cellValue === "object") {
    switch (cellValue.type) {
      case "link":
        return new TableLogLinkCell(cellValue);
      case "formattedValue":
        return new FormattedValueCell(cellValue);
      default:
        break;
    }
  }
  return new DefaultCell(cellValue);
}

function baseTableCellStyle(params) {
  const isValueRow = params.data.ev === "Value";

  let cellStyle = {};

  if (isValueRow) {
    cellStyle["borderBottomColor"] = "#827878";
  }

  return cellStyle;
}

/**
 * Function to add styling to table cells with conditions based on their values.
 *
 * @param {Array} params
 * @returns {object}
 * @private
 */
function tableCellStyle(params) {
  let cellStyle = baseTableCellStyle(params);
  const isCellFailed = params.data.passed[params.colDef.field] === false;

  if (isCellFailed) {
    cellStyle["color"] = "red";
    cellStyle["fontWeight"] = "bold";
  }

  return cellStyle;
}

function ignoredTableCellStyle(params) {
  let cellStyle = baseTableCellStyle(params);
  cellStyle["color"] = "grey";
  cellStyle["fontStyle"] = "italic";
  return cellStyle;
}

function tableLogCellRender(cell) {
  const tableCell = tableLogCellType(cell.value);
  return tableCell.render();
}

function tableLogComparator(valueA, valueB, nodeA, nodeB, isInverted) {
  const a = tableLogCellType(valueA);
  const b = tableLogCellType(valueB);
  return a.compare(b);
}

export function processCellForClipboard(param) {
  const tableCell = tableLogCellType(param.value);
  return tableCell.getValue();
}

/**
 * Function to prepare the column definitions for TableLog assertions.
 *
 * @param {Array} columns
 * @returns {object}
 *  {
 *    title: string,
 *    field: string,
 *    cellStyle: object,
 *    headerStyle: object,
 *  }
 * @private
 */

export function prepareTableLogColumnDefs(columns, display_index) {
  let columnDefs = display_index
    ? [
        {
          headerName: "ID",
          field: "id",
          pinned: "left",
          resizable: true,
          suppressSizeToFit: true,
          width: 75,
          filterParams: { excelMode: "windows" },
        },
      ]
    : [];

  columns.forEach((column) => {
    columnDefs.push({
      headerName: column,
      field: column,
      filterParams: { excelMode: "windows" },
      cellRenderer: tableLogCellRender,
      comparator: tableLogComparator,
    });
  });

  return columnDefs;
}

/**
 * Prepare the row data of TableLog assertions.
 *
 * @param {Array} indexes - indexes of the rows
 * @param {Array} table - the table itself as an array of objects where the keys
 *  are the column titles
 * @param {Array} columns - column titles
 * @returns {Array}
 * @private
 */
export function prepareTableLogRowData(indexes, table, columns, display_index) {
  let rowData = [];

  indexes.forEach((index) => {
    let row = columns.reduce((accumulator, column, idx) => {
      // Array.isArray(table[index])
      accumulator[column] = table[index][idx];
      return accumulator;
    }, {});
    if (display_index) row["id"] = index;

    rowData.push(row);
  });

  return rowData;
}

function isIgnoredColumn(column, included_columns, excluded_columns) {
  return (
    (excluded_columns && _.includes(excluded_columns, column)) ||
    (included_columns && !_.includes(included_columns, column))
  );
}

/**
 * Prepare the column definitions for TableMatch assertion.
 *
 * @param {Array} columns
 * @returns {Array}
 * @private
 */
export function prepareTableMatchColumnDefs(
  columns,
  included_columns,
  excluded_columns
) {
  let columnDefs = [
    {
      headerName: "ID",
      field: "id",
      pinned: "left",
      resizable: true,
      suppressSizeToFit: true,
      width: 75,
      filterParams: { excelMode: "windows" },
      cellStyle: tableCellStyle,
    },
    {
      headerName: "Expected/Value",
      field: "ev",
      pinned: "left",
      resizable: true,
      suppressSizeToFit: true,
      width: 125,
      filterParams: { excelMode: "windows" },
      cellStyle: tableCellStyle,
    },
  ];

  columns.forEach((column) => {
    columnDefs.push({
      headerName: column,
      field: column,
      filterParams: { excelMode: "windows" },
      cellStyle: isIgnoredColumn(column, included_columns, excluded_columns)
        ? ignoredTableCellStyle
        : tableCellStyle,
      headerClass: isIgnoredColumn(column, included_columns, excluded_columns)
        ? css(styles.ignored_column)
        : null,
    });
  });
  return columnDefs;
}

/**
 * Prepare the row data of TableMatch assertion.
 *
 * @param {Array} data - the table itself as an array of objects where the keys
 * are the column titles
 * @param {Array} columns - column titles
 * @returns {Array}
 * @private
 */
export function prepareTableRowData(data, columns) {
  let rowData = [];

  data.forEach((line) => {
    const [index, data, diff, errors, extra] = line;

    let passed = {};

    let expectedRow = columns.reduce((accumulator, column, index) => {
      // the value of diff[column] might be a boolean type false.
      if (diff.hasOwnProperty(column)) {
        accumulator[column] = diff[column];
        passed[column] = false;
      } else if (errors[column]) {
        accumulator[column] = errors[column];
        passed[column] = false;
      } else if (extra[column]) {
        accumulator[column] = extra[column];
        passed[column] = true;
      } else {
        accumulator[column] = data[index];
        passed[column] = true;
      }

      return accumulator;
    }, {});

    expectedRow["id"] = index;
    expectedRow["ev"] = "Expected";
    expectedRow["passed"] = passed;

    rowData.push(expectedRow);

    let valueRow = columns.reduce((accumulator, column, index) => {
      accumulator[column] = data[index];

      return accumulator;
    }, {});

    valueRow["id"] = index;
    valueRow["ev"] = "Value";
    valueRow["passed"] = passed;

    rowData.push(valueRow);
  });

  return rowData;
}

/**
 * Prepare the column definitions for ColumnContain assertion.
 *
 * @param {string} column - name of the column
 * @returns {Array}
 * @private
 */
export function prepareTableColumnContainColumnDefs(column) {
  const cellStyleFn = (params) => {
    return !params.data.passed ? { color: "red", fontWeight: "bold" } : null;
  };
  return [
    {
      headerName: "ID",
      field: "id",
      pinned: "left",
      resizable: true,
      suppressSizeToFit: true,
      width: 75,
      filterParams: { excelMode: "windows" },
      cellStyle: cellStyleFn,
    },
    {
      headerName: column,
      field: "value",
      resizable: true,
      suppressSizeToFit: true,
      filterParams: { excelMode: "windows" },
      cellStyle: cellStyleFn,
    },
  ];
}

/**
 * Prepare the row data of ColumnContain assertion.
 *
 * @param {Array} data
 * @param {Array} values
 * @returns {Array}
 * @private
 */
export function prepareTableColumnContainRowData(data, values) {
  return data.map((line) => {
    const [index, value, passed] = line;

    return {
      id: index,
      expected: values,
      value: value,
      passed: passed,
    };
  });
}

/**
 * Prepare the text display before the table for ColumnContain assertions.
 * The text is the values that are checked against the table.
 *
 * @param values
 * @returns {Array}
 * @private
 */
export function prepareTableColumnContainPreText(values) {
  return values
    .map((value) => JSON.stringify(value))
    .reduce((prev, curr) => [prev, ", ", curr]);
}

/**
 * Calculate the height of the grid. If the grid has less than
 * maximumNumberOfRowsVisible, then the grid will display every row of data
 * available. If it has more than that value then maximumNumberOfRowsVisible
 * number of rows will be displayed and the table will be scrollable.
 *
 * @param {number} numberOfRows
 * @param {number} maximumNumberOfRowsVisible - Maximum number of rows to be
 * displayed
 * @returns {number}
 * @private
 */
export function calculateTableGridHeight(
  numberOfRows,
  maximumNumberOfRowsVisible = 20
) {
  const rowHeight = 28;
  const headerHeight = 32;
  const bottomPaddingOnGrid = 16 + 2;

  return numberOfRows <= maximumNumberOfRowsVisible
    ? numberOfRows * rowHeight + headerHeight + bottomPaddingOnGrid
    : maximumNumberOfRowsVisible * rowHeight +
        headerHeight +
        bottomPaddingOnGrid;
}

/**
 * Convert Ag-Grid columntDefs and row Data to HTML table DOM object
 *
 * @param {Array} columnDefs - Ag-Grid header
 * @param {Array} rowData - Ag-Grid data
 * @returns {string} - HTML Table
 */
export function gridToDOM(columnDefs, rowData) {
  let headerKey = [];
  let table = document.createElement("table");

  let header = document.createElement("tr");
  columnDefs.forEach((el) => {
    if (el.hide) {
      return;
    }
    let th = document.createElement("th");
    th.innerText = el.headerName;
    header.appendChild(th);
    headerKey.push(el.field);
  });
  table.appendChild(header);

  rowData.forEach((el) => {
    let tr = document.createElement("tr");
    headerKey.forEach((key) => {
      let td = document.createElement("td");
      td.innerText = el[key];
      tr.appendChild(td);
    });
    table.appendChild(tr);
  });
  return domToString(table);
}

const styles = StyleSheet.create({
  ignored_column: {
    fontStyle: "italic",
  },
});
