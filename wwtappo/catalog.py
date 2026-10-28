import json
from pathlib import Path
from dataclasses import dataclass

ROOT = Path(__file__).parent
RARITIES = ("common", "uncommon", "rare", "epic")
RARITY_LABELS = {"common": "普通", "uncommon": "珍稀", "rare": "稀有", "epic": "史诗"}
TYPES = ("character", "accessory", "emote")
TYPE_LABELS = {"character": "角色", "accessory": "配件", "emote": "表情"}


@dataclass(frozen=True)
class Item:
    id: str
    asset: int
    type: str
    rarity: str
    name: str
    role: int
    role_name: str
    series: str
    starter: bool

    @property
    def image(self) -> Path:
        return ROOT / "assets" / "items" / f"{self.asset}.webp"


class Catalog:
    def __init__(self, path: Path) -> None:
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.series: dict[str, str] = raw["series"]
        self.roles: dict[int, str] = {int(key): name for key, name in raw["roles"].items()}
        self.items = tuple(Item(**item) for item in raw["items"])
        self.by_id = {item.id: item for item in self.items}
        self.by_rarity = {r: tuple(x for x in self.items if x.rarity == r) for r in RARITIES}
        self.pools = {
            (t, r): tuple(x for x in self.items if x.type == t and x.rarity == r) for t in TYPES for r in RARITIES
        }
        self.starters = tuple(item for item in self.items if item.starter)

    def tiers(self, kind: str) -> tuple[str, ...]:
        return tuple(r for r in RARITIES if self.pools[(kind, r)])


CATALOG = Catalog(ROOT / "catalog.json")
