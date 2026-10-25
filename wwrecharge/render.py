import base64
import asyncio
import mimetypes
from io import BytesIO
from pathlib import Path
from functools import lru_cache
from dataclasses import dataclass
from collections.abc import Iterable

import qrcode
from jinja2 import Environment, TemplateError, FileSystemLoader, select_autoescape
from qrcode.constants import ERROR_CORRECT_M
from playwright.async_api import Error as BrowserError

from .models import DISCLAIMER, OFFICIAL_URL, Role, Goods, Order, CartItem, PayChannel, RechargeError, cart_total

_ROOT = Path(__file__).parent
_ENV = Environment(loader=FileSystemLoader(_ROOT / "templates"), autoescape=select_autoescape())
_ICON_SEM = asyncio.Semaphore(4)
_ASSETS = (
    "banner.webp",
    "mc_logo.png",
    "kuro_logo.webp",
    "card_bg.webp",
    "modal_bg.webp",
    "tag_first.png",
    "tag_extra.png",
    "tag_star.png",
    "bonus_left.png",
    "bonus_left_inner.png",
    "bonus_center.png",
    "bonus_right.png",
    "shopping_bg.png",
    "cart.png",
    "wx.png",
    "ali.png",
)


@dataclass(frozen=True)
class Player:
    uid: str
    name: str
    server: str


@dataclass(frozen=True)
class Product:
    index: int
    name: str
    price: str
    image: str
    badge: str
    badge_type: str
    remaining: int | None
    buy_limit: int | None
    available: bool


@dataclass(frozen=True)
class LineItem:
    name: str
    quantity: int
    price: str
    subtotal: str
    image: str = ""


ContextValue = str | dict[str, str] | Player | list[Product] | list[LineItem]


def _data_url(data: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


@lru_cache(maxsize=1)
def assets() -> dict[str, str]:
    result: dict[str, str] = {}
    for name in _ASSETS:
        mime, _ = mimetypes.guess_type(name)
        if mime is None:
            raise ValueError(f"未知素材格式：{name}")
        result[Path(name).stem] = _data_url((_ROOT / "assets" / name).read_bytes(), mime)
    return result


def qr_data(url: str) -> str:
    code = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=8, border=4)
    code.add_data(url)
    code.make(fit=True)
    image = code.make_image(fill_color="black", back_color="white")
    output = BytesIO()
    image.save(output)
    return _data_url(output.getvalue(), "image/png")


async def _render(template: str, context: dict[str, ContextValue], *, ordered: bool = False) -> bytes:
    from plugins.XutheringWavesUID.XutheringWavesUID.utils.render_utils import render_html

    try:
        context["assets"] = await asyncio.to_thread(assets)
        context["official_url"] = OFFICIAL_URL
        result: bytes | None = await render_html(_ENV, template, context)
    except (BrowserError, OSError, TemplateError) as exc:
        message = (
            "订单已创建，但二维码渲染失败，请到官方充值中心确认，勿立即重复下单。"
            if ordered
            else "商品列表渲染失败，请稍后再试。"
        )
        raise RechargeError(message) from exc
    if not result:
        raise RechargeError("图片渲染不可用，请使用官方充值中心；若已下单，请勿立即重复下单。")
    return result


async def _icons(goods: Iterable[Goods]) -> dict[str, str]:
    from plugins.XutheringWavesUID.XutheringWavesUID.utils.render_utils import get_image_b64_with_cache

    from gsuid_core.data_store import get_res_path

    cache = get_res_path("XWUIDCollection") / "recharge_icons"

    async def fetch(url: str) -> tuple[str, str]:
        async with _ICON_SEM:
            return url, await get_image_b64_with_cache(url, cache, quality=85)

    return dict(await asyncio.gather(*(fetch(url) for url in {item.icon for item in goods})))


def _badge(item: Goods) -> tuple[str, str]:
    if item.privilege == 1:
        return f"首充+{item.extra}", "first"
    if item.extra > 0:
        return f"额外+{item.extra}", "extra"
    return item.discount or "", "bonus"


async def render_catalogue(role: Role, goods: tuple[Goods, ...]) -> bytes:
    icons = await _icons(goods)
    products = [
        Product(
            index,
            item.name,
            item.price_text,
            icons[item.icon],
            *_badge(item),
            item.remaining,
            item.buy_limit,
            item.status == 1 and item.remaining != 0,
        )
        for index, item in enumerate(goods, 1)
    ]
    return await _render("catalogue.html", {"player": Player(role.uid, role.name, role.server), "products": products})


async def render_order(role: Role, cart: tuple[CartItem, ...], channel: PayChannel, order: Order | None) -> bytes:
    icons = await _icons(i.goods for i in cart)
    lines = [
        LineItem(i.goods.name, i.quantity, i.goods.price_text, f"{i.subtotal:.2f}", icons[i.goods.icon]) for i in cart
    ]
    context: dict[str, ContextValue] = {
        "player": Player(role.uid, role.name, role.server),
        "items": lines,
        "count": str(sum(i.quantity for i in cart)),
        "total": f"{cart_total(cart):.2f}",
        "order_number": order.number if order else "",
        "qr": await asyncio.to_thread(qr_data, order.url if order else OFFICIAL_URL),
        "channel": "微信" if channel == "23" else "支付宝",
        "channel_icon": "wx" if channel == "23" else "ali",
        "disclaimer": DISCLAIMER if order else "",
    }
    return await _render("order.html", context, ordered=order is not None)
