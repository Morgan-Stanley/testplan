import subprocess
import tempfile
from itertools import count
from pathlib import Path

import pytest

# tpsreport command should already be available after installation
# TODO: to be refactored with jq (apply jq op on gened data before diff)

# NOTE: useful when normalise test data
# $ jq 'walk( if type == "object" and has("uid") then .uid = "" | .hash = "" else . end )' data > data_

DATA_DIR = Path(__file__).parent / "data"


@pytest.mark.parametrize(
    "from_cmd, input_file, to_cmd, ref_file",
    [
        ("fromjson", "old.data", "tojson", None),
        ("fromjson", "curr.data", "tojson", None),
        # ("fromjson", "curr.data", "tojson", "curr.data"),
    ],
    ids=count(0),
)
def test_convert_roundtrip(from_cmd, input_file, to_cmd, ref_file):
    input_file = str(DATA_DIR / input_file)
    try:
        f = tempfile.NamedTemporaryFile(delete=False)
        f.close()
        subprocess.run(
            ["tpsreport", "convert", from_cmd, input_file, to_cmd, f.name],
            check=True,
        )
        if ref_file:
            ref_file = str(DATA_DIR / ref_file)
            subprocess.run(["diff", f.name, ref_file], check=True)
    finally:
        Path(f.name).unlink()
