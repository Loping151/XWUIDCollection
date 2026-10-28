from gsuid_core.data_store import get_res_path
from gsuid_core.utils.plugins_config.models import GSC, GsIntConfig, GsBoolConfig, GsFloatConfig
from gsuid_core.utils.plugins_config.gs_config import StringConfig

from .gacha import Rules

CONFIG_PATH = get_res_path("XWUIDCollection") / "tappo.json"
RATE_KEYS = ("TappoRateCommon", "TappoRateUncommon", "TappoRateRare", "TappoRateEpic")

CONFIG_DEFAULT: dict[str, GSC] = {
    "TappoDailyDraws": GsIntConfig("每日开箱上限", "每人每天最多开箱次数，0 点重置", 100, max_value=10000),
    "TappoRateCommon": GsFloatConfig("普通概率(%)", "官方 90", 90.0, min_value=0, max_value=100),
    "TappoRateUncommon": GsFloatConfig("珍稀概率(%)", "官方 9.5", 9.5, min_value=0, max_value=100),
    "TappoRateRare": GsFloatConfig("稀有概率(%)", "官方 0.49", 0.49, min_value=0, max_value=100),
    "TappoRateEpic": GsFloatConfig("史诗概率(%)", "官方 0.01", 0.01, min_value=0, max_value=100),
    "TappoPity": GsIntConfig(
        "史诗保底抽数", "连续这么多抽未出史诗则必出，0 为不保底（官方无保底）", 0, max_value=10000
    ),
    "TappoTenFloor": GsBoolConfig("十连保底珍稀", "每个十连的第 10 抽至少珍稀（官方无）", False),
}

TappoConfig = StringConfig("XWUIDCollectionTappo", CONFIG_PATH, CONFIG_DEFAULT)


def daily_draws() -> int:
    return max(1, int(TappoConfig.get_config("TappoDailyDraws").data))


def rules() -> Rules:
    rates = tuple(max(0.0, float(TappoConfig.get_config(key).data)) for key in RATE_KEYS)
    return Rules(
        rates if sum(rates) > 0 else Rules().rates,
        max(0, int(TappoConfig.get_config("TappoPity").data)),
        bool(TappoConfig.get_config("TappoTenFloor").data),
    )
