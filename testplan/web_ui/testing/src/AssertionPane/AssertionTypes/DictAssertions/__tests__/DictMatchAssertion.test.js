import React from "react";
import { render } from "@testing-library/react";
import { StyleSheetTestUtils } from "aphrodite";

import DictMatchAssertion from "../DictMatchAssertion";

function defaultProps() {
  return {
    assertion: {
      category: "DEFAULT",
      machine_time: "2019-02-12T17:41:43.295236+00:00",
      description: "Simple dict match",
      comparison: [
        [0, "foo", "Passed", ["int", "1"], ["int", "1"]],
        [0, "bar", "Failed", ["int", "2"], ["int", "5"]],
        [0, "baz", "Ignored", ["int", "2"], ["int", "5"]],
        [0, "extra-key", "Failed", [null, "ABSENT"], ["int", "10"]],
      ],
      line_no: 524,
      expected_description: null,
      actual_description: null,
      meta_type: "assertion",
      include_keys: null,
      passed: false,
      exclude_keys: ["baz"],
      type: "DictMatch",
      utc_time: "2019-02-12T17:41:43.295231+00:00",
    },
  };
}

const newSimpleProps = () => ({
  assertion: {
    actual_description: null,
    comparison: [
      ["foo", "Passed", ["int", "1"], ["int", "1"]],
      ["bar", "Failed", ["int", "2"], ["int", "5"]],
      ["baz", "Ignored", ["int", "2"], ["int", "5"]],
      ["extra-key", "Failed", [null, "ABSENT"], ["int", "10"]],
    ],
    description: "simple dict match",
    exclude_keys: null,
    expected_description: null,
    include_keys: null,
    meta_type: "assertion",
    passed: false,
    timestamp: 1740990473.203493,
    type: "DictMatch",
  },
});

describe("DictMatchAssertion", () => {
  let component;

  beforeEach(() => {
    // Stop Aphrodite from injecting styles, this crashes the tests.
    StyleSheetTestUtils.suppressStyleInjection();
  });

  it("renders the correct HTML structure", () => {
    component = render(<DictMatchAssertion {...defaultProps()} />);
    expect(component.asFragment()).toMatchSnapshot();
  });

  it("renders the correct HTML structure with simple comparison", () => {
    component = render(<DictMatchAssertion {...newSimpleProps()} />);
    expect(component.asFragment()).toMatchSnapshot();
  });
});
