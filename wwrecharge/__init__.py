import time
import asyncio
from dataclasses import field, dataclass

import httpx
from pydantic import ValidationError

from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event

from .api import Cashier
from .state import RechargeState
from .config import enabled, cooldown, default_channel
from .models import OFFICIAL_ADVICE, Role, Order, RechargeError, cart_total
from .parser import payment, parse_cart, validate_cart
from .render import render_order, render_catalogue

sv_recharge = SV("充值", priority=5)
_state = RechargeState()
_watchers: set[asyncio.Task[None]] = set()


@dataclass(frozen=True)
class Credential:
    uid: str
    cookie: str = field(repr=False)
    did: str = field(repr=False)


async def _credential(ev: Event) -> Credential:
    from plugins.XutheringWavesUID.XutheringWavesUID.utils.constants import WAVES_GAME_ID
    from plugins.XutheringWavesUID.XutheringWavesUID.utils.database.models import WavesBind, WavesUser

    if ev.at and ev.at != ev.user_id:
        raise RechargeError("充值仅限本人已登录角色，请勿指定其他用户。")
    uid = await WavesBind.get_uid_by_game(ev.user_id, ev.bot_id)
    if not uid:
        raise RechargeError("请先绑定自己的鸣潮特征码并登录库街区。")
    if not uid.isdigit() or int(uid) >= 200000000:
        raise RechargeError("官方充值中心仅支持国服角色。")
    user = await WavesUser.select_waves_user(uid, ev.user_id, ev.bot_id, game_id=WAVES_GAME_ID)
    if user is None or not user.cookie or not user.is_login or user.status == "无效":
        raise RechargeError("需先登录。")
    return Credential(uid, user.cookie, user.did)


async def _watch(bot: Bot, ev: Event, token: str, role: Role, order: Order, summary: str) -> None:
    deadline = time.monotonic() + 600
    async with httpx.AsyncClient(timeout=httpx.Timeout(10, connect=5), follow_redirects=False) as client:
        cashier = Cashier(client, token)
        while time.monotonic() < deadline:
            await asyncio.sleep(3)
            try:
                status = await cashier.order_status(role, order.number)
            except (httpx.HTTPError, ValidationError):
                continue
            except RechargeError as exc:
                logger.warning(f"[ww充值] 订单状态查询中止：{exc}")
                return
            if status == 0:
                logger.info(f"[ww充值] 订单 {order.number} 支付成功")
                await bot.send(f"充值成功\n{summary}\n到账以游戏内为准", at_sender=bool(ev.group_id))
                return
            if status == 2:
                await bot.send(f"订单支付失败或已关闭\n{summary}", at_sender=bool(ev.group_id))
                return


async def _recharge(bot: Bot, ev: Event, credential: Credential) -> None:
    text, channel = payment(ev.text, default_channel())
    async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=8), follow_redirects=False) as client:
        cashier = Cashier(client)
        await cashier.login(credential.cookie, credential.did)
        role = await cashier.role(credential.uid)
        fresh = await cashier.goods(role)
        if not fresh:
            raise RechargeError("该角色当前没有可购买的商品，请使用官方充值中心。")
        owner = (ev.bot_id, ev.user_id)
        if not text:
            image = await render_catalogue(role, fresh)
            _state.remember(owner, credential.uid, fresh)
            await bot.send(image)
            return
        displayed = _state.displayed(owner, credential.uid, fresh)
        cart = validate_cart(parse_cart(text, displayed), fresh, await cashier.limits(role))
        order = None
        if enabled():
            _state.reserve_order(credential.uid, cooldown())
            order = await cashier.create_order(role, cart, channel)
    image = await render_order(role, cart, channel, order)
    if order is None:
        await bot.send(image)
        return
    items = "、".join(f"{item.goods.name} ×{item.quantity}" for item in cart)
    summary = f"{role.name} · UID {role.uid}\n{items}\n合计 ¥{cart_total(cart):.2f}"
    await bot.send(f"{summary}（{'微信' if channel == '23' else '支付宝'}）\n{OFFICIAL_ADVICE}")
    await bot.send(image)
    task = asyncio.create_task(_watch(bot, ev, cashier.token, role, order, summary))
    _watchers.add(task)
    task.add_done_callback(_watchers.discard)


@sv_recharge.on_command(("充值", "充钱", "储值", "重置"), block=True)
async def cmd_ww_recharge(bot: Bot, ev: Event) -> None:
    try:
        credential = await _credential(ev)
        lock = _state.lock(credential.uid)
        if lock.locked():
            await bot.send("该角色的充值请求正在处理中，请稍候。")
            return
        async with lock:
            await _recharge(bot, ev, credential)
    except RechargeError as exc:
        await bot.send(f"{exc}\n{OFFICIAL_ADVICE}")
    except (httpx.HTTPError, ValidationError) as exc:
        logger.warning(f"[ww充值] 官方接口请求失败：{type(exc).__name__}")
        await bot.send(f"官方充值中心请求失败或返回数据异常，请稍后再试。\n{OFFICIAL_ADVICE}")
