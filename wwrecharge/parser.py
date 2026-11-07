import re
import math
import unicodedata
from decimal import Decimal

from .models import Goods, Limits, CartItem, PayChannel, RechargeError, cart_total

_NUM = r"[0-9零〇一二两兩三四五六七八九十]+"
_DIGITS = {c: i for i, c in enumerate("零一二三四五六七八九")}
_DIGITS.update({"〇": 0, "两": 2, "兩": 2})
_TARGET = re.compile(rf"(\d+(?:\.\d+)?|{_NUM})\s*([wW万])?\s*(元|块)?")
_ORDER_CAP = Decimal("50000")


def number(text: str) -> int:
    if text.isascii() and text.isdigit():
        return int(text)
    if text in _DIGITS:
        return _DIGITS[text]
    if text.count("十") == 1:
        left, right = text.split("十")
        if (not left or left in _DIGITS) and (not right or right in _DIGITS):
            return (_DIGITS[left] if left else 1) * 10 + (_DIGITS[right] if right else 0)
    raise RechargeError("数量或编号无法识别，请使用数字。")


def payment(text: str, default: PayChannel) -> tuple[str, PayChannel]:
    text = unicodedata.normalize("NFKC", text).strip()
    channels: set[PayChannel] = set()
    for word, channel in (("支付宝", "24"), ("微信", "23")):
        if word in text:
            channels.add("24" if channel == "24" else "23")
            text = text.replace(word + "支付", "").replace(word, "").strip()
    if len(channels) > 1:
        raise RechargeError("每次只能选择一种支付方式：微信或支付宝。")
    return text, next(iter(channels)) if channels else default


def _quantity(text: str) -> tuple[str, int]:
    prefix = re.fullmatch(rf"({_NUM})\s*(?:个|個|张|張|份|次)\s*(.+)", text)
    if prefix:
        return prefix[2].strip(), number(prefix[1])
    suffix = re.fullmatch(rf"(.+?)\s*[xX*×]\s*({_NUM})", text)
    if suffix:
        return suffix[1].strip(), number(suffix[2])
    return text, 1


def _match(label: str, goods: tuple[Goods, ...]) -> Goods:
    if re.fullmatch(_NUM, label):
        n = number(label)
        if 1 <= n <= len(goods):
            return goods[n - 1]
        candidates = [g for g in goods if g.amount == n and n > 0]
        if not candidates:
            candidates = [g for g in goods if g.price == Decimal(n)]
    elif label in {"月卡", "月相卡", "月相观测卡", "月相觀測卡"}:
        candidates = [g for g in goods if g.id.endswith(".month")]
    elif re.fullmatch(r"\d+(?:\.\d{1,2})?(?:元|块|塊)", label):
        candidates = [g for g in goods if g.price == Decimal(label[:-1])]
    else:
        candidates = [g for g in goods if label == g.name or label == g.id]
        if not candidates:
            candidates = [g for g in goods if label and label in g.name]
    if not candidates:
        raise RechargeError(f"找不到商品「{label}」，请发送 ww充值 查看列表。")
    if len(candidates) > 1:
        names = "、".join(g.name for g in candidates)
        raise RechargeError(f"「{label}」对应多个商品：{names}。请使用列表编号或完整名称。")
    return candidates[0]


def parse_cart(text: str, goods: tuple[Goods, ...]) -> tuple[CartItem, ...]:
    if not text or len(text) > 200:
        raise RechargeError("请输入商品编号或名称，例如：ww充值1+2、ww充值3个月卡。")
    parts = re.split(r"[+、,，;；和]", unicodedata.normalize("NFKC", text))
    if len(parts) > 30 or any(not p.strip() for p in parts):
        raise RechargeError("购物车格式有误，例如：ww充值1+2+3。")
    items: dict[str, CartItem] = {}
    for part in parts:
        label, quantity = _quantity(part.strip())
        if quantity < 1:
            raise RechargeError("商品数量必须大于 0。")
        selected = _match(label, goods)
        previous = items[selected.id].quantity if selected.id in items else 0
        items[selected.id] = CartItem(selected, previous + quantity)
    return tuple(items.values())


def _known(n: int, goods: tuple[Goods, ...]) -> bool:
    return 1 <= n <= len(goods) or any(g.amount == n or g.price == n for g in goods)


def _decimal(value: str) -> Decimal:
    return Decimal(value) if "." in value else Decimal(number(value))


