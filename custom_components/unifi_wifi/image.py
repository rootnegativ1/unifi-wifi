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
    CONF_COORDINATOR,
    CONF_MONITORED_SSIDS,
    CONF_NETWORK_NAME,
    CONF_PPSK,
    CONF_QRTEXT,
    CONF_SITE,
    CONF_SSID,
    CONF_TIMESTAMP,
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


class UnifiWifiImage(CoordinatorEntity, ImageEntity, RestoreEntity):
    """Representation of a Unifi Wifi image."""

    def __init__(self, hass: HomeAssistant, coordinator: UnifiWifiCoordinator, ssid: str, key: dict = {}):
        """Initialize the image."""
        super().__init__(coordinator)

        idssid = self._ssid_index(ssid)

        dt = dt_util.utcnow()
        self._attributes = {
            CONF_ENABLED: self.coordinator.wlanconf[idssid][CONF_ENABLED],
            CONF_COORDINATOR: self.coordinator.name,
            CONF_SITE: self.coordinator.site,
            CONF_SSID: ssid,
            UNIFI_ID: self.coordinator.wlanconf[idssid][UNIFI_ID],
            CONF_TIMESTAMP: int(dt_util.utc_to_timestamp(dt))
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
        self._attributes[CONF_QRTEXT] = f"WIFI:T:WPA;S:{ssid};P:{self._attributes[CONF_PASSWORD]};;"
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

    def _create_qr(self) -> None:
        qrtext = f"WIFI:T:WPA;S:{self._attributes[CONF_SSID]};P:{self._attributes[CONF_PASSWORD]};;"

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=16,
            border=2
        )
        qr.add_data(qrtext)
        qr.make(fit=True)
        # fill_color defaults to black and back_color defaults to white
        #   so there's no need to pass them as arguments in make_image() method
        #   https://github.com/lincolnloop/python-qrcode/blob/main/qrcode/image/pil.py#L12
        #   img = qr.make_image(fill_color='black', back_color='white')
        img = qr.make_image()

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
        if self._attributes[CONF_PPSK]:
            idnetwork = self._network_index(self._attributes[UNIFI_NETWORKCONF_ID])
            new_password = self.coordinator.wlanconf[idssid][UNIFI_PRESHARED_KEYS][idnetwork][UNIFI_PASSWORD]
        else:
            new_password = self.coordinator.wlanconf[idssid][UNIFI_PASSPHRASE]

        enabled_change = bool(self._attributes[CONF_ENABLED] != enabled_state)
        password_change = bool(self._attributes[CONF_PASSWORD] != new_password)

        if enabled_change:
            self._attributes[CONF_ENABLED] = enabled_state
            self._attributes[UNIFI_ID] = self.coordinator.wlanconf[idssid][UNIFI_ID]

            _LOGGER.debug("SSID %s on coordinator %s is now %s", self._attributes[CONF_SSID], self._attributes[CONF_COORDINATOR], 'enabled' if bool(self._attributes[CONF_ENABLED]) else 'disabled')

            self.async_write_ha_state()

        if password_change:
            self._attributes[CONF_PASSWORD] = new_password
            self._attributes[UNIFI_ID] = self.coordinator.wlanconf[idssid][UNIFI_ID]
            self._attributes[CONF_QRTEXT] = f"WIFI:T:WPA;S:{self._attributes[CONF_SSID]};P:{self._attributes[CONF_PASSWORD]};;"

            dt = dt_util.utcnow()
            self._attributes[CONF_TIMESTAMP] = int(dt_util.utc_to_timestamp(dt))
            self._attr_image_last_updated = dt

            self._create_qr()

            self.async_write_ha_state()

            if self._attributes[CONF_PPSK]:
                _LOGGER.debug("SSID (ppsk) %s (%s) on coordinator %s has a new password", self._attributes[CONF_SSID], self._attributes[CONF_NETWORK_NAME], self._attributes[CONF_COORDINATOR])
            else:
                _LOGGER.debug("SSID %s on coordinator %s has a new password", self._attributes[CONF_SSID], self._attributes[CONF_COORDINATOR])