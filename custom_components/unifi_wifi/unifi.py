# https://developers.home-assistant.io/docs/integration_fetching_data/
# https://stackoverflow.com/questions/26685248/difference-between-data-and-json-parameters-in-python-requests-package
# https://developers.home-assistant.io/docs/api_lib_auth/?_highlight=aiohttp#async-example
# https://book.pythontips.com/en/latest/args_and_kwargs.html
# https://stackoverflow.com/questions/11277432/how-can-i-remove-a-key-from-a-python-dictionary
# https://developers.home-assistant.io/docs/asyncio_working_with_async?_highlight=executor#calling-sync-functions-from-async
# https://stackoverflow.com/questions/22351254/python-script-to-convert-image-into-byte-array
# https://developers.home-assistant.io/docs/core/entity/image/#methods

"""Unifi Wifi coordinator and image classes."""

from __future__ import annotations

import logging, mimetypes, os, collections, aiohttp, async_timeout, qrcode, io

from datetime import timedelta
from homeassistant.components.image import ImageEntity
from homeassistant.const import (
    CONF_ENABLED,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_SSL,
    CONF_USERNAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN
)
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify
from .const import (
    DOMAIN,
    CONF_FORCE_PROVISION,
    CONF_MANAGED_APS,
    CONF_MONITORED_SSIDS,
    CONF_QRTEXT,
    CONF_SITE,
    CONF_SSID,
    CONF_TIMESTAMP,
    CONF_UNIFI_OS,
    UNIFI_ID,
    UNIFI_NAME,
    UNIFI_PASSWORD
)

_LOGGER = logging.getLogger(__name__)

DEBUG = True

