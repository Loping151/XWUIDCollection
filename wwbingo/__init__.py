import base64
from pathlib import Path
from datetime import datetime, timezone, timedelta

from jinja2 import Environment, FileSystemLoader

from gsuid_core.bot import Bot
from gsuid_core.sv import SV
from gsuid_core.models import Event
from gsuid_core.logger import logger
from gsuid_core.utils.image.convert import convert_img

from .char_data import (
    FOUR_STAR_IDS,
    MALE_ROVER_IDS,
    FEMALE_ROVER_IDS,
    get_char_attribute,
)
from .config import get_bingo_ids

sv_ww_bingo = SV("宾果", priority=5)

TEMPLATE_DIR = Path(__file__).parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
_STAMP_PATH = Path(__file__).parent / "assets" / "stamp.png"

_stamp_b64_cache = ""


def _get_stamp_b64() -> str:
    global _stamp_b64_cache
    if _stamp_b64_cache:
        return _stamp_b64_cache
    if _STAMP_PATH.exists():
        try:
            data = _STAMP_PATH.read_bytes()
            _stamp_b64_cache = "data:image/png;base64," + base64.b64encode(data).decode()
        except Exception:
            _stamp_b64_cache = ""
    return _stamp_b64_cache


def _count_lines(owned_grid) -> int:
    n = 0
    for r in range(6):
        if all(owned_grid[r][c] for c in range(6)):
            n += 1
    for c in range(6):
        if all(owned_grid[r][c] for r in range(6)):
            n += 1
    if all(owned_grid[i][i] for i in range(6)):
        n += 1
    if all(owned_grid[i][5 - i] for i in range(6)):
        n += 1
    return n


def _badge_for(lines: int) -> str:
    if lines <= 0:
        return "未认证成功"
    if lines == 1:
        return "鸣潮收藏家"
    if lines <= 3:
        return "鸣潮老资历"
    if lines <= 6:
        return "鸣潮活化石"
    return "鸣潮活祖宗"


@sv_ww_bingo.on_command(
    ("宾果", "冰果", "冰菓", "五星宾果", "角色宾果", "bingo", "bg"),
    block=True,
    to_ai="""鸣潮五星角色宾果收集图：把本地已有的角色数据摆进 6x6 棋盘,已拥有的高亮,连成一条线就算收藏家。

当用户问「宾果 / 五星宾果 / 收集图」时调用,需绑定特征码,角色列表读本地缓存(不额外请求库洛)。

Args:
    text: 无需参数。
""",
)
async def cmd_ww_bingo(bot: Bot, ev: Event):
    from plugins.XutheringWavesUID.XutheringWavesUID.utils.at_help import ruser_id
    from plugins.XutheringWavesUID.XutheringWavesUID.utils.database.models import WavesBind
    from plugins.XutheringWavesUID.XutheringWavesUID.utils.char_info_utils import (
        get_all_roleid_detail_info_int,
    )
    from plugins.XutheringWavesUID.XutheringWavesUID.utils.image import (
        img_to_b64,
        pil_to_b64,
        get_attribute,
        get_event_avatar,
        get_square_avatar_path,
    )
    from plugins.XutheringWavesUID.XutheringWavesUID.utils.render_utils import (
        render_html,
        get_footer_b64,
    )
    from plugins.XutheringWavesUID.XutheringWavesUID.utils.resource.constant import (
        SPECIAL_CHAR_INT,
        SPECIAL_CHAR_INT_ALL,
    )
    from plugins.XutheringWavesUID.XutheringWavesUID.wutheringwaves_config import PREFIX

    logger.info("[ww宾果] 开始执行[五星宾果]")
    user_id = ruser_id(ev)
    uid = await WavesBind.get_uid_by_game(user_id, ev.bot_id)
    if not uid:
        return await bot.send(f"还没绑定特征码呢，先 {PREFIX}绑定 再来玩五星宾果吧~", at_sender=True)

    detail_map = await get_all_roleid_detail_info_int(uid)
    owned = set(detail_map.keys()) if detail_map else set()
    if not owned:
        return await bot.send(
            f"本地还没有你的角色数据，先用【{PREFIX}刷新面板】更新一下再来玩宾果吧~",
            at_sender=True,
        )

    ids = get_bingo_ids()

    attr_icon_cache = {}

    async def _attr_icon(name: str) -> str:
        if not name:
            return ""
        if name not in attr_icon_cache:
            im = await get_attribute(name, is_simple=True)
            attr_icon_cache[name] = pil_to_b64(im, quality=80)
        return attr_icon_cache[name]

    special_set = set(SPECIAL_CHAR_INT_ALL)
    owned_specials = owned & special_set
    male_owned = bool(owned & set(MALE_ROVER_IDS))
    female_owned = bool(owned & set(FEMALE_ROVER_IDS))

    def _chain_of(_cid):
        d = detail_map.get(_cid) if detail_map else None
        try:
            return d.get_chain_num() if d else None
        except Exception:
            return None

    cells = []
    for cid in ids:
        head_id = cid
        if cid in special_set:
            is_owned = bool(owned_specials)
            pair = SPECIAL_CHAR_INT.get(cid, [cid])
            if male_owned:
                head_id = next((i for i in pair if i in MALE_ROVER_IDS), cid)
            elif female_owned:
                head_id = next((i for i in pair if i in FEMALE_ROVER_IDS), cid)
            chain = _chain_of(next(iter(owned_specials))) if owned_specials else None
        else:
            is_owned = cid in owned
            chain = _chain_of(cid) if is_owned else None
        head = img_to_b64(
            get_square_avatar_path(head_id), quality=75, bake=True, cover_size=(160, 160)
        )
        attr_icon = await _attr_icon(get_char_attribute(cid) or "")
        cells.append({"owned": is_owned, "head": head, "attr": attr_icon, "chain": chain})

    owned_grid = [[cells[r * 6 + c]["owned"] for c in range(6)] for r in range(6)]
    lines = _count_lines(owned_grid)
    owned_count = sum(1 for c in cells if c["owned"])

    avatar = await get_event_avatar(ev)
    avatar_url = pil_to_b64(avatar, quality=80)
    nickname = (ev.sender or {}).get("nickname") or f"玩家{str(uid)[-8:]}"

    badge = _badge_for(lines)
    certified = lines >= 1
    has_four = any(cid in set(FOUR_STAR_IDS) for cid in ids)
    title = "鸣潮角色" if has_four else "鸣潮五星角色"
    tail = badge if certified else "鸣潮角色收藏家"
    current_date = (
        datetime.now(timezone.utc)
        .astimezone(timezone(timedelta(hours=8)))
        .strftime("%Y.%m.%d")
    )

    context = {
        "title": title,
        "nickname": nickname[:12],
        "avatar_url": avatar_url,
        "cells": cells,
        "lines": lines,
        "owned_count": owned_count,
        "total": len(cells),
        "certified": certified,
        "badge": badge,
        "subtitle": f"只要连成一条线 说明你是{tail}",
        "current_date": current_date,
        "stamp_url": _get_stamp_b64(),
        "footer_b64": get_footer_b64(footer_type="white") or "",
    }

    img_bytes = await render_html(_jinja_env, "bingo.html", context)
    if not img_bytes:
        return await bot.send("渲染失败！", at_sender=True)

    await bot.send(await convert_img(img_bytes))
