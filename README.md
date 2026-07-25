# CFITSIO Interface Library — with JPEG-LS compression

> **This is a fork of [HEASARC/cfitsio](https://github.com/HEASARC/cfitsio)
> that adds JPEG-LS as a tiled-image compression algorithm**, alongside the
> stock Rice, GZIP, PLIO and Hcompress. It supports both fully lossless and
> *near-lossless* compression with a guaranteed per-pixel error bound.
>
> On real telescope images JPEG-LS compresses **3–8% better than Rice**
> losslessly, and near-lossless mode reaches **2–180×** depending on how
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
      -DBUILD_SHARED_LIBS=OFF -DCHARLS_BUILD_TESTS=OFF
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

### User Guides for C programmers
* `cfitsio.tex` (LaTeX source file)
* `cfitsio.ps`  (PostScript file)
* `cfitsio.pdf` (Portable Document Format)

### User Guides for Fortran programmers
* `fitsio.tex` (LaTeX source file)
* `fitsio.ps`  (PostScript file)
* `fitsio.pdf` (Portable Document Format)

### Quick Start Guide
* `quick.tex` (LaTeX source file)
* `quick.ps`  (PostScript file)
* `quick.pdf` (Portable Document Format)

## Building CFITSIO

The CFITSIO code (contained in `*.c` source files and several `*.h` header files) should compile and run on most Unix platforms without modification. The standard way to build the library on Unix systems is the usual GNU-like approach, i.e. by first typing

```bash
% ./configure  [--prefix=/target/installation/path]
```

at the operating system prompt.  Type `./configure` and not simply `configure` to ensure that the configure script in the current directory is run and not some other system-wide configure script. The optional `prefix` argument to configure gives the path to the directory where the CFITSIO library and include files should be installed via the later `make install` command. For example,

```bash
% ./configure --prefix=/usr1/local
```

will cause the later `make install` command to copy the library file(s) to `/usr1/local/lib` and the necessary header files to `/usr1/local/include` (assuming of course that the process has permission to write to these directories).

All the available configure options can be seen by entering the command

```bash
% ./configure --help
```

The configure command customizes the Makefile for a particular system, so after it has been run, type

```bash
% make
```

at the prompt, and this will compile the source files and build the library (static `libcfitsio.a` as well as the shared version `libcfitsio.so|.dylib`) and the helper utilities (`fpack`, `funpack`, `fitscopy`, `imcopy`, et al.) and test program (`testprog`).  To copy the library, header files, and utilities to the chosen install location, type this command:

```bash
% make check
% make install
```

When installing in /usr/local on Linux and some other systems, it may be necessary to rebuild the linker cache by running:

```bash
% sudo ldconfig
```

Alternatively, the library and utilities may be built on many systems using the CMake program.  Specific instructions for using CMake on Windows platforms can be found in the `README.win` file, but for Unix systems (e.g., Linux or macOS) the procedure should be similar to the following:

While in the CFITSIO source code directory:

```bash
% mkdir cmbuild
% cd cmbuild
% cmake -G "Unix Makefiles" ..
% cmake --build .
% cmake --install . [--prefix /usr/local]
```

Where the final step uses an optional installation prefix.

Additional options for installing CFITSIO on macOS via third-party package managers or the XCode GUI can be found in the `README.MacOS` file.


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

Any problem reports or suggestions for improvements are welcome and should be sent to the CFITSIO/CCFITS help desk at:

[ccfits@heasarc.gsfc.nasa.gov](mailto:ccfits@heasarc.gsfc.nasa.gov)

-------------------------------------------------------------------------
William D. Pence
HEASARC, NASA/GSFC
