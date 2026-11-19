import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(ROOT, "engine")

BOOK = {"sheets": {"Sheet1": {"A1": 1, "A2": "text", "A3": True, "B1": 2.5},
                   "Sheet2": {"C3": "other"}, "Empty": {}}}


def run(args, stdin=None):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, ENGINE] + args, input=stdin, capture_output=True,
                       text=True, env=env, check=True)
    return json.loads(p.stdout)


class CliTest(unittest.TestCase):
    def test_stdin_round_trip(self):
        self.assertEqual(run(["-"], json.dumps(BOOK)), BOOK)

    def test_file_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "book.json")
            with open(path, "w") as f:
                json.dump(BOOK, f)
            self.assertEqual(run([path]), BOOK)

    def test_types_preserved(self):
        out = run(["-"], json.dumps(BOOK))["sheets"]["Sheet1"]
        self.assertIs(type(out["A1"]), int)
        self.assertIs(out["A3"], True)
        self.assertEqual(out["B1"], 2.5)

    def test_cell(self):
        self.assertEqual(run(["-", "--cell", "Sheet1!A1"], json.dumps(BOOK)), 1)
        self.assertEqual(run(["-", "--cell", "Sheet2!C3"], json.dumps(BOOK)), "other")
        self.assertIs(run(["-", "--cell", "Sheet1!A3"], json.dumps(BOOK)), True)

    def test_cell_blank_is_null(self):
        self.assertIsNone(run(["-", "--cell", "Sheet1!Z9"], json.dumps(BOOK)))

    def test_cell_absolute_ref(self):
        self.assertEqual(run(["-", "--cell", "Sheet1!$B$1"], json.dumps(BOOK)), 2.5)


class ComputeTest(unittest.TestCase):
    def test_compute_does_not_alias_input(self):
        from src.cli import compute
        book = {"sheets": {"S": {"A1": 1}}}
        out = compute(book)
        out["sheets"]["S"]["A1"] = 2
        self.assertEqual(book["sheets"]["S"]["A1"], 1)


if __name__ == "__main__":
    unittest.main()