def money_target(text: str, goods: tuple[Goods, ...]) -> Decimal | None:
    match = _TARGET.fullmatch(unicodedata.normalize("NFKC", text).strip())
    if not match:
        return None
    value, wan, yuan = match.groups()
    if not wan and not yuan and ("." in value or number(value) < 1 or _known(number(value), goods)):
        return None
    if not wan and yuan and any(g.price == _decimal(value) for g in goods):
        return None
    target = _decimal(value) * (10000 if wan else 1)
    if target <= 0:
        raise RechargeError("金额必须大于 0。")
    return target


def moon_cart(target: Decimal, goods: tuple[Goods, ...], limits: Limits) -> tuple[CartItem, ...]:
    packs: list[tuple[Goods, int]] = []
    for g in goods:
        if g.amount <= 0 or not g.name.endswith("月相") or g.status != 1:
            continue
        caps = [limits.per_item, limits.total]
        caps += [c for c in (g.remaining, g.buy_limit) if c is not None and c >= 0]
        if min(caps) > 0:
            packs.append((g, min(caps)))
    if not packs:
        raise RechargeError("当前没有可购买的月相商品。")
    cents = [int(g.price * 100) for g, _ in packs]
    goal = int(target * 100)
    unit = math.gcd(*cents)
    reach = min(
        sum(c * cap for c, (_, cap) in zip(cents, packs)),
        goal + max(cents),
        int(_ORDER_CAP * 100),
    )
    ceiling = reach // unit
    best = [0] + [limits.total + 1] * ceiling
    layers: list[tuple[int, int, int, bytearray]] = []
    for index, (c, (_, cap)) in enumerate(zip(cents, packs)):
        chunk = 1
        while cap > 0:
            take = min(chunk, cap)
            cap -= take
            chunk *= 2
            span = c // unit * take
            if span > ceiling:
                break
            used = bytearray(ceiling + 1)
            for s in range(ceiling, span - 1, -1):
                if best[s - span] + take < best[s]:
                    best[s] = best[s - span] + take
                    used[s] = 1
            layers.append((index, take, span, used))
    reachable = [s for s in range(1, ceiling + 1) if best[s] <= limits.total]
    if not reachable:
        raise RechargeError("当前没有可购买的月相商品。")
    if goal > reachable[-1] * unit:
        raise RechargeError(f"单笔订单最多 {Decimal(reachable[-1] * unit) / 100} 元，请分次充值。")
    s = min(reachable, key=lambda s: (abs(s * unit - goal), best[s], s))
    counts = [0] * len(packs)
    for index, take, span, used in reversed(layers):
        if used[s]:
            s -= span
            counts[index] += take
    return tuple(CartItem(g, n) for (g, _), n in zip(packs, counts) if n)


def build_cart(text: str, goods: tuple[Goods, ...], limits: Limits) -> tuple[CartItem, ...]:
    target = money_target(text, goods)
    return parse_cart(text, goods) if target is None else moon_cart(target, goods, limits)


def validate_cart(cart: tuple[CartItem, ...], fresh: tuple[Goods, ...], limits: Limits) -> tuple[CartItem, ...]:
    available = {g.id: g for g in fresh}
    checked: list[CartItem] = []
    for item in cart:
        if item.goods.id not in available:
            raise RechargeError(f"「{item.goods.name}」已不可购买，请重新发送 ww充值。")
        current = available[item.goods.id]
        if current.name != item.goods.name or current.price != item.goods.price:
            raise RechargeError("商品信息已变动，请重新发送 ww充值 查看价格。")
        if current.status != 1 or current.remaining == 0 or current.buy_limit == 0:
            raise RechargeError(f"「{current.name}」当前不可购买。")
        caps = [limits.per_item]
        for count in (current.remaining, current.buy_limit):
            if count is not None and count >= 0:
                caps.append(count)
        maximum = min(caps)
        if not 1 <= item.quantity <= maximum:
            raise RechargeError(f"「{current.name}」本次最多可购买 {maximum} 件。")
        checked.append(CartItem(current, item.quantity))
    result = tuple(checked)
    if not result or sum(i.quantity for i in result) > limits.total:
        raise RechargeError(f"购物车最多可购买 {limits.total} 件商品。")
    if sum(i.quantity for i in result if i.goods.is_pass) > 1:
        raise RechargeError("每个订单只能购买一份通行证。")
    if cart_total(result) > _ORDER_CAP:
        raise RechargeError(f"单笔订单金额不能超过 {_ORDER_CAP} 元。")
    return result
