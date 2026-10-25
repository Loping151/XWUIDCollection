import json
from uuid import uuid4

import httpx
from pydantic import JsonValue, TypeAdapter, ValidationError

from .models import (
    Role,
    Goods,
    Order,
    Limits,
    Permit,
    CartItem,
    Envelope,
    PayChannel,
    PayMethods,
    OrderStatus,
    RechargeError,
    sorted_goods,
)

_TRADE = "https://sdkapi.kurogame.com/sdk/trade/webmall"
_PERMIT = "https://api.kurobbs.com/user/account/getPermitAccountParam"
_ROLES = TypeAdapter(list[Role])
_GOODS = TypeAdapter(list[Goods])


class Cashier:
    def __init__(self, client: httpx.AsyncClient, token: str = "") -> None:
        self.client = client
        self._token = token
        self._base: dict[str, str] = {
            "gameId": "G152",
            "pkgId": "A1409",
            "channelId": "21",
            "deviceNum": uuid4().hex,
            "deviceModel": "Chrome",
            "deviceBrand": "Generic",
            "os": "Windows",
            "osVersion": "10",
            "platform": "h5",
            "version": "1.0.0",
            "source": "pc",
        }

    async def login(self, cookie: str, did: str) -> None:
        headers = {
            "token": cookie,
            "devCode": did or self._base["deviceNum"],
            "source": "android",
            "version": "3.0.1",
            "versionCode": "30001",
            "lang": "zh-Hans",
            "countryCode": "CN",
            "channelId": "2",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "okhttp/3.11.0",
        }
        response = await self.client.post(_PERMIT, headers=headers, content=b"")
        response.raise_for_status()
        body = Envelope.model_validate_json(response.content)
        if body.code != 200:
            raise RechargeError("库街区登录已失效或授权失败，请重新登录后再试。")
        self._token = Permit.model_validate(body.data).access_token

    @property
    def token(self) -> str:
        return self._token

    async def _call(self, path: str, role: Role | None = None, **extra: str) -> JsonValue:
        body = dict(self._base)
        if role is not None:
            body["roleToken"] = role.token
        body.update(extra)
        response = await self.client.post(f"{_TRADE}/{path}.lg", headers={"KURO-ACCESS-TOKEN": self._token}, json=body)
        response.raise_for_status()
        result = Envelope.model_validate_json(response.content)
        if result.code == 401:
            raise RechargeError("官方充值中心登录已失效，请重新登录库街区后再试。")
        if result.code != 0:
            raise RechargeError(f"官方充值中心拒绝请求（错误码 {result.code}），请到官方渠道确认。")
        return result.data

    async def role(self, uid: str) -> Role:
        roles = _ROLES.validate_python(await self._call("v1/rolelist"))
        matches = [role for role in roles if role.uid == uid]
        if len(matches) != 1:
            raise RechargeError("当前登录账号没有该特征码的角色，请确认绑定与登录账号。")
        return matches[0]

    async def goods(self, role: Role) -> tuple[Goods, ...]:
        result = _GOODS.validate_python(await self._call("v1/goodlist", role))
        if len({g.id for g in result}) != len(result):
            raise RechargeError("官方商品列表存在重复项目，请稍后再试。")
        return sorted_goods(result)

    async def limits(self, role: Role) -> Limits:
        return Limits.model_validate(await self._call("v1/goods-limit", role))

    async def create_order(self, role: Role, cart: tuple[CartItem, ...], channel: PayChannel) -> Order:
        encoded = json.dumps(
            [{"goodsId": item.goods.id, "quantity": item.quantity} for item in cart], separators=(",", ":")
        )
        methods = PayMethods.model_validate(await self._call("v2/paytype", role, cartItemJson=encoded))
        if not any(method.channel == channel for method in methods.methods):
            raise RechargeError("该购物车暂不支持所选支付方式，请切换微信或支付宝。")
        try:
            data = await self._call(
                "v1/order/cart/create",
                role,
                cartItemJson=encoded,
                payChannel=channel,
                isLastPurchase="0",
                payChannelDiscountToken="",
            )
            order = Order.model_validate(data)
        except (httpx.HTTPError, ValidationError) as exc:
            raise RechargeError("下单结果未知，请到官方充值中心确认，勿立即重复下单。") from exc
        order.validate_channel(channel)
        return order

    async def order_status(self, role: Role, number: str) -> int:
        result = OrderStatus.model_validate(await self._call("v1/order/query", role, orderNum=number))
        if result.number != number:
            raise RechargeError("官方订单查询结果与订单号不一致。")
        return result.status
