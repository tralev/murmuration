"""
Doc-drift guards. The repo maintains a code↔doc map (the README module table,
sci.md's numbered sections, and the cross-links between them). These cheap
tests fail loudly when that map goes stale — a module named in the README that
no longer exists, or a broken `sci.md#anchor` link.
"""

import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def _read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return fh.read()


def _github_slug(heading):
    """GitHub's heading-anchor algorithm: lowercase, drop non-word/space/hyphen,
    spaces→hyphens."""
    s = heading.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"\s+", "-", s)


class TestReadmeModuleTable(unittest.TestCase):
    def test_every_backticked_py_module_exists(self):
        """Every ``file.py`` named in the README resolves to a real file — so a
        renamed/removed module can't leave a dangling reference."""
        readme = _read("README.md")
        modules = set(re.findall(r"`([A-Za-z0-9_]+\.py)`", readme))
        self.assertGreater(len(modules), 8)          # the table is populated
        missing = [m for m in modules if not os.path.exists(os.path.join(HERE, m))]
        self.assertEqual(missing, [], f"README names missing modules: {missing}")


class TestSciAnchors(unittest.TestCase):
    def test_sci_md_anchor_links_resolve(self):
        """Every `sci.md#anchor` referenced from the Markdown docs points at a
        real heading in sci.md."""
        sci = _read("sci.md")
        headings = {_github_slug(h) for h in re.findall(r"^#+\s+(.*)$", sci,
                                                        flags=re.MULTILINE)}
        self.assertIn("46-implementation-notes-where-the-code-refines-the-"
                      "idealised-model", headings)      # sanity: slugger works

        # Only real markdown links `[label](sci.md#anchor)` — not prose that
        # merely mentions an anchor.
        refs = set()
        for doc in ("README.md", "sci.md", "tests.md"):
            refs |= set(re.findall(r"\]\(sci\.md#([\w-]+)\)", _read(doc)))
        self.assertGreater(len(refs), 0, "expected some sci.md links to check")
        broken = sorted(a for a in refs if a not in headings)
        self.assertEqual(broken, [], f"broken sci.md anchors: {broken}")


class TestNamedTestFilesExist(unittest.TestCase):
    def test_run_tests_modules_are_real(self):
        """Every unittest module in run_tests.sh's MODULES list exists — so the
        gate can't silently skip a suite that was renamed."""
        gate = _read("run_tests.sh")
        m = re.search(r'MODULES="([^"]+)"', gate)
        self.assertIsNotNone(m, "could not find the MODULES list")
        mods = re.findall(r"test_\w+", m.group(1))
        self.assertGreaterEqual(len(mods), 5)
        for mod in mods:
            self.assertTrue(os.path.exists(os.path.join(HERE, mod + ".py")),
                            f"run_tests.sh runs missing module {mod}")


# ══════════════════════════════════════════════════════════════════════
#  Discovery gate (tests.md §3.1)
# ══════════════════════════════════════════════════════════════════════

class TestDiscovery(unittest.TestCase):
    EXPECTED = 4

    def test_module_test_count(self):
        import test_docs_3d as m
        n = unittest.TestLoader().loadTestsFromModule(m).countTestCases()
        self.assertEqual(n, self.EXPECTED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
