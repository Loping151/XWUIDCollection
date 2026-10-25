from typing import Literal
from decimal import Decimal
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

from pydantic import Field, BaseModel, JsonValue, ConfigDict, field_validator

OFFICIAL_URL = "https://pay.kurogames.com/mc/cashier"
DISCLAIMER = "本二维码从官方获得，与本插件无关；请确保信任服务提供者，请勿扫描未知二维码！"
OFFICIAL_ADVICE = f"建议使用官方渠道{OFFICIAL_URL}"
PayChannel = Literal["23", "24"]


class RechargeError(ValueError):
    pass


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, coerce_numbers_to_str=True)


class Envelope(ApiModel):
    code: int
    data: JsonValue = None


class Permit(ApiModel):
    access_token: str = Field(alias="accessToken", min_length=1, repr=False)


class Role(ApiModel):
    uid: str = Field(alias="roleId", min_length=1)
    name: str = Field(alias="roleName", min_length=1)
    server: str = Field(alias="serverName", min_length=1)
    token: str = Field(alias="roleToken", min_length=1, repr=False)


class Goods(ApiModel):
    id: str = Field(alias="goodsId", min_length=1)
    name: str = Field(alias="goodsName", min_length=1)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    currency: Literal["CNY"]
    icon: str = Field(alias="iconUrl")
    status: int
    amount: int = Field(alias="get", ge=0)
    extra: int = Field(alias="extraGet", ge=0)
    privilege: int
    tag: int
    buy_limit: int | None = Field(alias="buyLimit")
    remaining: int | None = Field(alias="canBuyCount")
    discount: str | None = None

    @field_validator("icon")
    @classmethod
    def check_icon(cls, value: str) -> str:
        url = urlsplit(value)
        if (
            url.scheme != "https"
            or url.netloc != "pro-cdn-sdk.kurogame.com"
            or not url.path.startswith("/pro/resource/")
        ):
            raise ValueError("商品图片地址不是官方素材地址")
        return value

    @property
    def price_text(self) -> str:
        return f"{self.price:.2f}"

    @property
    def is_pass(self) -> bool:
        return self.id.rsplit(".", 1)[-1] in {"bp60", "bp68", "bp128"}


class Limits(ApiModel):
    total: int = Field(alias="cartLimitCount", ge=0)
    per_item: int = Field(alias="goodsLimitCount", ge=0)


class PayMethod(ApiModel):
    channel: str = Field(alias="payChannel")
    name: str


class PayMethods(ApiModel):
    methods: list[PayMethod] = Field(alias="payTypeList")


class Order(ApiModel):
    number: str = Field(alias="orderNum", min_length=1)
    url: str = Field(alias="orderUrl", min_length=1, repr=False)
    channel: PayChannel = Field(alias="payChannel")

    def validate_channel(self, requested: PayChannel) -> None:
        url = urlsplit(self.url)
        query = parse_qs(url.query, keep_blank_values=True)
        key = "pr" if self.channel == "23" else "key"
        valid_query = set(query) == {key} and len(query[key]) == 1 and bool(query[key][0])
        valid = (
            self.channel == "23"
            and url.scheme == "weixin"
            and url.netloc == "wxpay"
            and url.path == "/bizpayurl"
            and url.query.startswith("pr=")
        ) or (
            self.channel == "24"
            and url.scheme == "https"
            and url.netloc == "sdkapi.kurogame.com"
            and url.path == "/sdk/trade/page/aliPay"
            and url.query.startswith("key=")
        )
        if self.channel != requested or not valid or not valid_query or url.fragment:
            raise RechargeError("官方订单返回的支付地址异常，请到官方充值中心确认订单。")


class OrderStatus(ApiModel):
    status: int
    number: str = Field(alias="orderNum", min_length=1)


@dataclass(frozen=True)
class CartItem:
    goods: Goods
    quantity: int

    @property
    def subtotal(self) -> Decimal:
        return self.goods.price * self.quantity


def sorted_goods(goods: list[Goods]) -> tuple[Goods, ...]:
    rank = {1: 0, 2: 1, 0: 2}
    return tuple(sorted(goods, key=lambda g: (rank[g.tag] if g.tag in rank else 3, g.price)))


def cart_total(cart: tuple[CartItem, ...]) -> Decimal:
    return sum((item.subtotal for item in cart), Decimal("0"))
