"""
Tools for working with Gaussian grids.

Adopted from: https://gist.github.com/ajdawson/b64d24dfac618b91974f
"""
from __future__ import (absolute_import, division, print_function)

import functools

import numpy as np
import numpy.linalg as la
from numpy.polynomial.legendre import legcompanion, legder, legval


def __single_arg_fast_cache(func):
    """Caching decorator for functions of one argument."""
    class CachingDict(dict):

        def __missing__(self, key):
            result = self[key] = func(key)
            return result

        @functools.wraps(func)
        def __getitem__(self, *args, **kwargs):
            return super(CachingDict, self).__getitem__(*args, **kwargs)

    return CachingDict().__getitem__


@__single_arg_fast_cache
def gaussian_latitudes(nlat: int):
    """
    Construct latitudes for a Gaussian grid.

    Parameters
    ----------
    nlat
        The number of latitudes in the Gaussian grid.

    Returns
    -------
    latitudes
        `numpy.ndarray` of latitudes (in degrees) with a length of `nlat`.
    """
    if abs(int(nlat)) != nlat:
        raise ValueError('nlat must be a non-negative integer')
    # Create the coefficients of the Legendre polynomial and construct the
    # companion matrix:
    cs = np.array([0] * nlat + [1], dtype=int)
    cm = legcompanion(cs)
    # Compute the eigenvalues of the companion matrix (the roots of the
    # Legendre polynomial) taking advantage of the fact that the matrix is
    # symmetric:
    roots = la.eigvalsh(cm)
    roots.sort()
    # Improve the roots by one application of Newton's method, using the
    # solved root as the initial guess:
    fx = legval(roots, cs)
    fpx = legval(roots, legder(cs))
    roots -= fx / fpx
    # The roots should exhibit symmetry, but with a sign change, so make sure
    # this is the case:
    roots = (roots - roots[::-1]) / 2.
    # Convert the roots from the interval [-1, 1] to latitude values on the
    # interval [-90, 90] degrees:
    latitudes = np.rad2deg(np.arcsin(roots))
    # Flip latitudes such that it is oriented from North to South [90, -90]
    latitudes = np.flip(latitudes)
    return latitudes
