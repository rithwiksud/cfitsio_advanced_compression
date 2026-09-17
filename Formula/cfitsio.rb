class Cfitsio < Formula
  desc "C access to FITS data files, with JPEG-LS tiled image compression"
  homepage "https://github.com/rithwiksud/cfitsio_advanced_compression"
  url "https://github.com/rithwiksud/cfitsio_advanced_compression.git",
      revision: "74dfe871600da53a631d7be94b9de5e762e6f4b2"
  version "4.7.0-jpegls"
  license "CFITSIO"

  depends_on "cmake" => :build

  # CharLS is a git submodule of the fork.  Pin it explicitly as a resource so
  # the build does not depend on how the downloader handles submodules.
  resource "charls" do
    url "https://github.com/team-charls/charls.git",
        revision: "c0bae6496fa5d787fbb4698debd1e5decb40cf3a"
  end

  def install
    # The submodule directory exists but is empty in a plain checkout.
    rm_r(buildpath/"charls") if (buildpath/"charls").exist?
    (buildpath/"charls").install resource("charls")

    # The CMake build defines HAVE_CHARLS, so JPEG-LS is compiled in, and it
    # gives libcfitsio an @rpath install_name (unlike the autotools build).
    args = %W[
      -DCMAKE_INSTALL_RPATH=#{rpath}
      -DCMAKE_INSTALL_INCLUDEDIR=include
      -DUSE_PTHREADS=ON
      -DTESTS=OFF
    ]

    system "cmake", "-S", ".", "-B", "build", *args, *std_cmake_args
    system "cmake", "--build", "build"
    system "cmake", "--install", "build"
  end

  test do
    # 1. Create a small FITS image using the installed library.
    (testpath/"make_image.c").write <<~EOS
      #include <stdio.h>
      #include "fitsio.h"
      int main(void) {
          fitsfile *f; int status = 0; long naxes[2] = {64, 64};
          short data[64*64];
          for (int i = 0; i < 64*64; i++) data[i] = (short)(i % 500);
          fits_create_file(&f, "!image.fits", &status);
          fits_create_img(f, SHORT_IMG, 2, naxes, &status);
          fits_write_img(f, TSHORT, 1, 64*64, data, &status);
          fits_close_file(f, &status);
          return status;
      }
    EOS

    system ENV.cc, "make_image.c", "-o", "make_image",
           "-I#{include}", "-L#{lib}", "-lcfitsio", "-lm"
    system "./make_image"

    # 2. Compress it with JPEG-LS.  This fails at run time unless HAVE_CHARLS
    #    was defined at build time, so it is the real check that the codec is in.
    system bin/"fpack", "-j", "-O", "image.fits.fz", "image.fits"
    assert_path_exists testpath/"image.fits.fz"

    # 3. Decompress and confirm the round-trip is lossless.
    system bin/"funpack", "-O", "roundtrip.fits", "image.fits.fz"
    assert_path_exists testpath/"roundtrip.fits"

    (testpath/"verify.c").write <<~EOS
      #include <stdio.h>
      #include <stdlib.h>
      #include <math.h>
      #include "fitsio.h"
      static void load(const char *fn, double *out) {
          fitsfile *f; int status = 0, anynul = 0;
          fits_open_image(&f, fn, READONLY, &status);
          fits_read_img(f, TDOUBLE, 1, 64*64, NULL, out, &anynul, &status);
          fits_close_file(f, &status);
          if (status) { fits_report_error(stderr, status); exit(status); }
      }
      int main(void) {
          static double a[64*64], b[64*64];
          load("image.fits", a);
          load("roundtrip.fits", b);
          for (int i = 0; i < 64*64; i++)
              if (fabs(a[i] - b[i]) > 0.0) { printf("MISMATCH at %d\\n", i); return 1; }
          printf("lossless\\n");
          return 0;
      }
    EOS

    system ENV.cc, "verify.c", "-o", "verify",
           "-I#{include}", "-L#{lib}", "-lcfitsio", "-lm"
    assert_equal "lossless", shell_output("./verify").strip
  end
end
