"""UnifiWifi controller and image classes."""

from __future__ import annotations

import logging, mimetypes, os, collections, aiohttp, async_timeout

from datetime import timedelta
from homeassistant.components.image import ImageEntity
from homeassistant.const import (
    CONF_ENABLED,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_SSL,
    CONF_USERNAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN
)
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util, slugify
from .const import (
    DOMAIN,
    CONF_BASEURL,
    CONF_CONTROLLER_NAME,
    CONF_MONITORED_SSIDS,
    CONF_SITE,
    CONF_SSID,
    CONF_UNIFI_OS,
    UNIFI_ID,
    UNIFI_NAME,
    UNIFI_PASSWORD
)
from . import qr_code as qr

_LOGGER = logging.getLogger(__name__)




# https://developers.home-assistant.io/docs/integration_fetching_data/
class UnifiWifiController(DataUpdateCoordinator):
    """Representation of a Unifi Wifi controller"""

    def __init__(self, hass, conf):
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=f"{conf[CONF_CONTROLLER_NAME]} UniFi Controller",
            # Polling interval. Will only be polled if there are subscribers.
            # update_interval=timedelta(seconds=30),
            update_interval=conf[CONF_SCAN_INTERVAL],
        )

        self.wlanconf = []
        self.controller_name = conf[CONF_CONTROLLER_NAME]
        self.verify_ssl = conf[CONF_VERIFY_SSL]
        self.site = conf[CONF_SITE]
        self._baseurl = conf[CONF_BASEURL]
        self._user = conf[CONF_USERNAME]
        self._password = conf[CONF_PASSWORD]
        self._unifi_os = conf[CONF_UNIFI_OS]
        if self._unifi_os:
            self._login_prefix = '/api/auth'
            self._api_prefix = '/proxy/network'
        else:
            self._login_prefix = '/api'
            self._api_prefix = ''

    async def _async_update_data(self):
        try:
            async with async_timeout.timeout(10):
                return await self._get_wlanconf()
        except ApiAuthError as err:
            raise ConfigEntryAuthFailed from err
        except ApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    async def _request(self, session: aiohttp.ClientSession, method: str, path: str, **kwargs) -> aiohttp.ClientResponse:
        """Make a request."""
        # https://developers.home-assistant.io/docs/api_lib_auth/?_highlight=aiohttp#async-example
        # https://book.pythontips.com/en/latest/args_and_kwargs.html
        # https://stackoverflow.com/questions/11277432/how-can-i-remove-a-key-from-a-python-dictionary

        # headers = kwargs.pop("headers", None) # remove headers from kwargs
        # if headers is None:
            # headers = {}
        # else:
            # headers = dict(headers)

        # return await session.request(method, f"{self._baseurl}{path}", **kwargs, headers=headers)

        return await session.request(method, f"{self._baseurl}{path}", **kwargs)

    async def _login(self, session: aiohttp.ClientSession) -> bool:
        data = {'username': self._user, 'password': self._password}
        kwargs = {'data': data}
        path = f"{self._login_prefix}/login"
        resp = await self._request(session, 'post', path, **kwargs)

        # json = await resp.json()
        # _LOGGER.debug("login response: %s", json)

        self._cookie = resp.cookies
        self._csrf_token = resp.headers['X-CSRF-Token']

        return True

    async def _logout(self, session: aiohttp.ClientSession) -> bool:
        headers = {'X-CSRF-Token': self._csrf_token, 'content-length': '0'}
        kwargs = {'cookies': self._cookie, 'headers': headers}
        path = f"{self._login_prefix}/logout"
        resp = await self._request(session, 'post', path, **kwargs)

        # json = await resp.json()
        # _LOGGER.debug("logout response: %s", json)

        return True

    async def _update_wlanconf(self, session: aiohttp.ClientSession) -> bool:
        kwargs = {'cookies': self._cookie}
        path = f"{self._api_prefix}/api/s/{self.site}/rest/wlanconf"
        resp = await self._request(session, 'get', path, **kwargs)

        json = await resp.json()
        self.wlanconf = json['data']
        # _LOGGER.debug("_update_wlanconf response: %s", json)

        return True

    async def _get_wlanconf(self) -> bool:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            await self._login(session)

            await self._update_wlanconf(session)

            return await self._logout(session)

    async def set_wlanconf(self, ssid: str, payload: str) -> bool:
        # https://stackoverflow.com/questions/26685248/difference-between-data-and-json-parameters-in-python-requests-package
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            await self._login(session)

            await self._update_wlanconf(session)

            found = False
            for wlan in self.wlanconf:
                if wlan[UNIFI_NAME] == ssid:
                    idno = wlan[UNIFI_ID]
                    found = True

            if found:
                headers = {'X-CSRF-Token': self._csrf_token}
                kwargs = {'cookies': self._cookie, 'headers': headers, 'json': payload}
                path = f"{self._api_prefix}/api/s/{self.site}/rest/wlanconf/{idno}"
                resp = await self._request(session, 'put', path, **kwargs)

                await self.async_refresh()

                # json = await resp.json()
                # _LOGGER.debug("set_wlanconf response: %s", json)
            else:
                raise ValueError(f"The ssid {ssid} cannot be found at site {self.site} on controller {self.controller_name}")

            return await self._logout(session)


