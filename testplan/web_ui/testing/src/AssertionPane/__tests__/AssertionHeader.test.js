import React from "react";
import { render } from "@testing-library/react";
import { StyleSheetTestUtils } from "aphrodite";

import AssertionHeader from "../AssertionHeader";

const props = {
  assertion: {
    utc_time: "2024-12-24T09:35:56.113946+00:00",
    machine_time: "2024-12-24T17:35:56.113951+08:00",
    type: "Equal",
    meta_type: "assertion",
    description: "soda water == soda water",
    line_no: 26,
    category: "DEFAULT",
    flag: "DEFAULT",
    file_path: "/dummy/examples/Driver/Dependency/suites.py",
    passed: true,
    first: "soda water",
    second: "soda water",
    label: "==",
    type_actual: "str",
    type_expected: "str",
  },
  displayPath: false,
  uid: "c260c2af-888a-4853-86b2-82a14f44066e", // generated
  toggleExpand: jest.fn(),
  showStatusIcons: false,
};

describe("AssertionHeader", () => {
  let component;

  beforeEach(() => {
    // Stop Aphrodite from injecting styles, this crashes the tests.
    StyleSheetTestUtils.suppressStyleInjection();
  });

  it("renders the correct HTML structure", () => {
    component = render(<AssertionHeader {...props} />);
    expect(component.getByText(props.assertion.description)).toBeDefined();
    expect(component.asFragment()).toMatchSnapshot();
  });

  it("renders the correct HTML structure with status icons enabled", () => {
    component = render(
      <AssertionHeader {...{ ...props, showStatusIcons: true }} />
    );
    expect(
      component.container.querySelector("svg").getAttribute("data-icon")
    ).toEqual("check");
    expect(component.asFragment()).toMatchSnapshot();
  });

  it("renders the correct HTML structure with code context enabled", () => {
    component = render(
      <AssertionHeader {...{ ...props, displayPath: true }} />
    );
    expect(
      component.getByText(props.assertion.file_path, { exact: false })
    ).toBeDefined();
    expect(component.asFragment()).toMatchSnapshot();
  });
});
