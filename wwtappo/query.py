import re
from os.path import commonprefix
from dataclasses import dataclass
from collections.abc import Callable

from .catalog import TYPE_LABELS, RARITY_LABELS, Item, Catalog

TYPE_WORDS = {"角色": "character", "皮肤": "character", "形象": "character", "配件": "accessory", "表情": "emote"}


@dataclass(frozen=True)
class Query:
    kind: str | None = None
    rarity: str | None = None
    series: str | None = None
    roles: tuple[int, ...] = ()

    def match(self, item: Item) -> bool:
        return (
            (self.kind is None or item.type == self.kind)
            and (self.rarity is None or item.rarity == self.rarity)
            and (self.series is None or item.series == self.series)
            and (not self.roles or item.role in self.roles)
        )

    def title(self, catalog: Catalog) -> str:
        parts = []
        if self.roles:
            names = [_roles(catalog)[role] for role in self.roles]
            parts.append(names[0] if len(names) == 1 else commonprefix(names).rstrip("（("))
        if self.series:
            parts.append(catalog.series[self.series])
        if self.rarity:
            parts.append(RARITY_LABELS[self.rarity])
        if self.kind:
            parts.append(TYPE_LABELS[self.kind])
        return " · ".join(parts)


def _norm(text: str) -> str:
    return re.sub(r"[\s·・（）()]", "", text).lower()


def _roles(catalog: Catalog) -> dict[int, str]:
    return {0: "阿布", **catalog.roles}


def _match_roles(catalog: Catalog, key: str) -> tuple[int, ...]:
    if not key:
        return ()
    roles = _roles(catalog)
    exact = tuple(rid for rid, name in roles.items() if _norm(name) == key)
    return exact or tuple(rid for rid, name in roles.items() if _norm(name).startswith(key))


def parse(text: str, catalog: Catalog, alias: Callable[[str], str | None] | None = None) -> Query | None:
    rest = re.sub(r"\s+", "", text)
    kind = rarity = series = None
    for word, value in TYPE_WORDS.items():
        if word in rest:
            kind, rest = value, rest.replace(word, "")
    for value, label in RARITY_LABELS.items():
        if label in rest:
            rarity, rest = value, rest.replace(label, "")
    keys = {}
    for code, name in catalog.series.items():
        keys[name] = code
        keys[name.removeprefix("创作者合作系列 · ").removesuffix("系列")] = code
    for key in sorted(keys, key=len, reverse=True):
        found = rest.lower().find(key.lower())
        if found >= 0:
            series, rest = keys[key], rest[:found] + rest[found + len(key) :]
            break
    rest = rest.removesuffix("系列")
    roles: tuple[int, ...] = ()
    if rest:
        roles = _match_roles(catalog, _norm(rest))
        if not roles and alias:
            name = alias(rest)
            roles = _match_roles(catalog, _norm(name)) if name else ()
        if not roles:
            return None
    if not (kind or rarity or series or roles):
        kind = "character"
    return Query(kind, rarity, series, roles)
