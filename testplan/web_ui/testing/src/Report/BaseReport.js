import React from "react";

import { filterReport } from "./reportUtils";
import { defaultAssertionStatus } from "../Common/context";
import { generateURLWithParameters } from "../Common/utils";

/**
 * BaseReport component.
 *
 */
class BaseReport extends React.Component {
    constructor(props) {
        super(props);
        this.setError = this.setError.bind(this);
        //this.setReport = this.setReport.bind(this);
        //this.getReport = this.getReport.bind(this);
        this.updateTreeView = this.updateTreeView.bind(this);
        this.handleColumnResizing = this.handleColumnResizing.bind(this);
        this.updateAssertionStatus = this.updateAssertionStatus.bind(this);
        this.updateGlobalExpand = this.updateGlobalExpand.bind(this);
        this.updateTimeDisplay = this.updateTimeDisplay.bind(this);
        this.updatePathDisplay = this.updatePathDisplay.bind(this);
        this.handleNavFilter = this.handleNavFilter.bind(this);

        defaultAssertionStatus.updateAssertionStatus
            = this.updateAssertionStatus;
        defaultAssertionStatus.updateGlobalExpand = this.updateGlobalExpand;

        this.state = {
            navWidth: null,
            report: null,
            filteredReport: {
                filter: { text: null, filters: null },
                report: null,
            },
            loading: false,
            error: null,
            treeView: true,
            displayTime: false,
            displayPath: false,
            assertionStatus: defaultAssertionStatus,
        };
    }

    setError(error) {
        console.log(error);
        this.setState({error: error, loading: false});
    }

    /**
    * Fetch the Testplan report once the component has mounted.
    * @public
    */
    componentDidMount() {
        this.setState({ loading: true }, this.getReport);
    }

    /**
    * Update the global expand status
    *
    * @param {String} status - the new global expand status
    */
    updateGlobalExpand(status) {
        this.setState((prev) => {
            const assertionStatus = prev.assertionStatus;
            assertionStatus.globalExpand = {
                status: status,
                time: new Date().getTime(),
            };
            return { ...prev, assertionStatus };
        });
        const newUrl = generateURLWithParameters(
            window.location,
            window.location.pathname,
            { expand: status }
        );
        this.props.history.push(newUrl);
    }

    /**
    * Update the expand status of assertions
    *
    * @param {Array} uids - the array of assertion unique id
    * @param {String} status - the new expand status of assertions
    * @public
    */
    updateAssertionStatus(uids, status) {
        this.setState((prev) => {
            const assertionStatus = prev.assertionStatus;
            uids.forEach((uid) => {
                assertionStatus.assertions[uid] = {
                    status: status,
                    time: new Date().getTime(),
                };
            });
            return { ...prev, assertionStatus };
        });
    }

    /**
    * Update the flag for whether to use tree view navigation or the default one.
    *
    * @param {boolean} treeView.
    * @public
    */
    updateTreeView(treeView) {
        this.setState({ treeView: treeView });
    }

    /**
    * Update file path and line number display of each assertion.
    *
    * @param {boolean} displayPath.
    * @public
    */
    updatePathDisplay(displayPath) {
        this.setState({ displayPath: displayPath });
    }

    /**
    * Update execution time display of each navigation entry and each assertion.
    *
    * @param {boolean} displayTime.
    * @public
    */
    updateTimeDisplay(displayTime) {
      this.setState({ displayTime: displayTime });
    }

    /**
    * Handle resizing event and update NavList & Center Pane.
    */
    handleColumnResizing(navWidth) {
        this.setState({ navWidth: navWidth });
    }

    /**
    * Handle filter expressions being typed into the filter box.
    *
    * @param {Object} filter - the parsed filter expression
    * @public
    */
    handleNavFilter(filter) {
        // eslint-disable-line no-unused-vars
        const filteredReport = filterReport(this.state.report, filter);

        this.setState({
            filteredReport,
        });
    }
}

export default BaseReport;