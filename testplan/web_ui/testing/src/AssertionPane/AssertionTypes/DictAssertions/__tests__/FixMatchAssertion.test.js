import React from "react";
import { render } from "@testing-library/react";
import { StyleSheetTestUtils } from "aphrodite";

import FixMatchAssertion from "../FixMatchAssertion";

function defaultProps() {
  return {
    assertion: {
      category: "DEFAULT",
      machine_time: "2019-02-12T17:41:43.309890+00:00",
      description: null,
      comparison: [
        [0, 555, "Failed", "", ""],
        [0, "", "Failed", "", ""],
        [1, 600, "Passed", ["str", "A"], ["str", "A"]],
        [1, 601, "Failed", ["str", "A"], ["str", "B"]],
        [1, 683, "Passed", "", ""],
        [1, "", "Passed", "", ""],
        [2, 688, "Passed", ["str", "a"], ["str", "a"]],
        [2, 689, "Passed", ["str", "a"], ["REGEX", "[a-z]"]],
        [1, "", "Passed", "", ""],
        [2, 688, "Passed", ["str", "b"], ["str", "b"]],
        [2, 689, "Passed", ["str", "b"], ["str", "b"]],
        [0, "", "Failed", "", ""],
        [1, 600, "Failed", ["str", "B"], ["str", "C"]],
        [1, 601, "Passed", ["str", "B"], ["str", "B"]],
        [1, 683, "Passed", "", ""],
        [1, "", "Passed", "", ""],
        [2, 688, "Passed", ["str", "c"], ["str", "c"]],
        [2, 689, "Passed", ["str", "c"], ["func", "VAL in ('c', 'd')"]],
        [1, "", "Passed", "", ""],
        [2, 688, "Passed", ["str", "d"], ["str", "d"]],
        [2, 689, "Passed", ["str", "d"], ["str", "d"]],
        [0, 36, "Passed", ["int", "6"], ["int", "6"]],
        [0, 38, "Passed", ["int", "5"], ["func", "VAL >= 4"]],
        [0, 22, "Passed", ["int", "5"], ["int", "5"]],
        [0, 55, "Passed", ["int", "2"], ["int", "2"]],
      ],
      line_no: 667,
      expected_description: null,
      actual_description: null,
      meta_type: "assertion",
      include_keys: null,
      passed: false,
      exclude_keys: null,
      type: "FixMatch",
      utc_time: "2019-02-12T17:41:43.309884+00:00",
    },
  };
}

describe("FixMatchAssertion", () => {
  let props;
  let component;

  beforeEach(() => {
    // Stop Aphrodite from injecting styles, this crashes the tests.
    StyleSheetTestUtils.suppressStyleInjection();
    props = defaultProps();
    component = undefined;
  });

  it("renders the correct HTML structure", () => {
    component = render(<FixMatchAssertion {...props} />);
    expect(component.asFragment()).toMatchSnapshot();
  });
});
