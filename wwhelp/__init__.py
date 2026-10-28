import json
from pathlib import Path

from PIL import Image

from gsuid_core.sv import SV, get_plugin_available_prefix
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.help.utils import register_help
from gsuid_core.help.draw_new_plugin_help import get_new_help

ROOT = Path(__file__).parent
ICON = ROOT.parent / "ICON.png"
TEXT_PATH = ROOT / "texture2d"
PREFIX = get_plugin_available_prefix("XWUIDCollection")

sv_collection_help = SV("合集帮助")


@sv_collection_help.on_fullmatch(
    ("c帮助", "c幫助", "合集帮助", "合集幫助", "帮助合集", "幫助合集"),
    block=True,
    to_ai="""返回 XWUIDCollection（xwuid 小合集：高考、宾果、充值、Tappo 开箱）的命令帮助图。

当用户问「合集帮助 / c帮助 / tappo 怎么玩」时调用。

Args:
    text: 无需参数。
""",
)
async def send_collection_help(bot: Bot, ev: Event) -> None:
    from plugins.XutheringWavesUID.XutheringWavesUID.utils.image import get_footer

    image = await get_new_help(
        plugin_name="XWUIDCollection",
        plugin_info={},
        plugin_icon=Image.open(ICON),
        plugin_help=json.loads((ROOT / "help.json").read_text(encoding="utf-8")),
        plugin_prefix=PREFIX,
        help_mode="dark",
        banner_bg=Image.open(TEXT_PATH / "banner_bg.jpg"),
        banner_sub_text="鸣潮小合集",
        help_bg=Image.open(TEXT_PATH / "bg.jpg"),
        cag_bg=Image.open(TEXT_PATH / "cag_bg.png"),
        item_bg=Image.open(TEXT_PATH / "item.png"),
        icon_path=ROOT / "icon_path",
        footer=get_footer(),
        enable_cache=True,
        column=3,
        pm=ev.user_pm,
    )
    await bot.send(image)


register_help("XWUIDCollection", f"{PREFIX}c帮助", Image.open(ICON))
