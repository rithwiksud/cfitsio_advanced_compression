# Changelog

This fork adds JPEG-LS (ISO/IEC 14495-1, via CharLS) tiled image compression
to CFITSIO, with lossless and near-lossless modes, plus fixes to shared
CFITSIO code found along the way (see `UPSTREAM_FIXES.md` for the changes
that should be merged back into HEASARC CFITSIO).

Base: upstream HEASARC CFITSIO 4.7.0, commit `b05876e7` ("Additional version
string updates"). Everything below is fork work on top of that commit,
oldest first.

---

## 2026-07-25 — `7afa21d1` Add JPEG-LS tiled compression support (JPEGLS_1)

The initial integration. Defines `JPEGLS_1 = 61` in `fitsio.h`, adds
`imcomp_jpegls_encode()` / `imcomp_jpegls_decode()` wrappers around the
CharLS C API in `imcompress.c`, encode/decode dispatch for 8-, 16- and
32-bit integer tiles (16-bit uses the arithmetic `value + 32768` conversion
to match FITS BZERO semantics; 32-bit splits into two 16-bit planes), a
512x512 default 2D tile shape, `ZCMPTYPE = 'JPEGLS'` header handling, the
`-j` flag in fpack, and `fits_set_jpegls_maxerr` / `fits_get_jpegls_maxerr`
API entry points.

## 2026-07-25 — `f9e97899` Vendor CharLS as a git submodule

Adds `charls/` (CharLS 3.0.x) as a submodule and wires include/link paths
into the autotools and CMake builds.

## 2026-07-25 — `c1a282bf` Add JPEG-LS near-lossless mode and fix tile buffer sizing

`fpack -jN` sets the JPEG-LS NEAR parameter (max absolute error per sample;
recorded in the codestream so decode needs no external metadata). For split
32-bit tiles NEAR applies to the low plane only, since a high-plane error of
1 would become 65536. Also replaces the worst-case output-buffer allocation
with an optimistic estimate plus a grow-and-retry path for incompressible
tiles (`imcomp_jpegls_max_encoded_size`).

## 2026-07-25 — `565a257c` Widen JPEG-LS 32-bit plane length header from 2 to 4 bytes

The upper-plane stream length in the 32-bit container header grows from 2 to
4 bytes (big-endian), removing a 64 KB cap on the encoded upper plane.

## 2026-07-25 — `9aebea4e` Add JPEG-LS benchmarks, synthetic test data, ratio tests, docs and CI

Adds `test_jpegls_nearlossless.py` (round-trip max-error sweep),
`test_jpegls_compression_ratio.py` (ratio floor vs Rice/GZIP/Hcompress),
`jpegls_synthetic.py` test-data generator, benchmark docs, and the
`jpegls.yml` GitHub Actions workflow.

## 2026-07-25 — `2994e378`, `68a2ba46`, `fbd55a3c`, `eea50bf1`, `c956046f` Benchmark and docs iterations

Benchmark refinements: peak-RSS measurement (median of 5), default-tiling
rows for Rice and Hcompress, near-lossless comparison against quantized Rice
and Hcompress, SDSS sweep capped at max error 2 with the tile-size
explanation for the K-band gap, and a noise-sigma secondary axis on the
near-lossless plot.

## 2026-07-25 — `3900d23b` Fix Linux CI: build CharLS as PIC and link the C++ runtime

## 2026-07-25 — `9bf191eb` Make JPEG-LS support optional

CFITSIO builds without the CharLS submodule: `HAVE_CHARLS` is defined only
when `charls/` is present; without it, `JPEGLS_1` fails cleanly at run time
instead of failing to compile.

## 2026-07-25 — `1e279f22` CI verifies JPEG-LS is compiled in, and covers the no-CharLS path

## 2026-07-25 — `4675b504`, `df69d90b` Build hygiene

Gitignore `make check` artifacts; untrack `tests/.dirstamp`.

## 2026-08-12 — `48845af4` Warn when near-lossless JPEG-LS is combined with float quantization

`fpack -jN` on a floating-point image now prints an advisory: the NEAR error
is incurred in already-quantized integer units and is rescaled by the
per-tile BSCALE on decode, so the error in physical units is
BSCALE-dependent, not simply N.

## 2026-08-12 — `c9777011` Fix JPEG-LS 32-bit tile compression regressing near 65536-multiple boundaries

Introduces the per-tile baseline rebase: before splitting a 32-bit tile into
16-bit planes, the tile is rebased to its own minimum value. Without this,
nearly-identical neighboring pixels straddling a fixed 65536 boundary wrap
around in the lower plane and wreck JPEG-LS's local prediction. The
container header becomes `[4-byte upper_len BE][4-byte baseline BE]`, with
the lower stream's length inferred from the remaining bytes. (Breaking
format change vs. the earlier `[upper_len][lower_len]` header; no version
marker, old files are not supported.)

## 2026-08-12 — `4be10189` Add test-only escape hatch to disable JPEG-LS per-tile baseline rebase

`CFITSIO_JPEGLS_NO_TILE_BASELINE=1` forces baseline 0 for benchmarking the
rebase itself.

## 2026-08-13 — Correctness guards: null preservation, overflow saturation, lossy flag, and a shared funpack fix

Five fixes from a review of the CharLS integration, plus one upstream bug
found while verifying them (all covered by the new `test_jpegls_guards.py`,
which also runs in CI):

- **Null pixels survive near-lossless compression.** NEAR > 0 could perturb
  the null marker itself (BLANK for integer images, the quantized
  `COMPRESS_NULL_VALUE` for floats), turning nulls into valid-looking values
  and valid pixels within NEAR of the marker into false nulls. Any tile
  containing the marker is now encoded losslessly; NEAR is per-codestream,
  so decoding handles mixed tiles automatically.
- **The 32-bit per-tile baseline excludes null pixels.** A single BLANK (a
  huge negative reserved value) used to become the tile baseline, putting
  all real pixels back at their raw absolute offsets and forfeiting the
  rebase. Excluded null pixels wrap modulo 2^32 in the split, which the
  decoder's modulo arithmetic reconstructs exactly.
- **32-bit near-lossless reconstruction saturates at 2^32-1.** The low
  plane's NEAR error could wrap `(split + baseline)` past 2^32-1 for values
  within NEAR of INT32_MAX, turning an error of at most NEAR into one of
  ~2^32. `imcomp_jpegls_decode` now reports the stream's NEAR parameter and
  the reconstruction saturates only when NEAR > 0 (lossless tiles keep exact
  modulo arithmetic, which the wrapped nulls depend on).
- **An identically-zero upper plane is elided.** When the rebased tile range
  fits in 16 bits (the common case for real 32-bit data), the encoder writes
  `upper_len = 0` instead of a JPEG-LS stream of zeros, and the decoder
  reconstructs the zero plane directly.
- **fpack treats `-jN` (N > 0) as lossy.** `fpack -jN -D` used to delete the
  original without the "compressed with a LOSSY method" prompt because
  `islossless` was never cleared for near-lossless JPEG-LS.
- **funpack no longer scrambles null-bearing float tiles with 2D tilings**
  (shared-code fix, all codecs; see `UPSTREAM_FIXES.md`).

Also updates the stale `imcomp_calc_max_elem` header comment (the 32-bit
container header is 8 bytes, not 4) and its allocation to match.
