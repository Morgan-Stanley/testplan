import React, { useState } from "react";
import PropTypes from "prop-types";
import { StyleSheet, css } from "aphrodite";
import axios from "axios";
import _ from "lodash";
import { library } from "@fortawesome/fontawesome-svg-core";
import { faInfoCircle } from "@fortawesome/free-solid-svg-icons";

import DictCellRenderer from "./DictCellRenderer";
import { defaultFixSpec } from "./../../../Common/defaults";
import { RED, BLACK, MEDIUM_GREY, DARK_GREY } from "../../../Common/defaults";

library.add(faInfoCircle);

/**
 * Custom cell renderer component used by FixLog and FixMatch assertions.
 *
 * It renders the cells with the following content:
 *
 * {icon} {mainText} {subText}
 *
 * Where:
 *  - icon is an info logo for FIX keys,
 *  - mainText is the main data of the cell, it can be a key or a value,
 *  - subText is the type of the value in subscript and
 */
export default function FixCellRenderer(props) {
  if (!props.data) {
    return null;
  }

  const colField = props.colDef.field;
  const tagInfo = defaultFixSpec.tags[props.data.key.value];
  let toolTipComp = null;

  if (tagInfo) {
    if (colField === "key") {
      toolTipComp = (
        <FixTagTooltip names={tagInfo.names} descr={tagInfo.descr} />
      );
    } else if (tagInfo.enum_type) {
      if (colField === "value" && props.data.value) {
        toolTipComp = (
          <FixTagValueTooltip
            num={tagInfo.num}
            value={props.data.value.value}
          />
        );
      } else if (colField === "expected" && props.data.expected) {
        toolTipComp = (
          <FixTagValueTooltip
            num={tagInfo.num}
            value={props.data.expected.value}
          />
        );
      }
    }
  }

  return (
    <>
      <DictCellRenderer
        data={props.data}
        value={props.value}
        colDef={props.colDef}
        tooltip={toolTipComp}
      />
    </>
  );
}

FixCellRenderer.propTypes = {
  /** The meta info of current cell */
  data: PropTypes.object,
  /** The row index of the current cell */
  rowIndex: PropTypes.number,
  /** The Column definition of the current cell */
  colDef: PropTypes.object,
};

/**
 * Render a tooltip of a fix tag number.
 */
export const FixTagTooltip = (props) => {
  if (_.isEmpty(props.names) && _.isEmpty(props.descr)) {
    return null;
  }

  return (
    <>
      {props.names ? (
        <span className={css(styles.tooltipTitle)}>
          {props.names.join(" ")}
        </span>
      ) : null}
      {props.descr ? (
        <>
          <br />
          <span className={css(styles.tooltipDescription)}>{props.descr}</span>
        </>
      ) : null}
    </>
  );
};

/**
 * Render a tooltip of a fix tag value.
 */
export const FixTagValueTooltip = (props) => {
  const [content, setContent] = useState(null);

  if (content === null) {
    axios
      .get(`/api/v1/metadata/fix-spec/tags/${props.num}/enum-vals`)
      .then((response) => {
        const enum_vals = response.data;
        for (let i = 0; i < enum_vals.length; i++) {
          if (enum_vals[i].value === props.value.toString()) {
            setContent({
              text: enum_vals[i].descr || enum_vals[i].short_descr,
              style: css(styles.tooltipDescription),
            });
            return;
          }
        }
        setContent({
          text: "(No description)",
          style: css(styles.tooltipNoConent),
        });
      })
      .catch((err) => {
        setContent({
          text: "Failed to load description",
          style: css(styles.tooltipFailToLoad),
        });
      });
    return <span className={css(styles.tooltipLoading)}>{"Loading..."}</span>;
  } else {
    return <span className={content.style}>{content.text}</span>;
  }
};

FixTagTooltip.propTypes = {
  /** The tag names */
  names: PropTypes.arrayOf(PropTypes.string),
  /** The tag description */
  descr: PropTypes.string,
};

FixTagValueTooltip.propTypes = {
  /** The tag number */
  num: PropTypes.number,
  /** The tag number */
  value: PropTypes.string,
};

const styles = StyleSheet.create({
  tooltipTitle: {
    fontWeight: "bold",
    fontColor: BLACK,
  },
  tooltipDescription: {
    fontStyle: "normal",
    fontColor: BLACK,
  },
  tooltipNoConent: {
    fontStyle: "normal",
    fontColor: DARK_GREY,
  },
  tooltipLoading: {
    fontStyle: "italic",
    fontColor: MEDIUM_GREY,
  },
  tooltipFailToLoad: {
    fontStyle: "italic",
    fontColor: RED,
  },
});
