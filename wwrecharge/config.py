from gsuid_core.data_store import get_res_path
from gsuid_core.utils.plugins_config.models import GSC, GsIntConfig, GsStrConfig, GsBoolConfig
from gsuid_core.utils.plugins_config.gs_config import StringConfig

from .models import PayChannel, RechargeError

CONFIG_PATH = get_res_path("XWUIDCollection") / "recharge.json"

CONFIG_DEFAULT: dict[str, GSC] = {
    "RechargeEnable": GsBoolConfig(
        "允许下单（开启后自行负责）",
        "关闭时仅展示商品与订单预览，不创建订单、不显示支付二维码。开启后会向官方创建订单并发送支付二维码，涉及真实支付，开启后自行负责",
        False,
    ),
    "RechargeCooldown": GsIntConfig(
        "下单冷却(秒)",
        "同一用户两次下单的最小间隔",
        30,
        max_value=3600,
    ),
    "RechargePayChannel": GsStrConfig(
        "默认扫码方式",
        "用户也可在充值指令后加微信或支付宝",
        "微信",
        options=["微信", "支付宝"],
    ),
}

RechargeConfig = StringConfig("XWUIDCollectionRecharge", CONFIG_PATH, CONFIG_DEFAULT)


def enabled() -> bool:
    setting: object = RechargeConfig.get_config("RechargeEnable")
    if not isinstance(setting, GsBoolConfig):
        raise RechargeError("充值开关配置类型错误，请联系管理员。")
    return setting.data


def cooldown() -> int:
    setting: object = RechargeConfig.get_config("RechargeCooldown")
    if not isinstance(setting, GsIntConfig):
        raise RechargeError("充值冷却配置类型错误，请联系管理员。")
    return max(0, min(3600, setting.data))


def default_channel() -> PayChannel:
    setting: object = RechargeConfig.get_config("RechargePayChannel")
    if not isinstance(setting, GsStrConfig) or setting.data not in {"微信", "支付宝"}:
        raise RechargeError("充值扫码方式配置错误，请联系管理员。")
    return "24" if setting.data == "支付宝" else "23"
