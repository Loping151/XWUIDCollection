import importlib.util
import unittest
from pathlib import Path


def _load_ui_style_module():
    path = Path(__file__).resolve().parents[1] / "wwbingo" / "ui_style.py"
    spec = importlib.util.spec_from_file_location("xwuidcollection_bingo_ui_style", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load ui_style module spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BingoUIStyleTests(unittest.TestCase):
    def test_normalize_bingo_ui_style_accepts_classic_and_wcl(self) -> None:
        mod = _load_ui_style_module()
        self.assertEqual(mod.normalize_bingo_ui_style("classic"), "classic")
        self.assertEqual(mod.normalize_bingo_ui_style("wcl"), "wcl")

    def test_normalize_bingo_ui_style_accepts_common_aliases(self) -> None:
        mod = _load_ui_style_module()
        self.assertEqual(mod.normalize_bingo_ui_style("默认"), "classic")
        self.assertEqual(mod.normalize_bingo_ui_style("原版"), "classic")
        self.assertEqual(mod.normalize_bingo_ui_style("连线"), "wcl")
        self.assertEqual(mod.normalize_bingo_ui_style("WavesCollectLine"), "wcl")

    def test_normalize_bingo_ui_style_falls_back_to_classic(self) -> None:
        mod = _load_ui_style_module()
        self.assertEqual(mod.normalize_bingo_ui_style(""), "classic")
        self.assertEqual(mod.normalize_bingo_ui_style("unknown"), "classic")
        self.assertEqual(mod.normalize_bingo_ui_style(None), "classic")


if __name__ == "__main__":
    unittest.main()
