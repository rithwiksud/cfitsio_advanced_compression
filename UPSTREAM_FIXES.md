# Fixes to shared CFITSIO code that should be merged upstream

This fork's purpose is JPEG-LS support, but along the way we found and fixed
bugs in code paths that ship in stock HEASARC CFITSIO and affect the
existing codecs (Rice, GZIP, Hcompress, PLIO). These are independent of
JPEG-LS and are good candidates for an upstream pull request or bug report.

## 1. funpack scrambles float images containing nulls when tiles are 2D

**File:** `imcompress.c`, `fits_read_write_compressed_img()`
**Symptom:** `funpack` of a floating-point compressed image that contains
undefined pixels (NaNs) silently misplaces pixels whenever the tiling is a
true 2D grid smaller than the image — e.g. `fpack -t 512,512` with Rice or
GZIP on any float image with NaNs. Values land at wrong coordinates and the
NaN mask is scattered; no error is reported.

**Root cause:** when a decompressed tile contained nulls, the tile was
written to the output file with `fits_write_imgnull()` at a *running linear
pixel offset* (`firstelem`), which implicitly assumes every tile spans the
full image width. The code even carried a comment admitting the assumption
("this assumes that the tiled pixels are in the same order as in the
uncompressed FITS image... it almost alway is in practice"). The assumption
holds for the traditional row-by-row default tiling, which is why the bug
went unnoticed; it fails for any 2D tiling.

**Fix in this fork:** for `TFLOAT`/`TDOUBLE` output, substitute the FITS
null representation (NaN) directly into the tile buffer, then write the tile
with the strided `fits_write_subset()`, which places every tile shape
correctly. The legacy `fits_write_imgnull` path is kept for other datatypes
(not reachable via `fits_img_decompress`, which enables null checking only
for float and double images).

**Reproduction (against stock CFITSIO):**

```sh
# any float FITS image with NaNs
fpack -t 512,512 image.fit     # Rice, 2D tiles
funpack image.fit.fz           # output image is scrambled, silently
```

Regression-tested in `test_jpegls_guards.py` ("shared funpack fix" section),
which runs the same scenario with Rice `-t 512,512` and verifies both the
NaN mask and the pixel values. Astropy's independent decoder reads the same
`.fz` correctly, confirming the compressed file is valid and the bug is
purely in the funpack write path.

## 2. (Minor) `fits_read_write_compressed_img` never sets `*anynul`

**File:** `imcompress.c`, `fits_read_write_compressed_img()`
**Note:** the function initializes `*anynul = 0` and tests `anynul` as a
pointer, but never sets `*anynul = 1` when a tile reports nulls. Callers
that rely on it (none in this repo — `fits_img_decompress` ignores it) would
always see 0. Not fixed here since nothing consumes the value; flagging it
for whoever touches this function upstream.

---

Everything else in this fork (the JPEG-LS codec itself, its container
format, near-lossless guards, fpack `-j` flag, tests, CI) is fork-specific
and documented in `CHANGELOG.md`.
