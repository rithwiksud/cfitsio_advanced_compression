#!/usr/bin/env python3
"""
JPEG-LS correctness-guard test suite for fpack/funpack.

Covers the null-pixel and overflow guarantees of the JPEG-LS path, plus the
2D-tile null-placement fix in funpack that all codecs share:

  1. Near-lossless -jN treats undefined pixels as sacred: any tile containing
     the null marker (BLANK for integer images, the quantized null for float
     images) is encoded losslessly, so nulls survive bit-exact and no valid
     pixel can be perturbed onto the marker (false nulls).
  2. fpack flags -jN (N > 0) as LOSSY: with -D it must prompt before deleting
     the original, and must not prompt for lossless -j0.
  3. 32-bit near-lossless reconstruction saturates at the top of the range:
     values at/near INT32_MAX stay within the NEAR bound instead of wrapping
     to ~INT32_MIN.
  4. The 32-bit per-tile baseline excludes null pixels, so one BLANK does not
     forfeit the rebase (compressed size stays small).
  5. An identically-zero upper plane is signalled with upper_len == 0 instead
     of an explicit JPEG-LS stream, and decodes correctly.
  6. funpack places null-bearing float tiles correctly with 2D tilings
     (regression for the shared fits_read_write_compressed_img linear-offset
     bug; tested for JPEG-LS and for RICE with -t 512,512).

Usage:  python3 test_jpegls_guards.py
"""

import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from astropy.io import fits

HERE = os.path.dirname(os.path.abspath(__file__))
FPACK = os.path.join(HERE, "fpack")
FUNPACK = os.path.join(HERE, "funpack")

npass = 0
nfail = 0


def check(name, cond, detail=""):
    global npass, nfail
    if cond:
        npass += 1
        print(f"  PASS  {name}")
    else:
        nfail += 1
        print(f"  FAIL  {name}  {detail}")


def run(cmd, stdin=None):
    p = subprocess.run(cmd, capture_output=True, text=True, input=stdin)
    return p.returncode == 0, (p.stdout + p.stderr).strip()


def roundtrip(data, flags, tmpdir, header=None, raw=False):
    """fpack <flags> then funpack -O.  Returns (decoded, fz_path)."""
    src = os.path.join(tmpdir, "in.fit")
    packed = src + ".fz"
    out = os.path.join(tmpdir, "out.fit")
    for f in (src, packed, out):
        if os.path.exists(f):
            os.remove(f)

    hdu = fits.PrimaryHDU(data)
    if header:
        for k, v in header.items():
            hdu.header[k] = v
    hdu.writeto(src, overwrite=True)

    ok, msg = run([FPACK] + flags + [src])
    if not ok:
        raise RuntimeError(f"fpack failed: {msg}")
    ok, msg = run([FUNPACK, "-O", out, packed])
    if not ok:
        raise RuntimeError(f"funpack failed: {msg}")
    with fits.open(out, do_not_scale_image_data=raw) as h:
        return h[0].data.copy(), packed


def upper_lengths(fz_path):
    """Per-tile upper-plane stream lengths from the 32-bit container."""
    with fits.open(fz_path, disable_image_compression=True) as h:
        return [int.from_bytes(bytes(r[:4]), "big")
                for r in h[1].data["COMPRESSED_DATA"]]


