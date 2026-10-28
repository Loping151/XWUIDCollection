import re
from datetime import datetime, timezone, timedelta
from collections import Counter

from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.utils.image.convert import convert_img

from . import store
from .gacha import Award, draw, synthesize_all
from .query import parse
from .config import rules, daily_draws
from .render import render_atlas, render_awards
from .catalog import CATALOG, TYPE_LABELS, RARITY_LABELS

sv_tappo = SV("Tappo开箱", priority=5)
sv_tappo_atlas = SV("Tappo图鉴", priority=4)
sv_tappo_synth = SV("Tappo合成", priority=4)

BATCH = 10
MAX_BATCHES = 10
_CN = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _today() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")


def _batches(text: str) -> int | None:
    text = re.sub(r"\s+", "", text)
    if text in ("", "十连"):
        return 1
    if text in ("全部", "梭哈"):
        return 10000
    found = re.fullmatch(r"(\d{1,4}|[一二两三四五六七八九十])[次个发]?(?:十连)?", text)
    if not found:
        return None
    value = found.group(1)
    return _CN[value] if value in _CN else int(value)


async def _send(bot: Bot, image: bytes | None, awards: list[Award]) -> None:
    if image:
        await bot.send(await convert_img(image))
        return
    await bot.send("获得：" + "、".join(award.item.name for award in awards), at_sender=True)


@sv_tappo.on_command(
    ("tp", "tappo"),
    block=True,
    to_ai="""Wuwa Tappo 桌宠开箱：每次十连，抽角色形象、配件、表情收集图鉴，每天有次数上限。

当用户说「开箱 / tappo 抽一下 / tp十连」时调用。

Args:
    text: 可选十连次数，如 "3" 即开 3 次十连，单次最多 10 次十连；留空开 1 次十连；"全部" 开到上限。
""",
)
async def cmd_ww_tappo(bot: Bot, ev: Event) -> None:
    batches = _batches(ev.text)
    if not batches:
        return
    limit = daily_draws()
    today = _today()
    who = await store.owner(ev)
    async with store.lock(who.key):
        box = store.load(who)
        left = box.left(today, limit)
        if left <= 0:
            await bot.send("今天的开箱次数用完了，明天再来吧", at_sender=True)
            return
        n = min(min(batches, MAX_BATCHES) * BATCH, left)
        current = rules()
        awards = draw(box, CATALOG, n, current)
        box.spend(today, n)
        store.save(who, box)
    logger.info(f"[ww开箱] {who.key} 开箱 {n} 次")
    groups = [awards[i : i + BATCH] for i in range(0, n, BATCH)]
    image = await render_awards(ev, who.uid, box, groups, "开箱结果", left - n, limit, current.pity)
    await _send(bot, image, awards)


@sv_tappo_atlas.on_command(
    ("tp图鉴", "tappo图鉴"),
    block=True,
    to_ai="""Wuwa Tappo 收集图鉴：展示已收集与未收集的桌宠角色形象、配件、表情。

Args:
    text: 可选筛选，可组合：角色/配件/表情、普通/珍稀/稀有/史诗、系列名、角色名。留空显示角色形象。
""",
)
async def cmd_ww_tappo_atlas(bot: Bot, ev: Event) -> None:
    from plugins.XutheringWavesUID.XutheringWavesUID.utils.name_convert import alias_to_char_name_optional

    query = parse(ev.text, CATALOG, alias_to_char_name_optional)
    if query is None or not any(query.match(item) for item in CATALOG.items):
        await bot.send(f"没有找到「{ev.text.strip()}」相关的收集物", at_sender=True)
        return
    who = await store.owner(ev)
    async with store.lock(who.key):
        box = store.load(who)
    image = await render_atlas(ev, who.uid, box, query)
    if not image:
        await bot.send("渲染失败", at_sender=True)
        return
    await bot.send(await convert_img(image))


@sv_tappo_synth.on_command(
    ("tp合成", "tappo合成"),
    block=True,
    to_ai="""Wuwa Tappo 一键合成：把重复的桌宠收集物合成为更高稀有度的同品类收集物。

Args:
    text: 无需参数。
""",
)
async def cmd_ww_tappo_synth(bot: Bot, ev: Event) -> None:
    who = await store.owner(ev)
    async with store.lock(who.key):
        box = store.load(who)
        done = synthesize_all(box, CATALOG)
        if not done:
            await bot.send("没有可合成的重复收集物", at_sender=True)
            return
        store.save(who, box)
    spent: Counter[tuple[str, str]] = Counter()
    for entry in done:
        spent[(entry.source, entry.kind)] += entry.cost
    note = " · ".join(f"{RARITY_LABELS[r]}{TYPE_LABELS[k]} ×{n}" for (r, k), n in spent.items())
    limit = daily_draws()
    left = box.left(_today(), limit)
    awards = [entry.award for entry in done]
    logger.info(f"[ww开箱] {who.key} 合成 {len(done)} 次")
    image = await render_awards(ev, who.uid, box, [awards], "合成结果", left, limit, rules().pity, note)
    await _send(bot, image, awards)
