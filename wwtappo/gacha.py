import random
from dataclasses import field, asdict, dataclass
from collections.abc import Iterable

from .catalog import TYPES, RARITIES, Item, Catalog

UPGRADE_COST = 10
SAME_COST = 5


@dataclass(frozen=True)
class Rules:
    rates: tuple[float, ...] = (90, 9.5, 0.49, 0.01)
    pity: int = 0
    ten_floor: bool = False


@dataclass
class Box:
    owned: dict[str, int] = field(default_factory=dict)
    pity: int = 0
    draws: int = 0
    day: str = ""
    used: int = 0

    @classmethod
    def new(cls, catalog: Catalog) -> "Box":
        return cls(owned={item.id: 1 for item in catalog.starters})

    @classmethod
    def load(cls, raw: object, catalog: Catalog) -> "Box":
        box = cls.new(catalog)
        if not isinstance(raw, dict):
            return box
        owned = raw.get("owned")
        if isinstance(owned, dict):
            for key, count in owned.items():
                if key in catalog.by_id and type(count) is int and count > 0:
                    box.owned[key] = count
        for key in ("pity", "draws", "used"):
            value = raw.get(key)
            if type(value) is int and value >= 0:
                setattr(box, key, value)
        if isinstance(raw.get("day"), str):
            box.day = raw["day"]
        return box

    def dump(self) -> dict[str, object]:
        return asdict(self)

    def merge(self, other: "Box", catalog: Catalog) -> None:
        for key, count in other.owned.items():
            extra = count - (1 if catalog.by_id[key].starter else 0)
            if extra > 0:
                self.owned[key] = self.owned.get(key, 0) + extra
        self.pity = max(self.pity, other.pity)
        self.draws += other.draws

    def left(self, today: str, limit: int) -> int:
        return max(0, limit - (self.used if self.day == today else 0))

    def spend(self, today: str, n: int) -> None:
        if self.day != today:
            self.day, self.used = today, 0
        self.used += n

    def spare(self, pool: Iterable[Item]) -> int:
        return sum(max(0, self.owned.get(item.id, 0) - 1) for item in pool)

    def collected(self, pool: Iterable[Item]) -> int:
        return sum(1 for item in pool if self.owned.get(item.id, 0) > 0)


@dataclass(frozen=True)
class Award:
    item: Item
    fresh: bool


@dataclass(frozen=True)
class Synthesis:
    kind: str
    source: str
    cost: int
    award: Award


def _award(box: Box, item: Item) -> Award:
    count = box.owned.get(item.id, 0)
    box.owned[item.id] = count + 1
    return Award(item, count == 0)


def _roll(rng: random.Random, rates: tuple[float, ...], floor: int) -> str:
    n = rng.random() * sum(rates)
    level = 0
    for level, rate in enumerate(rates):
        if n < rate:
            break
        n -= rate
    return RARITIES[max(level, floor)]


def draw(box: Box, catalog: Catalog, n: int, rules: Rules, rng: random.Random | None = None) -> list[Award]:
    rng = rng or random.Random()
    awards: list[Award] = []
    high = False
    for i in range(n):
        if i % 10 == 0:
            high = False
        box.pity += 1
        floor = 1 if rules.ten_floor and i % 10 == 9 and not high else 0
        rarity = "epic" if 0 < rules.pity <= box.pity else _roll(rng, rules.rates, floor)
        if rarity == "epic":
            box.pity = 0
        high = high or rarity != "common"
        awards.append(_award(box, rng.choice(catalog.by_rarity[rarity])))
        box.draws += 1
    return awards


def _consume(box: Box, pool: Iterable[Item], cost: int) -> None:
    for item in sorted(pool, key=lambda x: box.owned.get(x.id, 0), reverse=True):
        take = min(cost, box.owned.get(item.id, 0) - 1)
        if take > 0:
            box.owned[item.id] -= take
            cost -= take
        if cost == 0:
            return


def synthesize_all(box: Box, catalog: Catalog, rng: random.Random | None = None) -> list[Synthesis]:
    rng = rng or random.Random()
    done: list[Synthesis] = []
    for kind in TYPES:
        tiers = catalog.tiers(kind)
        for i, rarity in enumerate(tiers):
            source = catalog.pools[(kind, rarity)]
            target = tiers[i + 1] if i + 1 < len(tiers) else rarity
            cost = SAME_COST if target == rarity else UPGRADE_COST
            pool = catalog.pools[(kind, target)]
            while box.spare(source) >= cost:
                fresh = [item for item in pool if item.id not in box.owned]
                if target == rarity and not fresh:
                    break
                _consume(box, source, cost)
                done.append(Synthesis(kind, rarity, cost, _award(box, rng.choice(fresh or pool))))
    return done
