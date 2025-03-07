import React from "react";
import { render } from "@testing-library/react";
import { StyleSheetTestUtils } from "aphrodite";

import DictLogAssertion from "../DictLogAssertion";

function defaultProps() {
  return {
    assertion: {
      category: "DEFAULT",
      machine_time: "2019-02-12T17:41:43.302500+00:00",
      description: null,
      flattened_dict: [
        [0, "baz", ["str", "hello world"]],
        [0, "foo", ""],
        [0, "", ["int", "1"]],
        [0, "", ["int", "2"]],
        [0, "", ["int", "3"]],
        [0, "bar", ""],
        [1, "color", ["str", "blue"]],
      ],
      line_no: 579,
      meta_type: "entry",
      type: "DictLog",
      utc_time: "2019-02-12T17:41:43.302494+00:00",
    },
  };
}

describe("DictLogAssertion", () => {
  let props;
  let component;

  beforeEach(() => {
    // Stop Aphrodite from injecting styles, this crashes the tests.
    StyleSheetTestUtils.suppressStyleInjection();
    props = defaultProps();
    component = undefined;
  });

  it("renders the correct HTML structure", () => {
    component = render(<DictLogAssertion {...props} />);
    expect(component.asFragment()).toMatchSnapshot();
  });
});
