"""Platform for Local File camera integration."""
from __future__ import annotations

import logging
#import mimetypes
import os

#from homeassistant.components.camera import Camera
from homeassistant.components.local_file.camera import LocalFile
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from . import (
    DOMAIN,
    CONF_NETWORKS,
    CONF_SSID
    )

_LOGGER = logging.getLogger(__name__)

def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Local File camera platform."""
    if discovery_info is None:
        return

    address = hass.data[DOMAIN][CONF_ADDRESS]
    configured_networks = hass.data[DOMAIN][CONF_NETWORKS]
    cameras = []
    for network in configured_networks:
        ind = address[network[CONF_SSID]]
        ssid = configured_networks[ind][CONF_SSID]
        name = f"{ssid} wifi"
        file_path = f"/config/www/{ssid}_wifi_qr.png"
        camera = LocalFile(name, file_path)
        _LOGGER.debug("Setting up camera for ssid: %s", ssid)
        cameras.append(camera)

    add_entities(cameras)
