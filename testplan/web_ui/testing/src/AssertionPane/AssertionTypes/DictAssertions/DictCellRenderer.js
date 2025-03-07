import React, { useState } from "react";
import PropTypes from "prop-types";
import Popover from "@material-ui/core/Popover";
import Typography from "@material-ui/core/Typography";
import { makeStyles } from "@material-ui/core/styles";
import { INDENT_MULTIPLIER } from "./../../../Common/defaults";

const useStyles = makeStyles((theme) => ({
  popover: {
    pointerEvents: "none",
  },
  paper: {
    padding: theme.spacing(1),
    maxWidth: "25em",
    overflowY: "hidden",
  },
  typography: {
    fontSize: "small",
  },
}));

/**
 * Custom cell renderer component used by DictLog and DictMatch assertions.
 *
 * It renders the cells with the following content:
 *
 * {icon} {mainText} {subText}
 *
 * Where:
 *  - icon is an info logo for custom,
 *  - mainText is the main data of the cell, it can be a key or a value,
 *  - subText is the type of the value in subscript and
 */
export default function DictCellRenderer(props) {
  const classes = useStyles();
  const [anchorEl, setAnchorEl] = useState(null);
  const open = Boolean(anchorEl);

  if (!props.value) {
    return null;
  }

  let mainText = props.value.value;
  let subText;
  let indentStyle = {};

  if (props.colDef.field === "key") {
    if (props.data.descriptor.isListKey && mainText) {
      subText = "list";
    }
    if (props.data.descriptor.indent) {
      const indent = props.data.descriptor.indent * INDENT_MULTIPLIER;
      indentStyle.marginLeft = `${indent}rem`;
    }
  } else {
    subText = props.value.type;
  }

  return (
    <div style={indentStyle}>
      <span
        style={{ userSelect: "all" }}
        onMouseEnter={(event) => {
          if (props.tooltip) {
            setAnchorEl(event.currentTarget);
          }
        }}
        onMouseLeave={() => {
          setAnchorEl(null);
        }}
      >
        {mainText}
      </span>
      <sub>{subText}</sub>
      <Popover
        id="mouse-over-popover"
        className={classes.popover}
        classes={{
          paper: classes.paper,
        }}
        open={open}
        anchorEl={anchorEl}
        anchorOrigin={{
          vertical: "bottom",
          horizontal: "right",
        }}
        transformOrigin={{
          vertical: "top",
          horizontal: "left",
        }}
        onClose={() => {
          setAnchorEl(null);
        }}
        disableRestoreFocus
      >
        <Typography className={classes.typography}>
          <>{props.tooltip}</>
        </Typography>
      </Popover>
    </div>
  );
}

DictCellRenderer.propTypes = {
  /** The meta info of current row. */
  data: PropTypes.object,
  /** The info logo for FIX keys, */
  icon: PropTypes.object,
  /** ID of the cell being rendered. */
  id: PropTypes.string,
  /** Function to call when mouse enters cell. */
  onMouseEnter: PropTypes.func,
  /** Function to call when mouse leaves cell. */
  onMouseLeave: PropTypes.func,
  /** Column field */
  colDef: PropTypes.object,
};
