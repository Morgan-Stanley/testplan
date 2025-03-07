import React from "react";
import { render } from "@testing-library/react";
import { MemoryRouter, Route } from "react-router-dom";
import { StyleSheetTestUtils } from "aphrodite";

import TableLogAssertion from "../TableLogAssertion";

function defaultProps() {
  return {
    assertion: {
      category: "DEFAULT",
      machine_time: "2019-02-12T17:41:43.241786+00:00",
      description: "Table Log: list of dicts",
      line_no: 472,
      display_index: false,
      meta_type: "entry",
      columns: ["age", "name"],
      indices: [0, 1, 2],
      table: [
        [32, "Bob"],
        [24, "Susan"],
        [67, "Rick"],
      ],
      type: "TableLog",
      utc_time: "2019-02-12T17:41:43.241777+00:00",
    },
  };
}

function advancedTableProps() {
  return {
    assertion: {
      flag: "DEFAULT",
      machine_time: "2021-06-25T16:06:10.622340+00:00",
      line_no: 92,
      display_index: false,
      description: "table log assertion",
      table: [
        [
          "External Link",
          {
            link: "https://www.google.com",
            title: "Google",
            new_window: true,
            inner: false,
            type: "link",
          },
        ],
        [
          "Internal Link",
          {
            link: "/",
            title: "Home",
            new_window: true,
            inner: true,
            type: "link",
          },
        ],
        [
          "Formatted Value - 0.6",
          {
            value: 0.6,
            display: "60%",
            type: "formattedValue",
          },
        ],
        [
          "Formatted Value - 0.08",
          {
            value: 0.08,
            display: "8%",
            type: "formattedValue",
          },
        ],
      ],
      columns: ["Description", "Data"],
      meta_type: "entry",
      category: "DEFAULT",
      type: "TableLog",
      indices: [0, 1, 2, 3],
      utc_time: "2021-06-25T08:06:10.622331+00:00",
    },
  };
}

const newProps = () => ({
  assertion: {
    type: "TableLog",
    meta_type: "entry",
    timestamp: 1741061226.285205,
    description: "Table Log: list of dicts",
    table: [
      ["Bob", 32],
      ["Susan", 24],
      ["Rick", 67],
    ],
    display_index: true,
    columns: ["name", "age"],
  },
});

describe("TableLogAssertion", () => {
  let component;

  beforeEach(() => {
    // Stop Aphrodite from injecting styles, this crashes the tests.
    StyleSheetTestUtils.suppressStyleInjection();
    component = undefined;
  });

  it("renders the table log HTML structure", () => {
    let props = defaultProps();
    component = render(<TableLogAssertion {...props} />);
    expect(component.asFragment()).toMatchSnapshot();
  });

  it("renders the advanced table log HTML structure", () => {
    let props = advancedTableProps();
    // since we call useParams when rendering relative link
    component = render(
      <MemoryRouter initialEntries={["/testplan/dummy_uid"]}>
        <Route path="/testplan/:uid">
          <TableLogAssertion {...props} />
        </Route>
      </MemoryRouter>
    );
    expect(component.asFragment()).toMatchSnapshot();
    expect(
      component.getByText("Home").closest("a").getAttribute("href")
    ).toEqual("/testplan/dummy_uid/");
  });

  it("renders the table log HTML structure given new format assertion", () => {
    component = render(<TableLogAssertion {...newProps()} />);
    expect(component.asFragment()).toMatchSnapshot();
  });
});
