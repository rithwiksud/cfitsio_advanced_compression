#!/usr/bin/env python3
"""
Lossless compression-ratio comparison: JPEG-LS vs Rice, Hcompress and GZIP.

Uses the synthetic integer images of Pence, Seaman & White (2009) section 3.1
(see jpegls_synthetic.py), which have known noise properties, plus a smooth
structured image.  All algorithms run lossless, with identical tiling, so the
comparison isolates the codec.

What this asserts, and why those and not others -- the thresholds come from
measuring K (see experiments/fit_k.py), which found for 16-bit images:

    Hcompress K = 0.67    JPEG-LS K = 0.72    Rice K = 1.01    GZIP K = 2.07

so:
  * JPEG-LS beats Rice and GZIP by a clear margin -> asserted strictly.
  * JPEG-LS and Hcompress are within ~1% of each other; JPEG-LS does NOT
    beat Hcompress, so this asserts only that it stays competitive.  Do not
    "fix" a failure here by loosening the tolerance without re-measuring K.

Usage:  python3 test_jpegls_compression_ratio.py
"""

import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from astropy.io import fits

from jpegls_synthetic import nbits_image, gaussian_image

HERE = os.path.dirname(os.path.abspath(__file__))
FPACK = os.path.join(HERE, "fpack")
FUNPACK = os.path.join(HERE, "funpack")

TILE = "512,512"

ALGOS = {
    "JPEG-LS":   ["-j"],
    "Rice":      ["-r"],
    "Hcompress": ["-h", "-s", "0"],   # scale 0 = lossless
    "GZIP":      ["-g"],
}

# JPEG-LS must not fall below Hcompress by more than this fraction.
HCOMPRESS_TOLERANCE = 0.05


def measure(data, flags, tmpdir):
    """Compress and decompress; return (ratio, lossless, message)."""
    src = os.path.join(tmpdir, "in.fit")
    fz = src + ".fz"
    out = os.path.join(tmpdir, "out.fit")
    for f in (src, fz, out):
        if os.path.exists(f):
            os.remove(f)

    fits.PrimaryHDU(data).writeto(src, overwrite=True)

    p = subprocess.run([FPACK] + flags + ["-t", TILE, src],
                       capture_output=True, text=True)
    if p.returncode != 0 or not os.path.exists(fz):
        return None, False, (p.stdout + p.stderr).strip().splitlines()[:1]

    p = subprocess.run([FUNPACK, "-O", out, fz], capture_output=True, text=True)
    if p.returncode != 0:
        return None, False, "funpack failed"

    # CHECK: the codec really was lossless. A ratio from an accidentally
    # lossy run (e.g. Hcompress with a non-zero scale) would look great and
    # mean nothing, so losslessness is verified rather than assumed.
    decoded = fits.getdata(out)
    lossless = np.array_equal(decoded.astype(np.int64), data.astype(np.int64))

    with fits.open(fz, disable_image_compression=True) as hdul:
        comp_bytes = hdul[1].size

    raw_bytes = data.size * data.dtype.itemsize
    return raw_bytes / comp_bytes, lossless, ""


def main():
    for binary in (FPACK, FUNPACK):
        if not os.path.exists(binary):
            sys.exit(f"missing {binary} - run 'make fpack funpack' first")

    shape = (512, 512)
    y, x = np.mgrid[0:512, 0:512]

    cases = []
    # Pence set 1: exactly N bits of uniform noise.
    for n in (2, 4, 6, 8, 10, 12):
        cases.append((f"uniform {n:>2} noise bits",
                      nbits_image(n, shape, np.int16, seed=100 + n)))
    # Pence set 2: Gaussian noise.
    for s in (1.0, 8.0, 64.0, 500.0):
        cases.append((f"Gaussian sigma={s:<5g}",
                      gaussian_image(s, shape, np.int16, seed=int(200 + s))))
    # A structured image, which the synthetic sets deliberately lack.
    cases.append(("smooth + Poisson",
                  (1000 + 200 * np.sin(x / 30.0) * np.cos(y / 30.0)
                   + np.random.default_rng(7).poisson(20, shape)).astype(np.int16)))

    tmpdir = tempfile.mkdtemp(prefix="jpegls_ratio_")
    failures = []

    try:
        header = f"{'image':<26} " + " ".join(f"{n:>10}" for n in ALGOS)
        print(header)
        print("-" * len(header))

        for label, data in cases:
            ratios = {}
            for name, flags in ALGOS.items():
                ratio, lossless, msg = measure(data, flags, tmpdir)
                if ratio is None:
                    failures.append(f"{label}: {name} failed to compress ({msg})")
                    continue
                if not lossless:
                    failures.append(f"{label}: {name} was NOT lossless")
                ratios[name] = ratio

            print(f"{label:<26} " + " ".join(f"{ratios.get(n, float('nan')):>10.3f}"
                                             for n in ALGOS))

            jls = ratios.get("JPEG-LS")
            if jls is None:
                continue

            # CHECK: JPEG-LS strictly beats Rice and GZIP on every image.
            # Measured K backs this up (JPEG-LS 0.72 vs Rice 1.01, GZIP 2.07),
            # so a regression here means the codec or its tiling broke.
            for weaker in ("Rice", "GZIP"):
                if weaker in ratios and jls <= ratios[weaker]:
                    failures.append(
                        f"{label}: JPEG-LS {jls:.3f} did not beat {weaker} "
                        f"{ratios[weaker]:.3f}")

            # CHECK: JPEG-LS stays competitive with Hcompress -- deliberately
            # NOT "beats". Hcompress edges ahead on structureless noise
            # (K 0.67 vs 0.72) while JPEG-LS wins on structured images. The
            # honest assertion is a bounded gap, not superiority.
            hc = ratios.get("Hcompress")
            if hc is not None and jls < hc * (1.0 - HCOMPRESS_TOLERANCE):
                failures.append(
                    f"{label}: JPEG-LS {jls:.3f} fell more than "
                    f"{HCOMPRESS_TOLERANCE:.0%} below Hcompress {hc:.3f}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print()
    if failures:
        for f in failures:
            print(f"FAIL  {f}")
        print(f"\n{len(failures)} failure(s)")
        return 1

    print("All ratio checks passed "
          "(JPEG-LS > Rice and > GZIP; within "
          f"{HCOMPRESS_TOLERANCE:.0%} of Hcompress; all algorithms lossless)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
