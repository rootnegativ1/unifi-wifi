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

import logging, aiohttp, asyncio


from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL
)
from homeassistant.core import callback, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, IntegrationError
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed
)
from .const import (
    CONF_FORCE_PROVISION,
    CONF_MANAGED_APS,
    CONF_SITE,
    CONF_UNIFI_OS,
    UNIFI_ID,
    UNIFI_NAME
)

UNIFI_CSRF_TOKEN = 'X-CSRF-Token'

EXTRA_DEBUG = False


_LOGGER = logging.getLogger(__name__)


class ApiAuthError(IntegrationError):
    """Raised when a status code of 401 HTTPUnauthorized is received."""


class ApiError(IntegrationError):
    """Raised when a status code of 500 or greater is received."""


class UnifiWifiCoordinator(DataUpdateCoordinator):
    """Representation of a Unifi Wifi coordinator"""

    def __init__(self, hass: HomeAssistant, conf: ConfigType):
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=f"{conf[CONF_NAME]} UniFi coordinator",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=conf[CONF_SCAN_INTERVAL],
        )

        self.networkconf = []
        self.sysinfo = []
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
        self._timeout = conf[CONF_TIMEOUT]
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
            async with asyncio.timeout(self._timeout):
                return await self._update_info()
        except ApiAuthError as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            raise ConfigEntryAuthFailed from err
        except ApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def _request(self, session: aiohttp.ClientSession, method: str, path: str, **kwargs) -> aiohttp.ClientResponse:
        """Make a request."""
        headers = kwargs.pop("headers", None) # remove headers from kwargs
        if headers is None:
            headers = {}
        else:
            headers = dict(headers)

        fullpath = f"https://{self._host}:{self._port}{path}"
        resp = await session.request(method, fullpath, **kwargs, headers=headers)

        _LOGGER.debug("_request method %s on path %s (status %s)", method, fullpath, resp.status)

        if EXTRA_DEBUG:
            _LOGGER.debug("_request kwargs: %s", kwargs)
            _LOGGER.debug("_request headers: %s", headers)
            _LOGGER.debug("%s response: %s", path, await resp.json())
            _LOGGER.debug("%s response cookies: %s", path, resp.cookies)
            _LOGGER.debug("%s response headers: %s", path, resp.headers)

        status = resp.status
        if status == 401:
            raise ApiAuthError(f"{await resp.json()}")
        if status >= 500:
            raise ApiError(f"{await resp.json()}")

        if not resp.ok: # not a 2xx status code
            resp.raise_for_status()

        return resp

    async def _login(self, session: aiohttp.ClientSession):
        """log into a UniFi controller."""
        payload = {'username': self._user, 'password': self._password}
        headers = {'Content-Type': 'application/json', 'accept': 'application/json'}
        kwargs = {'json': payload, 'headers': headers}
        path = f"{self._login_prefix}/login"
        return await self._request(session, 'post', path, **kwargs)

    async def _logout(self, session: aiohttp.ClientSession, csrf_token: str) -> bool:
        """log out of a UniFi controller."""
        headers = {'Content-Length': '0'}
        if self._unifi_os:
            headers[UNIFI_CSRF_TOKEN] = csrf_token
        kwargs = {'headers': headers}
        path = f"{self._login_prefix}/logout"
        resp = await self._request(session, 'post', path, **kwargs)

        return True

    async def _force_provision(self, session: aiohttp.ClientSession, csrf_token: str) -> bool:
        headers = {'Content-Type': 'application/json'}
        if self._unifi_os:
            headers[UNIFI_CSRF_TOKEN] = csrf_token
        kwargs = {'headers': headers}

        aps = []
        if self._aps == []:
            # GET info on adopted access points from controller
            path = f"{self._api_prefix}/api/s/{self.site}/stat/device-basic"
            resp = await self._request(session, 'get', path, **kwargs)

            json = await resp.json()

            conf = json['data']
            for device in conf:
                if device['type'] == 'uap' or (device['type'] == 'udm' and device['model'] == 'UDM'):
                    aps.append(device)
        else:
            aps = self._aps

        path = f"{self._api_prefix}/api/s/{self.site}/cmd/devmgr"
        for ap in aps:
            payload = {'cmd': 'force-provision', 'mac': ap[CONF_MAC]}
            kwargs['json'] = payload
            resp = await self._request(session, 'post', path, **kwargs)

        return True

    async def _get_networkconf(self, session: aiohttp.ClientSession, csrf_token: str) -> bool:
        """Get networkconf info from a UniFi controller."""
        headers = {}
        if self._unifi_os:
            headers[UNIFI_CSRF_TOKEN] = csrf_token
        kwargs = {'headers': headers}
        path = f"{self._api_prefix}/api/s/{self.site}/rest/networkconf"
        resp = await self._request(session, 'get', path, **kwargs)

        conf = await resp.json()
        self.networkconf = conf['data']

        return True

    async def _get_sysinfo(self, session: aiohttp.ClientSession, csrf_token: str) -> bool:
        """Get system info from a UniFi controller."""
        headers = {}
        if self._unifi_os:
            headers[UNIFI_CSRF_TOKEN] = csrf_token
        kwargs = {'headers': headers}
        path = f"{self._api_prefix}/api/s/{self.site}/stat/sysinfo"
        resp = await self._request(session, 'get', path, **kwargs)

        conf = await resp.json()
        self.sysinfo = conf['data']

        return True

    async def _get_wlanconf(self, session: aiohttp.ClientSession, csrf_token: str) -> bool:
        """Get wlanconf info from a UniFi controller."""
        headers = {}
        if self._unifi_os:
            headers[UNIFI_CSRF_TOKEN] = csrf_token
        kwargs = {'headers': headers}
        path = f"{self._api_prefix}/api/s/{self.site}/rest/wlanconf"
        resp = await self._request(session, 'get', path, **kwargs)

        conf = await resp.json()
        self.wlanconf = conf['data']

        return True

    async def _update_info(self) -> bool:
        # this function is only used in _async_update_data()
        # which is used to keep the coordinator and its entities updated
        async with aiohttp.ClientSession(
            # https://docs.aiohttp.org/en/stable/client_advanced.html#ssl-control-for-tcp-sockets
            connector=aiohttp.TCPConnector(ssl=False),
            # without unsafe=True the login response cookie must be explicitly passed in each request
            # https://docs.aiohttp.org/en/stable/client_advanced.html#cookie-safety
            cookie_jar=aiohttp.CookieJar(unsafe=True)
        ) as session:
            _LOGGER.debug("_update_info Updating info for %s", self.name)

            resp = await self._login(session)
            csrf_token = ''
            if self._unifi_os:
                csrf_token = resp.headers[UNIFI_CSRF_TOKEN]

            await self._get_sysinfo(session, csrf_token)

            await self._get_networkconf(session, csrf_token)

            await self._get_wlanconf(session, csrf_token)

            await self._logout(session, csrf_token)

            return await session.close()

    async def set_wlanconf(self, ssid: str, payload: str, force: bool = False) -> bool:
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False),
            cookie_jar=aiohttp.CookieJar(unsafe=True)
        ) as session:
            _LOGGER.debug("set_wlanconf Setting new conf value for %s for %s", ssid, self.name)

            resp = await self._login(session)

            csrf_token = ''
            if self._unifi_os:
                csrf_token = resp.headers[UNIFI_CSRF_TOKEN]

            await self._get_wlanconf(session, csrf_token)

            idssid = [wlan[UNIFI_NAME] for wlan in self.wlanconf].index(ssid)
            idno = self.wlanconf[idssid][UNIFI_ID]
            headers = {'Content-Type': 'application/json'}
            if self._unifi_os:
                headers[UNIFI_CSRF_TOKEN] = csrf_token
            kwargs = {'headers': headers, 'json': payload}
            path = f"{self._api_prefix}/api/s/{self.site}/rest/wlanconf/{idno}"
            resp = await self._request(session, 'put', path, **kwargs)

            if self._force or force:
                await self._force_provision(session, csrf_token)

            await self._logout(session, csrf_token)

            await session.close()

            return await self.async_request_refresh()