class UnifiWifiCoordinator(DataUpdateCoordinator):
    """Representation of a Unifi Wifi coordinator"""

    def __init__(self, hass, conf):
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=f"{conf[CONF_NAME]} UniFi coordinator",
            # Polling interval. Will only be polled if there are subscribers.
            # update_interval=timedelta(seconds=30),
            update_interval=conf[CONF_SCAN_INTERVAL],
        )

        self.wlanconf = []
        self.name = conf[CONF_NAME]
        self.verify_ssl = conf[CONF_VERIFY_SSL]
        self.site = conf[CONF_SITE]
        self._host = conf[CONF_HOST]
        self._port = conf[CONF_PORT]
        self._user = conf[CONF_USERNAME]
        self._password = conf[CONF_PASSWORD]
        self._force = conf[CONF_FORCE_PROVISION]
        self._aps = conf[CONF_MANAGED_APS]
        self._unifi_os = conf[CONF_UNIFI_OS]
        if self._unifi_os:
            self._login_prefix = '/api/auth'
            self._api_prefix = '/proxy/network'
        else:
            self._login_prefix = '/api'
            self._api_prefix = ''

    async def _async_update_data(self):
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                return await self._update_wlanconf()
        except ConnectionError as err:
            # # Raising ConfigEntryAuthFailed will cancel future updates
            # # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            # raise ConfigEntryAuthFailed from err
            raise PlatformNotReady(f"Error communicating with API: {err}")

    async def _request(self, session: aiohttp.ClientSession, method: str, path: str, **kwargs) -> aiohttp.ClientResponse:
        """Make a request."""
        headers = kwargs.pop("headers", None) # remove headers from kwargs
        if headers is None:
            headers = {}
        else:
            headers = dict(headers)

        fullpath = f"https://{self._host}:{self._port}{path}"
        if DEBUG:
            _LOGGER.debug("_request path %s", fullpath)
            _LOGGER.debug("_request kwargs %s", kwargs)
            _LOGGER.debug("_request headers %s", headers)

        return await session.request(method, fullpath, **kwargs, headers=headers)

    async def _login(self, session: aiohttp.ClientSession):
        """log into a UniFi controller."""
        payload = {'username': self._user, 'password': self._password}
        headers = {'Content-Type': 'application/json'}
        kwargs = {'json': payload, 'headers': headers}
        path = f"{self._login_prefix}/login"
        resp = await self._request(session, 'post', path, **kwargs)

        if DEBUG:
            _LOGGER.debug("_login response: %s", await resp.json())
            _LOGGER.debug("_login response cookies: %s", resp.cookies)
            _LOGGER.debug("_login response headers: %s", resp.headers)

        return resp

    async def _logout(self, session: aiohttp.ClientSession, csrf_token: str) -> None:
        """log out of a UniFi controller."""
        headers = {'Content-Length': '0'}
        if self._unifi_os:
            headers['X-CSRF-Token'] = csrf_token
        kwargs = {'headers': headers}
        path = f"{self._login_prefix}/logout"
        resp = await self._request(session, 'post', path, **kwargs)

        if DEBUG:
            _LOGGER.debug("_logout response: %s", await resp.json())

    async def _force_provision(self, session: aiohttp.ClientSession, csrf_token: str) -> bool:
        if not self._force: return True

        headers = {'Content-Type': 'application/json'}
        if self._unifi_os:
            headers['X-CSRF-Token'] = csrf_token
        kwargs = {'headers': headers}

        aps = []
        if self._aps == []:
            # GET info on adopted access points from controller
            path = f"{self._api_prefix}/api/s/default/stat/device-basic"
            resp = await self._request(session, 'get', path, **kwargs)

            json = await resp.json()
            if DEBUG:
                _LOGGER.debug("device-basic (_force_provision) response: %s", json)

            data = json['data']
            for device in data:
                if device['type'] == 'uap' or (device['type'] == 'udm' and device['model'] == 'UDM'):
                    aps.append(device)
        else:
            aps = self._aps

        path = f"{self._api_prefix}/api/s/{self.site}/cmd/devmgr"
        for ap in aps:
            payload = {'cmd': 'force-provision', 'mac': ap[CONF_MAC]}
            kwargs['json'] = payload
            resp = await self._request(session, 'post', path, **kwargs)

            if DEBUG:
                _LOGGER.debug("_force_provision response for %s: %s", ap[CONF_MAC], await resp.json())

        return True

    async def _get_wlanconf(self, session: aiohttp.ClientSession, csrf_token: str) -> bool:
        """Get wlanconf info from a UniFi controller."""
        headers = {}
        if self._unifi_os:
            headers['X-CSRF-Token'] = csrf_token
        kwargs = {'headers': headers}
        path = f"{self._api_prefix}/api/s/{self.site}/rest/wlanconf"
        resp = await self._request(session, 'get', path, **kwargs)

        json = await resp.json()
        self.wlanconf = json['data']
        if DEBUG:
            _LOGGER.debug("_get_wlanconf response: %s", await resp.text())

        return True

    # this function is only used in _async_update_data()
    # which is used to keep the coordinator and its entities updated
    async def _update_wlanconf(self) -> bool:
        async with aiohttp.ClientSession(
            # https://docs.aiohttp.org/en/stable/client_advanced.html#ssl-control-for-tcp-sockets
            connector=aiohttp.TCPConnector(ssl=False),
            # without unsafe=True the login response cookie must be explicitly passed in each request
            # https://docs.aiohttp.org/en/stable/client_advanced.html#cookie-safety
            cookie_jar=aiohttp.CookieJar(unsafe=True)
        ) as session:
            resp = await self._login(session)
            csrf_token = ''
            if self._unifi_os:
                csrf_token = resp.headers['X-CSRF-Token']

            await self._get_wlanconf(session, csrf_token)

            await self._logout(session, csrf_token)

            return await session.close()

    async def set_wlanconf(self, ssid: str, payload: str) -> bool:
        async with aiohttp.ClientSession(
            # https://docs.aiohttp.org/en/stable/client_advanced.html#ssl-control-for-tcp-sockets
            connector=aiohttp.TCPConnector(ssl=False),
            # without unsafe=True the login response cookie must be explicitly passed in each request
            # https://docs.aiohttp.org/en/stable/client_advanced.html#cookie-safety
            cookie_jar=aiohttp.CookieJar(unsafe=True)
        ) as session:
            resp = await self._login(session)
            csrf_token = ''
            if self._unifi_os:
                csrf_token = resp.headers['X-CSRF-Token']

            await self._get_wlanconf(session, csrf_token)

            ind = [wlan[UNIFI_NAME] for wlan in self.wlanconf].index(ssid)
            idno = self.wlanconf[ind][UNIFI_ID]

            headers = {'Content-Type': 'application/json'}
            if self._unifi_os:
                headers['X-CSRF-Token'] = csrf_token
            kwargs = {'headers': headers, 'json': payload}
            path = f"{self._api_prefix}/api/s/{self.site}/rest/wlanconf/{idno}"
            resp = await self._request(session, 'put', path, **kwargs)

            await self.async_request_refresh()

            if DEBUG:
                _LOGGER.debug("set_wlanconf response: %s", await resp.json())

            await self._force_provision(session, csrf_token)

            await self._logout(session, csrf_token)

            return await session.close()