class UnifiWifiImage(CoordinatorEntity, ImageEntity, RestoreEntity):
    """Representation of a Unifi Wifi image."""

    def __init__(self, hass, coordinator, ssid):
        """Initialize the image."""
        super().__init__(coordinator)

        ind = self._update_index(ssid)
        password = self.coordinator.wlanconf[ind][UNIFI_PASSWORD]

        utc = dt_util.utcnow()
        self._attributes = {
            CONF_ENABLED: self.coordinator.wlanconf[ind][CONF_ENABLED],
            CONF_CONTROLLER_NAME: self.coordinator.controller_name,
            CONF_SITE: self.coordinator.site,
            CONF_SSID: ssid,
            UNIFI_ID: self.coordinator.wlanconf[ind][UNIFI_ID],
            CONF_PASSWORD: password,
            'qr_text': f"WIFI:T:WPA;S:{ssid};P:{password};;",
            'timestamp': int(dt_util.utc_to_timestamp(utc))
        }

        self._update_qr()

        self._attr_name = f"{self._attributes[CONF_CONTROLLER_NAME]} {self._attributes[CONF_SITE]} {ssid} wifi"
        self._attr_unique_id = slugify(f"{DOMAIN}_{self._attr_name}_image")
        self._attr_image_last_updated = utc

        _verify_ssl = self.coordinator.verify_ssl
        if _verify_ssl:
            self._attr_image_url = f"https://127.0.0.1:8123/local/{self._attributes[CONF_CONTROLLER_NAME]}_{self._attributes[CONF_SITE]}_{ssid}_wifi_qr.png"
        else:
            self._attr_image_url = f"http://127.0.0.1:8123/local/{self._attributes[CONF_CONTROLLER_NAME]}_{self._attributes[CONF_SITE]}_{ssid}_wifi_qr.png"

        self._client = get_async_client(hass, verify_ssl=_verify_ssl)
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
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        # await self.coordinator.async_refresh()
        await self.coordinator.async_request_refresh()

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

            for attr in [CONF_ENABLED, CONF_CONTROLLER_NAME, CONF_SITE, CONF_SSID, UNIFI_ID, CONF_PASSWORD, 'qr_text', 'timestamp']:
                if attr in last_state.attributes:
                    self._attributes[attr] = last_state.attributes[attr]
            _LOGGER.debug("Restored: %s", self._attr_name)
        else:
            _LOGGER.debug("Unable to restore: %s", self._attr_name)

    def _update_qr(self) -> None:
        # should this be run as async?
        # https://developers.home-assistant.io/docs/asyncio_working_with_async?_highlight=executor#calling-sync-functions-from-async
        # await hass.async_add_executor_job(qr.create, self._attributes[CONF_CONTROLLER_NAME], self._attributes[CONF_SITE], self._attributes[CONF_SSID], self._attributes[CONF_PASSWORD])
        qr.create(self._attributes[CONF_CONTROLLER_NAME], self._attributes[CONF_SITE], self._attributes[CONF_SSID], self._attributes[CONF_PASSWORD])

    def _update_index(self, ssid):
        for wlan in self.coordinator.wlanconf:
            if wlan[CONF_NAME] == ssid:
                return self.coordinator.wlanconf.index(wlan)
        raise ValueError(f"SSID {ssid} not found at site {self.coordinator.site} on controller {self.coordinator.controller_name}")

    def _update_data(self) -> None:
        ind = self._update_index(self._attributes[CONF_SSID])
        enabled_change = bool(self._attributes[CONF_ENABLED] != self.coordinator.wlanconf[ind][CONF_ENABLED])
        password_change = bool(self._attributes[CONF_PASSWORD] != self.coordinator.wlanconf[ind][UNIFI_PASSWORD])

        if enabled_change:
            self._attributes[CONF_ENABLED] = self.coordinator.wlanconf[ind][CONF_ENABLED]
            self._attributes[UNIFI_ID] = self.coordinator.wlanconf[ind][UNIFI_ID]

            _LOGGER.debug("SSID %s at site %s on controller %s is now %s", self._attributes[CONF_SSID], self._attributes[CONF_SITE], self._attributes[CONF_CONTROLLER_NAME], 'enabled' if self._attributes[CONF_ENABLED] == 'true' else 'disabled')

        if password_change:
            self._attributes[CONF_PASSWORD] = self.coordinator.wlanconf[ind][UNIFI_PASSWORD]
            self._attributes[UNIFI_ID] = self.coordinator.wlanconf[ind][UNIFI_ID]
            self._attributes['qr_text'] = f"WIFI:T:WPA;S:{self._attributes[CONF_SSID]};P:{self._attributes[CONF_PASSWORD]};;"

            utc = dt_util.utcnow()
            self._attributes['timestamp'] = int(dt_util.utc_to_timestamp(utc))
            self._attr_image_last_updated = utc

            self._update_qr()

            _LOGGER.debug("SSID %s at site %s on controller %s has a new password", self._attributes[CONF_SSID], self._attributes[CONF_SITE], self._attributes[CONF_CONTROLLER_NAME])