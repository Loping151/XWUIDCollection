import math
import time
import asyncio
from weakref import WeakValueDictionary
from collections import OrderedDict
from dataclasses import field, dataclass

from .models import Role, Goods, Limits, RechargeError

Owner = tuple[str, str]


@dataclass(frozen=True)
class Catalogue:
    uid: str
    goods: tuple[Goods, ...]
    expires: float


@dataclass
class Listing:
    token: str = field(repr=False)
    role: Role
    goods: tuple[Goods, ...]
    limits: Limits
    expires: float = field(default_factory=lambda: time.monotonic() + 600)
    images: dict[str, bytes] = field(default_factory=dict, repr=False)


class RechargeState:
    def __init__(self) -> None:
        self._locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()
        self._catalogues: OrderedDict[Owner, Catalogue] = OrderedDict()
        self._cooldowns: dict[str, float] = {}
        self._listings: dict[str, Listing] = {}

    def listing(self, uid: str) -> Listing | None:
        cached = self._listings.get(uid)
        return cached if cached and cached.expires > time.monotonic() else None

    def store(self, uid: str, listing: Listing) -> None:
        now = time.monotonic()
        self._listings = {key: value for key, value in self._listings.items() if value.expires > now}
        self._listings[uid] = listing

    def forget(self, uid: str) -> None:
        self._listings.pop(uid, None)

    def lock(self, uid: str) -> asyncio.Lock:
        if uid not in self._locks:
            lock = asyncio.Lock()
            self._locks[uid] = lock
            return lock
        return self._locks[uid]

    def remember(self, owner: Owner, uid: str, goods: tuple[Goods, ...]) -> None:
        self._catalogues[owner] = Catalogue(uid, goods, time.monotonic() + 300)
        self._catalogues.move_to_end(owner)
        while len(self._catalogues) > 256:
            self._catalogues.popitem(last=False)

    def displayed(self, owner: Owner, uid: str, fresh: tuple[Goods, ...]) -> tuple[Goods, ...]:
        if owner not in self._catalogues:
            return fresh
        catalogue = self._catalogues[owner]
        if catalogue.uid != uid or catalogue.expires <= time.monotonic():
            raise RechargeError("绑定或商品列表已变动，请重新发送 ww充值 后再选择商品。")
        return catalogue.goods

    def reserve_order(self, uid: str, seconds: int) -> None:
        now = time.monotonic()
        self._cooldowns = {key: until for key, until in self._cooldowns.items() if until > now}
        if uid in self._cooldowns:
            remaining = math.ceil(self._cooldowns[uid] - now)
            raise RechargeError(f"该角色下单过于频繁，请在 {remaining} 秒后重试。")
        self._cooldowns[uid] = now + seconds
