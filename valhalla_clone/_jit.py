"""Optional numba acceleration: falls back to plain Python when numba is absent."""

try:
    from numba import njit as _njit

    def jit(fn):
        return _njit(cache=True, fastmath=False)(fn)

    HAVE_NUMBA = True
except ImportError:  # pragma: no cover - exercised only without numba

    def jit(fn):
        return fn

    HAVE_NUMBA = False
