/**
 * Sample Testplan reports to be used in development & testing.
 */
const TESTPLAN_REPORT = {
  category: "testplan",
  name: "Sample Testplan",
  status: "failed",
  uid: "520a92e4-325e-4077-93e6-55d7091a3f83",
  tags_index: {},
  status_override: null,
  meta: {},
  timer: {
    run: [
      {
        start: "2018-10-15T14:30:10.998071+00:00",
        end: "2018-10-15T14:30:11.296158+00:00",
      },
    ],
  },
  entries: [
    {
      name: "Primary",
      status: "failed",
      category: "multitest",
      description: null,
      status_override: null,
      uid: "21739167-b30f-4c13-a315-ef6ae52fd1f7",
      type: "TestGroupReport",
      logs: [],
      tags: {
        simple: ["server"],
      },
      timer: {
        run: [
          {
            start: "2018-10-15T14:30:11.009705+00:00",
            end: "2018-10-15T14:30:11.159661+00:00",
          },
        ],
        setup: [
          {
            start: "2018-10-15T14:30:10.079745+00:00",
            end: "2018-10-15T14:30:11.008995+00:00",
          },
        ],
      },
      entries: [
        {
          status: "failed",
          category: "testsuite",
          name: "AlphaSuite",
          status_override: null,
          description: null,
          uid: "cb144b10-bdb0-44d3-9170-d8016dd19ee7",
          type: "TestGroupReport",
          logs: [],
          tags: {
            simple: ["server"],
          },
          timer: {
            run: [
              {
                start: "2018-10-15T14:30:11.009872+00:00",
                end: "2018-10-15T14:30:11.158224+00:00",
              },
            ],
          },
          entries: [
            {
              category: "testcase",
              name: "test_equality_passing",
              status: "passed",
              status_override: null,
              description: null,
              uid: "736706ef-ba65-475d-96c5-f2855f431028",
              type: "TestCaseReport",
              logs: [],
              tags: {
                colour: ["white"],
              },
              timer: {
                run: [
                  {
                    start: "2018-10-15T14:30:11.010072+00:00",
                    end: "2018-10-15T14:30:11.132214+00:00",
                  },
                ],
              },
              entries: [
                {
                  category: "DEFAULT",
                  machine_time: "2018-10-15T15:30:11.010098+00:00",
                  description: "passing equality",
                  line_no: 24,
                  label: "==",
                  second: 1,
                  meta_type: "assertion",
                  passed: true,
                  type: "Equal",
                  utc_time: "2018-10-15T14:30:11.010094+00:00",
                  first: 1,
                },
              ],
            },
            {
              category: "testcase",
              name: "test_equality_passing2",
              status: "failed",
              tags: {},
              status_override: null,
              description: null,
              uid: "78686a4d-7b94-4ae6-ab50-d9960a7fb714",
              type: "TestCaseReport",
              logs: [],
              timer: {
                run: [
                  {
                    start: "2018-10-15T14:30:11.510072+00:00",
                    end: "2018-10-15T14:30:11.632214+00:00",
                  },
                ],
              },
              entries: [
                {
                  category: "DEFAULT",
                  machine_time: "2018-10-15T15:30:11.510098+00:00",
                  description: "passing equality",
                  line_no: 24,
                  label: "==",
                  second: 1,
                  meta_type: "assertion",
                  passed: true,
                  type: "Equal",
                  utc_time: "2018-10-15T14:30:11.510094+00:00",
                  first: 1,
                },
              ],
            },
          ],
        },
        {
          status: "passed",
          category: "testsuite",
          name: "BetaSuite",
          status_override: null,
          description: null,
          uid: "6fc5c008-4d1a-454e-80b6-74bdc9bca49e",
          type: "TestGroupReport",
          logs: [],
          tags: {
            simple: ["client"],
          },
          timer: {
            run: [
              {
                start: "2018-10-15T14:30:11.009872+00:00",
                end: "2018-10-15T14:30:11.158224+00:00",
              },
            ],
          },
          entries: [
            {
              category: "testcase",
              name: "test_equality_passing",
              status: "passed",
              tags: {},
              status_override: null,
              description: null,
              uid: "8865a23d-1823-4c8d-ab37-58d24fc8ac05",
              type: "TestCaseReport",
              logs: [],
              timer: {
                run: [
                  {
                    start: "2018-10-15T14:30:11.010072+00:00",
                    end: "2018-10-15T14:30:11.132214+00:00",
                  },
                ],
              },
              entries: [
                {
                  category: "DEFAULT",
                  machine_time: "2018-10-15T15:30:11.010098+00:00",
                  description: "passing equality",
                  line_no: 24,
                  label: "==",
                  second: 1,
                  meta_type: "assertion",
                  passed: true,
                  type: "Equal",
                  utc_time: "2018-10-15T14:30:11.010094+00:00",
                  first: 1,
                },
              ],
            },
          ],
        },
      ],
    },
    {
      name: "Secondary",
      status: "passed",
      category: "multitest",
      tags: {},
      description: null,
      status_override: null,
      uid: "8c3c7e6b-48e8-40cd-86db-8c8aed2592c8",
      type: "TestGroupReport",
      logs: [],
      timer: {
        run: [
          {
            start: "2018-10-15T14:30:12.009705+00:00",
            end: "2018-10-15T14:30:12.159661+00:00",
          },
        ],
        setup: [
          {
            start: "2018-10-15T14:30:11.879705+00:00",
            end: "2018-10-15T14:30:12.008705+00:00",
          },
        ],
        teardown: [
          {
            start: "2018-10-15T14:30:12.160132+00:00",
            end: "2018-10-15T14:30:12.645329+00:00",
          },
        ],
      },
      entries: [
        {
          status: "passed",
          category: "testsuite",
          name: "GammaSuite",
          tags: {},
          status_override: null,
          description: null,
          uid: "08d4c671-d55d-49d4-96ba-dc654d12be26",
          type: "TestGroupReport",
          logs: [],
          timer: {
            run: [
              {
                start: "2018-10-15T14:30:12.009872+00:00",
                end: "2018-10-15T14:30:12.158224+00:00",
              },
            ],
          },
          entries: [
            {
              category: "testcase",
              name: "test_equality_passing",
              status: "passed",
              tags: {},
              status_override: null,
              description: null,
              uid: "f73bd6ea-d378-437b-a5db-00d9e427f36a",
              type: "TestCaseReport",
              logs: [],
              timer: {
                run: [
                  {
                    start: "2018-10-15T14:30:12.010072+00:00",
                    end: "2018-10-15T14:30:12.132214+00:00",
                  },
                ],
              },
              entries: [
                {
                  category: "DEFAULT",
                  machine_time: "2018-10-15T15:30:12.010098+00:00",
                  description: "passing equality",
                  line_no: 24,
                  label: "==",
                  second: 1,
                  meta_type: "assertion",
                  passed: true,
                  type: "Equal",
                  utc_time: "2018-10-15T14:30:12.010094+00:00",
                  first: 1,
                },
                {
                  category: "DEFAULT",
                  machine_time: "2018-10-15T15:30:14.015698+00:00",
                  description: "passing equality",
                  line_no: 24,
                  label: "==",
                  second: 1,
                  meta_type: "assertion",
                  passed: true,
                  type: "Equal",
                  utc_time: "2018-10-15T14:30:14.015698+00:00",
                  first: 1,
                },
                {
                  category: "DEFAULT",
                  machine_time: "2018-10-15T15:32:21.123494+00:00",
                  description: "passing equality",
                  line_no: 24,
                  label: "==",
                  second: 1,
                  meta_type: "assertion",
                  passed: false,
                  type: "Equal",
                  utc_time: "2018-10-15T14:32:21.123494+00:00",
                  first: 1,
                },
                {
                  category: "DEFAULT",
                  machine_time: "2018-10-15T15:33:37.015678+00:00",
                  description: "passing equality",
                  line_no: 24,
                  label: "==",
                  second: 1,
                  meta_type: "assertion",
                  passed: true,
                  type: "Equal",
                  utc_time: "2018-10-15T14:33:37.015678+00:00",
                  first: 1,
                },
              ],
            },
          ],
        },
      ],
    },
  ],
};

