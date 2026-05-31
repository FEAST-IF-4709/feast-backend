import pytest


class PytestTestRunner:
    """Delegates `manage.py test` to pytest, preserving all pytest.ini config."""

    def __init__(self, verbosity=1, failfast=False, keepdb=False, **kwargs):
        self.verbosity = verbosity
        self.failfast = failfast
        self.keepdb = keepdb

    def run_tests(self, test_labels):
        argv = ["--tb=short"]
        if self.verbosity >= 2:
            argv.append("-v")
        if self.failfast:
            argv.append("-x")
        if test_labels:
            argv.extend(self._to_pytest_paths(test_labels))
        result = pytest.main(argv)
        # pytest exit code 5 = no tests collected — treat as success, not failure
        return 0 if result == pytest.ExitCode.NO_TESTS_COLLECTED else result

    @staticmethod
    def _to_pytest_paths(labels):
        """Convert Django dotted labels (apps.foo.bar) to pytest paths (apps/foo/bar)."""
        return [label.replace(".", "/") for label in labels]
