import React from "react";
import { render } from "@testing-library/react";
import { StyleSheetTestUtils } from "aphrodite";

import LogfileMatchAssertion from "../LogfileMatchAssertion";

function defaultProps() {
  return {
    assertion: {
      utc_time: "2020-01-01T00:00:00.000000+00:00",
      machine_time: "2020-01-01T00:00:00.000000+00:00",
      type: "LogfileMatch",
      meta_type: "assertion",
      category: "DEFAULT",
      passed: false,
      description: null,
      timeout: 2.0,
      results: [
        {
          matched: "okok",
          pattern: ".*ok.*",
          start_pos: "<BOF>",
          end_pos: "<inode 110000, position 5>",
        },
        {
          matched: "okok",
          pattern: ".*ok.*",
          start_pos: "<inode 110000, position 5>",
          end_pos: "<inode 110000, position 10>",
        },
      ],
      failure: [
        {
          matched: null,
          pattern: ".*ok.*",
          start_pos: "<inode 110000, position 10>",
          end_pos: "<inode 110000, position 15>",
        },
      ],
    },
  };
}

describe("LogfileMatchAssertion", () => {
  let props;
  let component;

  beforeEach(() => {
    // Stop Aphrodite from injecting styles, this crashes the tests.
    StyleSheetTestUtils.suppressStyleInjection();
    props = defaultProps();
    component = undefined;
  });

  it("renders the correct HTML structure", () => {
    component = render(<LogfileMatchAssertion {...props} />);
    expect(component.asFragment()).toMatchSnapshot();
  });
});
