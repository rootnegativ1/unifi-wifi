"""UnifiWifiController and UnifiWifiImage classes."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from .const import (
    DOMAIN,
    CONF_CONTROLLER_NAME,
    CONF_MONITORED_SSIDS,
    CONF_SITE
)
from . import unifi

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    coordinators,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Unifi Wifi image platform."""

    entities = []
    for conf in hass.data[DOMAIN]:
        for x in coordinators:
            if conf[CONF_CONTROLLER_NAME] == x.controller_name:
                await x.async_refresh()
                for wlan in conf[CONF_MONITORED_SSIDS]:
                    entities.append(unifi.UnifiWifiImage(hass, x, wlan[CONF_NAME]))
                    _LOGGER.debug("Setting up image for SSID %s on controller %s", wlan[CONF_NAME], x.controller_name)

    async_add_entities(entities)