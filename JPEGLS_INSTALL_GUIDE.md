# Using JPEG-LS-enabled CFITSIO in an existing C project

This guide is for someone who already has a C project that links against
stock CFITSIO and wants it to handle FITS files compressed with JPEG-LS
(`ZCMPTYPE = 'JPEGLS_1'`).

**No C source changes are needed to read JPEG-LS files.**
`fits_open_file`, `fits_read_img`, `fits_read_pix` and the rest decompress
JPEG-LS tiles automatically, exactly as they already handle RICE or GZIP.
The only thing that changes is *which* CFITSIO your project uses.

Writing JPEG-LS is different: `JPEGLS_1` and `fits_set_jpegls_maxerr()`
do not exist in stock `fitsio.h`, so code that *creates* JPEG-LS files must
be recompiled against the new header.

## Three ways to do this

| | What it does | Best when |
|---|---|---|
| **Option A** | Build the fork somewhere and repoint your project's `-I`/`-L` flags at it | You want to change nothing outside your own project |
| **Option B** | Build the fork and install it over your existing CFITSIO prefix | Your project links `-lcfitsio` with no hardcoded path |
| **Option C** | `brew tap` + `brew install` (macOS) | You are on macOS and want the shortest path |

Option C is the least work and needs no build steps; start there if you are
on macOS. Options A and B share Steps 1-3 below and diverge at Step 4.

## Prerequisites

- macOS with Xcode command line tools (`xcode-select --install`), or Linux
- `cmake`
- `git`

---

# Option C — Homebrew (macOS)

```bash
brew tap rithwiksud/astro https://github.com/rithwiksud/cfitsio_advanced_compression
brew install rithwiksud/astro/cfitsio
```

This builds CharLS and CFITSIO, puts `fpack` and `funpack` on your `PATH`,
and links `fitsio.h` and `libcfitsio.dylib` into `/opt/homebrew/include` and
`/opt/homebrew/lib` — the same locations the stock `cfitsio` formula uses.
It compiles from source and takes a minute or two.

Check it worked:

```bash
fpack -j -O test.fits.fz your_image.fits    # -j = JPEG-LS
```

## Building your project

Your existing link line works unchanged. No `-lcharls`, no `-lc++`, no
rpath, no `DYLD_LIBRARY_PATH`:

```bash
gcc myprogram.c -I/opt/homebrew/include -L/opt/homebrew/lib -lcfitsio -lm -o myprogram
```

CharLS is compiled into `libcfitsio.dylib`, so there is nothing extra to
resolve.

## If you already have stock CFITSIO from Homebrew

Both install the same files, so only one can be active. Swap:

```bash
brew uninstall cfitsio        # or: brew unlink cfitsio
brew tap rithwiksud/astro https://github.com/rithwiksud/cfitsio_advanced_compression
brew install rithwiksud/astro/cfitsio
```

To go back to stock at any time:

```bash
brew uninstall rithwiksud/astro/cfitsio
brew install cfitsio
```

Programs that were already built against the Homebrew CFITSIO **do not need
recompiling** to read JPEG-LS. The fork installs to the same
`/opt/homebrew/opt/cfitsio` path and keeps the same library version
(`SOVERSION 10`, 4.7.0), so existing binaries load the new library and gain
JPEG-LS support as-is.

Other Homebrew packages that link CFITSIO — `astrometry-net`, `gnuastro`,
`healpix`, `montage` and roughly thirty others — keep working for the same
reason: the fork is a superset of upstream 4.7.0. Check anything you depend
on heavily before relying on this.

## If your stock CFITSIO was NOT installed with Homebrew

This is the case if you built CFITSIO from source (`./configure && make
install`, or CMake), installed it from a package manager other than
Homebrew, or got it as part of another toolchain. It usually lives in
`/usr/local`, sometimes `/opt/local` (MacPorts) or a conda environment.

Homebrew will not touch that installation. You now have two CFITSIOs on the
machine, and the one your project picks depends entirely on its `-I`/`-L`
flags. Find out what you have:

