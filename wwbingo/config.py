import random
from typing import Dict, List

from gsuid_core.data_store import get_res_path
from gsuid_core.utils.plugins_config.models import (
    GSC,
    GsBoolConfig,
    GsListStrConfig,
)
from gsuid_core.utils.plugins_config.gs_config import StringConfig

from .char_data import FIVE_STAR_IDS, FOUR_STAR_IDS, ROVER_IDS, has_head

CONFIG_PATH = get_res_path("XWUIDCollection") / "config.json"

REFERENCE_BINGO_IDS: List[int] = [
    1211, 1605, 1510, 1507, 1207, 1107,
    1508, 1410, 1209, 1205, 1305, 1105,
    1206, 1607, 1208, 1503, 1104, 1306,
    1302, 1506, 1603, 1108, 1404, 1405,
    1505, 1509, 1407, 1301, 1409, 1210,
    1203, 1412, 1606, 1608, 1304, 1411,
]

CONFIG_DEFAULT: Dict[str, GSC] = {
    "BingoRoleIds": GsListStrConfig(
        "宾果角色ID(6x6=36,行优先,留空随机)",
        "填 36 个角色ID自定义棋盘(从左到右、从上到下);留空则每次随机生成合法组合",
        [],
    ),
    "BingoWith4Star": GsBoolConfig(
        "随机时带四星",
        "随机生成棋盘时是否把四星也算进去(默认关,只随五星)",
        False,
    ),
}

XWUIDCollectionConfig = StringConfig("XWUIDCollection", CONFIG_PATH, CONFIG_DEFAULT)


def _random_bingo_ids() -> List[int]:
    pool = [c for c in FIVE_STAR_IDS if has_head(c)]
    if XWUIDCollectionConfig.get_config("BingoWith4Star").data:
        pool += [c for c in FOUR_STAR_IDS if has_head(c)]
    rovers = [r for r in ROVER_IDS if has_head(r)]

    picks: List[int] = []
    if rovers:
        picks.append(random.choice(rovers))
    need = 36 - len(picks)
    picks += random.sample(pool, min(need, len(pool)))
    random.shuffle(picks)
    return picks[:36]


def get_bingo_ids() -> List[int]:
    raw = XWUIDCollectionConfig.get_config("BingoRoleIds").data or []
    ids: List[int] = []
    for x in raw:
        try:
            ids.append(int(str(x).strip()))
        except (TypeError, ValueError):
            continue
    if not ids:
        return _random_bingo_ids()
    if len(ids) < 36:
        for d in _random_bingo_ids():
            if d not in ids:
                ids.append(d)
            if len(ids) >= 36:
                break
    return ids[:36]
