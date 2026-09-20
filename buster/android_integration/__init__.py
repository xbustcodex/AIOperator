"""Android/Termux integration for Buster OS."""

from buster.android_integration.device import (
    DeviceInfo,
    device_info,
    is_termux,
)

__all__ = ["DeviceInfo", "device_info", "is_termux"]