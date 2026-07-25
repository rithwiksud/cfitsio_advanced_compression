/*
 * JPEG-LS Compression Test for CFITSIO
 *
 * Tests JPEG-LS compression round-trip for 8-bit, 16-bit, and 32-bit data.
 * Verifies lossless compression and compares ratios against RICE baseline.
 *
 * Usage: ./test_jpegls_compression
 *
 * Build: gcc -o test_jpegls_compression test_jpegls_compression.c -I. -L./.libs -lcfitsio -lm
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <sys/stat.h>
#include "fitsio.h"

/* Test configuration */
#define IMAGE_WIDTH  256
#define IMAGE_HEIGHT 256
#define TILE_WIDTH   64
#define TILE_HEIGHT  64

/* Report CFITSIO error and exit */
static void check_status(int status, const char *msg) {
    if (status) {
        fprintf(stderr, "ERROR: %s\n", msg);
        fits_report_error(stderr, status);
        exit(status);
    }
}

/* Get file size in bytes */
static long get_file_size(const char *filename) {
    struct stat st;
    if (stat(filename, &st) != 0) return -1;
    return (long)st.st_size;
}

/* Create uncompressed FITS file with test data */
static void create_test_image_byte(const char *filename, unsigned char *data) {
    fitsfile *fptr;
    int status = 0;
    long naxes[2] = {IMAGE_WIDTH, IMAGE_HEIGHT};
    long fpixel[2] = {1, 1};
    char create_name[256];

    /* Generate gradient test pattern */
    for (int y = 0; y < IMAGE_HEIGHT; y++) {
        for (int x = 0; x < IMAGE_WIDTH; x++) {
            data[y * IMAGE_WIDTH + x] = (unsigned char)((x + y * 2) & 0xFF);
        }
    }

    snprintf(create_name, sizeof(create_name), "!%s", filename);
    fits_create_file(&fptr, create_name, &status);
    check_status(status, "create_test_image_byte: create file");

    fits_create_img(fptr, BYTE_IMG, 2, naxes, &status);
    check_status(status, "create_test_image_byte: create image");

    fits_write_pix(fptr, TBYTE, fpixel, IMAGE_WIDTH * IMAGE_HEIGHT, data, &status);
    check_status(status, "create_test_image_byte: write pixels");

    fits_close_file(fptr, &status);
    check_status(status, "create_test_image_byte: close file");
}

static void create_test_image_short(const char *filename, short *data) {
    fitsfile *fptr;
    int status = 0;
    long naxes[2] = {IMAGE_WIDTH, IMAGE_HEIGHT};
    long fpixel[2] = {1, 1};
    char create_name[256];

    /* Generate gradient test pattern spanning full int16 range */
    for (int y = 0; y < IMAGE_HEIGHT; y++) {
        for (int x = 0; x < IMAGE_WIDTH; x++) {
            int idx = y * IMAGE_WIDTH + x;
            data[idx] = (short)((idx * 7 - 32000) % 65536 - 32768);
        }
    }

    snprintf(create_name, sizeof(create_name), "!%s", filename);
    fits_create_file(&fptr, create_name, &status);
    check_status(status, "create_test_image_short: create file");

    fits_create_img(fptr, SHORT_IMG, 2, naxes, &status);
    check_status(status, "create_test_image_short: create image");

    fits_write_pix(fptr, TSHORT, fpixel, IMAGE_WIDTH * IMAGE_HEIGHT, data, &status);
    check_status(status, "create_test_image_short: write pixels");

    fits_close_file(fptr, &status);
    check_status(status, "create_test_image_short: close file");
}

static void create_test_image_int(const char *filename, int *data) {
    fitsfile *fptr;
    int status = 0;
    long naxes[2] = {IMAGE_WIDTH, IMAGE_HEIGHT};
    long fpixel[2] = {1, 1};
    char create_name[256];

    /* Generate gradient test pattern spanning int32 range */
    for (int y = 0; y < IMAGE_HEIGHT; y++) {
        for (int x = 0; x < IMAGE_WIDTH; x++) {
            int idx = y * IMAGE_WIDTH + x;
            data[idx] = (int)((long)idx * 65537 - 0x80000000L);
        }
    }

    snprintf(create_name, sizeof(create_name), "!%s", filename);
    fits_create_file(&fptr, create_name, &status);
    check_status(status, "create_test_image_int: create file");

    fits_create_img(fptr, LONG_IMG, 2, naxes, &status);
    check_status(status, "create_test_image_int: create image");

    fits_write_pix(fptr, TINT, fpixel, IMAGE_WIDTH * IMAGE_HEIGHT, data, &status);
    check_status(status, "create_test_image_int: write pixels");

    fits_close_file(fptr, &status);
    check_status(status, "create_test_image_int: close file");
}

