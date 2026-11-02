"""MS43X patches: XDF writing, the patch rules, the ICV delete on a real bin, checksums."""
from pathlib import Path

import numpy as np
import pytest

from motronic_autotuner.core.xdf import Xdf
from motronic_autotuner.ms43_turbo import checksum
from motronic_autotuner.ms43_turbo.patches import ICV_DELETE_M54B30, Patch, PatchError, apply_patch, parse_values

XDF_TEXT = """<XDFFORMAT version="1.70">
  <XDFHEADER>
    <deftitle>test</deftitle>
    <BASEOFFSET offset="0" subtract="0" />
    <DEFAULTS datasizeinbits="8" sigdigits="2" outputtype="1" signed="0" lsbfirst="1" float="0" />
  </XDFHEADER>
  <XDFTABLE uniqueid="0x1"><title>ip_curve__x</title>
    <XDFAXIS id="x"><indexcount>1</indexcount></XDFAXIS><XDFAXIS id="y"><indexcount>4</indexcount></XDFAXIS>
    <XDFAXIS id="z"><EMBEDDEDDATA mmedtypeflags="0x02" mmedaddress="0x10" mmedelementsizebits="16" mmedrowcount="4" />
      <MATH equation="0.5*X"><VAR id="X" /></MATH></XDFAXIS></XDFTABLE>
  <XDFTABLE uniqueid="0x2"><title>ip_map__a__b</title>
    <XDFAXIS id="x"><indexcount>3</indexcount></XDFAXIS><XDFAXIS id="y"><indexcount>2</indexcount></XDFAXIS>
    <XDFAXIS id="z"><EMBEDDEDDATA mmedtypeflags="0x06" mmedaddress="0x40" mmedelementsizebits="8" mmedrowcount="2" mmedcolcount="3" />
      <MATH equation="0.375*X-48.0"><VAR id="X" /></MATH></XDFAXIS></XDFTABLE>
  <XDFTABLE uniqueid="0x3"><title>ip_dup__a</title>
    <XDFAXIS id="z"><EMBEDDEDDATA mmedtypeflags="0x02" mmedaddress="0x60" mmedelementsizebits="8" />
      <MATH equation="X"><VAR id="X" /></MATH></XDFAXIS></XDFTABLE>
  <XDFTABLE uniqueid="0x4"><title>ip_dup__b</title>
    <XDFAXIS id="z"><EMBEDDEDDATA mmedtypeflags="0x02" mmedaddress="0x61" mmedelementsizebits="8" />
      <MATH equation="X"><VAR id="X" /></MATH></XDFAXIS></XDFTABLE>
  <XDFTABLE uniqueid="0x6"><title>ip_square</title>
    <XDFAXIS id="z"><EMBEDDEDDATA mmedtypeflags="0x02" mmedaddress="0x90" mmedelementsizebits="8" />
      <MATH equation="X*X"><VAR id="X" /></MATH></XDFAXIS></XDFTABLE>
  <XDFCONSTANT uniqueid="0x5"><title>c_const</title>
    <EMBEDDEDDATA mmedtypeflags="0x02" mmedaddress="0x80" mmedelementsizebits="8" />
    <MATH equation="32.0*X"><VAR id="X" /></MATH></XDFCONSTANT>
</XDFFORMAT>
"""


@pytest.fixture
def xdf(tmp_path):
    p = tmp_path / "t.xdf"
    p.write_text(XDF_TEXT, encoding="utf-8")
    return Xdf(p)


def patch(values: str) -> Patch:
    return Patch("t", "Test patch", "", values, reminders=("Clear adaptations.",))


def test_parse_values_names_and_shapes():
    items = parse_values("a\n1\n2\nb__x\n1 2 3\n4 5 6\n")
    assert [(n, v.shape) for n, v in items] == [("a", (2, 1)), ("b__x", (2, 3))]
    with pytest.raises(ValueError, match="different lengths"):
        parse_values("a\n1 2\n3\n")
    with pytest.raises(ValueError, match="before the first name"):
        parse_values("1 2\na\n3\n")