// Simple passed report that only contains one MultiTest and one suite.
const SIMPLE_PASSED_REPORT = {
  category: "testplan",
  name: "Sample Testplan",
  status: "passed",
  uid: "520a92e4-325e-4077-93e6-55d7091a3f83",
  tags_index: {},
  status_override: null,
  meta: {},
  timer: {
    run: [
      {
        start: "2018-10-15T14:30:10.998071+00:00",
        end: "2018-10-15T14:30:11.296158+00:00",
      },
    ],
  },
  entries: [
    {
      name: "Primary",
      status: "passed",
      category: "multitest",
      description: null,
      status_override: null,
      uid: "21739167-b30f-4c13-a315-ef6ae52fd1f7",
      type: "TestGroupReport",
      logs: [],
      tags: {
        simple: ["server"],
      },
      timer: {
        run: [
          {
            start: "2018-10-15T14:30:11.009705+00:00",
            end: "2018-10-15T14:30:11.159661+00:00",
          },
        ],
        setup: [
          {
            start: "2018-10-15T14:30:11.879705+00:00",
            end: "2018-10-15T14:30:12.008705+00:00",
          },
        ],
        teardown: [
          {
            start: "2018-10-15T14:30:12.160132+00:00",
            end: "2018-10-15T14:30:12.645329+00:00",
          },
        ],
      },
      entries: [
        {
          status: "passed",
          category: "testsuite",
          name: "AlphaSuite",
          status_override: null,
          description: null,
          uid: "cb144b10-bdb0-44d3-9170-d8016dd19ee7",
          type: "TestGroupReport",
          logs: [],
          tags: {
            simple: ["server"],
          },
          timer: {
            run: [
              {
                start: "2018-10-15T14:30:11.009872+00:00",
                end: "2018-10-15T14:30:11.158224+00:00",
              },
            ],
          },
          entries: [
            {
              category: "testcase",
              name: "test_equality_passing",
              status: "passed",
              status_override: null,
              description: null,
              uid: "736706ef-ba65-475d-96c5-f2855f431028",
              type: "TestCaseReport",
              logs: [],
              tags: {
                colour: ["white"],
              },
              timer: {
                run: [
                  {
                    start: "2018-10-15T14:30:11.010072+00:00",
                    end: "2018-10-15T14:30:11.132214+00:00",
                  },
                ],
              },
              entries: [
                {
                  category: "DEFAULT",
                  machine_time: "2018-10-15T15:30:11.010098+00:00",
                  description: "passing equality",
                  line_no: 24,
                  label: "==",
                  second: 1,
                  meta_type: "assertion",
                  passed: true,
                  type: "Equal",
                  utc_time: "2018-10-15T14:30:11.010094+00:00",
                  first: 1,
                },
                {
                  category: "DEFAULT",
                  machine_time: "2018-10-15T15:30:11.020128+00:00",
                  description: "log a fix message",
                  line_no: 28,
                  flag: "DEFAULT",
                  meta_type: "entry",
                  type: "FixLog",
                  utc_time: "2018-10-15T14:30:11.020124+00:00",
                  flattened_dict: [
                    [0, 36, ["int", "6"]],
                    [0, 22, ["int", "5"]],
                    [0, 55, ["int", "2"]],
                    [0, 38, ["int", "5"]],
                    [0, 555, ""],
                    [0, "", ""],
                    [1, 556, ["str", "USD"]],
                    [1, 624, ["int", "1"]],
                    [0, "", ""],
                    [1, 556, ["str", "EUR"]],
                    [1, 624, ["int", "2"]],
                  ],
                },
              ],
            },
          ],
        },
      ],
    },
  ],
};

