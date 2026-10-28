import os
import re
import json
import asyncio
import hashlib
from pathlib import Path
from weakref import WeakValueDictionary
from dataclasses import dataclass

from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.data_store import get_res_path

from .gacha import Box
from .catalog import CATALOG

DATA_DIR = get_res_path(["XWUIDCollection", "tappo"])
_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()


@dataclass(frozen=True)
class Owner:
    key: str
    fallbacks: tuple[str, ...] = ()
    uid: str = ""


def _safe(text: str) -> str:
    return text if re.fullmatch(r"[\w-]{1,64}", text, re.ASCII) else hashlib.sha1(text.encode()).hexdigest()


def _path(key: str) -> Path:
    return DATA_DIR / f"{key}.json"


def _read(key: str) -> object:
    path = _path(key)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning(f"[ww开箱] 读取 {key} 失败：{exc}")
        return None


def _write(key: str, data: dict[str, object]) -> None:
    path = _path(key)
    path.parent.mkdir(exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, path)


async def owner(ev: Event) -> Owner:
    from plugins.XutheringWavesUID.XutheringWavesUID.utils.util import hide_uid
    from plugins.XutheringWavesUID.XutheringWavesUID.utils.constants import WAVES_GAME_ID
    from plugins.XutheringWavesUID.XutheringWavesUID.utils.database.models import WavesBind, WavesUser

    user = _safe(ev.user_id)
    uid = await WavesBind.get_uid_by_game(ev.user_id, ev.bot_id)
    if not uid:
        return Owner(f"user/{user}")
    waves = await WavesUser.select_waves_user(uid, ev.user_id, ev.bot_id, game_id=WAVES_GAME_ID)
    shown = hide_uid(uid, waves.hide_uid_self_value if waves else "")
    bound = f"user/{user}_{_safe(uid)}"
    if waves and waves.cookie:
        return Owner(f"uid/{_safe(uid)}", (bound, f"user/{user}"), shown)
    return Owner(bound, (f"user/{user}",), shown)


def lock(key: str) -> asyncio.Lock:
    if key not in _locks:
        current = asyncio.Lock()
        _locks[key] = current
        return current
    return _locks[key]


def load(who: Owner) -> Box:
    box = Box.load(_read(who.key), CATALOG)
    merged = [key for key in who.fallbacks if _path(key).exists()]
    if merged:
        for key in merged:
            box.merge(Box.load(_read(key), CATALOG), CATALOG)
        save(who, box)
        for key in merged:
            _path(key).unlink(missing_ok=True)
        logger.info(f"[ww开箱] {'、'.join(merged)} 并入 {who.key}")
    return box


def save(who: Owner, box: Box) -> None:
    _write(who.key, box.dump())
