import React from "react";
import { render } from "@testing-library/react";
import { StyleSheetTestUtils } from "aphrodite";

import { SORT_TYPES, FILTER_OPTIONS } from "./../../../../Common/defaults";
import DictButtonGroup from "../DictButtonGroup";

function defaultProps() {
  return {
    uid: "sort-test-uid",
    defaultSortType: SORT_TYPES.BY_STATUS,
    sortTypeList: [
      SORT_TYPES.NONE,
      SORT_TYPES.ALPHABETICAL,
      SORT_TYPES.REVERSE_ALPHABETICAL,
      SORT_TYPES.BY_STATUS,
    ],
    filterOptionList: [
      FILTER_OPTIONS.FAILURES_ONLY,
      FILTER_OPTIONS.EXCLUDE_IGNORABLE,
    ],
    flattenedDict: [
      [0, "foo", "Passed", ["int", "1"], ["int", "1"]],
      [0, "bar", "Failed", ["int", "2"], ["int", "5"]],
      [0, "extra-key", "Failed", [null, "ABSENT"], ["int", "10"]],
    ],
    setRowData: jest.fn(),
  };
}

describe("DictLogAssertion", () => {
  let props;
  let component;

  beforeEach(() => {
    // Stop Aphrodite from injecting styles, this crashes the tests.
    StyleSheetTestUtils.suppressStyleInjection();
    props = {};
    component = undefined;
  });

  it("renders DictButtonGroup component", () => {
    props = defaultProps();
    component = render(<DictButtonGroup {...props} />);
    expect(component.asFragment()).toMatchSnapshot();
  });
});
