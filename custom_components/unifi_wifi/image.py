"""Platform for Unifi Wifi image integration."""

from __future__ import annotations

import logging
import mimetypes
import os

from homeassistant.components.image import ImageEntity
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util, slugify
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
    """Set up the Unifi Wifi image platform."""
    if discovery_info is None:
        return

    address = hass.data[DOMAIN][CONF_ADDRESS]
    configured_networks = hass.data[DOMAIN][CONF_MONITORED_NETWORKS]
    entities = []
    for i in configured_networks:
        ind = address[i[CONF_SSID]]
        ssid = configured_networks[ind][CONF_SSID]
        
        # make this dependent upon ssl stuff
        # use an If statement
        url_path = f"http://127.0.0.1:8123/local/{ssid}_wifi_qr.png"
        
        entity = ImageEntity(hass)
        entity._attr_name = f"{ssid} wifi"
        entity._attr_unique_id = slugify(f"{DOMAIN}_{ssid}_image")
        entity._attr_image_url = url_path
        entity._attr_image_last_updated = dt_util.utcnow()
        
        _LOGGER.debug("Setting up image for ssid: %s", ssid)
        entities.append(entity)

    add_entities(entities)