import base64
from pathlib import Path
from functools import cache
from dataclasses import dataclass

from jinja2 import Environment, FileSystemLoader, select_autoescape

from gsuid_core.models import Event

from .gacha import Box, Award
from .query import Query
from .catalog import TYPES, CATALOG, RARITIES, TYPE_LABELS, RARITY_LABELS, Item

ROOT = Path(__file__).parent
ASSETS = ROOT / "assets"
_ENV = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape())
_MIME = {".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg", ".woff2": "font/woff2"}


@dataclass(frozen=True)
class Card:
    name: str
    head: str
    tail: str
    rarity: str
    label: str
    image: str
    count: int
    fresh: bool = False


@cache
def _uri(path: Path) -> str:
    return f"data:{_MIME[path.suffix]};base64,{base64.b64encode(path.read_bytes()).decode()}"


def _card(item: Item, box: Box, fresh: bool = False) -> Card:
    label = f"{RARITY_LABELS[item.rarity]} · {TYPE_LABELS[item.type]}"
    head, _, tail = item.name.partition(" · ")
    return Card(item.name, head, tail, item.rarity, label, _uri(item.image), box.owned.get(item.id, 0), fresh)


def _progress(box: Box) -> list[dict[str, object]]:
    rows = []
    for kind in TYPES:
        pool = [item for item in CATALOG.items if item.type == kind]
        rows.append({"label": TYPE_LABELS[kind], "owned": box.collected(pool), "total": len(pool)})
    return rows


async def _render(ev: Event, template: str, context: dict[str, object]) -> bytes | None:
    from plugins.XutheringWavesUID.XutheringWavesUID.utils.image import pil_to_b64, get_event_avatar
    from plugins.XutheringWavesUID.XutheringWavesUID.utils.render_utils import render_html, get_footer_b64

    avatar = await get_event_avatar(ev, is_valid_at_param=False)
    context.update(
        nickname=((ev.sender or {}).get("nickname") or "漂泊者")[:12],
        avatar=pil_to_b64(avatar, quality=80),
        font=_uri(ASSETS / "font" / "tappo.woff2"),
        ui={path.stem: _uri(path) for path in sorted((ASSETS / "ui").iterdir())},
        footer=get_footer_b64(footer_type="black") or "",
    )
    return await render_html(_ENV, template, context)


async def render_awards(
    ev: Event,
    uid: str,
    box: Box,
    batches: list[list[Award]],
    title: str,
    left: int,
    limit: int,
    pity: int,
    note: str = "",
) -> bytes | None:
    sections = [
        {
            "label": f"第 {i} 次十连" if len(batches) > 1 else "",
            "cards": [_card(award.item, box, award.fresh) for award in batch],
        }
        for i, batch in enumerate(batches, 1)
    ]
    context: dict[str, object] = {
        "uid": uid,
        "title": title,
        "note": note,
        "sections": sections,
        "left": left,
        "limit": limit,
        "pity": pity - box.pity if pity else 0,
        "collected": box.collected(CATALOG.items),
        "total": len(CATALOG.items),
        "progress": _progress(box),
    }
    return await _render(ev, "draw.html", context)


async def render_atlas(ev: Event, uid: str, box: Box, query: Query) -> bytes | None:
    groups = []
    count = 0
    for rarity in reversed(RARITIES):
        items = [item for item in CATALOG.items if item.rarity == rarity and query.match(item)]
        if not items:
            continue
        count += len(items)
        groups.append(
            {
                "rarity": rarity,
                "label": RARITY_LABELS[rarity],
                "owned": box.collected(items),
                "total": len(items),
                "cards": [_card(item, box) for item in items],
            }
        )
    context: dict[str, object] = {
        "uid": uid,
        "title": query.title(CATALOG),
        "groups": groups,
        "columns": 12 if count > 300 else 9,
        "collected": box.collected(CATALOG.items),
        "total": len(CATALOG.items),
        "progress": _progress(box),
    }
    return await _render(ev, "atlas.html", context)
