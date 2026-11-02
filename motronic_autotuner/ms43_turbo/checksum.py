"""MS43 (MS43X001) checksums of a 512 KB binary, ported from
BMW-XDFs/ms43_checksum.py (reverse engineered from the boot and program code).

* Calibration CRC: CRC-16 (reflected, poly 0xA001, no final xor) chained
  over the segments listed in the descriptor at 0x73FE0, seeded through a
  pointer. The seed does not reproduce in every bin, so a patched bin keeps
  its CRC NEUTRAL instead: two unused padding bytes inside the CRC range
  (0x72FF8) are set so that the CRC of the patched calibration equals the
  input bin's for any seed. The stored CRC word is then exactly as valid as
  it was in the input.
* Calibration monitor sum (u32 at 0x72FFC): the seed at 0x6FDB8 plus the
  little-endian u16 word sum of the two segments listed at 0x6FDCE. The
  ``_mon`` tables lie in those segments, so a patch that touches them gets
  the sum recalculated (only when the input bin's sum was valid).

A patch may only change bytes inside the calibration CRC segments; program
code is refused.
"""

from __future__ import annotations

import struct

BIN_SIZE = 0x80000
CAL_DESC = 0x73FE0
MON_STORED, MON_SEED, MON_DESC = 0x72FFC, 0x6FDB8, 0x6FDCE
PAD = 0x72FF8
"""Two 0xFF padding bytes before the monitor sum, inside calibration CRC segment 1."""

_TABLE = []
for _i in range(256):
    _c = _i
    for _ in range(8):
        _c = (_c >> 1) ^ 0xA001 if _c & 1 else _c >> 1
    _TABLE.append(_c)


def crc(data: bytes, c: int = 0) -> int:
    for x in data:
        c = (c >> 8) ^ _TABLE[(c ^ x) & 0xFF]
    return c


def cal_segments(b: bytes) -> list[tuple[int, int]]:
    """Calibration CRC segments, (start, end) inclusive file offsets."""
    n = struct.unpack_from("<H", b, CAL_DESC + 2)[0]
    if not 1 <= n <= 8:
        raise ValueError(f"calibration CRC descriptor lists {n} segments; not an MS43X001 binary?")
    segs = [struct.unpack_from("<II", b, CAL_DESC + 4 + 8 * i) for i in range(n)]
    if any(not (0 <= s <= e < len(b)) for s, e in segs):
        raise ValueError("calibration CRC descriptor points outside the binary; not an MS43X001 binary?")
    return segs


def stream(b: bytes, segs: list[tuple[int, int]]) -> bytes:
    return b"".join(b[s:e + 1] for s, e in segs)


def monitor_segments(b: bytes) -> list[tuple[int, int]]:
    """Monitor sum segments, (start, end) with the end exclusive of its last word."""
    out = []
    for i in range(2):
        s = struct.unpack_from("<HH", b, MON_DESC + 8 * i)
        e = struct.unpack_from("<HH", b, MON_DESC + 4 + 8 * i)
        out.append((s[1] << 16 | s[0], e[1] << 16 | e[0]))
    return out


def monitor_sum(b: bytes) -> int:
    total = struct.unpack_from("<I", b, MON_SEED)[0]
    for s, e in monitor_segments(b):
        total += sum(struct.unpack_from(f"<{(e - s) // 2}H", b, s))
    return total & 0xFFFFFFFF


def stored_monitor_sum(b: bytes) -> int:
    return struct.unpack_from("<I", b, MON_STORED)[0]


def neutralize(ref: bytes, new: bytes) -> bytes:
    """A copy of ``new`` whose calibration CRC (seed 0, so for any seed) equals ``ref``'s,
    by setting the two padding bytes at PAD."""
    segs = cal_segments(ref)
    pos = sum(e - s + 1 for s, e in segs if e < PAD) + (PAD - next(s for s, e in segs if s <= PAD <= e))
    want = crc(stream(ref, segs), 0)
    out = bytearray(new)
    out[PAD:PAD + 2] = ref[PAD:PAD + 2]
    have = crc(stream(out, segs), 0)
    n = len(stream(out, segs))
    basis = []
    for k in range(16):
        z = bytearray(n)
        z[pos + k // 8] = 1 << (k % 8)
        basis.append(crc(z, 0))
    piv: dict[int, tuple[int, int]] = {}
    for k, v in enumerate(basis):
        m = 1 << k
        for bit in range(15, -1, -1):
            if not v >> bit & 1:
                continue
            if bit in piv:
                v ^= piv[bit][0]
                m ^= piv[bit][1]
            else:
                piv[bit] = (v, m)
                break
    t, x = want ^ have, 0
    for bit in range(15, -1, -1):
        if t >> bit & 1:
            if bit not in piv:
                raise ValueError("cannot keep the calibration CRC with this padding position")
            t ^= piv[bit][0]
            x ^= piv[bit][1]
    out[PAD] ^= x & 0xFF
    out[PAD + 1] ^= x >> 8
    if crc(stream(out, segs), 0) != want:
        raise ValueError("calibration CRC could not be kept")
    return bytes(out)


def fix(original: bytes, patched: bytes, messages: list[str]) -> bytes:
    """Monitor sum and calibration CRC of ``patched`` made as valid as ``original``'s."""
    if len(original) != BIN_SIZE or len(patched) != BIN_SIZE:
        raise ValueError(f"checksums are handled for 512 KB MS43 binaries only (this one is {len(original)} bytes)")
    segs = cal_segments(original)
    reserved = set(range(PAD, PAD + 2)) | set(range(MON_STORED, MON_STORED + 4))
    changed = [i for i in range(len(original)) if original[i] != patched[i]]
    outside = [i for i in changed if not any(s <= i <= e for s, e in segs)]
    if outside:
        raise ValueError(f"{len(outside)} changed bytes lie outside the calibration area (first at {outside[0]:#x}); "
                         "program code is not patched")
    if reserved.intersection(changed):
        raise ValueError("the patch writes over the checksum bytes at 0x72FF8 .. 0x72FFF")
    out = bytearray(patched)
    mon_was_ok = monitor_sum(original) == stored_monitor_sum(original)
    if monitor_sum(out) != stored_monitor_sum(out):
        if mon_was_ok:
            struct.pack_into("<I", out, MON_STORED, monitor_sum(out))
            messages.append(f"Checksum: monitor sum at {MON_STORED:#x} recalculated "
                            f"({stored_monitor_sum(original):#010x} -> {stored_monitor_sum(out):#010x}).")
        else:
            messages.append("Checksum: the monitor sum was already wrong in the input bin; left as it was.")
    else:
        messages.append("Checksum: monitor sum unchanged (no monitored data touched).")
    fixed = neutralize(original, bytes(out))
    messages.append(f"Checksum: calibration CRC kept equal to the input bin's (padding {PAD:#x}: "
                    f"{patched[PAD:PAD + 2].hex()} -> {fixed[PAD:PAD + 2].hex()}).")
    if mon_was_ok and monitor_sum(fixed) != stored_monitor_sum(fixed):
        raise ValueError("monitor sum check failed after the patch")
    return fixed
