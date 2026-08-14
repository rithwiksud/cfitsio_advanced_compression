/*
 * Dependency-free helper for the JPEG-LS CI smoke test: synthesizes a small
 * FITS image and verifies pixel-for-pixel equality between two FITS files,
 * using only the CFITSIO C API. This exists so the CI workflow that proves
 * "fpack -j / funpack really round-trip" needs no Python or third-party
 * library -- fpack/funpack add HISTORY/CHECKSUM header cards on write, so a
 * raw byte comparison of the two files is not the right check; only the
 * pixel data needs to match.
 *
 * Usage:
 *   smoke_test_helper create <file> <nx> <ny>
 *   smoke_test_helper compare <file_a> <file_b>
 *
 * Build: gcc -o smoke_test_helper smoke_test_helper.c -I. -L./.libs -lcfitsio -lm
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "fitsio.h"

static void die(int status, const char *msg) {
    fprintf(stderr, "ERROR: %s\n", msg);
    if (status) fits_report_error(stderr, status);
    exit(status ? status : 1);
}

static int cmd_create(const char *file, long nx, long ny) {
    fitsfile *fptr;
    int status = 0;
    long naxes[2] = {nx, ny};
    long fpixel[2] = {1, 1};
    long npix = nx * ny;
    short *data = malloc(npix * sizeof(short));
    if (!data) die(0, "out of memory");

    for (long i = 0; i < npix; i++)
        data[i] = (short)((i * 7919) % 30000 - 15000);

    remove(file);
    fits_create_file(&fptr, file, &status);
    fits_create_img(fptr, SHORT_IMG, 2, naxes, &status);
    fits_write_pix(fptr, TSHORT, fpixel, npix, data, &status);
    fits_close_file(fptr, &status);
    free(data);
    if (status) die(status, "failed to create test image");
    return 0;
}

static int cmd_compare(const char *file_a, const char *file_b) {
    fitsfile *fa, *fb;
    int status = 0, anynul = 0;
    long naxes_a[2], naxes_b[2];
    int naxis_a, naxis_b, bitpix;
    long fpixel[2] = {1, 1};

    fits_open_file(&fa, file_a, READONLY, &status);
    fits_open_file(&fb, file_b, READONLY, &status);
    if (status) die(status, "failed to open input files");

    fits_get_img_param(fa, 2, &bitpix, &naxis_a, naxes_a, &status);
    fits_get_img_param(fb, 2, &bitpix, &naxis_b, naxes_b, &status);
    if (status) die(status, "failed to read image parameters");

    if (naxis_a != naxis_b || naxes_a[0] != naxes_b[0] || naxes_a[1] != naxes_b[1])
        die(0, "image dimensions differ");

    long npix = naxes_a[0] * naxes_a[1];
    short *a = malloc(npix * sizeof(short));
    short *b = malloc(npix * sizeof(short));
    if (!a || !b) die(0, "out of memory");

    fits_read_pix(fa, TSHORT, fpixel, npix, NULL, a, &anynul, &status);
    fits_read_pix(fb, TSHORT, fpixel, npix, NULL, b, &anynul, &status);
    if (status) die(status, "failed to read pixel data");

    fits_close_file(fa, &status);
    fits_close_file(fb, &status);

    int mismatches = 0;
    for (long i = 0; i < npix; i++) {
        if (a[i] != b[i]) {
            mismatches++;
            if (mismatches <= 5)
                fprintf(stderr, "pixel %ld: %d != %d\n", i, a[i], b[i]);
        }
    }
    free(a);
    free(b);

    if (mismatches) {
        fprintf(stderr, "FAIL: %d of %ld pixels differ\n", mismatches, npix);
        return 1;
    }
    printf("OK: %ld pixels identical\n", npix);
    return 0;
}

int main(int argc, char **argv) {
    if (argc >= 2 && strcmp(argv[1], "create") == 0 && argc == 5)
        return cmd_create(argv[2], atol(argv[3]), atol(argv[4]));
    if (argc >= 2 && strcmp(argv[1], "compare") == 0 && argc == 4)
        return cmd_compare(argv[2], argv[3]);

    fprintf(stderr, "usage: %s create <file> <nx> <ny>\n", argv[0]);
    fprintf(stderr, "       %s compare <file_a> <file_b>\n", argv[0]);
    return 2;
}
