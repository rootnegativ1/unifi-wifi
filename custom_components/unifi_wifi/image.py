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
from homeassistant.util.dt import parse_datetime, utcnow
from homeassistant.util import slugify
from .const import (
    DOMAIN,
    CONF_BACK_COLOR,
    CONF_COORDINATOR,
    CONF_FILE_OUTPUT,
    CONF_FILL_COLOR,
    CONF_HIDE_SSID,
    CONF_MONITORED_SSIDS,
    CONF_NETWORK_NAME,
    CONF_PPSK,
    CONF_PRESHARED_KEYS,
    CONF_QR_QUALITY,
    CONF_QR_TEXT,
    CONF_SITE,
    CONF_SSID,
    CONF_TIMESTAMP,
    CONF_WPA_MODE,
    UNIFI_HIDE_SSID,
    UNIFI_ID,
    UNIFI_NAME,
    UNIFI_NETWORKCONF_ID,
    UNIFI_X_PASSPHRASE,
    UNIFI_PASSWORD,
    UNIFI_PRESHARED_KEYS,
    UNIFI_WPA3_SUPPORT,
    UNIFI_WPA3_TRANSITION
)
from .coordinator import UnifiWifiCoordinator

EXTRA_DEBUG = False

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    coordinators: list[UnifiWifiCoordinator],
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
                            network_id = x.networkconf[idpresharedkey][UNIFI_ID]
                            if EXTRA_DEBUG: _LOGGER.debug("ppsk %s found at index %i with id %s in networkconf on coordinator %s", ppsk[CONF_NAME], idpresharedkey, network_id, conf[CONF_NAME])

                            # find [network_id, password] dictionary in private pre-shared keys
                            idkey = [k[UNIFI_NETWORKCONF_ID] for k in keys].index(network_id)
                            key = keys[idkey]
                            if EXTRA_DEBUG: _LOGGER.debug("ppsk %s found with entry %s in wlanconf on coordinator %s", ppsk[CONF_NAME], key, conf[CONF_NAME])

                            image = UnifiWifiImage(hass, x, wlan[CONF_NAME], ppsk[CONF_FILL_COLOR], ppsk[CONF_BACK_COLOR], ppsk[CONF_FILE_OUTPUT], ppsk[CONF_QR_QUALITY], key = key)
                            entities.append(image)
                            i = [network[UNIFI_ID] for network in x.networkconf].index(key[UNIFI_NETWORKCONF_ID])
                            _LOGGER.debug("Setting up image for SSID (ppsk) %s (%s) on coordinator %s", wlan[CONF_NAME], x.networkconf[i][UNIFI_NAME], conf[CONF_NAME])
                        except ValueError as err:
                            raise IntegrationError(f"ppsk {ppsk[CONF_NAME]} not found under SSID {wlan[CONF_NAME]} on coordinator {x.name}: {err}")
                else: # create image entities for ALL private pre-shared keys
                    for key in keys:
                        image = UnifiWifiImage(hass, x, wlan[CONF_NAME], wlan[CONF_FILL_COLOR], wlan[CONF_BACK_COLOR], wlan[CONF_FILE_OUTPUT], wlan[CONF_QR_QUALITY], key = key)
                        entities.append(image)
                        i = [network[UNIFI_ID] for network in x.networkconf].index(key[UNIFI_NETWORKCONF_ID])
                        _LOGGER.debug("Setting up image for SSID (ppsk) %s (%s) on coordinator %s", wlan[CONF_NAME], x.networkconf[i][UNIFI_NAME], conf[CONF_NAME])
            else:
                image = UnifiWifiImage(hass, x, wlan[CONF_NAME], wlan[CONF_FILL_COLOR], wlan[CONF_BACK_COLOR], wlan[CONF_FILE_OUTPUT], wlan[CONF_QR_QUALITY])
                entities.append(image)
                _LOGGER.debug("Setting up image for SSID %s on coordinator %s", wlan[CONF_NAME], conf[CONF_NAME])

    async_add_entities(entities)


