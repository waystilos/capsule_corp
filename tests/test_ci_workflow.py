import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml"


class CiWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_text_key_steps(self):
        for needle in (
            "python -m unittest discover -s tests -t .",
            "python bin/capsule check . --trust",
            "shellcheck config/*.sh",
            "bash -n",
        ):
            self.assertIn(needle, self.text)

    def test_parsed_matrix(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        data = yaml.safe_load(self.text)
        matrix = data["jobs"]["test"]["strategy"]["matrix"]
        pys = {str(v) for v in matrix["python-version"]}
        self.assertEqual(pys, {"3.8", "3.12"})
        oses = set(matrix["os"]) | {i["os"] for i in matrix.get("include", [])}
        for os_name in ("ubuntu-latest", "windows-latest", "macos-latest"):
            self.assertIn(os_name, oses)
        self.assertIn("lint-and-installers", data["jobs"])


if __name__ == "__main__":
    unittest.main()