/* Compress file using specified compression type */
static long compress_file(const char *infile, const char *outfile, int comp_type) {
    fitsfile *infptr, *outfptr;
    int status = 0;
    char create_name[256];

    fits_open_file(&infptr, infile, READONLY, &status);
    check_status(status, "compress_file: open input");

    snprintf(create_name, sizeof(create_name), "!%s", outfile);
    fits_create_file(&outfptr, create_name, &status);
    check_status(status, "compress_file: create output");

    /* Set compression parameters */
    fits_set_compression_type(outfptr, comp_type, &status);
    check_status(status, "compress_file: set compression type");

    fits_set_tile_dim(outfptr, 2, (long[]){TILE_WIDTH, TILE_HEIGHT}, &status);
    check_status(status, "compress_file: set tile dimensions");

    /* Compress the image */
    fits_img_compress(infptr, outfptr, &status);
    check_status(status, "compress_file: compress image");

    fits_close_file(outfptr, &status);
    check_status(status, "compress_file: close output");

    fits_close_file(infptr, &status);
    check_status(status, "compress_file: close input");

    return get_file_size(outfile);
}

/* Read back compressed image data */
static void read_compressed_byte(const char *filename, unsigned char *data) {
    fitsfile *fptr;
    int status = 0;
    long fpixel[2] = {1, 1};
    int anynul = 0;

    fits_open_file(&fptr, filename, READONLY, &status);
    check_status(status, "read_compressed_byte: open file");

    /* Move to image HDU (HDU 2 for compressed) */
    fits_movabs_hdu(fptr, 2, NULL, &status);
    check_status(status, "read_compressed_byte: move to HDU 2");

    fits_read_pix(fptr, TBYTE, fpixel, IMAGE_WIDTH * IMAGE_HEIGHT, NULL, data, &anynul, &status);
    check_status(status, "read_compressed_byte: read pixels");

    fits_close_file(fptr, &status);
    check_status(status, "read_compressed_byte: close file");
}

static void read_compressed_short(const char *filename, short *data) {
    fitsfile *fptr;
    int status = 0;
    long fpixel[2] = {1, 1};
    int anynul = 0;

    fits_open_file(&fptr, filename, READONLY, &status);
    check_status(status, "read_compressed_short: open file");

    fits_movabs_hdu(fptr, 2, NULL, &status);
    check_status(status, "read_compressed_short: move to HDU 2");

    fits_read_pix(fptr, TSHORT, fpixel, IMAGE_WIDTH * IMAGE_HEIGHT, NULL, data, &anynul, &status);
    check_status(status, "read_compressed_short: read pixels");

    fits_close_file(fptr, &status);
    check_status(status, "read_compressed_short: close file");
}

static void read_compressed_int(const char *filename, int *data) {
    fitsfile *fptr;
    int status = 0;
    long fpixel[2] = {1, 1};
    int anynul = 0;

    fits_open_file(&fptr, filename, READONLY, &status);
    check_status(status, "read_compressed_int: open file");

    fits_movabs_hdu(fptr, 2, NULL, &status);
    check_status(status, "read_compressed_int: move to HDU 2");

    fits_read_pix(fptr, TINT, fpixel, IMAGE_WIDTH * IMAGE_HEIGHT, NULL, data, &anynul, &status);
    check_status(status, "read_compressed_int: read pixels");

    fits_close_file(fptr, &status);
    check_status(status, "read_compressed_int: close file");
}

/* Test JPEG-LS compression for 8-bit data */
static int test_byte_compression(void) {
    const char *raw_file = "/tmp/test_jpegls_byte.fits";
    const char *jls_file = "/tmp/test_jpegls_byte_jls.fits";
    const char *rice_file = "/tmp/test_jpegls_byte_rice.fits";

    unsigned char *original = malloc(IMAGE_WIDTH * IMAGE_HEIGHT);
    unsigned char *result = malloc(IMAGE_WIDTH * IMAGE_HEIGHT);
    if (!original || !result) {
        fprintf(stderr, "Memory allocation failed\n");
        return -1;
    }

    printf("\n=== 8-bit (BYTE) Compression Test ===\n");

    /* Create test image */
    create_test_image_byte(raw_file, original);
    long raw_size = get_file_size(raw_file);

    /* Test JPEG-LS compression */
    long jls_size = compress_file(raw_file, jls_file, JPEGLS_1);
    read_compressed_byte(jls_file, result);

    int mismatch = 0;
    for (int i = 0; i < IMAGE_WIDTH * IMAGE_HEIGHT; i++) {
        if (original[i] != result[i]) {
            fprintf(stderr, "JPEG-LS mismatch at %d: expected %u, got %u\n",
                    i, original[i], result[i]);
            mismatch++;
            if (mismatch > 10) break;
        }
    }

    if (mismatch) {
        printf("JPEG-LS: FAILED (%d mismatches)\n", mismatch);
        free(original);
        free(result);
        return -1;
    }
    printf("JPEG-LS: PASSED (lossless, ratio %.2f:1)\n",
           (double)raw_size / jls_size);

    /* Test RICE baseline */
    long rice_size = compress_file(raw_file, rice_file, RICE_1);
    printf("RICE:    ratio %.2f:1 (baseline)\n", (double)raw_size / rice_size);

    /* Compare ratios */
    if (jls_size > rice_size) {
        printf("WARNING: JPEG-LS larger than RICE for this pattern\n");
    }

    /* Cleanup */
    remove(raw_file);
    remove(jls_file);
    remove(rice_file);
    free(original);
    free(result);

    return 0;
}

