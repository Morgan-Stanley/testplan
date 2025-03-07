import React from "react";
import { render } from "@testing-library/react";
import { StyleSheetTestUtils } from "aphrodite";

import FixLogAssertion from "../FixLogAssertion";

function defaultProps() {
  return {
    assertion: {
      category: "DEFAULT",
      machine_time: "2019-02-12T17:41:43.314860+00:00",
      description: null,
      flattened_dict: [
        [0, 555, ""],
        [0, "", ""],
        [1, 624, ["int", "1"]],
        [1, 556, ["str", "USD"]],
        [0, "", ""],
        [1, 624, ["int", "2"]],
        [1, 556, ["str", "EUR"]],
        [0, 36, ["int", "6"]],
        [0, 38, ["int", "5"]],
        [0, 22, ["int", "5"]],
        [0, 55, ["int", "2"]],
      ],
      line_no: 688,
      meta_type: "entry",
      type: "FixLog",
      utc_time: "2019-02-12T17:41:43.314849+00:00",
    },
  };
}

const newSimpleProps = () => ({
  assertion: {
    type: "FixLog",
    meta_type: "entry",
    timestamp: 1741056209.060932,
    description: null,
    flattened_dict: [
      [36, ["int", 6]],
      [22, ["int", 5]],
      [55, ["int", 2]],
      [38, ["int", 5]],
      [555, ""],
      ["", ""],
      1,
      [556, ["str", "USD"]],
      [624, ["int", 1]],
      -1,
      ["", ""],
      1,
      [556, ["str", "EUR"]],
      [624, ["int", 2]],
    ],
  },
});

describe("FixLogAssertion", () => {
  let component;

  beforeEach(() => {
    // Stop Aphrodite from injecting styles, this crashes the tests.
    StyleSheetTestUtils.suppressStyleInjection();
  });

  it("renders the correct HTML structure with old format data", () => {
    component = render(<FixLogAssertion {...defaultProps()} />);
    expect(component.asFragment()).toMatchSnapshot();
    expect(component.getAllByText("624")).toHaveLength(2);
    expect(
      component
        .getByText("36")
        .compareDocumentPosition(component.getByText("38"))
    ).toEqual(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it("renders the correct HTML structure with new format data", () => {
    component = render(<FixLogAssertion {...newSimpleProps()} />);
    expect(component.asFragment()).toMatchSnapshot();
    expect(component.getAllByText("556")).toHaveLength(2);
    expect(
      component
        .getByText("55")
        .compareDocumentPosition(component.getByText("38"))
    ).toEqual(Node.DOCUMENT_POSITION_FOLLOWING);
  });
});
