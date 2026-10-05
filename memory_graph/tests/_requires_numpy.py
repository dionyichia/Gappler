"""Import this first in any test that needs numpy and scipy.

Without them the whole test module is reported as skipped, not as passing and
not as an error, so the stdlib-only graph tests still run anywhere.
"""

import unittest

try:
    import numpy  # noqa: F401
    import scipy  # noqa: F401
except ImportError as exc:  # pragma: no cover - depends on the machine
    raise unittest.SkipTest(f"needs numpy and scipy: {exc}")
