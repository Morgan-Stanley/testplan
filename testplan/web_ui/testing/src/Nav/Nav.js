import React from "react";
import PropTypes from "prop-types";
import NavList from "./NavList";
import TreeViewNav from "./TreeView";
import {
  GetSelectedUid,
  GetNavEntries,
  GetInteractiveNavEntries,
} from "./navUtils";
import { useAtomValue } from "jotai";
import {
  hideEmptyTestcasesPreference,
  hideSkippedTestcasesPreference,
  useTreeViewPreference,
} from "../UserSettings/UserSettings";

/**
 * Nav component:
 *   * render breadcrumbs menu.
 *   * render list menu.
 *   * handle clicking through menus, tracking what has been selected.
 *   * auto select entries if the list is empty or has 1 entry.
 *   * Adds extra buttons for running testcases interactively and controlling
 *     environments.
 */
const Nav = (props) => {
  const useTreeView = useAtomValue(useTreeViewPreference);
  const displayEmpty = !useAtomValue(hideEmptyTestcasesPreference);
  const displaySkipped = !useAtomValue(hideSkippedTestcasesPreference);

  if (useTreeView && !props.interactive) {
    const navEntries = props.report ? props.report.entries : [];
    return (
      <TreeViewNav
        interactive={false}
        width={props.navListWidth}
        entries={navEntries}
        handleColumnResizing={props.handleColumnResizing}
        filter={props.filter}
        displayEmpty={displayEmpty}
        displaySkipped={displaySkipped}
        displayTags={props.displayTags}
        displayTime={props.displayTime}
        selected={props.selected}
        selectedUid={GetSelectedUid(props.selected)}
        url={props.url}
      />
    );
  } else if (!useTreeView && !props.interactive) {
    const navEntries = GetNavEntries(props.selected);
    return (
      <NavList
        interactive={false}
        width={props.navListWidth}
        entries={navEntries}
        handleColumnResizing={props.handleColumnResizing}
        filter={props.filter}
        displayEmpty={displayEmpty}
        displaySkipped={displaySkipped}
        displayTags={props.displayTags}
        displayTime={props.displayTime}
        selectedUid={GetSelectedUid(props.selected)}
        handleClick={props.handleClick}
        envCtrlCallback={props.envCtrlCallback}
        url={props.url}
      />
    );
  } else if (useTreeView && props.interactive) {
    const navEntries = props.report ? props.report.entries : [];
    return (
      <TreeViewNav
        interactive={true}
        width={props.navListWidth}
        entries={navEntries}
        handleColumnResizing={props.handleColumnResizing}
        filter={null}
        displayEmpty={true}
        displaySkipped={true}
        displayTags={false}
        displayTime={props.displayTime}
        selected={props.selected}
        selectedUid={GetSelectedUid(props.selected)}
        handleClick={props.handleClick}
        envCtrlCallback={props.envCtrlCallback}
        url={props.url}
      />
    );
  } else if (!useTreeView && props.interactive) {
    const navEntries = GetInteractiveNavEntries(props.selected);
    return (
      <NavList
        interactive={true}
        width={props.navListWidth}
        entries={navEntries}
        handleColumnResizing={props.handleColumnResizing}
        filter={null}
        displayEmpty={true}
        displaySkipped={true}
        displayTags={false}
        displayTime={props.displayTime}
        selectedUid={GetSelectedUid(props.selected)}
        handleClick={props.handleClick}
        envCtrlCallback={props.envCtrlCallback}
        url={props.url}
      />
    );
  }
};

Nav.propTypes = {
  /** Interactive mode flag */
  interactive: PropTypes.bool,
  /** Testplan report */
  report: PropTypes.object,
  /** Selected navigation entries. */
  selected: PropTypes.arrayOf(PropTypes.object),
  /** Function to handle saving the assertions found by the Nav */
  saveAssertions: PropTypes.func,
  /** Entity filter */
  filter: PropTypes.string,
  /** Flag to display tags on navbar */
  displayTags: PropTypes.bool,
  /** Flag to display execution time on navbar */
  displayTime: PropTypes.bool,
  /** Flag to display empty testcase on navbar */
  displayEmpty: PropTypes.bool,

  url: PropTypes.string,
};

export default Nav;
