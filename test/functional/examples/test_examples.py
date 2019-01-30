import os
import re
import sys
import subprocess
import pytest

from testplan.common.utils.path import change_directory

import platform


FILE_DIR = os.path.dirname(__file__)

ON_WINDOWS = platform.system() == 'Windows'

KNOWN_EXCEPTIONS = [
    "TclError: Can't find a usable init\.tcl in the following directories:", # Matplotlib module improperly installed. Will skip Data Science example.
    "ImportError: lib.*\.so\..+: cannot open shared object file: No such file or directory", # Matplotlib module improperly installed. Will skip Data Science example.
    "ImportError: No module named sklearn.*", # Missing module sklearn. Will skip Data Science example.
    "ImportError: No module named Tkinter", # Missing module Tkinter. Will skip Data Science example.
    "ImportError: No module named _tkinter.*", # Missing module Tkinter. Will skip Data Science example.
    "RuntimeError: Download pyfixmsg library .*", # Missing module pyfixmsg. Will skip FIX example.
    "No spec file set\. You should download .*", # Missing FIX spec file. Will skip FIX example.
    "AttributeError: 'module' object has no attribute 'poll'",
    "RuntimeError: You need to compile test binary first.", # Need to compile cpp binary first. Will skip GTest example.
    "FATAL ERROR: Network error: Connection refused", # We don't fail a pool test for connection incapability.
    "lost connection"
]

SKIP = [
    os.path.join('ExecutionPools', 'Remote', 'test_plan.py'),
    os.path.join('ExecutionPools', 'Treadmill', 'test_plan.py'),
]

SKIP_ON_WINDOWS = [
    os.path.join('Cpp', 'GTest', 'test_plan.py'),
    os.path.join('Cpp', 'HobbesTest', 'test_plan.py'),
]

# Contents to look for under root dir.
ROOT_DIR_CONTENTS = [
    'examples',
    'test',
    'testplan',
]


def _param_formatter(param):
    if 'examples' in param:
        return repr(param.rsplit('examples')[1])
    return repr(param)


def _examples_root():
    """
    Find the examples directory that sits next to test & testplan
    """

    cwd = FILE_DIR
    while True:
        contents = os.listdir(cwd)
        if all([entry in contents for entry in ROOT_DIR_CONTENTS]):
            break
        parent_dir = os.path.dirname(cwd)
        if os.path.realpath(cwd) == os.path.realpath(parent_dir):
            raise RuntimeError('Could not find repo directory')
        cwd = parent_dir

    return os.path.abspath(os.path.join(
        cwd,
        'examples'
    ))


@pytest.mark.parametrize(
    'root,filename',
    [
        (os.path.abspath(root), filename)
        for root, _, files in os.walk(
            _examples_root(), followlinks=True)
        for filename in files
        if 'test_plan' in filename
    ],
    ids=_param_formatter,
)
def test_example(root, filename):
    file_path = os.path.join(root, filename)

    if ON_WINDOWS and any(
        [file_path.endswith(skip_name) for skip_name in SKIP_ON_WINDOWS]
    ):
        pytest.skip()
    elif any([file_path.endswith(skip_name) for skip_name in SKIP]):
        pytest.skip()

    with change_directory(root), open(filename) as file_obj:
        file_obj.readline()
        second_line = file_obj.readline()
        try:
            subprocess.check_output(
                [sys.executable, filename],
                stderr=subprocess.STDOUT
            )
        except subprocess.CalledProcessError as e:
            out = e.output.decode()
            for exception in KNOWN_EXCEPTIONS:
                if re.search(exception, out):
                    pytest.xfail()
            assert 'Exception in test_plan definition' not in out, \
                'Exception raised in test_plan definition.'
            assert 'Traceback (most recent call last):' not in out, \
                'Exception raised during test:\n{}'.format(out)
            assert \
                ('# This plan contains tests that demonstrate failures '
                 'as well.') == second_line.strip(), \
                "Expected \'{}\' example to pass, it failed.\n{}".format(
                    file_path,
                    out
                )
