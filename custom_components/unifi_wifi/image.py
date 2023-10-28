"""UnifiWifiImage platform."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from typing import List # required for type hinting (function annotation)
from .const import (
    DOMAIN,
    CONF_MONITORED_SSIDS
)
from .unifi import UnifiWifiCoordinator, UnifiWifiImage

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    coordinators: List[UnifiWifiCoordinator],
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Unifi Wifi image platform."""

    entities = []

    for idconf, conf in enumerate(hass.data[DOMAIN]):
        x = coordinators[idconf]
        await x.async_refresh()
        for wlan in conf[CONF_MONITORED_SSIDS]:
            entities.append(UnifiWifiImage(hass, x, wlan[CONF_NAME]))
            _LOGGER.debug("Setting up image for SSID %s on coordinator %s", wlan[CONF_NAME], conf[CONF_NAME])

    async_add_entities(entities)