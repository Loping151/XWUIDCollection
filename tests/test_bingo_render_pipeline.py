import unittest
from pathlib import Path


class BingoRenderPipelineSourceTests(unittest.TestCase):
    def test_wcl_style_uses_same_html_render_pipeline_as_classic(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (root / "wwbingo" / "__init__.py").read_text(encoding="utf-8")

        self.assertIn('template_name = "bingo_wcl.html" if get_bingo_ui_style() == "wcl" else "bingo.html"', source)
        self.assertIn('render_html(_jinja_env, template_name, context)', source)
        self.assertNotIn('draw_wcl_bingo_img', source)

    def test_wcl_template_exists_next_to_classic_template(self) -> None:
        template_dir = Path(__file__).resolve().parents[1] / "wwbingo" / "templates"
        self.assertTrue((template_dir / "bingo.html").exists())
        self.assertTrue((template_dir / "bingo_wcl.html").exists())


if __name__ == "__main__":
    unittest.main()
