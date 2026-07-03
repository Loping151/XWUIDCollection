import ast
import unittest
from pathlib import Path


class BingoConfigSourceTests(unittest.TestCase):
    def test_bingo_ui_style_has_console_options(self) -> None:
        path = Path(__file__).resolve().parents[1] / "wwbingo" / "config.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and key.value == "BingoUIStyle":
                        self.assertIsInstance(value, ast.Call)
                        option_keyword = next(
                            (kw for kw in value.keywords if kw.arg == "options"),
                            None,
                        )
                        self.assertIsNotNone(option_keyword)
                        self.assertEqual(
                            ast.literal_eval(option_keyword.value),
                            ["classic", "wcl"],
                        )
                        return
        self.fail("BingoUIStyle config was not found")


if __name__ == "__main__":
    unittest.main()
