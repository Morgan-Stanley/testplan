import React from 'react';
import PropTypes from 'prop-types';
import TreeView from '@material-ui/lab/TreeView';
import ExpandMoreIcon from '@material-ui/icons/ExpandMore';
import ChevronRightIcon from '@material-ui/icons/ChevronRight';
import TreeItem from '@material-ui/lab/TreeItem';
import { css, StyleSheet } from 'aphrodite';
import Column from './Column';
import NavEntry from './NavEntry';
import { applyAllFilters } from './navUtils';
import { STATUS, MEDIUM_GREY } from "../Common/defaults";
import { CATEGORIES } from "../Common/defaults";
import { generatePath } from 'react-router';
import { NavLink } from 'react-router-dom';
import TagList from './TagList';
import { makeStyles } from '@material-ui/core/styles';

const TreeViewNav = (props) => {
  return (
    <>
      <Column
        width={props.width}
        handleColumnResizing={props.handleColumnResizing}
      >
        <TreeView
          selected={
            props.selected
              ? props.selected[props.selected.length - 1].uids.join("/")
              : props.selectedUid
          }
          className={css(styles.treeView)}
          disableSelection={true}
          defaultCollapseIcon={<ExpandMoreIcon />}
          defaultExpandIcon={<ChevronRightIcon />}
        >
          {
            <Tree
              entries={props.entries}
              displayEmpty={props.displayEmpty}
              filter={props.filter}
              url={props.url}
              displayTags={props.displayTags}
              displayTime={props.displayTime}
            />
          }
        </TreeView>
      </Column>
    </>
  );
};


TreeViewNav.propTypes = {
  /** Nav list entries to be displayed */
  entries: PropTypes.arrayOf(PropTypes.shape({
    uid: PropTypes.string,
    name: PropTypes.string,
    description: PropTypes.string,
    status: PropTypes.oneOf(STATUS),
    counter: PropTypes.shape({
      passed: PropTypes.number,
      failed: PropTypes.number,
    }),
  })),
  /** Number of entries in the breadcrumb menu */
  breadcrumbLength: PropTypes.number,
  /** Function to handle Nav list resizing */
  handleColumnResizing: PropTypes.func,
  /** Entity filter */
  filter: PropTypes.string,
  /** Flag to display empty testcase on navbar */
  displayEmpty: PropTypes.bool,
  /** Flag to display tags on navbar */
  displayTags: PropTypes.bool,
  /** Flag to display execution time on navbar */
  displayTime: PropTypes.bool,
  /** Entry uid to be focused */
  selectedUid: PropTypes.string,

  url: PropTypes.string
};

export default TreeViewNav;

const Tree = (props) => {
  let entries = filterEntries(props.filter, props.entries, props.displayEmpty);
  return Array.isArray(entries) ?
    entries.map((entry) =>
      <Node
        key={entry.uids? entry.uids.join('/'): entry.hash || entry.uid}
        displayEmpty
        displayTags={props.displayTags}
        displayTime={props.displayTime}
        entries={props.entries}
        filter={props.filter}
        url={props.url}
        entry={entry}
      />) : null;
};

const filterEntries = (filter, entries, displayEmpty) => {
  let filteredEntries = applyAllFilters(filter, entries, displayEmpty);
  return filteredEntries.map(
    (entry) => filterEntriesOfEntry(entry, filter, displayEmpty));
};

const filterEntriesOfEntry = (entry, filter, displayEmpty) => {
  if (Array.isArray(entry.entries)) {
    let tmp = { entries: filterEntries(filter, entry.entries, displayEmpty) };
    return { ...entry, ...tmp };
  }
  return entry;
};

