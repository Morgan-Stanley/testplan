/**
 * Common utility functions.
 */
import { NAV_ENTRY_DISPLAY_DATA, EXPAND_STATUS, VIEW_TYPE } from "./defaults";
import JSON5 from "json5";
import _ from "lodash";

/**
 * Calculate execution time of an entry with timer field
 */
function calcExecutionTime(entry) {
  let elapsed = null;
  if (entry.timer && entry.timer.run) {
    elapsed = 0;
    entry.timer.run.forEach((interval) => {
      elapsed +=
        timeToTimestamp(interval.end) - timeToTimestamp(interval.start);
    });
  }
  return elapsed;
}

/**
 * Calculate elapsed time of a timer field
 */
function calcElapsedTime(timerField) {
  let elapsed = null;
  if (timerField && Array.isArray(timerField) && !_.isEmpty(timerField)) {
    elapsed = 0;
    timerField.forEach((interval) => {
      elapsed +=
        timeToTimestamp(interval.end) - timeToTimestamp(interval.start);
    });
  }
  return elapsed < 0 ? null : elapsed;
}

/**
 * Convert string (old) / float (new) to timestamp.
 *
 * @param {object|string} time
 * @returns {number}
 */
function timeToTimestamp(time) {
  return typeof time === "string"
    ? new Date(time).getTime()
    : typeof time === "number"
    ? time * 1000
    : time;
}

/**
 * Get the data to be used when displaying the nav entry.
 *
 * @param {object} entry - nav entry.
 * @returns {Object}
 */
function getNavEntryDisplayData(entry) {
  let metadata = {};
  for (const attribute of NAV_ENTRY_DISPLAY_DATA) {
    if (entry.hasOwnProperty(attribute)) {
      metadata[attribute] = entry[attribute];
    }
  }
  return metadata;
}

/**
 * Returns true of any element of an iterable is true. If not, returns false.
 *
 * @param iterable
 * @returns {boolean}
 */
function any(iterable) {
  for (let index = 0; index < iterable.length; ++index) {
    if (iterable[index]) return true;
  }

  return false;
}

/**
 * Returns a sorted array of the given iterable.
 *
 * @param iterable
 * @param {function} key - function that serves as a key for the sort comparison
 * @param {boolean} reverse - if true, the sorted list is reversed
 * @returns {Array}
 */
function sorted(iterable, key = (item) => item, reverse = false) {
  return iterable.sort((firstMember, secondMember) => {
    let reverser = reverse ? 1 : -1;

    return key(firstMember) < key(secondMember)
      ? reverser
      : key(firstMember) > key(secondMember)
      ? reverser * -1
      : 0;
  });
}

/**
 * Creates a string that can be used for dynamic id attributes
 * Example: "id-so7567s1pcpojemi"
 * @returns {string}
 */
function uniqueId() {
  return "id-" + Math.random().toString(36).substr(2, 16);
}

/**
 * Generate a hash code by string
 * @param {string} str - string that generate hash code
 * @returns {number}
 */
function hashCode(str) {
  var hash = 0,
    i,
    chr,
    len;
  if (str.length === 0) return hash;
  for (i = 0, len = str.length; i < len; i++) {
    chr = str.charCodeAt(i);
    hash = (hash << 5) - hash + chr;
    hash |= 0; // Convert to 32bit integer
  }
  return hash;
}

/**
 * Get the string representation of a HTML DOM node
 * @param {object} dom - HTML DOM node
 * @returns {string}
 */
function domToString(dom) {
  let tmp = document.createElement("div");
  tmp.appendChild(dom);
  return tmp.innerHTML;
}

/**
 * Get encoded URI Component from an an encoded URI Component
 * @param {string} uid - string to be encoded
 * @returns {string}
 */
function encodeURIComponent2(str) {
  return encodeURIComponent(encodeURIComponent(str));
}

/**
 * Same as {@link formatMilliseconds} but the input is in seconds
 * @param {number} durationInSeconds
 * @returns {string}
 */
function formatSeconds(durationInSeconds) {
  let durationInMilliseconds = durationInSeconds * 1000;
  return formatMilliseconds(durationInMilliseconds);
}

/**
 * Formats the input number representing milliseconds into a string
 * with format H:m:s.SSS. Each value is displayed only if it is greater
 * than 0 or the previous value has been displayed.
 * @param {number} durationInMilliseconds
 * @returns {string}
 */
