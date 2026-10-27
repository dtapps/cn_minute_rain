"""Constants for cn_minute_rain."""

from __future__ import annotations

DOMAIN = "cn_minute_rain"
PLATFORMS = ["sensor"]

CONF_NAME = "name"
CONF_LONGITUDE = "longitude"
CONF_LATITUDE = "latitude"
CONF_SCAN_INTERVAL = "scan_interval"

API_URL = "https://mpf.weather.com.cn/mpf_v3/webgis/minute"

# 更新频率默认值（分钟）；可在添加/选项流程里自定义
DEFAULT_SCAN_INTERVAL_MINUTES = 5

# 单次接口请求的超时（秒）。抽成常量是为了让超时行为可被测试注入。
REQUEST_TIMEOUT_SECONDS = 10

# 分钟级降水预报覆盖的时长（分钟），用于把离散强度点折算成“多少分钟后下雨”
PRECIP_WINDOW_MINUTES = 120
