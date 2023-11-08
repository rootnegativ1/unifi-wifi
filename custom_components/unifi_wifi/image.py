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
    CONF_MONITORED_SSIDS,
    UNIFI_ID,
    UNIFI_NAME,
    UNIFI_NETWORKCONF_ID,
    UNIFI_PRESHARED_KEYS
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
            # check if private pre-shared keys are configured
            keys = []
            # ppsk = False
            for y in x.wlanconf:
                if y[UNIFI_NAME] == wlan[CONF_NAME]:
                    try:
                        keys = y[UNIFI_PRESHARED_KEYS]
                        # ppsk = True
                        break
                    except:
                        break

            if keys:
                for k in keys:
                    entities.append(UnifiWifiImage(hass, x, wlan[CONF_NAME], k))
                    idnetwork = [network[UNIFI_ID] for network in x.networkconf].index(k[UNIFI_NETWORKCONF_ID])
                    _LOGGER.debug("Setting up image for SSID (ppsk) %s (%s) on coordinator %s", wlan[CONF_NAME], x.networkconf[idnetwork][UNIFI_NAME], conf[CONF_NAME])
            else:
                entities.append(UnifiWifiImage(hass, x, wlan[CONF_NAME]))
                _LOGGER.debug("Setting up image for SSID %s on coordinator %s", wlan[CONF_NAME], conf[CONF_NAME])

    async_add_entities(entities)