```bash
# where is the non-Homebrew one?
find /usr/local /opt/local -name "fitsio.h" 2>/dev/null

# which fpack is first on PATH?
which -a fpack

# which library does an already-built program use?
otool -L myprogram | grep cfitsio        # Linux: ldd myprogram | grep cfitsio
```

Then pick one of these.

**1. Point your project at the Homebrew copy explicitly.** Put the Homebrew
paths *first* so they win:

```bash
gcc myprogram.c -I/opt/homebrew/include -L/opt/homebrew/lib -lcfitsio -lm -o myprogram
```

Confirm with `otool -L myprogram` that it resolves to
`/opt/homebrew/opt/cfitsio/lib/libcfitsio.10.dylib` and not your old copy.
This is the safest choice: your existing installation is left alone.

**2. Or replace the old installation instead**, using Option B below with
`<prefix>` set to wherever that CFITSIO lives (typically `/usr/local`). Then
every project on the machine, including ones you have not rebuilt, gets
JPEG-LS without any flag changes. Use this when the old installation is the
one everything already points at.

Do not install the fork over `/usr/local` *and* brew-install it. Two copies
in two prefixes is exactly how you end up debugging which one a program
loaded.

## Caveats

- Every install compiles from source; there are no prebuilt bottles.
- **Python tooling is unaffected.** Astropy does not link `libcfitsio` (it
  has its own compression code), and the PyPI `fitsio` package bundles its
  own copy. Neither sees this change.
- On Linux, Homebrew works but building from source (Options A/B) is the
  usual route.

---

# Options A and B — build from source

## Step 1: Get the code

CharLS (the JPEG-LS codec) is a git submodule, so clone recursively:

```bash
mkdir -p ~/dev && cd ~/dev
git clone --recursive https://github.com/rithwiksud/cfitsio_advanced_compression.git
cd cfitsio_advanced_compression
```

If you already cloned without `--recursive`:

```bash
git submodule update --init
```

Either way, confirm CharLS is present:

```bash
ls charls/include/charls/charls.h
```

## Step 2: Build CharLS

```bash
cmake -S charls -B charls/build -DCMAKE_BUILD_TYPE=Release \
      -DBUILD_SHARED_LIBS=OFF -DCHARLS_BUILD_TESTS=OFF \
      -DCMAKE_POSITION_INDEPENDENT_CODE=ON
cmake --build charls/build -j
```

This produces `charls/build/libcharls.a`.

## Step 3: Build CFITSIO

The Makefile finds `charls/` on its own and adds the include and link flags,
so no extra configure arguments are needed:

```bash
./configure
make -j
```

**If `make` stops on `testf77` with `ld: library 'curl' not found`**, rebuild
without Fortran:

```bash
./configure --without-fortran
make -j
```

That failure comes from a Homebrew `gfortran`, which does not search the
macOS SDK where `libcurl.tbd` lives. Only the Fortran test program is
affected — the C library, `fpack` and `funpack` build fine — but the failure
stops the build and silently prevents `make install` from installing
anything. Nothing in JPEG-LS uses Fortran.

You now have:

```
~/dev/cfitsio_advanced_compression/.libs/libcfitsio.a       (static)
~/dev/cfitsio_advanced_compression/.libs/libcfitsio.dylib   (shared)
~/dev/cfitsio_advanced_compression/fitsio.h                 (same API, plus JPEG-LS)
```

Confirm JPEG-LS is compiled in, using any FITS image:

```bash
./fpack -j test.fits
```

If that writes `test.fits.fz` without errors, the build is good. If CharLS
was missing at build time, CFITSIO still builds but `-j` fails at run time
with "CFITSIO was built without CharLS".

## Step 4A: Option A — point your project at the new library

In your project's Makefile, CMakeLists.txt or Xcode settings, change both
the include path and the library path:

**Before**
```
-I/path/to/old/cfitsio
-L/path/to/old/cfitsio -lcfitsio
```

**After**
```
-I$HOME/dev/cfitsio_advanced_compression
-L$HOME/dev/cfitsio_advanced_compression/.libs -lcfitsio
```

