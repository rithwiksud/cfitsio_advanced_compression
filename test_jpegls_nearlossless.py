#!/usr/bin/env python3
"""
JPEG-LS test suite for fpack/funpack.

Drives the fpack and funpack binaries directly (no CFITSIO Python bindings),
and for every case checks that the round-tripped image satisfies the max
error (NEAR) bound that was requested on the command line.

  * MAXERR = 0 must be bit-exact.
  * MAXERR = N must satisfy  max|original - decoded| <= N.

Also covers the tile-buffer regression cases: JPEG-LS can *expand*
incompressible data, so high-entropy tiles must still compress (the encoder
grows its output buffer and retries) rather than failing outright.

Usage:  python3 test_jpegls_nearlossless.py
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

# 0..8 as the main sweep, plus 16 and 32 to confirm larger NEAR values work.
MAX_ERRORS = list(range(0, 9)) + [16, 32]


def run(cmd):
    """Run a command, returning (ok, combined_output)."""
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode == 0, (p.stdout + p.stderr).strip()


def roundtrip(data, max_err, tmpdir):
    """fpack -j<max_err> then funpack. Returns (ok, decoded_or_None, msg)."""
    src = os.path.join(tmpdir, "in.fit")
    packed = src + ".fz"
    out = os.path.join(tmpdir, "out.fit")
    for f in (src, packed, out):
        if os.path.exists(f):
            os.remove(f)

    fits.PrimaryHDU(data).writeto(src, overwrite=True)

    ok, msg = run([FPACK, f"-j{max_err}", src])
    if not ok:
        return False, None, f"fpack failed: {msg}"
    if not os.path.exists(packed):
        return False, None, "fpack produced no .fz"

    ok, msg = run([FUNPACK, "-O", out, packed])
    if not ok:
        return False, None, f"funpack failed: {msg}"

    return True, fits.getdata(out), ""


def check(name, data, tmpdir, results):
    """Run the full MAXERR sweep for one image, recording pass/fail."""
    for max_err in MAX_ERRORS:
        label = f"{name:<28} -j{max_err:<3}"
        ok, decoded, msg = roundtrip(data, max_err, tmpdir)

        if not ok:
            results.append((label, False, msg))
            continue

        if decoded.shape != data.shape:
            results.append((label, False, f"shape {decoded.shape} != {data.shape}"))
            continue

        # CHECK: the per-pixel error bound.
        # Compared in int64 because the data may be unsigned: subtracting in
        # the native dtype would wrap around and silently hide a large error
        # as a small one.
        diff = np.abs(decoded.astype(np.int64) - data.astype(np.int64))
        observed = int(diff.max())

        if max_err == 0:
            # CHECK (lossless): -j0 must be bit-identical. Any difference at
            # all is a correctness bug, not a tolerance question.
            passed = observed == 0
            detail = "bit-exact" if passed else f"lossless violated, max diff {observed}"
        else:
            # CHECK (near-lossless): -jN promises max|orig - decoded| <= N.
            # This is the contract the flag advertises, so it is asserted
            # exactly, not approximately.
            passed = observed <= max_err
            detail = f"max diff {observed} <= {max_err}"
            if not passed:
                detail = f"max diff {observed} EXCEEDS {max_err}"

        results.append((label, passed, detail))


def main():
    for binary in (FPACK, FUNPACK):
        if not os.path.exists(binary):
            sys.exit(f"missing {binary} - run 'make fpack funpack' first")

    rng = np.random.default_rng(42)
    tmpdir = tempfile.mkdtemp(prefix="jpegls_test_")
    results = []

    y, x = np.mgrid[0:256, 0:256]
    smooth = 1000 + 50 * np.sin(x / 20.0) + 50 * np.cos(y / 25.0)

    # --- data types -----------------------------------------------------
    # CHECKS: every integer type JPEG-LS claims to support survives a
    # round-trip. FITS stores unsigned types via BZERO, and has no native
    # signed-byte BITPIX, so int8 is deliberately absent. int32/uint32
    # exercise the two-plane split path, which is separate code from 8/16-bit.
    cases = [
        ("uint8", (smooth / 8).astype(np.uint8)),
        ("int16", (smooth + rng.poisson(30, smooth.shape)).astype(np.int16)),
        ("uint16", (smooth + rng.poisson(30, smooth.shape)).astype(np.uint16)),
        ("int32", (smooth * 100 + rng.poisson(30, smooth.shape)).astype(np.int32)),
        ("uint32", (smooth * 100 + rng.poisson(30, smooth.shape)).astype(np.uint32)),
    ]

    # --- buffer regressions: incompressible / high-entropy tiles ---------
    # CHECKS two distinct bugs that both aborted the entire file:
    #  * Random 16-bit tiles are incompressible, and JPEG-LS *expands* such
    #    data by up to 6.25%. The output buffer used to be sized without that
    #    allowance, so encoding failed outright. Pins the grow-and-retry fix.
    #  * Wide-range int32 puts real entropy in BOTH 16-bit planes, so the
    #    high plane no longer compresses under the old 2-byte (64 KB) length
    #    header. Pins the 4-byte header.
    cases += [
        ("uint16 random (incompress.)", rng.integers(0, 65535, (512, 512)).astype(np.uint16)),
        ("int16 random (incompress.)", rng.integers(-32768, 32767, (512, 512)).astype(np.int16)),
        ("int32 wide dynamic range", rng.integers(0, 2**31 - 1, (256, 256)).astype(np.int32)),
    ]

    # --- multidimensional ------------------------------------------------
    cases += [
        ("3D cube (int16)", (smooth[None, :, :] + rng.poisson(5, (4, 256, 256))).astype(np.int16)),
    ]

    try:
        for name, data in cases:
            check(name, data, tmpdir, results)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    width = max(len(label) for label, _, _ in results)
    passed = 0
    for label, ok, detail in results:
        mark = "PASS" if ok else "FAIL"
        passed += ok
        print(f"{label:<{width}}  {mark}  {detail}")

    total = len(results)
    print(f"\n{passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
