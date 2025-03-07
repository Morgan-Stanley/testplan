import React from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { css, StyleSheet } from "aphrodite";

const LogfileMatchEntry = ({ pattern, startPos, endPos, matched }) => {
  const info = matched
    ? `Match between ${startPos} and ${endPos} found.`
    : `No match from ${startPos} found, search ended at ${endPos}`;

  return (
    <>
      <div>
        <span className={css(styles.infoText)}>{info}</span>
      </div>
      <div>
        <strong className={css(styles.title)}>Pattern:</strong>
        <SyntaxHighlighter
          language="regex"
          PreTag="span"
          customStyle={{ padding: 0 }}
        >
          {pattern}
        </SyntaxHighlighter>
      </div>
      {matched ? (
        <div>
          <strong className={css(styles.title)}>Log Line:</strong>
          <span className={css(styles.inputText)}>{matched}</span>
        </div>
      ) : null}
    </>
  );
};

const LogfileMatchAssertion = ({ assertion }) => {
  const { timeout, results, failure } = assertion;

  const timeoutMsg =
    (assertion.passed ? "Passed" : "Failed") +
    (timeout === 0 ? " when scanning till <EOF>." : ` in ${timeout} seconds.`);
  const entries = [...results, ...failure].map((entry, index) => {
    const { matched, pattern, start_pos: startPos, end_pos: endPos } = entry;
    return (
      <LogfileMatchEntry
        key={`logmatch${index}`}
        matched={matched}
        pattern={pattern}
        startPos={startPos}
        endPos={endPos}
      />
    );
  });

  return (
    <>
      <div>
        <span>
          <b>{timeoutMsg}</b>
        </span>
      </div>
      {entries}
    </>
  );
};

const styles = StyleSheet.create({
  infoText: {
    padding: 0,
    lineHeight: "1.1",
    fontWeight: "bold",
  },
  inputText: {
    paddingTop: "1em",
    marginBottom: "0",
  },
  title: {
    paddingRight: "0.5em",
  },
});

export default LogfileMatchAssertion;