CharLS must also be linked, along with the C++ runtime it needs
(`-lc++` on macOS, `-lstdc++` on Linux), after `-lcharls`:

```
-L$HOME/dev/cfitsio_advanced_compression/charls/build -lcharls -lc++
```

### Make sure the program can find the library at run time

`make` leaves a shared library in `.libs/`, but the path recorded in your
program points at the *install* directory, which does not exist until you run
`make install`. A program linked against `.libs` can build cleanly and then
fail to start:

```
# Linux
libcfitsio.so.10: cannot open shared object file: No such file or directory
# macOS
dyld: Library not loaded: <prefix>/lib/libcfitsio.10.dylib
```

**Recommended: link CFITSIO statically.** Name the archive directly instead
of using `-lcfitsio`. There is then no shared library to locate, so no rpath
and no `DYLD_LIBRARY_PATH` to manage:

```bash
gcc myprogram.c \
  -I$HOME/dev/cfitsio_advanced_compression \
  $HOME/dev/cfitsio_advanced_compression/.libs/libcfitsio.a \
  -L$HOME/dev/cfitsio_advanced_compression/charls/build -lcharls -lc++ \
  -lm -lcurl -lz -o myprogram
```

`-lcurl` and `-lz` are required because a static CFITSIO no longer carries
its own dependencies. Drop `-lcurl` if CFITSIO was configured without curl.

**On Linux**, `-Wl,-rpath` is an alternative:

```bash
gcc myprogram.c \
  -I$HOME/dev/cfitsio_advanced_compression \
  -L$HOME/dev/cfitsio_advanced_compression/.libs -lcfitsio \
  -Wl,-rpath,$HOME/dev/cfitsio_advanced_compression/.libs \
  -L$HOME/dev/cfitsio_advanced_compression/charls/build -lcharls -lstdc++ \
  -lm -o myprogram
```

**`-Wl,-rpath` does not work on macOS here.** Libtool gives
`libcfitsio.dylib` an install_name that is an absolute path
(`<prefix>/lib/libcfitsio.10.dylib`) rather than `@rpath/...`; check with
`otool -D .libs/libcfitsio.10.dylib`. dyld follows that absolute path and
never consults the rpath. On macOS, link statically or use Option B.

`DYLD_LIBRARY_PATH` (Linux: `LD_LIBRARY_PATH`) also works, but must be set by
every user, script and service that runs the program, and it affects library
resolution for the whole process. Prefer static linking or a real install.

If your build uses a variable like `CFITSIO_DIR`, repoint it at
`~/dev/cfitsio_advanced_compression` and add the CharLS flags alongside.

Then go to Step 5.

## Step 4B: Option B — install over your existing CFITSIO

Use this when your project does `#include <fitsio.h>` and links `-lcfitsio`
without a hardcoded path.

**1. Find your current installation.**

```bash
brew --prefix cfitsio                                   # if it came from Homebrew
find /usr /opt /usr/local -name "fitsio.h" 2>/dev/null   # otherwise
```

That gives a prefix such as `/usr/local` or `/opt/homebrew`; call it
`<prefix>`.

**2. Install CharLS and CFITSIO there.**

```bash
cmake --install charls/build --prefix <prefix>

make clean
./configure --prefix=<prefix>          # add --without-fortran if needed
make -j
make install
```

**`make clean` is required on macOS.** If you already built in Step 3 without
`--prefix`, the object files are unchanged, so `make` will not relink
`libcfitsio.dylib`, and `make install` copies a library whose install_name
still points at the old location. Everything linking it — including the
newly installed `fpack` — then aborts at startup with `Library not loaded:`
naming a path in your source tree. Verify afterwards:

```bash
otool -D <prefix>/lib/libcfitsio.10.dylib    # must print <prefix>/lib/...
```

This overwrites `fitsio.h` and `libcfitsio.*` at `<prefix>`, so any project
building against `-I<prefix>/include -L<prefix>/lib -lcfitsio` picks up
JPEG-LS.

**3. Usually nothing else changes.**