class UnifiWifiImage(CoordinatorEntity, ImageEntity, RestoreEntity):
    """Representation of a Unifi Wifi image."""

    def __init__(self, hass, coordinator, ssid):
        """Initialize the image."""
        super().__init__(coordinator)

        ind = self._find_index(ssid)
        password = self.coordinator.wlanconf[ind][UNIFI_PASSWORD]

        # dt = dt_util.now() # int(dt_util.as_timestamp(dt))
        dt = dt_util.utcnow()
        self._attributes = {
            CONF_ENABLED: self.coordinator.wlanconf[ind][CONF_ENABLED],
            CONF_NAME: self.coordinator.name,
            CONF_SITE: self.coordinator.site,
            CONF_SSID: ssid,
            UNIFI_ID: self.coordinator.wlanconf[ind][UNIFI_ID],
            CONF_PASSWORD: password,
            CONF_QRTEXT: f"WIFI:T:WPA;S:{ssid};P:{password};;",
            CONF_TIMESTAMP: int(dt_util.utc_to_timestamp(dt))
        }

        self._create_qr()

        self._attr_name = f"{self._attributes[CONF_NAME]} {ssid} wifi"
        self._attr_unique_id = slugify(f"{DOMAIN}_{self._attr_name}_image")
        self._attr_content_type: str = "image/png"
        self._attr_image_last_updated = dt

        verify_ssl = self.coordinator.verify_ssl
        if verify_ssl:
            self._attr_image_url = f"https://127.0.0.1:8123/local/{self._attributes[CONF_NAME]}_{ssid}_wifi_qr.png"
        else:
            self._attr_image_url = f"http://127.0.0.1:8123/local/{self._attributes[CONF_NAME]}_{ssid}_wifi_qr.png"

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
                CONF_ENABLED,
                CONF_NAME,
                CONF_SITE,
                CONF_SSID,
                UNIFI_ID,
                CONF_PASSWORD,
                CONF_QRTEXT, 
                CONF_TIMESTAMP
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
        path = f"/config/www/{self._attributes[CONF_NAME]}_{self._attributes[CONF_SSID]}_wifi_qr.png"
        img.save(path)

        # generate QR code byte string needed for the frontend
        x = io.BytesIO()
        img.save(x)
        self._code_bytes = x.getvalue()

    def _find_index(self, ssid):
        for wlan in self.coordinator.wlanconf:
            if wlan[UNIFI_NAME] == ssid:
                return self.coordinator.wlanconf.index(wlan)
        raise ValueError(f"SSID {ssid} not found on coordinator {self.coordinator.name}")

    def _update_data(self) -> None:
        ind = self._find_index(self._attributes[CONF_SSID])
        enabled_change = bool(self._attributes[CONF_ENABLED] != self.coordinator.wlanconf[ind][CONF_ENABLED])
        password_change = bool(self._attributes[CONF_PASSWORD] != self.coordinator.wlanconf[ind][UNIFI_PASSWORD])

        if enabled_change:
            self._attributes[CONF_ENABLED] = self.coordinator.wlanconf[ind][CONF_ENABLED]
            self._attributes[UNIFI_ID] = self.coordinator.wlanconf[ind][UNIFI_ID]

            _LOGGER.debug("SSID %s on coordinator %s is now %s", self._attributes[CONF_SSID], self._attributes[CONF_NAME], 'enabled' if self._attributes[CONF_ENABLED] == 'true' else 'disabled')

        if password_change:
            self._attributes[CONF_PASSWORD] = self.coordinator.wlanconf[ind][UNIFI_PASSWORD]
            self._attributes[UNIFI_ID] = self.coordinator.wlanconf[ind][UNIFI_ID]
            self._attributes[CONF_QRTEXT] = f"WIFI:T:WPA;S:{self._attributes[CONF_SSID]};P:{self._attributes[CONF_PASSWORD]};;"

            # dt = dt_util.now()
            # self._attributes[CONF_TIMESTAMP] = int(dt_util.as_timestamp(dt))
            # self._attr_image_last_updated = dt
            dt = dt_util.utcnow()
            self._attributes[CONF_TIMESTAMP] = int(dt_util.utc_to_timestamp(dt))
            self._attr_image_last_updated = dt

            self._create_qr()

            self.async_write_ha_state()

            _LOGGER.debug("SSID %s on coordinator %s has a new password", self._attributes[CONF_SSID], self._attributes[CONF_NAME])