from typing import Literal


BingoUIStyle = Literal["classic", "wcl"]


_CLASSIC_ALIASES = {"", "classic", "default", "html", "old", "原版", "默认", "经典"}
_WCL_ALIASES = {"wcl", "wavescollectline", "line", "连线", "收集图", "小黑盒"}


def normalize_bingo_ui_style(value: object) -> BingoUIStyle:
    style = str(value or "").strip().lower()
    if style in _WCL_ALIASES:
        return "wcl"
    if style in _CLASSIC_ALIASES:
        return "classic"
    return "classic"
