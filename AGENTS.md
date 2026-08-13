# AGENTS.md — map of this fork for AI agents and new contributors

This is a fork of HEASARC CFITSIO (base: 4.7.0, commit `b05876e7`) whose
purpose is **JPEG-LS (ISO/IEC 14495-1) tiled image compression** for
astronomical FITS data, with lossless and near-lossless (`-jN`) modes. It is
one half of a larger project (the sibling `astropy/` checkout in the parent
directory is the other half) aiming at cross-compatible compression between
C ground/flight tools (fpack/funpack) and Python tools (astropy).

Read these first, in order:

1. `CHANGELOG.md` — every fork commit and what it did, oldest first.
2. The design-notes comment block in `imcompress.c` (search for
   "JPEG-LS (ISO/IEC 14495-1) tile compression") — the authoritative spec of
   the container format and the near-lossless guarantees.
3. `UPSTREAM_FIXES.md` — fixes to *shared* CFITSIO code (not JPEG-LS
   specific) that should be merged into upstream HEASARC CFITSIO.
4. `docs/JPEGLS.md` — benchmark results and methodology.
5. `../CLAUDE.md` (parent directory, if present) — the cross-repo project
   context, including the Astropy side and the known cross-compatibility
   issues between the two toolchains.

## Fork-created files

| File | What it is |
|------|-----------|
| `CHANGELOG.md` | Per-commit history of the fork |
| `UPSTREAM_FIXES.md` | Shared-code fixes worth upstreaming (funpack 2D-tile null bug) |
| `AGENTS.md` | This file |
| `charls/` | CharLS 3.0.x, vendored as a git submodule (stock, no patches) |
| `docs/JPEGLS.md` | Benchmarks: ratio/speed/memory vs Rice, GZIP, Hcompress |
| `docs/maxerr_vs_ratio.png`, `docs/k_comparison.png` | Benchmark plots |
| `jpegls_synthetic.py` | Generates synthetic FITS test data (noise ramps, Gaussians, Poisson) |
| `test_jpegls_nearlossless.py` | Round-trip sweep: `-j0` bit-exact, `-jN` max-error bound, buffer-growth regression |
| `test_jpegls_guards.py` | Null preservation under NEAR, lossy `-D` prompt, INT32_MAX saturation, baseline null-exclusion, `upper_len == 0` sentinel, funpack 2D-tile fix |
| `test_jpegls_compression_ratio.py` | Ratio floors vs Rice/GZIP/Hcompress; verifies losslessness |
| `test_jpegls_compression.c` | C-level unit test of the encode/decode wrappers |
| `.github/workflows/jpegls.yml` | CI: autotools + CMake builds, with/without CharLS, runs all three Python suites |

## Fork-modified files

| File | Nature of changes |
|------|-------------------|
| `imcompress.c` | All JPEG-LS code: encoder/decoder wrappers, dispatch, container format, null/saturation guards; plus the shared funpack fix in `fits_read_write_compressed_img` (see `UPSTREAM_FIXES.md`) |
| `fitsio.h` | `JPEGLS_1 = 61`, `jpegls_maxerr` fields, `fits_set/get_jpegls_maxerr` prototypes |
| `utilities/fpack.c`, `fpack.h`, `fpackutil.c` | `-j[N]` flag, help text, lossy flag for `-jN`, default tiling |
| `Makefile.am`, `Makefile.in`, `CMakeLists.txt` | CharLS detection (`HAVE_CHARLS`), include/link wiring; builds cleanly without the submodule |
| `.github/workflows/ci.yml`, `codeql.yml` | Submodule checkout for CI |
| `README.md`, `.gitignore`, `.gitmodules` | Housekeeping |

## Invariants to preserve when changing the codec

- **16-bit conversion is arithmetic** (`value + 32768`), not a bitwise cast.
  This is deliberate (FITS BZERO semantics) and is the known
  cross-compatibility gap with astropy's current JPEGLS codec — do not
  "fix" one side without the other.
- **32-bit container**: `[4B upper_len BE][4B baseline BE][upper][lower]`;
  lower length inferred; `upper_len == 0` means implicit all-zero upper
  plane; baseline = min over non-null pixels; null pixels wrap mod 2^32.
- **Near-lossless never touches nulls**: tiles containing the null marker
  are encoded with NEAR = 0. NEAR lives in each codestream, so this needs no
  header support — any decoder change must keep reading NEAR per stream.
- **Decode saturation at 2^32-1 only when the lower stream's NEAR > 0.**
  Lossless tiles rely on exact modulo-2^32 arithmetic for the wrapped nulls.
- The upper plane of a 32-bit split is **always lossless** (a high-plane
  error of 1 is 65536 in the output).
- `CFITSIO_JPEGLS_NO_TILE_BASELINE=1` is a benchmarking escape hatch, not a
  compatibility mode.

## Running the tests

```sh
make fpack funpack -j
python3 test_jpegls_nearlossless.py     # 99 round-trip/error-bound cases
python3 test_jpegls_guards.py           # 23 null/overflow/container guards
python3 test_jpegls_compression_ratio.py
```

Requires numpy and astropy (any recent pip version; the tests drive the
fpack/funpack binaries, not CFITSIO bindings).