/* Test JPEG-LS compression for 16-bit data */
static int test_short_compression(void) {
    const char *raw_file = "/tmp/test_jpegls_short.fits";
    const char *jls_file = "/tmp/test_jpegls_short_jls.fits";
    const char *rice_file = "/tmp/test_jpegls_short_rice.fits";

    short *original = malloc(IMAGE_WIDTH * IMAGE_HEIGHT * sizeof(short));
    short *result = malloc(IMAGE_WIDTH * IMAGE_HEIGHT * sizeof(short));
    if (!original || !result) {
        fprintf(stderr, "Memory allocation failed\n");
        return -1;
    }

    printf("\n=== 16-bit (SHORT) Compression Test ===\n");

    /* Create test image */
    create_test_image_short(raw_file, original);
    long raw_size = get_file_size(raw_file);

    /* Test JPEG-LS compression */
    long jls_size = compress_file(raw_file, jls_file, JPEGLS_1);
    read_compressed_short(jls_file, result);

    int mismatch = 0;
    for (int i = 0; i < IMAGE_WIDTH * IMAGE_HEIGHT; i++) {
        if (original[i] != result[i]) {
            fprintf(stderr, "JPEG-LS mismatch at %d: expected %d, got %d\n",
                    i, original[i], result[i]);
            mismatch++;
            if (mismatch > 10) break;
        }
    }

    if (mismatch) {
        printf("JPEG-LS: FAILED (%d mismatches)\n", mismatch);
        free(original);
        free(result);
        return -1;
    }
    printf("JPEG-LS: PASSED (lossless, ratio %.2f:1)\n",
           (double)raw_size / jls_size);

    /* Test RICE baseline */
    long rice_size = compress_file(raw_file, rice_file, RICE_1);
    printf("RICE:    ratio %.2f:1 (baseline)\n", (double)raw_size / rice_size);

    /* Cleanup */
    remove(raw_file);
    remove(jls_file);
    remove(rice_file);
    free(original);
    free(result);

    return 0;
}

/* Test JPEG-LS compression for 32-bit data */
static int test_int_compression(void) {
    const char *raw_file = "/tmp/test_jpegls_int.fits";
    const char *jls_file = "/tmp/test_jpegls_int_jls.fits";
    const char *rice_file = "/tmp/test_jpegls_int_rice.fits";

    int *original = malloc(IMAGE_WIDTH * IMAGE_HEIGHT * sizeof(int));
    int *result = malloc(IMAGE_WIDTH * IMAGE_HEIGHT * sizeof(int));
    if (!original || !result) {
        fprintf(stderr, "Memory allocation failed\n");
        return -1;
    }

    printf("\n=== 32-bit (LONG) Compression Test ===\n");

    /* Create test image */
    create_test_image_int(raw_file, original);
    long raw_size = get_file_size(raw_file);

    /* Test JPEG-LS compression */
    long jls_size = compress_file(raw_file, jls_file, JPEGLS_1);
    read_compressed_int(jls_file, result);

    int mismatch = 0;
    for (int i = 0; i < IMAGE_WIDTH * IMAGE_HEIGHT; i++) {
        if (original[i] != result[i]) {
            fprintf(stderr, "JPEG-LS mismatch at %d: expected %d, got %d\n",
                    i, original[i], result[i]);
            mismatch++;
            if (mismatch > 10) break;
        }
    }

    if (mismatch) {
        printf("JPEG-LS: FAILED (%d mismatches)\n", mismatch);
        free(original);
        free(result);
        return -1;
    }
    printf("JPEG-LS: PASSED (lossless, ratio %.2f:1)\n",
           (double)raw_size / jls_size);

    /* Test RICE baseline */
    long rice_size = compress_file(raw_file, rice_file, RICE_1);
    printf("RICE:    ratio %.2f:1 (baseline)\n", (double)raw_size / rice_size);

    /* Cleanup */
    remove(raw_file);
    remove(jls_file);
    remove(rice_file);
    free(original);
    free(result);

    return 0;
}

int main(void) {
    int failures = 0;

    printf("CFITSIO JPEG-LS Compression Test Suite\n");
    printf("======================================\n");
    printf("Image size: %dx%d, Tile size: %dx%d\n",
           IMAGE_WIDTH, IMAGE_HEIGHT, TILE_WIDTH, TILE_HEIGHT);

    if (test_byte_compression() != 0) failures++;
    if (test_short_compression() != 0) failures++;
    if (test_int_compression() != 0) failures++;

    printf("\n======================================\n");
    if (failures == 0) {
        printf("All JPEG-LS compression tests PASSED\n");
        return EXIT_SUCCESS;
    } else {
        printf("%d test(s) FAILED\n", failures);
        return EXIT_FAILURE;
    }
}