def test_patch_writes_tables_and_constants(xdf):
    data = bytes(0x100)
    r = apply_patch(xdf, data, patch("ip_curve\n1\n2.5\n100\n0\nip_map\n0 0.375 0.75\n1.5 3 -48\nc_const\n8160\n"),
                    checksums=None)
    out = r.data
    assert np.frombuffer(out, "<u2", 4, 0x10).tolist() == [2, 5, 200, 0]
    # column-major 2 x 3 is stored column by column
    assert list(out[0x40:0x46]) == [128, 132, 129, 136, 130, 0]
    assert out[0x80] == 255
    np.testing.assert_allclose(xdf.read_raw(out, xdf.lookup("ip_map__a__b").z), [[0, 0.375, 0.75], [1.5, 3, -48]])
    assert "  ip_curve (ip_curve__x): 0 0 0 0  ->  1 2.5 100 0" in r.lines
    assert r.lines[-1] == "Reminder: Clear adaptations."
    assert sum(a != b for a, b in zip(data, out)) == 3 + 5 + 1   # nonzero bytes of the three objects


def test_unchanged_object_is_reported(xdf):
    r = apply_patch(xdf, bytes(0x100), patch("c_const\n0\n"), checksums=None)
    assert "  c_const: already at the patch values." in r.lines


def test_missing_objects_fail_and_are_all_listed(xdf):
    with pytest.raises(PatchError) as exc:
        apply_patch(xdf, bytes(0x100), patch("ip_curve\n1\n2\n3\n4\nip_nothere\n1\nc_gone\n5\n"), checksums=None)
    assert exc.value.problems == ["ip_nothere: not found in the XDF", "c_gone: not found in the XDF"]


@pytest.mark.parametrize("values, message", [
    ("ip_dup\n1\n", "matches several XDF titles"),
    ("ip_map\n1 2\n3 4\n", "the patch has 2 x 2 values, ip_map__a__b is 2 x 3"),
    ("ip_curve\n1\n2\n3\n40000\n", "outside the storable range 0 to 32767.5"),
    ("ip_square\n4\n", "not linear"),
])
def test_patch_refuses(xdf, values, message):
    with pytest.raises(PatchError, match=message):
        apply_patch(xdf, bytes(0x100), patch(values), checksums=None)


def test_curve_accepts_a_row_or_a_column(xdf):
    a = apply_patch(xdf, bytes(0x100), patch("ip_curve\n1 2 3 4\n"), checksums=None).data
    b = apply_patch(xdf, bytes(0x100), patch("ip_curve\n1\n2\n3\n4\n"), checksums=None).data
    assert a == b


# ---- the real MS43X001 XDF and the car's bin ----------------------------------------

REAL_XDF = Path(r"D:\Repos\BMW-XDFs\MS43\Siemens_MS43_MS43X001_512K.xdf")
REAL_BIN = Path(r"C:\Users\chavd\OneDrive\Desktop\_Files\bmw e36 m54b30 turbo\MS43_WBAAV51020JT00938_43X001_512KB_readback.bin")
real = pytest.mark.skipif(not (REAL_XDF.is_file() and REAL_BIN.is_file()), reason="MS43X001 XDF or bin not on this machine")


@real
def test_icv_delete_on_the_car_bin():
    xdf, data = Xdf(REAL_XDF), REAL_BIN.read_bytes()
    r = apply_patch(xdf, data, ICV_DELETE_M54B30)
    out = r.data
    assert len(out) == len(data)
    for name, values in parse_values(ICV_DELETE_M54B30.values):
        from motronic_autotuner.ms43_turbo.patches import resolve
        _, t = resolve(xdf, name)
        np.testing.assert_allclose(xdf.read_raw(out, t.z).ravel(), values.ravel(), atol=0.002)
    segs = checksum.cal_segments(data)
    assert checksum.crc(checksum.stream(out, segs)) == checksum.crc(checksum.stream(data, segs))
    assert checksum.monitor_sum(out) == checksum.stored_monitor_sum(out)
    assert any("monitor sum at 0x72ffc recalculated" in line for line in r.lines)
    # applying it again changes nothing
    again = apply_patch(xdf, out, ICV_DELETE_M54B30)
    assert again.data == out
    assert sum("already at the patch values" in line for line in again.lines) == 19


@real
def test_checksum_refuses_program_code():
    data = REAL_BIN.read_bytes()
    bad = bytearray(data)
    bad[0x10000] ^= 0xFF
    with pytest.raises(ValueError, match="outside the calibration area"):
        checksum.fix(data, bytes(bad), [])
