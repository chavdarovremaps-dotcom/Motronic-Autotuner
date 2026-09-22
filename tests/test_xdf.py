import struct

import numpy as np
import pytest

from motronic_autotuner.core.winols import STATUS_LOADED, STATUS_MISSING, TargetMap
from motronic_autotuner.core.xdf import Xdf, evaluate, import_xdf_maps

XDF = """<?xml version="1.0"?>
<XDFFORMAT version="1.80">
  <XDFHEADER>
    <deftitle>TEST</deftitle>
    <BASEOFFSET offset="16" subtract="0" />
    <DEFAULTS datasizeinbits="8" signed="0" lsbfirst="1" />
  </XDFHEADER>
  <XDFTABLE uniqueid="0x10">
    <title>axis_rpm</title>
    <XDFAXIS id="z">
      <EMBEDDEDDATA mmedtypeflags="0x02" mmedaddress="0x0" mmedelementsizebits="16" mmedrowcount="3" />
      <MATH equation="1.0*X"><VAR id="X" /></MATH>
    </XDFAXIS>
  </XDFTABLE>
  <XDFTABLE uniqueid="0x20">
    <title>ve_1</title>
    <XDFAXIS id="x">
      <units>rpm</units>
      <indexcount>3</indexcount>
      <embedinfo type="3" linkobjid="0x10" />
      <MATH equation="X"><VAR id="X" /></MATH>
    </XDFAXIS>
    <XDFAXIS id="y">
      <units>kPa</units>
      <indexcount>2</indexcount>
      <LABEL index="0" value="20.5" />
      <LABEL index="1" value="40" />
      <MATH equation="X"><VAR id="X" /></MATH>
    </XDFAXIS>
    <XDFAXIS id="z">
      <EMBEDDEDDATA mmedtypeflags="0x02" mmedaddress="0x6" mmedelementsizebits="16" mmedrowcount="2" mmedcolcount="3" />
      <units>VE</units>
      <MATH equation="0.5*X+1"><VAR id="X" /></MATH>
    </XDFAXIS>
  </XDFTABLE>
</XDFFORMAT>
"""


def make_bin() -> bytes:
    rpm = struct.pack("<3H", 800, 2000, 6000)
    z = struct.pack("<6H", 0, 2, 4, 6, 8, 10)  # -> 1, 2, 3 / 4, 5, 6
    return b"\xff" * 16 + rpm + z + b"\x00" * 8


def test_evaluate():
    x = np.array([0.0, 8.0, 16.0])
    np.testing.assert_allclose(evaluate("X/8-40", x), [-40, -39, -38])
    np.testing.assert_allclose(evaluate("0.0082921489*X", x), x * 0.0082921489)
    with pytest.raises(ValueError):
        evaluate("__import__('os')", x)


def test_read_map_with_linked_and_label_axes(tmp_path):
    xdf_path = tmp_path / "t.xdf"
    xdf_path.write_text(XDF)
    xdf = Xdf(xdf_path)
    m = xdf.read_map(make_bin(), "ve_1")
    assert m.x_axis.tolist() == [800, 2000, 6000]
    assert m.y_axis.tolist() == [20.5, 40]
    np.testing.assert_allclose(m.values, [[1, 2, 3], [4, 5, 6]])
    assert m.x_units == "rpm" and m.z_units == "VE"


def test_import_xdf_maps(tmp_path):
    xdf_path = tmp_path / "t.xdf"
    xdf_path.write_text(XDF)
    bin_path = tmp_path / "t.bin"
    bin_path.write_bytes(make_bin())
    targets = [
        TargetMap("ve_1", "map_ve", "rpm_ve", "base_ve_1", "VE", direct=True),
        TargetMap("ve_2", "map_ve", "rpm_ve", "base_ve_2", "VE", direct=True),
    ]
    r = import_xdf_maps(xdf_path, bin_path, targets)
    assert r.rows[0].status == STATUS_LOADED and r.rows[0].dims == "2 x 3"
    assert r.rows[1].status == STATUS_MISSING
    assert r.axes["rpm_ve"].tolist() == [800, 2000, 6000]
    assert r.base_maps["base_ve_1"].shape == (2, 3)
