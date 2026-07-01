import json
from typing import Dict, List, Optional

ATTRIBUTE_ID_MAP = {1: "冷凝", 2: "热熔", 3: "导电", 4: "气动", 5: "衍射", 6: "湮灭"}

_CHAR_ATTR_ID: Dict[int, int] = {
    1104: 1, 1105: 1, 1107: 1, 1108: 1, 1109: 1, 1110: 1,
    1203: 2, 1205: 2, 1206: 2, 1207: 2, 1208: 2, 1209: 2, 1210: 2, 1211: 2,
    1301: 3, 1302: 3, 1304: 5, 1305: 3, 1306: 3, 1308: 3, 1309: 3, 1310: 3,
    1404: 4, 1405: 4, 1406: 4, 1407: 4, 1408: 4, 1409: 4, 1410: 4, 1411: 4, 1412: 4,
    1501: 5, 1502: 5, 1503: 5, 1505: 5, 1506: 5, 1507: 5, 1508: 6, 1509: 5, 1510: 5, 1511: 5,
    1603: 6, 1604: 6, 1605: 6, 1606: 6, 1607: 6, 1608: 6, 1610: 6,
}

ROVER_IDS: List[int] = [1309, 1310, 1406, 1408, 1501, 1502, 1604, 1605]
MALE_ROVER_IDS: List[int] = [1309, 1406, 1501, 1605]
FEMALE_ROVER_IDS: List[int] = [1310, 1408, 1502, 1604]
FIVE_STAR_IDS: List[int] = [cid for cid in _CHAR_ATTR_ID if cid not in set(ROVER_IDS)]
FOUR_STAR_IDS: List[int] = [
    1102, 1103, 1106, 1202, 1204, 1303, 1307, 1402, 1403, 1504, 1601, 1602,
]

_attr_name_cache: Dict[int, Optional[str]] = {}
_head_cache: Dict[int, bool] = {}


def has_head(char_id: int) -> bool:
    if char_id in _head_cache:
        return _head_cache[char_id]
    ok = False
    try:
        from plugins.XutheringWavesUID.XutheringWavesUID.utils.image import (
            get_square_avatar_path,
        )

        ok = get_square_avatar_path(char_id).name == f"role_head_{char_id}.png"
    except Exception:
        ok = False
    _head_cache[char_id] = ok
    return ok


def get_char_attribute(char_id: int) -> Optional[str]:
    attr_id = _CHAR_ATTR_ID.get(char_id)
    if attr_id:
        return ATTRIBUTE_ID_MAP.get(attr_id)

    if char_id in _attr_name_cache:
        return _attr_name_cache[char_id]

    name: Optional[str] = None
    try:
        from plugins.XutheringWavesUID.XutheringWavesUID.utils.resource.RESOURCE_PATH import MAP_PATH

        path = MAP_PATH / "detail_json" / "char" / f"{char_id}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            name = ATTRIBUTE_ID_MAP.get(int(data.get("attributeId", 0)))
    except Exception:
        name = None

    _attr_name_cache[char_id] = name
    return name