// Simple failed report that only contains one MultiTest and one suite.
const SIMPLE_FAILED_REPORT = {
  category: "testplan",
  name: "Sample Testplan",
  status: "failed",
  uid: "520a92e4-325e-4077-93e6-55d7091a3f83",
  tags_index: {},
  status_override: null,
  meta: {},
  timer: {
    run: [
      {
        start: "2018-10-15T14:30:10.998071+00:00",
        end: "2018-10-15T14:30:11.296158+00:00",
      },
    ],
  },
  entries: [
    {
      name: "Primary",
      status: "failed",
      category: "multitest",
      description: null,
      status_override: null,
      uid: "21739167-b30f-4c13-a315-ef6ae52fd1f7",
      type: "TestGroupReport",
      logs: [],
      tags: {
        simple: ["server"],
      },
      timer: {
        run: [
          {
            start: "2018-10-15T14:30:11.009705+00:00",
            end: "2018-10-15T14:30:11.159661+00:00",
          },
        ],
        setup: [
          {
            start: "2018-10-15T14:30:10.079745+00:00",
            end: "2018-10-15T14:30:11.008995+00:00",
          },
        ],
      },
      entries: [
        {
          status: "failed",
          category: "testsuite",
          name: "AlphaSuite",
          status_override: null,
          description: null,
          uid: "cb144b10-bdb0-44d3-9170-d8016dd19ee7",
          type: "TestGroupReport",
          logs: [],
          tags: {
            simple: ["server"],
          },
          timer: {
            run: [
              {
                start: "2018-10-15T14:30:11.009872+00:00",
                end: "2018-10-15T14:30:11.158224+00:00",
              },
            ],
          },
          entries: [
            {
              category: "testcase",
              name: "test_equality_passing",
              status: "failed",
              status_override: null,
              description: null,
              uid: "736706ef-ba65-475d-96c5-f2855f431028",
              type: "TestCaseReport",
              logs: [],
              tags: {
                colour: ["white"],
              },
              timer: {
                run: [
                  {
                    start: "2018-10-15T14:30:11.010072+00:00",
                    end: "2018-10-15T14:30:11.132214+00:00",
                  },
                ],
              },
              entries: [
                {
                  category: "DEFAULT",
                  machine_time: "2018-10-15T15:30:11.010098+00:00",
                  description: "passing equality",
                  line_no: 24,
                  label: "==",
                  second: 1,
                  meta_type: "assertion",
                  passed: false,
                  type: "Equal",
                  utc_time: "2018-10-15T14:30:11.010094+00:00",
                  first: 1,
                },
                {
                  category: "DEFAULT",
                  machine_time: "2018-10-15T15:30:11.020128+00:00",
                  description: "log a fix message",
                  line_no: 28,
                  flag: "DEFAULT",
                  meta_type: "entry",
                  type: "FixLog",
                  utc_time: "2018-10-15T14:30:11.020124+00:00",
                  flattened_dict: [
                    [0, 36, ["int", "6"]],
                    [0, 22, ["int", "5"]],
                    [0, 55, ["int", "2"]],
                    [0, 38, ["int", "5"]],
                    [0, 555, ""],
                    [0, "", ""],
                    [1, 556, ["str", "USD"]],
                    [1, 624, ["int", "1"]],
                    [0, "", ""],
                    [1, 556, ["str", "EUR"]],
                    [1, 624, ["int", "2"]],
                  ],
                },
              ],
            },
          ],
        },
      ],
    },
  ],
};

