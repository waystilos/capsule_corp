import sys
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import _config  # noqa: E402


def parse(text):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        data = _config.parse_toml_fallback(text)
    return data, [str(w.message) for w in caught]


class TomlFallbackTests(unittest.TestCase):
    def test_flat_and_multiline_arrays(self):
        data, warns = parse('[t]\na = ["x", \'y\', "z,w"]  # c\nb = [\n  "p",\n  "q",\n]\nn = 3\nok = true\n')
        self.assertEqual(data["t"]["a"], ["x", "y", "z,w"])
        self.assertEqual(data["t"]["b"], ["p", "q"])
        self.assertEqual(data["t"]["n"], 3)
        self.assertIs(data["t"]["ok"], True)
        self.assertEqual(warns, [])

    def test_unsupported_constructs_warn_not_silent(self):
        text = 'f = 1.5\ninline = {a = 1}\nnested = [[1], [2]]\nd.k = 1\nm = """x\ny"""\nafter = 2\n[[bad]]\nk = 1\n'
        data, warns = parse(text)
        self.assertEqual(data, {"after": 2})
        joined = " | ".join(warns)
        for key in ("'f'", "'inline'", "'nested'", "'d.k'", "'m'", "[[bad]]"):
            self.assertIn(key, joined)

    def test_empty_array(self):
        data, warns = parse("a = []\n")
        self.assertEqual(data["a"], [])
        self.assertEqual(warns, [])


if __name__ == "__main__":
    unittest.main()