Projects linking the shared library need no build-file change: CharLS is
absorbed into `libcfitsio.dylib`/`.so`, leaving no symbols for your program
to resolve.

Add `-lcharls -lc++` (macOS) or `-lcharls -lstdc++` (Linux) only if you link
CFITSIO **statically**. `libcharls.a` is installed alongside `libcfitsio` in
`<prefix>/lib`, so no extra `-L` is needed. Adding the flags when linking
shared is harmless.

**Caveats:**

- If `<prefix>` is Homebrew-managed, a later `brew upgrade` or
  `brew reinstall cfitsio` silently replaces your build with stock CFITSIO.
  Use Option C on a Homebrew prefix instead.
- Architecture must match (arm64 vs x86_64).
- It is shared, system-wide state: every project using `<prefix>` gets the
  fork. Usually harmless, since it is a superset of stock CFITSIO.
- To undo, reinstall stock CFITSIO over the same prefix.

## Step 5: Verify

Run your program against a JPEG-LS file — one from `fpack -j`, or written by
Astropy's `JPEGLS` codec. Existing read calls work unchanged.

To make a test file:

```bash
~/dev/cfitsio_advanced_compression/fpack -j some_image.fits
```

---

# Distributing a prebuilt dylib

Handing colleagues a prebuilt `libcfitsio.dylib` to drop into place is
fragile on macOS, for reasons that are easy to miss:

- **Architecture.** A normal build is single-architecture and will not load
  on a Mac of the other kind. A distributable build needs
  `-arch arm64 -arch x86_64`, or two builds joined with `lipo -create`.
- **install_name.** The library records the absolute path it expects to live
  at (`otool -D`). Placed anywhere else, every program linking it aborts with
  `Library not loaded:`. A distributable library needs an install_name of
  `@rpath/libcfitsio.10.dylib` — the CMake build sets this, the autotools
  build does not — or `install_name_tool -id` applied afterwards.
- **Minimum OS.** The build records `minos` from the SDK it was built
  against, and older systems refuse it. Set `-mmacosx-version-min=` to the
  oldest macOS you support.
- **Gatekeeper.** Locally built libraries are only ad-hoc signed. Once
  downloaded they carry a quarantine attribute and may be refused; real
  distribution means Developer ID signing and notarization.
- **The header.** The library alone lets existing programs *read* JPEG-LS.
  Calling `fits_set_jpegls_maxerr()` needs the matching `fitsio.h`, so ship
  both.
- **Dependencies** are only `libSystem`, `libcurl`, `libz` and `libc++`, all
  of which ship with macOS — provided you did not build against Homebrew's
  curl or zlib.

For a genuine single-file hand-off, prefer the static `libcfitsio.a` built
universal: no install_name, no rpath, no dyld involvement, CharLS already
inside. Recipients relink rather than swap a file.

# Common pitfalls

- **`charls/` is empty** — cloned without `--recursive`. Run
  `git submodule update --init`.
- **`make` fails with `ld: library 'curl' not found` on `testf77`** — use
  `./configure --without-fortran`. This failure also prevents `make install`
  from installing anything, even with `make -k`.
- **"Undefined symbols for architecture…" at link time** — `-lcharls`, its
  `-L` path, or the C++ runtime is missing. `-lc++`/`-lstdc++` must come
  after `-lcharls`.
- **Builds fine, fails to start** with `libcfitsio.so.10: cannot open shared
  object file` (Linux) or `dyld: Library not loaded:` (macOS) — the recorded
  library path is the install directory and you have not run `make install`.
  On macOS `-Wl,-rpath` does not fix this; link statically or install.
- **"Unknown image compression type" at run time** — the program is loading a
  different CFITSIO. Run `otool -L myprogram` (Linux: `ldd`) and check which
  `libcfitsio` it names; fix `-L` order or link statically.
- **`fpack -j` says "CFITSIO was built without CharLS"** — CFITSIO was built
  with `charls/` missing or empty. Re-run Step 1, then rebuild.
- **Linux** — steps are identical, except link `-lstdc++` instead of `-lc++`.