// Simple error report that only contains one MultiTest and one suite.
const SIMPLE_ERROR_REPORT = {
  category: "testplan",
  name: "Testplan with errors",
  status: "error",
  uid: "520a92e4-325e-4077-93e6-55d7091a3f83",
  tags_index: {},
  status_override: null,
  meta: {},
  timer: {
    run: [
      {
        start: "2018-10-15T14:30:10.998071+00:00",
        end: "2018-10-15T14:30:11.296158+00:00",
      },
    ],
    setup: [
      {
        start: "2018-10-15T14:30:10.925461+00:00",
        end: "2018-10-15T14:30:10.997971+00:00",
      },
    ],
  },
  entries: [],
  logs: [
    {
      message:
        'While starting resource [client]\nTraceback (most recent call last):\n  File "/tmp/myworkspace/testplan/common/entity/base.py", line 143, in start\n    resource.start()\n  File "/tmp/myworkspace/testplan/testing/multitest/driver/base.py", line 148, in start\n    self.starting()\n  File "/tmp/myworkspace/testplan/testing/multitest/driver/tcp/client.py", line 161, in starting\n    1/0\nZeroDivisionError: integer division or modulo by zero\n',
      created: "2018-10-15T14:30:12.971680+00:00",
      levelno: 40,
      levelname: "ERROR",
      funcName: "post_step_call",
      lineno: 387,
      uid: "dbc47190-505b-4153-ab3e-fec460eac78d",
    },
  ],
};

