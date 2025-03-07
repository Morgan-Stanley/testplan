import { useState } from "react";
import PropTypes from "prop-types";
import { css, StyleSheet } from "aphrodite";
import { CardHeader, Tooltip } from "reactstrap";
import { library } from "@fortawesome/fontawesome-svg-core";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faLayerGroup,
  faTimes,
  faInfo,
  faCheck,
} from "@fortawesome/free-solid-svg-icons";
import Button from "@material-ui/core/Button";
import Linkify from "linkify-react";
import _ from "lodash";
import { getWorkspacePath } from "../Common/utils";

library.add(faLayerGroup);

const STATUS_ICONS = {
  false: faTimes,
  true: faCheck,
  undefined: faInfo,
};

/**
 * Header component of an assertion.
 */
function AssertionHeader({
  assertion,
  displayPath,
  uid,
  toggleExpand,
  showStatusIcons,
}) {
  const [isUTCTooltipOpen, setIsUTCTooltipOpen] = useState(false);
  const [isPathTooltipOpen, setIsPathTooltipOpen] = useState(false);
  const [isDurationTooltipOpen, setIsDurationTooltipOpen] = useState(false);
  const [is1LinerTooltipOpen, setIs1LinerTooltipOpen] = useState(false);

  /**
   * Toggle the visibility of tooltip of file path.
   */
  const togglePathTooltip = () => {
    setIsPathTooltipOpen(!isPathTooltipOpen);
  };

  /**
   * Toggle the visibility of tooltip of assertion start time.
   */
  const toggleUTCTooltip = () => {
    setIsUTCTooltipOpen(!isUTCTooltipOpen);
  };

  /**
   * Toggle the visibility of tooltip of duration between assertions.
   */
  const toggleDurationTooltip = () => {
    setIsDurationTooltipOpen(!isDurationTooltipOpen);
  };

  /**
   * Toggle the visibility of tooltip of duration between assertions.
   */
  const toggle1LinerTooltip = () => {
    setIs1LinerTooltipOpen(!is1LinerTooltipOpen);
  };

  const cardHeaderColorStyle =
    assertion.passed === undefined
      ? styles.cardHeaderColorLog
      : assertion.passed
      ? styles.cardHeaderColorPassed
      : styles.cardHeaderColorFailed;

  const timeInfoArray = assertion.timeInfoArray || [];
  let component =
    _.isEmpty(assertion.utc_time) && !_.isNumber(assertion.timestamp) ? (
      <span className={css(styles.cardHeaderAlignRight)}>
        <FontAwesomeIcon // Should be a nested assertion group
          size="sm"
          key="faLayerGroup"
          icon="layer-group"
          className={css(styles.icon)}
        />
      </span>
    ) : timeInfoArray.length === 0 ? (
      <span className={css(styles.cardHeaderAlignRight)}></span>
    ) : (
      <>
        <span
          className={css(
            styles.cardHeaderAlignRight,
            styles.timeInfo,
            styles.button
          )}
          onClick={toggleExpand}
          id={`tooltip_duration_${timeInfoArray[0]}`}
          style={{ order: 3, display: "inline-flex", alignItems: "center" }}
        >
          {timeInfoArray[2]}
        </span>
        <span
          className={css(styles.cardHeaderAlignRight, styles.button)}
          onClick={toggleExpand}
          style={{ order: 2 }}
        >
          &nbsp;&nbsp;
        </span>
        <span
          className={css(
            styles.cardHeaderAlignRight,
            styles.timeInfo,
            styles.button
          )}
          onClick={toggleExpand}
          id={`tooltip_utc_${timeInfoArray[0]}`}
          style={{ order: 1, display: "inline-flex", alignItems: "center" }}
        >
          {timeInfoArray[1]}
        </span>
        <span className={css(styles.cardHeaderAlignRight)} style={{ order: 5 }}>
          &nbsp;&nbsp;
        </span>
        <Tooltip
          placement="bottom"
          isOpen={isUTCTooltipOpen}
          target={`tooltip_utc_${timeInfoArray[0]}`}
          toggle={toggleUTCTooltip}
        >
          {"Assertion start time"}
        </Tooltip>
        <Tooltip
          placement="bottom"
          isOpen={isDurationTooltipOpen}
          target={`tooltip_duration_${timeInfoArray[0]}`}
          toggle={toggleDurationTooltip}
        >
          {"Time elapsed since last assertion"}
        </Tooltip>
      </>
    );

  const pathButton =
    assertion.file_path && assertion.line_no ? (
      <>
        <Button
          className={css(styles.pathButton)}
          onClick={() => {
            navigator.clipboard.writeText(getPath(assertion));
          }}
        >
          <span
            id={`tooltip_path_${uid}`}
            className={css(cardHeaderColorStyle)}
          >
            {renderPath(assertion)}
          </span>
        </Button>
        <Tooltip
          isOpen={isPathTooltipOpen}
          target={`tooltip_path_${uid}`}
          toggle={togglePathTooltip}
          style={{ maxWidth: "400px" }}
        >
          {getPath(assertion)}
        </Tooltip>
        <br></br>
      </>
    ) : (
      <></>
    );

  const oneLiner = assertion?.code_context ? (
    <>
      <span
        id={`tooltip_1liner_${uid}`}
        className={css(styles.cardHeader1liner)}
      >
        {assertion.code_context}
      </span>
      <Tooltip
        isOpen={is1LinerTooltipOpen}
        target={`tooltip_1liner_${uid}`}
        toggle={toggle1LinerTooltip}
        style={{ maxWidth: "400px" }}
      >
        {assertion.code_context}
      </Tooltip>
    </>
  ) : (
    <></>
  );

  const codeContext = displayPath ? (
    <>
      <div
        className={css(
          styles.cardHeaderCode,
          styles.cardHeaderAlignRight,
          styles.timeInfo
        )}
        style={{ order: 6, marginLeft: "10px" }}
      >
        <span>
          {pathButton}
          {oneLiner}
        </span>
      </div>
    </>
  ) : (
    <></>
  );

  const description = assertion.description ? (
    assertion.type === "Log" ? (
      <Linkify
        options={{
          target: "_blank",
          validate: {
            url: (value) => /^https?:\/\//.test(value),
          },
        }}
      >
        {assertion.description}
      </Linkify>
    ) : (
      assertion.description + " "
    )
  ) : (
    ""
  );

  const statusIcon = showStatusIcons ? (
    <span className={css(styles.statusIcon)}>
      <FontAwesomeIcon
        title={assertion.passed ? "passed" : "failed"}
        size="sm"
        icon={STATUS_ICONS[assertion.passed]}
        className={css(styles.icon)}
      />
    </span>
  ) : null;

  return (
    <CardHeader className={css(styles.cardHeader, cardHeaderColorStyle)}>
      <div style={{ display: "flex" }}>
        <span
          className={css(styles.button)}
          onClick={toggleExpand}
          style={{
            order: 4,
            flexGrow: 4,
            padding: ".125rem 0.75rem",
            display: "flex",
            alignItems: "center",
            ...assertion.custom_style,
          }}
        >
          {statusIcon}
          <span style={{ fontWeight: "bold" }}>{description}</span>
          <span>({assertion.type})</span>
        </span>
        {component}
        {codeContext}
        {/*
          TODO will be implemented when complete permalink feature
          linkIcon
        */}
      </div>
    </CardHeader>
  );
}

