# CFITSIO Interface Library — with JPEG-LS compression

> **This is a fork of [HEASARC/cfitsio](https://github.com/HEASARC/cfitsio)
> that adds JPEG-LS as a tiled-image compression algorithm**, alongside the
> stock Rice, GZIP, PLIO and Hcompress. It supports both fully lossless and
> *near-lossless* compression with a guaranteed per-pixel error bound.
>
> On real telescope images JPEG-LS compresses **3–8% better than Rice**
> losslessly, and near-lossless mode reaches **2–7×** at ±16 depending on how
> noise-dominated the image is. See [docs/JPEGLS.md](docs/JPEGLS.md) for the
> full benchmarks, methodology and a reproduction of the Pence et al. (2009)
> compression-efficiency analysis.

## Quick start: JPEG-LS

JPEG-LS is provided by [CharLS](https://github.com/team-charls/charls),
vendored as a git submodule, so clone with `--recursive` and build it first:

```bash
git clone --recursive https://github.com/rithwiksud/cfitsio_advanced_compression.git
cd cfitsio_advanced_compression

# already cloned without --recursive?
git submodule update --init

# 1. build the CharLS codec
cmake -S charls -B charls/build -DCMAKE_BUILD_TYPE=Release \
      -DBUILD_SHARED_LIBS=OFF -DCHARLS_BUILD_TESTS=OFF \
      -DCMAKE_POSITION_INDEPENDENT_CODE=ON
cmake --build charls/build -j

# 2. build CFITSIO (fpack/funpack)
./configure
make fpack funpack -j
```

### Using it

```bash
./fpack -j   image.fits      # lossless JPEG-LS
./fpack -j0  image.fits      # identical - 0 is the default max error
./fpack -j3  image.fits      # near-lossless, max absolute error 3 per pixel
./fpack -j16 image.fits      # near-lossless, max absolute error 16

./funpack image.fits.fz      # decompress (no flag needed - read from the file)
```

`-jN` sets the JPEG-LS `NEAR` parameter: **every pixel is guaranteed to be
within ±N of its original value**. `N` may be 0–255 (the codec caps it at
`min(255, max_sample/2)` per ISO/IEC 14495-1, so 0–127 for 8-bit data).

**Supported data types**: `uint8`, `int16`, `uint16`, `int32`, `uint32`.
FITS has no signed-byte BITPIX, so `int8` is not applicable. Images of 3+
dimensions are compressed as 2D slices. Tiles default to 512×512.

## Running the tests

```bash
make fpack funpack -j                        # tests drive these binaries
pip install numpy astropy                    # test dependencies

python3 test_jpegls_nearlossless.py          # correctness + error bounds
python3 test_jpegls_compression_ratio.py     # ratio vs Rice/Hcompress/GZIP

make check                                   # stock CFITSIO test suite
```

Both JPEG-LS suites run automatically in CI
(`.github/workflows/jpegls.yml`) on Ubuntu and macOS, together with a CMake
build, on every push and pull request to `main`/`develop`.

### What each test checks

**`test_jpegls_nearlossless.py`** — 99 cases: 9 images × 11 max-error settings
(`-j0` … `-j8`, plus `-j16` and `-j32`), each driving `fpack` and `funpack`
directly.

- **Lossless round-trip** — at `-j0`, decompressed output is *bit-identical*
  to the input. Anything else is a correctness bug.
- **Near-lossless error bound** — at `-jN`, `max|original − decoded| ≤ N`.
  This is the contract `-jN` advertises; it is checked in `int64` so unsigned
  wraparound cannot mask a violation.
- **Data-type coverage** — `uint8`, `int16`, `uint16`, `int32`, `uint32`,
  including the 32-bit two-plane split path.
- **Incompressible-data regression** — pure random `uint16`/`int16` tiles.
  JPEG-LS *expands* such data, which used to overflow the output buffer and
  abort the whole file; this pins the grow-and-retry fix.
- **Wide-dynamic-range regression** — int32 data spanning the full range, so
  both 16-bit planes carry real entropy. This pins the 4-byte plane-length
  header (a 2-byte header capped the high plane at 64 KB).
- **Multidimensional** — a 3D cube round-trips as 2D slices.

**`test_jpegls_compression_ratio.py`** — lossless ratio against the other
codecs, on the Pence synthetic images plus a structured one, all at identical
512×512 tiling.

- **Every codec is verified lossless** before its ratio is used — a ratio from
  an accidentally-lossy run would be meaningless.
- **JPEG-LS beats Rice and GZIP** on every image — asserted strictly.
- **JPEG-LS stays within 5% of Hcompress.** JPEG-LS does *not* uniformly beat
  Hcompress: it wins on structured images and at low noise, and loses slightly
  on pure high-entropy noise. The test asserts competitiveness rather than
  superiority, because that is what the measurements support.

---

CFITSIO is a library of ANSI C routines for reading and writing FITS format data files. A set of Fortran-callable wrapper routines are also included for the convenience of Fortran programmers.  This README file gives a brief summary of how to build and test CFITSIO, but the latest and most complete information may be found in the "docs" folder in the CFITSIO User's Guide:


## User Guides

### User Guides for C programmers

* `cfitsio.tex` (LaTeX source file)
* `cfitsio.pdf` (Portable Document Format)

### User Guides for Fortran programmers

* `fitsio.tex` (LaTeX source file)
* `fitsio.pdf` (Portable Document Format)

### Quick Start Guide

* `quick.tex` (LaTeX source file)
* `quick.pdf` (Portable Document Format)


## Building and Installing CFITSIO

The standard way to build the CFITSIO library from source on Unix-like systems is:

```bash
./configure --prefix=/target/installation/path
make
make install
```

For complete installation and build instructions across all platforms, please see [INSTALL.md](INSTALL.md).

The INSTALL.md guide includes details for:

- Advanced Unix/Linux options (CMake, shared libraries)
- macOS (Xcode, MacPorts, Homebrew, Conda)
- Windows (Visual Studio, CMake)


## Testing CFITSIO

The CFITSIO library may be tested by building and running the `testprog.c` program that is included with the release (in the `utilities` folder). On Unix systems, type:

```bash
% make testprog
% ./testprog > testprog.lis
% diff testprog.lis testprog.out
% cmp testprog.fit testprog.std
```

The `testprog` program should produce a FITS file called `testprog.fit` that is identical to the `testprog.std` FITS file included in this release.  The diagnostic messages (which were piped to the file `testprog.lis` in the Unix example) should be identical to the listing contained in the file `testprog.out`. The `diff` and `cmp` commands shown above should not report any differences in the files.

## Using CFITSIO

The CFITSIO User's Guide, contained in the files mentioned above, provides detailed documentation about how to build and use the CFITSIO library. It contains a description of every user-callable routine in the CFITSIO interface.

The `cookbook.c` file in the utilities folder provides some sample routines for performing common operations on various types of FITS files. Programmers are urged to examine these routines for recommended programming practices when using CFITSIO. Users are free to copy or modify these routines for their own purposes.


## Getting Help

Any problem reports or suggestions for improvements are welcome and should be sent to the CFITSIO/CCFITS help desk at:

[ccfits@heasarc.gsfc.nasa.gov](mailto:ccfits@heasarc.gsfc.nasa.gov)

-------------------------------------------------------------------------
William D. Pence
HEASARC, NASA/GSFC