// More complex error report.
const ERROR_REPORT = {
  category: "testplan",
  name: "Sample Error Testplan",
  status: "error",
  uid: "520a92e4-325e-4077-93e6-55d7091a3f83",
  tags_index: {},
  status_override: null,
  meta: {},
  timer: {
    run: [
      {
        start: "2018-10-15T14:30:10.998071+00:00",
        end: "2018-10-15T14:30:11.296158+00:00",
      },
    ],
  },
  entries: [
    {
      name: "Primary",
      status: "passed",
      category: "multitest",
      description: null,
      status_override: null,
      uid: "21739167-b30f-4c13-a315-ef6ae52fd1f7",
      type: "TestGroupReport",
      logs: [],
      tags: {
        simple: ["server"],
      },
      timer: {
        run: [
          {
            start: "2018-10-15T14:30:11.009705+00:00",
            end: "2018-10-15T14:30:11.159661+00:00",
          },
        ],
        setup: [
          {
            start: "2018-10-15T14:30:11.879705+00:00",
            end: "2018-10-15T14:30:12.008705+00:00",
          },
        ],
      },
      entries: [
        {
          status: "passed",
          category: "testsuite",
          name: "AlphaSuite",
          status_override: null,
          description: null,
          uid: "cb144b10-bdb0-44d3-9170-d8016dd19ee7",
          type: "TestGroupReport",
          logs: [],
          tags: {
            simple: ["server"],
          },
          timer: {
            run: [
              {
                start: "2018-10-15T14:30:11.009872+00:00",
                end: "2018-10-15T14:30:11.158224+00:00",
              },
            ],
          },
          entries: [
            {
              category: "testcase",
              name: "test_equality_passing",
              status: "passed",
              status_override: null,
              description: null,
              uid: "736706ef-ba65-475d-96c5-f2855f431028",
              type: "TestCaseReport",
              logs: [],
              tags: {
                colour: ["white"],
              },
              timer: {
                run: [
                  {
                    start: "2018-10-15T14:30:11.010072+00:00",
                    end: "2018-10-15T14:30:11.132214+00:00",
                  },
                ],
              },
              entries: [
                {
                  category: "DEFAULT",
                  machine_time: "2018-10-15T15:30:11.010098+00:00",
                  description: "passing equality",
                  line_no: 24,
                  label: "==",
                  second: 1,
                  meta_type: "assertion",
                  passed: true,
                  type: "Equal",
                  utc_time: "2018-10-15T14:30:11.010094+00:00",
                  first: 1,
                },
              ],
            },
          ],
        },
        {
          status: "passed",
          category: "testsuite",
          name: "BetaSuite",
          status_override: null,
          description: null,
          uid: "6fc5c008-4d1a-454e-80b6-74bdc9bca49e",
          type: "TestGroupReport",
          logs: [],
          tags: {
            simple: ["client"],
          },
          timer: {
            run: [
              {
                start: "2018-10-15T14:30:11.009872+00:00",
                end: "2018-10-15T14:30:11.158224+00:00",
              },
            ],
          },
          entries: [
            {
              category: "testcase",
              name: "test_equality_passing",
              status: "passed",
              tags: {},
              status_override: null,
              description: null,
              uid: "8865a23d-1823-4c8d-ab37-58d24fc8ac05",
              type: "TestCaseReport",
              logs: [],
              timer: {
                run: [
                  {
                    start: "2018-10-15T14:30:11.010072+00:00",
                    end: "2018-10-15T14:30:11.132214+00:00",
                  },
                ],
              },
              entries: [
                {
                  category: "DEFAULT",
                  machine_time: "2018-10-15T15:30:11.010098+00:00",
                  description: "passing equality",
                  line_no: 24,
                  label: "==",
                  second: 1,
                  meta_type: "assertion",
                  passed: true,
                  type: "Equal",
                  utc_time: "2018-10-15T14:30:11.010094+00:00",
                  first: 1,
                },
              ],
            },
          ],
        },
      ],
    },
    {
      name: "Secondary",
      status: "error",
      category: "multitest",
      tags: {},
      description: null,
      status_override: "error",
      uid: "8c3c7e6b-48e8-40cd-86db-8c8aed2592c8",
      type: "TestGroupReport",
      logs: [],
      timer: {
        run: [
          {
            start: "2018-10-15T14:30:12.009705+00:00",
            end: "2018-10-15T14:30:12.159661+00:00",
          },
        ],
        setup: [
          {
            start: "2018-10-15T14:30:11.879705+00:00",
            end: "2018-10-15T14:30:12.008705+00:00",
          },
        ],
      },
      entries: [
        {
          status: "error",
          category: "testsuite",
          name: "GammaSuite",
          tags: {},
          status_override: "error",
          description: null,
          uid: "08d4c671-d55d-49d4-96ba-dc654d12be26",
          type: "TestGroupReport",
          logs: [
            {
              message: "Some error message",
              funcName: "someFunc",
              levelno: 42,
              lineno: 32,
              uid: "58096ffc-1d67-4003-b0b0-a7b7a1bda0c8",
              levelname: "ERROR",
              created: "2018-10-15T14:30:12.009872+00:00",
            },
          ],
          timer: {
            run: [
              {
                start: "2018-10-15T14:30:12.009872+00:00",
                end: "2018-10-15T14:30:12.158224+00:00",
              },
            ],
          },
          entries: [],
        },
      ],
    },
  ],
};

