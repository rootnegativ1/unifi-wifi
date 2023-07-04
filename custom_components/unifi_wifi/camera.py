"""Platform for Local File camera integration."""

from __future__ import annotations

import logging
import mimetypes
import os

from homeassistant.components.local_file.camera import LocalFile
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify
from . import (
    DOMAIN,
    CONF_MONITORED_NETWORKS,
    CONF_SSID
    )

WWW_PATH = '/config/www'

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
    configured_networks = hass.data[DOMAIN][CONF_MONITORED_NETWORKS]
    entities = []
    for i in configured_networks:
        ind = address[i[CONF_SSID]]
        ssid = configured_networks[ind][CONF_SSID]
        
        name = f"{ssid} wifi"
        file_path = f"{WWW_PATH}/{ssid}_wifi_qr.png"
        
        entity = LocalFile(name, file_path)
        entity._attr_unique_id = slugify(f"{DOMAIN}_{ssid}_camera")
        
        _LOGGER.debug("Setting up camera for ssid: %s", ssid)
        entities.append(entity)

    add_entities(entities)