"""UnifiWifiImage platform."""

from __future__ import annotations

import logging, collections, qrcode, io


from homeassistant.components.image import ImageEntity
from homeassistant.const import (
    CONF_ENABLED,
    CONF_NAME,
    CONF_PASSWORD,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import IntegrationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify
from typing import List # required for type hinting (function annotation)
from .const import (
    DOMAIN,
    CONF_BACK_COLOR,
    CONF_COORDINATOR,
    CONF_FILL_COLOR,
    CONF_HIDE_SSID,
    CONF_MONITORED_SSIDS,
    CONF_NETWORK_NAME,
    CONF_PPSK,
    CONF_PRESHARED_KEYS,
    CONF_QRTEXT,
    CONF_SITE,
    CONF_SSID,
    CONF_TIMESTAMP,
    CONF_WPA3_SUPPORT,
    CONF_WPA3_TRANSITION,
    UNIFI_ID,
    UNIFI_NAME,
    UNIFI_NETWORKCONF_ID,
    UNIFI_PASSPHRASE,
    UNIFI_PASSWORD,
    UNIFI_PRESHARED_KEYS
)
from .coordinator import UnifiWifiCoordinator

EXTRA_DEBUG = False

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

            # check if preshared keys are configured for the current SSID
            keys = []
            for y in x.wlanconf:
                if y[UNIFI_NAME] == wlan[CONF_NAME]:
                    try:
                        keys = y[UNIFI_PRESHARED_KEYS]
                    except:
                        break

            if keys:
                if wlan[CONF_PRESHARED_KEYS]: # create image entities for SPECIFIC private pre-shared keys
                    for ppsk in wlan[CONF_PRESHARED_KEYS]:
                        try:
                            # find network_id in networkconf
                            idpresharedkey = [network[UNIFI_NAME] for network in x.networkconf].index(ppsk[CONF_NAME])
                            idnetwork = x.networkconf[idpresharedkey][UNIFI_ID]
                            if EXTRA_DEBUG: _LOGGER.debug("ppsk %s found at index %i with id %s in networkconf on coordinator %s", ppsk[CONF_NAME], idpresharedkey, idnetwork, conf[CONF_NAME])

                            # find [network_id, password] dictionary in private pre-shared keys
                            idkey = [k[UNIFI_NETWORKCONF_ID] for k in keys].index(idnetwork)
                            key = keys[idkey]
                            if EXTRA_DEBUG: _LOGGER.debug("ppsk %s found with entry %s in wlanconf on coordinator %s", ppsk[CONF_NAME], key, conf[CONF_NAME])

                            entities.append(UnifiWifiImage(hass, x, wlan[CONF_NAME], ppsk[CONF_FILL_COLOR], ppsk[CONF_BACK_COLOR], key))
                        except ValueError as err:
                            raise IntegrationError(f"ppsk {ppsk[CONF_NAME]} not found under SSID {wlan[CONF_NAME]} on coordinator {x.name}: {err}")
                else:
                    for key in keys: # create image entities for ALL private pre-shared keys
                        entities.append(UnifiWifiImage(hass, x, wlan[CONF_NAME], wlan[CONF_FILL_COLOR], wlan[CONF_BACK_COLOR], key))
                        idnetwork = [network[UNIFI_ID] for network in x.networkconf].index(key[UNIFI_NETWORKCONF_ID])
                        _LOGGER.debug("Setting up image for SSID (ppsk) %s (%s) on coordinator %s", wlan[CONF_NAME], x.networkconf[idnetwork][UNIFI_NAME], conf[CONF_NAME])
            else:
                entities.append(UnifiWifiImage(hass, x, wlan[CONF_NAME], wlan[CONF_FILL_COLOR], wlan[CONF_BACK_COLOR]))
                _LOGGER.debug("Setting up image for SSID %s on coordinator %s", wlan[CONF_NAME], conf[CONF_NAME])

    async_add_entities(entities)


class UnifiWifiImage(CoordinatorEntity, ImageEntity, RestoreEntity):
    """Representation of a Unifi Wifi image."""

    def __init__(self, hass: HomeAssistant, coordinator: UnifiWifiCoordinator, ssid: str, fill_color: str, back_color: str, key: dict = {}):
        """Initialize the image."""
        super().__init__(coordinator)

        idssid = self._ssid_index(ssid)

        if EXTRA_DEBUG:
            if bool(key):
                idnetwork = [x[UNIFI_ID] for x in self.coordinator.networkconf].index(key[UNIFI_NETWORKCONF_ID])
                name = slugify(f"{self.coordinator.name} {ssid} {self.coordinator.networkconf[idnetwork][UNIFI_NAME]} wifi")
            else:
                name = slugify(f"{self.coordinator.name} {ssid} wifi")
            _LOGGER.debug("wlanconf for image.%s: [%s]", name, self.coordinator.wlanconf[idssid])

        dt = dt_util.utcnow()
        self._attributes = {
            CONF_ENABLED: self.coordinator.wlanconf[idssid][CONF_ENABLED],
            CONF_HIDE_SSID: self.coordinator.wlanconf[idssid][CONF_HIDE_SSID],
            CONF_COORDINATOR: self.coordinator.name,
            CONF_SITE: self.coordinator.site,
            CONF_SSID: ssid,
            UNIFI_ID: self.coordinator.wlanconf[idssid][UNIFI_ID],
            CONF_TIMESTAMP: int(dt_util.utc_to_timestamp(dt)),
            CONF_BACK_COLOR: back_color,
            CONF_FILL_COLOR: fill_color,
            CONF_WPA3_SUPPORT: self.coordinator.wlanconf[idssid][CONF_WPA3_SUPPORT],
            CONF_WPA3_TRANSITION: self.coordinator.wlanconf[idssid][CONF_WPA3_TRANSITION]
        }

        if bool(key):
            self._attributes[CONF_PASSWORD] = key[UNIFI_PASSWORD]
            self._attributes[UNIFI_NETWORKCONF_ID] = key[UNIFI_NETWORKCONF_ID]
            idnetwork = [x[UNIFI_ID] for x in self.coordinator.networkconf].index(key[UNIFI_NETWORKCONF_ID])
            self._attributes[CONF_NETWORK_NAME] = self.coordinator.networkconf[idnetwork][UNIFI_NAME]
            self._attr_name = f"{self._attributes[CONF_COORDINATOR]} {ssid} {self._attributes[CONF_NETWORK_NAME]} wifi"
        else:
            self._attributes[CONF_PASSWORD] = self.coordinator.wlanconf[idssid][UNIFI_PASSPHRASE]
            self._attr_name = f"{self._attributes[CONF_COORDINATOR]} {ssid} wifi"

        self._attributes[CONF_PPSK] = bool(key)
        self._attr_unique_id = slugify(f"{DOMAIN}_{self._attr_name}_image")
        self._attr_content_type: str = "image/png"
        self._attr_image_last_updated = dt

        self._create_qr()

        verify_ssl = self.coordinator.verify_ssl
        if verify_ssl:
            self._attr_image_url = f"https://127.0.0.1:8123/local/{slugify(self._attr_name)}_qr.png"
        else:
            self._attr_image_url = f"http://127.0.0.1:8123/local/{slugify(self._attr_name)}_qr.png"

        self._client = get_async_client(hass, verify_ssl=verify_ssl)
        self.access_tokens: collections.deque = collections.deque([], 2)
        self.async_update_token()

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def name(self):
        """Name of the entity."""
        return self._attr_name

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_data()

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator.async_request_refresh()

    async def async_image(self) -> bytes | None:
        """Return bytes of image.
        
        Needed for frontend cache to refresh correctly.
        """
        return self._code_bytes

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/update_coordinator.py#L419
        self.async_on_remove(
            self.coordinator.async_add_listener(
                self._handle_coordinator_update, self.coordinator_context
            )
        )

        # Restore last state -- can't find the source link
        _LOGGER.debug("Trying to restore: %s", self._attr_name)
        if (
            last_state := await self.async_get_last_state()
        ) and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            #self._state = last_state.state
            # restore self._attr_image_last_updated since image uses it for the state
            #   and must be set to a datetime object
            self._attr_image_last_updated = dt_util.parse_datetime(last_state.state)

            for attr in [
                # CONF_ENABLED,
                # CONF_HIDE_SSID,
                # CONF_COORDINATOR,
                # CONF_SITE,
                # CONF_SSID,
                # CONF_PPSK,
                # UNIFI_ID,
                # CONF_PASSWORD,
                # CONF_QRTEXT, 
                CONF_TIMESTAMP,
                # UNIFI_NETWORKCONF_ID,
                # CONF_NETWORK_NAME
            ]:
                if attr in last_state.attributes:
                    self._attributes[attr] = last_state.attributes[attr]

            _LOGGER.debug("Restored: %s", self._attr_name)
        else:
            _LOGGER.debug("Unable to restore: %s", self._attr_name)

    def _hex_to_rgb(self, value: str):
        """return an RGB tuple of a hex color."""
        # https://stackoverflow.com/questions/29643352/converting-hex-to-rgb-value-in-python
        value = value.lstrip('#')
        return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))

    def _create_qr(self) -> None:
        """Create a QR code and save it as a PNG."""
        if self._attributes[CONF_WPA3_SUPPORT] and not self._attributes[CONF_WPA3_TRANSITION]:
            # add the WPA2/WPA3 transition mode disable flag
            # not sure if this is actually necessary
            qrtext = f"WIFI:T:WPA;R:1;S:{self._attributes[CONF_SSID]};P:{self._attributes[CONF_PASSWORD]};;"
        else:
            qrtext = f"WIFI:T:WPA;S:{self._attributes[CONF_SSID]};P:{self._attributes[CONF_PASSWORD]};;"

        self._attributes[CONF_QRTEXT] = qrtext

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=16,
            border=2
        )
        qr.add_data(qrtext)
        qr.make(fit=True)
        img = qr.make_image(back_color=self._hex_to_rgb(self._attributes[CONF_BACK_COLOR]), fill_color=self._hex_to_rgb(self._attributes[CONF_FILL_COLOR]))

        # generate QR code file
        path = f"/config/www/{slugify(self._attr_name)}_qr.png"
        img.save(path)

        # generate QR code byte string needed for the frontend
        x = io.BytesIO()
        img.save(x)
        self._code_bytes = x.getvalue()

    def _ssid_index(self, ssid: str) -> int:
        """Find the array index of a specific ssid in wlanconf."""
        try:
            return [x[UNIFI_NAME] for x in self.coordinator.wlanconf].index(ssid)
        except ValueError as err:
            raise IntegrationError(f"SSID {ssid} not found on coordinator {self.coordinator.name}: {err}")

    def _network_index(self, network_id: str) -> int:
        """Find the array index of a specific network in wlanconf."""
        try:
            idssid = self._ssid_index(self._attributes[CONF_SSID])
            return [x[UNIFI_NETWORKCONF_ID] for x in self.coordinator.wlanconf[idssid][UNIFI_PRESHARED_KEYS]].index(network_id)
        except ValueError as err:
            raise IntegrationError(f"Network {network_id} not found on coordinator {self.coordinator.name}: {err}")

    def _update_data(self) -> None:
        """Update state and attributes when changes are detected."""
        idssid = self._ssid_index(self._attributes[CONF_SSID])
        enabled_state = self.coordinator.wlanconf[idssid][CONF_ENABLED]
        hide_state = self.coordinator.wlanconf[idssid][CONF_HIDE_SSID]
        if self._attributes[CONF_PPSK]:
            idnetwork = self._network_index(self._attributes[UNIFI_NETWORKCONF_ID])
            new_password = self.coordinator.wlanconf[idssid][UNIFI_PRESHARED_KEYS][idnetwork][UNIFI_PASSWORD]
        else:
            new_password = self.coordinator.wlanconf[idssid][UNIFI_PASSPHRASE]

        enabled_change = bool(self._attributes[CONF_ENABLED] != enabled_state)
        hide_change = bool(self._attributes[CONF_HIDE_SSID] != hide_state)
        password_change = bool(self._attributes[CONF_PASSWORD] != new_password)

        if not (enabled_change or hide_change or password_change):
            return

        self._attributes[UNIFI_ID] = self.coordinator.wlanconf[idssid][UNIFI_ID]
        self._attributes[CONF_ENABLED] = enabled_state
        self._attributes[CONF_HIDE_SSID] = hide_state
        self._attributes[CONF_PASSWORD] = new_password
        self._attributes[CONF_QRTEXT] = f"WIFI:T:WPA;S:{self._attributes[CONF_SSID]};P:{self._attributes[CONF_PASSWORD]};;"

        if enabled_change:
            _LOGGER.debug("SSID %s on coordinator %s is now %s", self._attributes[CONF_SSID], self._attributes[CONF_COORDINATOR], 'enabled' if bool(self._attributes[CONF_ENABLED]) else 'disabled')

        if hide_change:
            _LOGGER.debug("SSID %s on coordinator %s is now %s", self._attributes[CONF_SSID], self._attributes[CONF_COORDINATOR], 'hidden' if bool(self._attributes[CONF_HIDE_SSID]) else 'broadcasting')

        if password_change:
            dt = dt_util.utcnow()
            self._attributes[CONF_TIMESTAMP] = int(dt_util.utc_to_timestamp(dt))
            self._attr_image_last_updated = dt

            self._create_qr()

            if self._attributes[CONF_PPSK]:
                _LOGGER.debug("SSID (ppsk) %s (%s) on coordinator %s has a new password", self._attributes[CONF_SSID], self._attributes[CONF_NETWORK_NAME], self._attributes[CONF_COORDINATOR])
            else:
                _LOGGER.debug("SSID %s on coordinator %s has a new password", self._attributes[CONF_SSID], self._attributes[CONF_COORDINATOR])

        self.async_write_ha_state()