AssertionHeader.propTypes = {
  /** Assertion being rendered */
  assertion: PropTypes.object,
  /** whether to display code context info */
  displayPath: PropTypes.bool,
  /** parent's (testcase's) uid */
  uid: PropTypes.string,
  /** triggered callback when clicking header */
  toggleExpand: PropTypes.func,
  /** whether to display status icon */
  showStatusIcons: PropTypes.bool,
};

const renderPath = (assertion) => {
  if (assertion.file_path && assertion.line_no) {
    return (
      <>
        <span className={css(styles.icon)}>
          <i className="fa fa-copy fa-s"></i>
        </span>
        <div className={css(styles.cardHeaderPath)}>
          <span className={css(styles.cardHeaderPathInner)}>
            {getWorkspacePath(getPath(assertion))}
          </span>
        </div>
      </>
    );
  }
  return null;
};

const getPath = (assertion) => {
  if (assertion.file_path && assertion.line_no) {
    return assertion.file_path + ":" + assertion.line_no;
  }
  return null;
};

const styles = StyleSheet.create({
  cardHeader: {
    padding: "0",
    fontSize: "small",
    lineHeight: 1.75,
    backgroundColor: "rgba(0,0,0,0)", // Move to defaults?
    borderBottom: "1px solid",
  },

  button: {
    cursor: "pointer",
  },

  cardHeaderColorLog: {
    borderBottomColor: "#000000", // Move to defaults?
    color: "#000000", // Move to defaults?
  },

  cardHeaderColorPassed: {
    borderBottomColor: "#28a745", // Move to defaults
    color: "#28a745", // Move to defaults
  },

  cardHeaderColorFailed: {
    borderBottomColor: "#dc3545", // Move to defaults
    color: "#dc3545", // Move to defaults
  },

  cardHeaderAlignRight: {
    float: "right",
  },

  timeInfo: {
    padding: "2px 0px",
  },

  cardHeaderPath: {
    float: "right",
    //fontSize: "smaller",
    maxWidth: "400px",
    "-webkit-line-clamp": 1,
    "-webkit-box-orient": "vertical",
    "white-space": "nowrap",
    direction: "rtl",
    overflow: "hidden",
    textOverflow: "ellipsis",
    textTransform: "none",
  },

  cardHeader1liner: {
    float: "right",
    maxWidth: "400px",
    "-webkit-line-clamp": 1,
    "-webkit-box-orient": "vertical",
    "white-space": "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
    textTransform: "none",
  },

  pathButton: {
    padding: "0px",
    fontFamily: "inherit",
    fontSize: "inherit",
    lineHeight: "0.8rem",
    letterSpacing: "normal",
  },

  cardHeaderPathInner: {
    unicodeBidi: "plaintext",
  },

  cardHeaderCode: {
    display: "flex",
    alignItems: "center",
    textAlign: "right",
    whiteSpace: "pre-wrap",
    fontFamily: "monospace",
    opacity: "80%",
    lineHeight: "0.8rem",
  },

  collapseDiv: {
    paddingLeft: "1.25rem",
  },

  icon: {
    margin: "0rem .25rem 0rem 0rem",
  },
  statusIcon: {
    display: "inline-flex",
    width: "1rem",
    justifyContent: "center",
  },
});

export default AssertionHeader;
