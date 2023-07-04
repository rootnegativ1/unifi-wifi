"""Platform for Unifi Wifi binary sensor integration."""
from __future__ import annotations

import logging

from datetime import datetime
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    CONF_ADDRESS,
    CONF_PASSWORD,
    CONF_ENABLED
    )
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify
from . import (
    DOMAIN,
    CONF_SSID,
    CONF_MONITORED_NETWORKS,
    CONF_UNIFIID
)

_LOGGER = logging.getLogger(__name__)

def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    """Set up the Unifi Wifi binary sensor platform."""
    if discovery_info is None:
        return

    address = hass.data[DOMAIN][CONF_ADDRESS]
    configured_networks = hass.data[DOMAIN][CONF_MONITORED_NETWORKS]
    entities = []
    for i in configured_networks:
        ind = address[i[CONF_SSID]]
        entity = UnifiWifiBinarySensor(
            hass,
            ind,
            configured_networks[ind][CONF_ENABLED],
            configured_networks[ind][CONF_SSID],
            configured_networks[ind][CONF_UNIFIID],
            configured_networks[ind][CONF_PASSWORD]
        )
        entities.append(entity)

    add_entities(entities)

class UnifiWifiBinarySensor(BinarySensorEntity, RestoreEntity):
    """Representation of a Unifi Wifi binary sensor."""

    def __init__(self, hass, _index, _state, _ssid, _unifi_id, _password):
        """Initialize the binary_sensor."""
        self._index = _index
        self._state = _state
        self._name = f"{_ssid} wifi"
        self._attr_unique_id = slugify(f"{DOMAIN}_{self._name}")
        self._attr_has_entity_name = True
        self._attributes = {
            "ssid": _ssid,
            "unifi_id": _unifi_id,
            "password": _password,
            "qr_text": f"WIFI:T:WPA;S:{_ssid};P:{_password};;",
            "timestamp": int(datetime.now().timestamp())
        }
        _LOGGER.debug("Setting up binary sensor for ssid: %s", _ssid)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def name(self):
        """Name of the entity."""
        return self._name

    @property
    def icon(self) -> str | None:
        """Icon of the entity."""
        if self._state:
            return "mdi:wifi"
        else:
            return "mdi:wifi-off"

    @property
    def is_on(self):
        """Return true if binary sensor is on."""
        return self._state

    # @property
    # def device_class(self):
        # """Return the class of this binary sensor, from DEVICE_CLASSES."""
        # return self._attr_device_class

    async def async_added_to_hass(self) -> None:
        """Restore last state"""
        _LOGGER.debug("Trying to restore: %s", self._name)
        await super().async_added_to_hass()
        if (
            last_state := await self.async_get_last_state()
        ) and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self._state = last_state.state
            for attr in ["ssid", "unifi_id", "password", "qr_text", "timestamp"]:
                if attr in last_state.attributes:
                    self._attributes[attr] = last_state.attributes[attr]
            _LOGGER.debug("Restored: %s", self._name)
        else:
            _LOGGER.debug("Unable to restore: %s", self._name)

    def update(self) -> None:
        """Fetch new state data for the sensor."""
        #This is the only method that should fetch new data for Home Assistant.
        self._state = self.hass.data[DOMAIN][CONF_MONITORED_NETWORKS][self._index]["enabled"]
        password = self.hass.data[DOMAIN][CONF_MONITORED_NETWORKS][self._index][CONF_PASSWORD]
        if password != self._attributes["password"]:
            self._attributes["password"] = password
            self._attributes["qr_text"] = f"WIFI:T:WPA;S:{self._attributes['ssid']};P:{password};;"
            self._attributes["timestamp"] = int(datetime.now().timestamp())