class UnifiWifiImage(CoordinatorEntity, ImageEntity, RestoreEntity):
    """Representation of a Unifi Wifi image."""

    def __init__(self, hass: HomeAssistant, coordinator: UnifiWifiCoordinator, ssid: str, fill_color: str, back_color: str, output: bool, quality: str, key: dict = {}):
        """Initialize the image."""
        super().__init__(coordinator)
        self.hass = hass

        idssid = self._ssid_index(ssid)

        dt = utcnow()

        attributes = {
            CONF_ENABLED: self.coordinator.wlanconf[idssid][CONF_ENABLED],
            CONF_HIDE_SSID: self.coordinator.wlanconf[idssid][UNIFI_HIDE_SSID],
            CONF_COORDINATOR: self.coordinator.name,
            CONF_SITE: self.coordinator.site,
            CONF_SSID: ssid,
            UNIFI_ID: self.coordinator.wlanconf[idssid][UNIFI_ID],
            CONF_TIMESTAMP: int(dt.timestamp()),
            CONF_BACK_COLOR: back_color,
            CONF_FILL_COLOR: fill_color,
            CONF_FILE_OUTPUT: output,
            CONF_QR_QUALITY: quality
        }

        wpa3_support = self.coordinator.wlanconf[idssid][UNIFI_WPA3_SUPPORT],
        wpa3_transition = self.coordinator.wlanconf[idssid][UNIFI_WPA3_TRANSITION]
        if wpa3_support and not wpa3_transition:
            wpa_mode = 'WPA3'
        elif wpa3_support and wpa3_transition:
            wpa_mode = 'WPA2/WPA3'
        else:
            wpa_mode = 'WPA2'
        attributes[CONF_WPA_MODE] = wpa_mode

        if bool(key):
            attributes[CONF_PPSK] = True
            attributes[CONF_PASSWORD] = key[UNIFI_PASSWORD]
            attributes[UNIFI_NETWORKCONF_ID] = key[UNIFI_NETWORKCONF_ID]
            idnetwork = [x[UNIFI_ID] for x in self.coordinator.networkconf].index(key[UNIFI_NETWORKCONF_ID])
            attributes[CONF_NETWORK_NAME] = self.coordinator.networkconf[idnetwork][UNIFI_NAME]
            self._attr_name = f"{attributes[CONF_COORDINATOR]} {ssid} {attributes[CONF_NETWORK_NAME]} wifi"
        else:
            attributes[CONF_PPSK] = False
            attributes[CONF_PASSWORD] = self.coordinator.wlanconf[idssid][UNIFI_X_PASSPHRASE]
            self._attr_name = f"{attributes[CONF_COORDINATOR]} {ssid} wifi"

        if EXTRA_DEBUG:
            _LOGGER.debug("wlanconf for image.%s: [%s]", slugify(self._attr_name), self.coordinator.wlanconf[idssid])

        # Set entity attributes AFTER all values have been determined
        # Any changes afterwards will not be updated until an entity update is triggered
        self._attributes = attributes

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
            # restore self._attr_image_last_updated since image uses it for the state
            # and must be set to a datetime object
            self._attr_image_last_updated = parse_datetime(last_state.state)

            # Sometimes on reboots, and otherwise, the image entity is (re-)added to HASS
            # If these attributes are not restored, then a timestamp update may be triggered
            # or the WPA_MODE defaults to WPA3
            for attr in [
                CONF_PASSWORD,
                CONF_TIMESTAMP,
                CONF_WPA_MODE
            ]:
                if attr in last_state.attributes:
                    self._attributes[attr] = last_state.attributes[attr]
                    if EXTRA_DEBUG: _LOGGER.debug("Restored attribute %s (%s)", attr, last_state.attributes[attr])

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
        idssid = self._ssid_index(self._attributes[CONF_SSID])

        wpa3_support = self.coordinator.wlanconf[idssid][UNIFI_WPA3_SUPPORT]
        wpa3_transition = self.coordinator.wlanconf[idssid][UNIFI_WPA3_TRANSITION]
        if wpa3_support and not wpa3_transition:
            wpa_mode = 'WPA3'
        elif wpa3_support and wpa3_transition:
            wpa_mode = 'WPA2/WPA3'
        else:
            wpa_mode = 'WPA2'

        if wpa_mode == 'WPA3':
            # add the WPA2/WPA3 transition mode disable flag
            # not sure if this is actually necessary
            qrtext = f"WIFI:T:WPA;R:1;S:{self._attributes[CONF_SSID]};P:{self._attributes[CONF_PASSWORD]};;"
        else:
            qrtext = f"WIFI:T:WPA;S:{self._attributes[CONF_SSID]};P:{self._attributes[CONF_PASSWORD]};;"

        self._attributes[CONF_QR_TEXT] = qrtext

        match self._attributes[CONF_QR_QUALITY]:
            case 'L':
                ec = qrcode.constants.ERROR_CORRECT_L
            case 'M':
                ec = qrcode.constants.ERROR_CORRECT_M
            case 'Q':
                ec = qrcode.constants.ERROR_CORRECT_Q
            case 'H':
                ec = qrcode.constants.ERROR_CORRECT_H

        qr = qrcode.QRCode(
            version = 1,
            error_correction = ec,
            box_size = 16,
            border = 2
        )
        qr.add_data(qrtext)
        qr.make(fit=True)
        img = qr.make_image(
            back_color=self._hex_to_rgb(self._attributes[CONF_BACK_COLOR]),
            fill_color=self._hex_to_rgb(self._attributes[CONF_FILL_COLOR])
        )

        # generate QR code file
        output = self._attributes[CONF_FILE_OUTPUT]
        if output:
            path = f"/config/www/{slugify(self._attr_name)}_qr.png"
            self.hass.async_add_executor_job(img.save, path)

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
        hide_state = self.coordinator.wlanconf[idssid][UNIFI_HIDE_SSID]

        wpa3_support = self.coordinator.wlanconf[idssid][UNIFI_WPA3_SUPPORT]
        wpa3_transition = self.coordinator.wlanconf[idssid][UNIFI_WPA3_TRANSITION]
        if wpa3_support and not wpa3_transition:
            wpa_mode = 'WPA3'
        elif wpa3_support and wpa3_transition:
            wpa_mode = 'WPA2/WPA3'
        else:
            wpa_mode = 'WPA2'

        if self._attributes[CONF_PPSK]:
            idnetwork = self._network_index(self._attributes[UNIFI_NETWORKCONF_ID])
            new_password = self.coordinator.wlanconf[idssid][UNIFI_PRESHARED_KEYS][idnetwork][UNIFI_PASSWORD]
        else:
            new_password = self.coordinator.wlanconf[idssid][UNIFI_X_PASSPHRASE]

        enabled_change = bool(self._attributes[CONF_ENABLED] != enabled_state)
        hide_change = bool(self._attributes[CONF_HIDE_SSID] != hide_state)
        wpa_change = bool(self._attributes[CONF_WPA_MODE] != wpa_mode)
        password_change = bool(self._attributes[CONF_PASSWORD] != new_password)

        if not (enabled_change or hide_change or wpa_change or password_change):
            return

        self._attributes[UNIFI_ID] = self.coordinator.wlanconf[idssid][UNIFI_ID]

        if enabled_change:
            self._attributes[CONF_ENABLED] = enabled_state
            _LOGGER.debug("SSID %s on coordinator %s is now %s", self._attributes[CONF_SSID], self._attributes[CONF_COORDINATOR], 'enabled' if bool(enabled_state) else 'disabled')

        if hide_change:
            self._attributes[CONF_HIDE_SSID] = hide_state
            _LOGGER.debug("SSID %s on coordinator %s is now %s", self._attributes[CONF_SSID], self._attributes[CONF_COORDINATOR], 'hidden' if bool(hide_state) else 'broadcasting')

        if wpa_change or password_change:
            self._attributes[CONF_WPA_MODE] = wpa_mode
            self._attributes[CONF_PASSWORD] = new_password
            dt = utcnow()
            self._attributes[CONF_TIMESTAMP] = int(dt.timestamp())
            self._attr_image_last_updated = dt

            self._create_qr()

            if wpa_change:
                _LOGGER.debug("SSID %s on coordinator %s is now in %s mode", self._attributes[CONF_SSID], self._attributes[CONF_COORDINATOR], wpa_mode)

            if password_change:
                if self._attributes[CONF_PPSK]:
                    _LOGGER.debug("SSID (ppsk) %s (%s) on coordinator %s has a new password", self._attributes[CONF_SSID], self._attributes[CONF_NETWORK_NAME], self._attributes[CONF_COORDINATOR])
                else:
                    _LOGGER.debug("SSID %s on coordinator %s has a new password", self._attributes[CONF_SSID], self._attributes[CONF_COORDINATOR])

        self.async_write_ha_state()