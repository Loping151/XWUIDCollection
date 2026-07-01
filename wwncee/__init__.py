import math
from pathlib import Path
from datetime import datetime
from typing import Tuple

import httpx
from jinja2 import Environment, FileSystemLoader

from gsuid_core.bot import Bot
from gsuid_core.sv import SV
from gsuid_core.models import Event
from gsuid_core.logger import logger
from gsuid_core.utils.image.convert import convert_img


sv_ww_gaokao = SV("高考", priority=5)

TEMPLATE_DIR = Path(__file__).parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))

SUBJECTS = ["语文", "数学", "英语", "物理", "化学", "生物"]


def _to_cn_rank(n: int) -> str:
    if n <= 0:
        return "未上榜"
    if n == 1:
        return "一"
    cn = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
    if n < 10:
        return cn[n]
    if n < 20:
        return "十" + (cn[n % 10] if n % 10 else "")
    if n < 100:
        return cn[n // 10] + "十" + (cn[n % 10] if n % 10 else "")
    return str(n)


async def _fetch_slash(token: str, waves_id: str, version: str) -> Tuple[int, int]:
    from plugins.XutheringWavesUID.XutheringWavesUID.utils.api.wwapi import (
        GET_SLASH_RANK_URL,
        SlashRankItem,
        SlashRankRes,
    )

    async with httpx.AsyncClient(timeout=httpx.Timeout(10)) as client:
        for page in range(1, 6):
            item = SlashRankItem(page=page, page_num=20, waves_id=waves_id, version=version)
            try:
                res = await client.post(
                    GET_SLASH_RANK_URL,
                    json=item.model_dump(),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {token}",
                    },
                )
            except Exception as e:
                logger.warning(f"[ww高考] 冥海排行请求失败: {e}")
                return 0, 0
            if res.status_code != 200:
                logger.warning(f"[ww高考] 冥海排行 {res.status_code}: {res.text}")
                return 0, 0
            data = SlashRankRes.model_validate(res.json())
            if not data.data or not data.data.rank_list:
                return 0, 0
            for r in data.data.rank_list:
                if r.waves_id == waves_id:
                    return int(r.score), int(r.rank)
    return 0, 0


async def _fetch_matrix(token: str, waves_id: str, version: str) -> Tuple[int, int]:
    from plugins.XutheringWavesUID.XutheringWavesUID.utils.api.wwapi import (
        GET_MATRIX_RANK_URL,
        MatrixRankItem,
        MatrixRankRes,
    )

    async with httpx.AsyncClient(timeout=httpx.Timeout(10)) as client:
        for page in range(1, 6):
            item = MatrixRankItem(page=page, page_num=20, waves_id=waves_id, version=version)
            try:
                res = await client.post(
                    GET_MATRIX_RANK_URL,
                    json=item.model_dump(),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {token}",
                    },
                )
            except Exception as e:
                logger.warning(f"[ww高考] 矩阵排行请求失败: {e}")
                return 0, 0
            if res.status_code != 200:
                logger.warning(f"[ww高考] 矩阵排行 {res.status_code}: {res.text}")
                return 0, 0
            data = MatrixRankRes.model_validate(res.json())
            if not data.data or not data.data.rank_list:
                return 0, 0
            for r in data.data.rank_list:
                if r.waves_id == waves_id:
                    return int(r.score), int(r.rank)
    return 0, 0


@sv_ww_gaokao.on_command(
    ("高考", "高考查分", "查分"),
    block=True,
    to_ai="""鸣潮恶搞·模拟高考出分：把冥歌海墟+终焉矩阵的远端排行分数包装成全国高考成绩单。

当用户问「高考 / 查分 / 高考查分」时调用，需绑定特征码并已上传冥海/矩阵记录。

Args:
    text: 无需参数。
""",
)
async def cmd_ww_gaokao(bot: Bot, ev: Event):
    from plugins.XutheringWavesUID.XutheringWavesUID.utils.util import get_version
    from plugins.XutheringWavesUID.XutheringWavesUID.utils.database.models import WavesBind
    from plugins.XutheringWavesUID.XutheringWavesUID.utils.render_utils import render_html
    from plugins.XutheringWavesUID.XutheringWavesUID.wutheringwaves_config import PREFIX, WutheringWavesConfig

    waves_id = await WavesBind.get_uid_by_game(ev.user_id, ev.bot_id)
    if not waves_id:
        return await bot.send(f"还没绑定特征码，先去 {PREFIX}绑定 吧。", at_sender=True)

    token = WutheringWavesConfig.get_config("WavesToken").data
    if not token:
        return await bot.send("总排行服务未启用（缺少 WavesToken）。", at_sender=True)

    version = get_version(dynamic=True, waves_id=waves_id, pages=1)

    slash_score, slash_rank = await _fetch_slash(token, waves_id, version)
    matrix_score, matrix_rank = await _fetch_matrix(token, waves_id, version)

    if slash_rank > 0 and matrix_rank > 0:
        global_rank = math.floor((slash_rank + matrix_rank) / 2)
    elif slash_rank > 0:
        global_rank = slash_rank
    elif matrix_rank > 0:
        global_rank = matrix_rank
    else:
        global_rank = 0

    total_score = slash_score + matrix_score

    rank_cn = _to_cn_rank(global_rank) if global_rank > 0 else "未上榜"
    if global_rank > 0:
        rank_text = f"恭喜你取得全国第{rank_cn}的好成绩！你们也来试试吧！"
    else:
        rank_text = "未在总排行中找到你的成绩，先查询冥海/矩阵再来查分吧！"

    nickname = (ev.sender or {}).get("nickname") or "考 生"
    avatar_url = (ev.sender or {}).get("avatar") or ""

    subjects = [{"name": name, "score": 0} for name in SUBJECTS]

    context = {
        "nickname": nickname,
        "avatar_url": avatar_url,
        "subjects": subjects,
        "slash_score": slash_score,
        "matrix_score": matrix_score,
        "total_score": total_score,
        "rank_text": rank_text,
        "current_date": datetime.now().strftime("%Y-%m-%d"),
    }

    img_bytes = await render_html(_jinja_env, "gaokao.html", context)
    if not img_bytes:
        return await bot.send("渲染失败！", at_sender=True)

    final = await convert_img(img_bytes)
    await bot.send(final)
