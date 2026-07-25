"""
Synthetic integer test images with known noise properties.

Reproduces the two image sets described in section 3.1 of

    Pence, Seaman & White (2009), "Lossless Astronomical Image Compression
    and the Effects of Noise", PASP 121, 414.  arXiv:0903.2140

The paper's central relation is

    R = BITPIX / (Nbits + K)

where R is the compression ratio, Nbits the number of noise bits per pixel,
and K the per-pixel overhead of the compression algorithm (lower is better).
Plotting BITPIX/R against Nbits turns that into a straight line of slope 1
whose intercept is K, which is how K is measured.

Two noise distributions are used so that the relation can be cross-checked:
they must land on the same line once the sqrt(12) factor of equation 4 is
applied to the Gaussian case.
"""

import numpy as np

__all__ = ["nbits_image", "gaussian_image", "gaussian_nbits", "BITPIX"]

BITPIX = {np.dtype(np.uint8): 8, np.dtype(np.int16): 16,
          np.dtype(np.uint16): 16, np.dtype(np.int32): 32,
          np.dtype(np.uint32): 32}


def nbits_image(nbits, shape=(1024, 1024), dtype=np.int16, seed=None):
    """Set 1 of the paper: exactly `nbits` bits of uniform noise per pixel.

    "the lowest N bits of each integer pixel were randomly assigned a value
    of 0 or 1 and the upper BITPIX - N bits are all set to 0"

    The image therefore contains, by construction, exactly `nbits` bits per
    pixel of incompressible noise.
    """
    rng = np.random.default_rng(seed)
    if nbits <= 0:
        return np.zeros(shape, dtype=dtype)
    return rng.integers(0, 2 ** int(nbits), size=shape).astype(dtype)


def gaussian_image(sigma, shape=(1024, 1024), dtype=np.int16, offset=None, seed=None):
    """Set 2 of the paper: Gaussian-distributed pixel values.

    "the pixels were assigned values randomly selected from a Gaussian
    distribution, with sigma ranging from 1.0 to 500. (We also added a
    constant offset to the pixels in these images to avoid negative
    values...)"

    The paper verified that the magnitude of the offset does not affect the
    compression ratio; `offset` is exposed here so that can be re-checked.
    """
    rng = np.random.default_rng(seed)
    if offset is None:
        offset = 10.0 * sigma      # comfortably positive
    values = rng.normal(loc=offset, scale=sigma, size=shape)
    return np.rint(values).astype(dtype)


def gaussian_nbits(sigma):
    """Equivalent noise bits for Gaussian noise -- equation 4 of the paper.

        Nbits = log2(sigma * sqrt(12)) = log2(sigma) + 1.792
    """
    return np.log2(sigma * np.sqrt(12.0))