function formatMilliseconds(durationInMilliseconds) {
  if (!_.isNumber(durationInMilliseconds)) {
    return "na";
  }

  let secondsInMilliseconds = durationInMilliseconds % 60000;
  let seconds = secondsInMilliseconds / 1000;
  let minutesInMilliseconds =
    (durationInMilliseconds - secondsInMilliseconds) / 60000;
  let minutes = minutesInMilliseconds % 60;
  let hours = (minutesInMilliseconds - minutes) / 60;

  const isDisplayedHours = hours > 0;
  const isDisplayedMinutes = isDisplayedHours || minutes > 0;

  let hoursDisplay = isDisplayedHours ? hours + "h" : "";
  let minutesDisplay = isDisplayedMinutes ? minutes + "m" : "";
  let secondsDisplay = seconds.toFixed(3) + "s";

  return (
    [hoursDisplay, minutesDisplay, secondsDisplay].filter(Boolean).join(" ") ||
    "0s"
  );
}

/**
 * Formats the input number representing milliseconds into a string
 * with format H:m:s.SSS. Each value is displayed only if it is greater
 * than 0 or the previous value has been displayed.
 * @param {number} durationInMilliseconds
 * @returns {string}
 */
function formatShortDuration(durationInMilliseconds) {
  if (!_.isNumber(durationInMilliseconds)) {
    return "na";
  }

  durationInMilliseconds = _.round(durationInMilliseconds, -2);

  let secondsInMilliseconds = durationInMilliseconds % 60000;
  let seconds = secondsInMilliseconds / 1000;
  let minutesInMilliseconds =
    (durationInMilliseconds - secondsInMilliseconds) / 60000;
  let minutes = minutesInMilliseconds % 60;
  let hours = (minutesInMilliseconds - minutes) / 60;

  const isDisplayedHours = hours > 0;
  const isDisplayedMinutes = minutes > 0;
  const isDisplayedSeconds = seconds > 0 && !isDisplayedHours;
  const isDisplayedMilliseconds = isDisplayedSeconds && !isDisplayedMinutes;

  let hoursDisplay = isDisplayedHours ? hours + "h" : "";
  let minutesDisplay = isDisplayedMinutes ? minutes + "m" : "";
  let secondsDisplay = isDisplayedSeconds
    ? isDisplayedMilliseconds
      ? seconds.toFixed(1) + "s"
      : seconds.toFixed(0) + "s"
    : null;

  return (
    [hoursDisplay, minutesDisplay, secondsDisplay].filter(Boolean).join(":") ||
    "0s"
  );
}

export {
  calcExecutionTime,
  calcElapsedTime,
  timeToTimestamp,
  getNavEntryDisplayData,
  any,
  sorted,
  uniqueId,
  hashCode,
  domToString,
  encodeURIComponent2,
  formatSeconds,
  formatMilliseconds,
  formatShortDuration,
};

/**
 * Reverses a Map.
 * @template T, U
 * @param {Map<T, U>} aMap - The map to reverse
 * @returns {Map<U, T>}
 */
export const reverseMap = (aMap) =>
  new Map(Array.from(aMap).map(([newVal, newKey]) => [newKey, newVal]));

export const isNonemptyArray = (x) => Array.isArray(x) && x.length;

export const unindent = (strArr, ...tagsArr) =>
  strArr
    .slice(1)
    .reduce((acc, str, i) => {
      return `${acc}${`${tagsArr[i]}${str}`.replace(/^\s+/gm, "")}`;
    }, strArr[0])
    .trimLeft();

export const flattened = (strArr, ...tagsArr) => {
  return _.spread(unindent)([strArr, ...tagsArr])
    .replace(/[ \t]*\n/g, " ")
    .trimRight();
};

/**
 * The difference between this and lodash.toPlainObject is that this also
 * plain-objectifies the object's prototype.too. The _...*In*_ suffix follows
 * the lodash naming scheme where the non-_...*In*_ function acts only on own
 * properties and the _...*In*_ acts on own and inherited properties.
 *
 * Only values meeting the redux definition of "plain" types will be returned,
 * e.g. the result shallowly omits functions and `symbol`'s.
 *
 * @example

 > const err = new Error('oops');
 > const errObjRepr = { name: 'Error', message: 'oops', stack: 'Uncaught Error: oops...' };
 > require('lodash').isEqual(toPlainObjectIn(err), errObjRepr);  // i.e. deep equals
 true

 * @param {object} obj
 * @param {boolean} [enumerableOnly=false] - whether or not to skip
 *     non-enumerable properties like Lodash does.
 * @returns {Object.<string, string | undefined | null | number | boolean | any[] | object>}
 */
