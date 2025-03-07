import { useState } from "react";
import PropTypes from "prop-types";
import { Button, ButtonGroup } from "reactstrap";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { library } from "@fortawesome/fontawesome-svg-core";
import {
  faSortAmountUp,
  faSortAmountDown,
} from "@fortawesome/free-solid-svg-icons";
import CopyButton from "./../CopyButton";
import { sortFlattenedJSON, flattenedDictToDOM } from "./dictAssertionUtils";
import { SORT_TYPES, FILTER_OPTIONS } from "./../../../Common/defaults";
import { uniqueId } from "./../../../Common/utils";

library.add(faSortAmountUp, faSortAmountDown);

/**
 * Component that renders the buttons of table.
 * DictLog and FixLog will render sort alphabetically buttons. DictMatch and
 * FixMatch will render sort by alphabet buttons and sort/filter by status
 * buttons.
 *
 * dictAssertionUtils' {@link sortFlattenedJSON} function is called to sort
 * the table data to be displayed.
 */
function DictButtonGroup({
  defaultSortType,
  defaultFilterOptions,
  flattenedDict,
  uid,
  setRowData,
  sortTypeList,
  filterOptionList,
}) {
  const [selectedSortType, setSelectedSortType] = useState(
    defaultSortType || SORT_TYPES.NONE
  );
  const [selectedFilterOptions, setSelectedFilterOptions] = useState(
    defaultFilterOptions || []
  );
  const [sortedData, setSortedData] = useState(flattenedDict);

  const noSort = () => {
    let sortedData = flattenedDict;
    setRowData(sortedData);
    setSelectedSortType(SORT_TYPES.NONE);
    setSortedData(sortedData);
  };

  const sortByChar = () => {
    let sortedData = sortAndFilterData(
      SORT_TYPES.ALPHABETICAL,
      selectedFilterOptions
    );
    setRowData(sortedData);
    setSelectedSortType(SORT_TYPES.ALPHABETICAL);
    setSortedData(sortedData);
  };

  const sortByCharReverse = () => {
    let sortedData = sortAndFilterData(
      SORT_TYPES.REVERSE_ALPHABETICAL,
      selectedFilterOptions
    );
    setRowData(sortedData);
    setSelectedSortType(SORT_TYPES.REVERSE_ALPHABETICAL);
    setSortedData(sortedData);
  };

  const sortByStatus = () => {
    let sortedData = sortAndFilterData(
      SORT_TYPES.BY_STATUS,
      selectedFilterOptions
    );
    setRowData(sortedData);
    setSelectedSortType(SORT_TYPES.BY_STATUS);
    setSortedData(sortedData);
  };

  const filterFailure = () => {
    let filterOptions = selectedFilterOptions;
    filterOptions =
      filterOptions.indexOf(FILTER_OPTIONS.FAILURES_ONLY) >= 0
        ? filterOptions.filter((opt) => opt !== FILTER_OPTIONS.FAILURES_ONLY)
        : filterOptions.concat([FILTER_OPTIONS.FAILURES_ONLY]);
    let sortedData = sortAndFilterData(selectedSortType, filterOptions);
    setRowData(sortedData);
    setSelectedFilterOptions(filterOptions);
    setSortedData(sortedData);
  };

  const filterIgnorable = () => {
    let filterOptions = selectedFilterOptions;
    filterOptions =
      filterOptions.indexOf(FILTER_OPTIONS.EXCLUDE_IGNORABLE) >= 0
        ? filterOptions.filter(
            (opt) => opt !== FILTER_OPTIONS.EXCLUDE_IGNORABLE
          )
        : filterOptions.concat([FILTER_OPTIONS.EXCLUDE_IGNORABLE]);
    let sortedData = sortAndFilterData(selectedSortType, filterOptions);
    setRowData(sortedData);
    setSelectedFilterOptions(filterOptions);
    setSortedData(sortedData);
  };

  const sortAndFilterData = (SortType, filterOptions) => {
    let sortedData = sortFlattenedJSON(
      flattenedDict,
      0,
      SortType === SORT_TYPES.REVERSE_ALPHABETICAL,
      SortType === SORT_TYPES.BY_STATUS
    );
    if (filterOptions.indexOf(FILTER_OPTIONS.FAILURES_ONLY) >= 0) {
      sortedData = sortedData.filter((line) => line[2] === "Failed");
    }
    if (filterOptions.indexOf(FILTER_OPTIONS.EXCLUDE_IGNORABLE) >= 0) {
      sortedData = sortedData.filter((line) => line[2] !== "Ignored");
    }
    return sortedData;
  };

  const buttonUid = uid || uniqueId();
  let buttonMap = {};

  buttonMap[SORT_TYPES.NONE] = {
    display: "Original order",
    onClick: noSort,
  };

  buttonMap[SORT_TYPES.ALPHABETICAL] = {
    display: (
      <FontAwesomeIcon
        size="sm"
        key="faSortAmountDown"
        icon="sort-amount-down"
      />
    ),
    onClick: sortByChar,
  };

  buttonMap[SORT_TYPES.REVERSE_ALPHABETICAL] = {
    display: (
      <FontAwesomeIcon size="sm" key="faSortAmountUp" icon="sort-amount-up" />
    ),
    onClick: sortByCharReverse,
  };

  buttonMap[SORT_TYPES.BY_STATUS] = {
    display: "Status",
    onClick: sortByStatus,
  };

  buttonMap[FILTER_OPTIONS.FAILURES_ONLY] = {
    display: "Failures only",
    onClick: filterFailure,
  };

  buttonMap[FILTER_OPTIONS.EXCLUDE_IGNORABLE] = {
    display: "Hide ignored items",
    onClick: filterIgnorable,
  };

  let buttonGroup = [];

  sortTypeList.forEach((sortType) => {
    buttonGroup.push(
      <Button
        key={buttonUid + "-" + sortType.toString()}
        outline
        color="secondary"
        size="sm"
        onClick={buttonMap[sortType]["onClick"]}
        active={selectedSortType === sortType}
      >
        {buttonMap[sortType]["display"]}
      </Button>
    );
  });

  if (filterOptionList) {
    filterOptionList.forEach((filterOption) => {
      buttonGroup.push(
        <Button
          key={buttonUid + "-" + filterOption.toString()}
          outline
          color="secondary"
          size="sm"
          onClick={buttonMap[filterOption]["onClick"]}
          active={selectedFilterOptions.indexOf(filterOption) >= 0}
        >
          {buttonMap[filterOption]["display"]}
        </Button>
      );
    });
  }

  let copyButton = <CopyButton value={flattenedDictToDOM(sortedData)} />;

  return (
    <ButtonGroup style={{ paddingBottom: ".5rem" }}>
      {buttonGroup}
      {copyButton}
    </ButtonGroup>
  );
}

DictButtonGroup.propTypes = {
  /** Button for sorting should be rendered. */
  sortTypeList: PropTypes.arrayOf(PropTypes.symbol).isRequired,
  /** Button for filtering should be rendered. */
  filterOptionList: PropTypes.arrayOf(PropTypes.symbol),
  /** Function to update the sort state if sort type changed */
  setRowData: PropTypes.func.isRequired,
  /** Default type of sort button */
  defaultSortType: PropTypes.symbol,
  /** The data will be sorted */
  flattenedDict: PropTypes.array,
  /** unique id */
  uid: PropTypes.string,
};

export default DictButtonGroup;