def main():
    tmpdir = tempfile.mkdtemp(prefix="jls_guards_")
    rng = np.random.default_rng(12345)
    try:
        # ------------------------------------------------------------------
        print("== null preservation: int16 + BLANK, -j3, multi-tile ==")
        d = rng.normal(1000, 200, (600, 700)).astype(np.int16)
        d[10:20, 10:20] = -32768            # nulls in tile (0,0)
        d[30, 30] = -32768 + 2              # valid pixel within NEAR of BLANK
        out, _ = roundtrip(d, ["-j3"], tmpdir, {"BLANK": -32768}, raw=True)
        check("null mask bit-exact", np.array_equal(out == -32768, d == -32768))
        check("null-bearing tile lossless", np.array_equal(out[:512, :512], d[:512, :512]))
        err = np.abs(out.astype(np.int32) - d.astype(np.int32))
        check("NEAR bound holds elsewhere", err.max() <= 3, f"max={err.max()}")
        check("near-lossless engaged in null-free tiles", not np.array_equal(out, d))

        # ------------------------------------------------------------------
        print("== null preservation: int32 + BLANK, -j5, multi-tile ==")
        d = rng.normal(0, 5e6, (600, 700)).astype(np.int32)
        d[10:20, 10:20] = -2147483648
        out, _ = roundtrip(d, ["-j5"], tmpdir, {"BLANK": -2147483648}, raw=True)
        check("null mask bit-exact",
              np.array_equal(out == -2147483648, d == -2147483648))
        check("null-bearing tile lossless", np.array_equal(out[:512, :512], d[:512, :512]))
        err = np.abs(out.astype(np.int64) - d.astype(np.int64))
        check("NEAR bound holds elsewhere", err.max() <= 5, f"max={err.max()}")

        # ------------------------------------------------------------------
        print("== null preservation: float32 + NaN (quantized), -j2 and -j0 ==")
        d = rng.normal(100.0, 5.0, (600, 700)).astype(np.float32)
        d[10:20, 10:20] = np.nan
        m = ~np.isnan(d)
        for flag in ("-j2", "-j0"):
            out, _ = roundtrip(d, [flag], tmpdir)
            check(f"{flag}: NaN mask bit-exact",
                  np.array_equal(np.isnan(out), np.isnan(d)),
                  f"in={np.isnan(d).sum()} out={np.isnan(out).sum()}")
            # quantize level 4, sigma 5 => delta 1.25; NEAR=2 adds 2*delta
            bound = 3.2 if flag == "-j2" else 0.7
            check(f"{flag}: values within quantization bound",
                  np.abs(out[m] - d[m]).max() <= bound,
                  f"max={np.abs(out[m] - d[m]).max()}")

        # ------------------------------------------------------------------
        print("== shared funpack fix: RICE with 2D tiles, float + NaN ==")
        out, _ = roundtrip(d, ["-t", "512,512"], tmpdir)
        check("NaN mask bit-exact",
              np.array_equal(np.isnan(out), np.isnan(d)),
              f"in={np.isnan(d).sum()} out={np.isnan(out).sum()}")
        check("values within quantization bound",
              np.abs(out[m] - d[m]).max() <= 0.7)

        # ------------------------------------------------------------------
        print("== lossy prompt: fpack -D must warn for -j3, not for -j0 ==")
        src = os.path.join(tmpdir, "prompt.fit")
        d = rng.normal(1000, 200, (128, 128)).astype(np.int16)
        for f in (src, src + ".fz"):
            if os.path.exists(f):
                os.remove(f)
        fits.PrimaryHDU(d).writeto(src)
        ok, msg = run([FPACK, "-j3", "-D", src], stdin="n\n")
        check("-j3 -D warns LOSSY", ok and "LOSSY" in msg, msg[:120])
        check("-j3 -D + 'n' keeps original", os.path.exists(src))
        os.remove(src + ".fz")
        ok, msg = run([FPACK, "-j0", "-D", src], stdin="")
        check("-j0 -D deletes without prompting",
              ok and "LOSSY" not in msg and not os.path.exists(src), msg[:120])

        # ------------------------------------------------------------------
        print("== 32-bit saturation: values at INT32_MAX, -j5 ==")
        d = rng.normal(0, 1000, (300, 300)).astype(np.int32)
        d[5:60, 5:60] = np.int32(2**31 - 1)
        d[100:150, 100:150] = np.int32(2**31 - 3)
        out, _ = roundtrip(d, ["-j5"], tmpdir)
        err = np.abs(out.astype(np.int64) - d.astype(np.int64))
        check("no wraparound, NEAR bound holds", err.max() <= 5, f"max={err.max()}")

        # ------------------------------------------------------------------
        print("== zero-upper-plane sentinel (upper_len == 0) ==")
        d = rng.normal(50000, 3000, (600, 700)).astype(np.int32)   # range << 2^16
        out, fz = roundtrip(d, ["-j"], tmpdir)
        check("small-range tile roundtrips exactly", np.array_equal(out, d))
        check("sentinel used for every tile",
              all(u == 0 for u in upper_lengths(fz)))
        d = rng.normal(0, 5e6, (600, 700)).astype(np.int32)        # range >> 2^16
        out, fz = roundtrip(d, ["-j"], tmpdir)
        check("large-range tile roundtrips exactly", np.array_equal(out, d))
        check("upper plane stored when needed",
              all(u > 0 for u in upper_lengths(fz)))

        # ------------------------------------------------------------------
        print("== baseline excludes nulls: one BLANK must not inflate output ==")
        d = rng.normal(50000, 3000, (600, 700)).astype(np.int32)
        _, fz_clean = roundtrip(d, ["-j"], tmpdir)
        size_clean = os.path.getsize(fz_clean)
        size_clean_copy = size_clean
        dn = d.copy()
        dn[5, 5] = -2147483648
        out, fz_null = roundtrip(dn, ["-j"], tmpdir, {"BLANK": -2147483648}, raw=True)
        check("roundtrip with null exact", np.array_equal(out, dn))
        size_null = os.path.getsize(fz_null)
        check("compressed size not blown up by the null",
              size_null <= 1.15 * size_clean_copy,
              f"clean={size_clean} null={size_null}")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print(f"\n{npass} passed, {nfail} failed")
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
