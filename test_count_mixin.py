"""
╔══════════════════════════════════════════════════════════════════════╗
║  TestCountMixin — shared discovery gate                              ║
╚══════════════════════════════════════════════════════════════════════╝

Shared mixin for TestDiscovery sanity checks.

Usage:
    from test_count_mixin import TestCountMixin

    class TestDiscovery(unittest.TestCase, TestCountMixin):
        EXPECTED_TEST_COUNT = 99
"""

import inspect


class TestCountMixin:
    """Mixin that provides a test_test_count method.

    Subclasses must define:
        EXPECTED_TEST_COUNT — the expected number of test methods
                              (including this one) in the module.
    """

    EXPECTED_TEST_COUNT = 0  # Must be overridden by subclass

    def test_test_count(self):
        """Ensure the total number of test methods in this module
        hasn't changed. Counts 'def test_' lines in the module's source."""
        # Resolve __file__ from the *subclass* module, not this mixin
        module_file = inspect.getfile(self.__class__)
        with open(module_file) as f:
            source = f.read()
        count = source.count('\n    def test_')

        self.assertEqual(count, self.EXPECTED_TEST_COUNT,
            f"Expected {self.EXPECTED_TEST_COUNT} test methods, got {count}. "
            f"If you intentionally added/removed tests, update "
            f"EXPECTED_TEST_COUNT in {self.__class__.__name__}.")