export const toPlainObjectIn = (obj, enumerableOnly = false) => {
  const objectify = (o) => {
    return Object.fromEntries(
      Object.entries(o)
        .filter(([_, v]) => _.isPlainObject(v.value))
        .filter(([_, v]) => !enumerableOnly || v.enumerable)
        .map(([k, v]) => [k, v.value])
    );
  };
  const ownDescriptors = Object.getOwnPropertyDescriptors(obj);
  const ownProps = objectify(ownDescriptors);
  const proto = Object.getPrototypeOf(obj);
  const protoDescriptors = Object.getOwnPropertyDescriptors(proto);
  const inheritedProps = objectify(protoDescriptors);
  return { ...inheritedProps, ...ownProps };
};

export const joinURLComponent = (base, component) => {
  return `${base.replace(/\/+$/, "").trim()}/${component}`;
};

/**
 * Parse JSON string to object.
 * @param {string} data - The json string
 * @returns {object}
 */
export const parseToJson = (data) => {
  let result = data;
  if (typeof data === "string" && data.length) {
    try {
      // Use cjson first to speed up the the process.
      result = JSON.parse(result);
    } catch {
      // Try json5 if JSON string contains NaN type https://json5.org/ .
      result = JSON5.parse(result);
    }
  }

  return result;
};

/**
 * Get the URL to retrieve the attachment from. Depending on whether we are
 * running in batch or interactive mode, the API for accessing attachments
 * is slightly different. We know we are running in interactive mode if there
 * is no report UID.
 */
export const getAttachmentUrl = (filePath, reportUid, prefix) => {
  if (_.isEmpty(prefix)) {
    prefix = "";
  } else {
    prefix += "/";
  }
  if (reportUid) {
    return `/api/v1/reports/${reportUid}/attachments/${prefix}${filePath}`;
  } else {
    return `/api/v1/interactive/attachments/${prefix}${filePath}`;
  }
};

/**
 * Get the URL to retrieve the resource data from API.
 * @param {string} resourceUid
 * @param {string} attachment
 * @returns {string}
 */
export const getResourceUrl = (resourceUid, attachment) => {
  if (_.isEmpty(attachment)) {
    return `/api/v1/testplan_monitor/${resourceUid}`;
  }
  return `/api/v1/testplan_monitor/${resourceUid}/attachments/${attachment}`;
};

/**
 * Get global expand status.
 */
export const globalExpandStatus = () => {
  const expand = new URLSearchParams(window.location.search).get("expand");
  switch (expand) {
    case EXPAND_STATUS.EXPAND:
      return EXPAND_STATUS.EXPAND;
    case EXPAND_STATUS.COLLAPSE:
      return EXPAND_STATUS.COLLAPSE;
    default:
      return EXPAND_STATUS.DEFAULT;
  }
};

/**
 *  Get global View panel type.
 */
export const globalViewPanel = () => {
  const view = new URLSearchParams(window.location.search).get("view");
  switch (view) {
    case VIEW_TYPE.ASSERTION:
      return VIEW_TYPE.ASSERTION;
    case VIEW_TYPE.RESOURCE:
      return VIEW_TYPE.RESOURCE;
    default:
      return VIEW_TYPE.DEFAULT;
  }
};

/**
 * Generate URL to the routes with current query parameters
 * @param {Location} historyLocation
 * @param {String} newURL
 * @param {Object} Parameters
 */
export const generateURLWithParameters = (
  historyLocation,
  newURL,
  newParameters
) => {
  const currentQuery = new URLSearchParams(historyLocation.search);
  const newQuery = {};
  for (const [key, value] of currentQuery) {
    newQuery[key] = value;
  }
  if (newParameters) {
    for (const key in newParameters) {
      if (_.isNil(newParameters[key])) {
        delete newQuery[key];
      } else {
        newQuery[key] = newParameters[key];
      }
    }
  }
  return `${newURL}?${new URLSearchParams(newQuery).toString()}`;
};

/**
 * Truncates excessively long strings
 * @param {String} str
 * @param {Number} maxLength
 * @param {Number} startLength
 * @param {Number} endLength
 */
export const truncateString = (
  str,
  maxLength = 15,
  startLength = 7,
  endLength = 7
) => {
  if (str.length <= maxLength) {
    return str;
  }

  const startPortion = str.slice(0, startLength);
  const endPortion = str.slice(-1 * endLength);

  return `${startPortion}...${endPortion}`;
};

/**
 * Extracts the "workspace" part of the path
 * @param {String} path
 */
export const getWorkspacePath = (path) => {
  const srcIndex = path.indexOf("/src/");

  if (srcIndex !== -1) {
    return path.slice(srcIndex + 1);
  } else {
    return path;
  }
};