const Node = (props) => {
  let [reportuid, ...selectionuids] = props.entry.uids;
  const linkTo = generatePath(props.url,
    {
      uid: reportuid,
      selection: selectionuids
    });
  const tags = (
    (props.displayTags && props.entry.tags)
      ? <TagList entryName={props.entry.name} tags={props.entry.tags} />
      : null
  );
  const treeViewClasses = getTreeViewStyles();
  return (
    <TreeItem
      classes={{
        root: treeViewClasses.root,
        content: treeViewClasses.content,
        iconContainer: treeViewClasses.iconContainer,
        label: treeViewClasses.label
      }}
      nodeId={ props.entry.uids ? props.entry.uids.join('/') : props.entry.uid}
      key={props.entry.hash || props.entry.uid}
      onLabelClick={event => {
        event.preventDefault();
      }}
      label={
        <NavLink
          className={css(styles.leafNode)}
          key={props.entry.hash || props.entry.uid}
          to={linkTo}>
          {tags}
          {createNavEntry(props, props.entry)}
        </NavLink>
      }>
      {props.entry.category === CATEGORIES['testcase'] ?
        null : continueTreeBranch(props, props.entry)}
    </TreeItem>
  );
};

const continueTreeBranch = (props, entry) => {
  return Array.isArray(entry.entries) ?
    entry.entries.map((entry) =>
      <Node
        key={entry.uids? entry.uids.join('/'): entry.hash || entry.uid}
        displayEmpty
        displayTags={props.displayTags}
        displayTime={props.displayTime}
        entries={props.entries}
        filter={props.filter}
        url={props.url}
        entry={entry}
      />) : null;
};

const createNavEntry = (props, entry) => {
  return (
    <NavEntry
      name={entry.name}
      description={entry.description}
      status={entry.status}
      type={entry.category}
      caseCountPassed={entry.counter.passed}
      caseCountFailed={entry.counter.failed + (entry.counter.error || 0)}
      executionTime={(entry.timer && entry.timer.run) ? (
        (new Date(entry.timer.run.end)).getTime() -
        (new Date(entry.timer.run.start)).getTime()) : null}
      displayTime={props.displayTime} />
  );
};

const getTreeViewStyles = makeStyles({
  root: {
    "& > .MuiTreeItem-content": {
      paddingLeft: "5px",
      paddingRight: "5px",
    },
    "&.Mui-selected > .MuiTreeItem-content": {
      backgroundColor: MEDIUM_GREY
    },
    "&.Mui-selected > .MuiTreeItem-content > .MuiTreeItem-label": {
      backgroundColor: MEDIUM_GREY
    },
    "&.Mui-selected > .MuiTreeItem-content:hover > .MuiTreeItem-label": {
      backgroundColor: MEDIUM_GREY
    },
    '&:focus > .MuiTreeItem-content .MuiTreeItem-label': {
      backgroundColor: 'rgba(0,0,0,0)',
    },
    "&.Mui-selected > .MuiTreeItem-content .MuiTreeItem-label:hover, .MuiTreeItem-root.Mui-selected:focus > .MuiTreeItem-content .MuiTreeItem-label": { // eslint-disable-line max-len
      backgroundColor: MEDIUM_GREY
    },
  },

  content: {
    '&:hover': {
      backgroundColor: MEDIUM_GREY
    }
  },

  iconContainer: {
    cursor: 'pointer'
  },

  label: {
    padding: '5px 0px',
    overflow: 'hidden',
    '&:hover': {
      backgroundColor: MEDIUM_GREY
    }
  },
});

const styles = StyleSheet.create({
  treeView: {
    overflowY: 'auto',
    overflowX: 'hidden',
    height: '100%',
    "::-webkit-scrollbar": {
      width: "6px",
    },
    "::-webkit-scrollbar-thumb": {
      backgroundColor: "rgba(0, 0, 0, 0.2)",
      borderRadius: "3px",
    },
    "::-webkit-scrollbar-thumb:hover": {
      backgroundColor: "rgba(0, 0, 0, 0.4)",
    }
  },
  
  leafNode: {
    textDecoration: 'none',
    color: '#495057'
  }
});