/**
 * Fake interactive report. All entries start with a status of "ready".
 */
const FakeInteractiveReport = {
  counter: { passed: 0, failed: 0 },
  entries: [
    {
      counter: { passed: 0, failed: 0 },
      category: "multitest",
      description: "Interactive MTest Desc",
      entries: [
        {
          counter: { passed: 0, failed: 0 },
          category: "testsuite",
          description: "Interactive Suite Desc",
          entries: [
            {
              counter: { passed: 0, failed: 0 },
              category: "testcase",
              description: "Interactive Testcase Desc",
              entries: [],
              logs: [],
              name: "test_interactive",
              name_type_index: [],
              status: "unknown",
              runtime_status: "ready",
              status_override: null,
              tags: {},
              tags_index: {},
              timer: {},
              type: "TestCaseReport",
              parent_uids: ["bbb", "ccc"],
              uid: "ddd",
            },
          ],
          logs: [],
          name: "Interactive Suite",
          name_type_index: [],
          part: null,
          status: "unknown",
          runtime_status: "ready",
          status_override: null,
          tags: {},
          tags_index: {},
          timer: {},
          type: "TestGroupReport",
          parent_uids: ["bbb"],
          uid: "ccc",
        },
      ],
      logs: [],
      name: "Interactive MTest",
      name_type_index: [],
      part: null,
      status: "unknown",
      runtime_status: "ready",
      status_override: null,
      tags: {},
      tags_index: {},
      timer: {},
      type: "TestGroupReport",
      parent_uids: [],
      uid: "bbb",
    },
  ],
  meta: {},
  name: "Fake Interactive Report",
  name_type_index: [],
  status: "unknown",
  runtime_status: "ready",
  status_override: null,
  tags_index: {},
  timer: null,
  uid: "_dev",
};

export {
  TESTPLAN_REPORT,
  SIMPLE_PASSED_REPORT,
  SIMPLE_FAILED_REPORT,
  SIMPLE_ERROR_REPORT,
  ERROR_REPORT,
  FakeInteractiveReport,
};
