.. _example_best_practice:

Best practice
*************

.. _example_common_utilities:

Helper Utilities
----------------

Testplan provides helper functions and a predefined testsuite that make it
easy for the user to add common testplan execution infomation - such as
env var, pwd, log file, driver metadata - to the test report.

Required files:
    - :download:`test_plan.py <../../../examples/Best Practice/Common Utilities/test_plan.py>`

test_plan.py
++++++++++++
.. literalinclude:: ../../../examples/Best Practice/Common Utilities/test_plan.py

Required files:
    - :download:`test_plan.py <../../../examples/Best Practice/Common Utilities/test_plan_metadata.py>`

test_plan_metadata.py
+++++++++++++++++++++
.. literalinclude:: ../../../examples/Best Practice/Common Utilities/test_plan_metadata.py