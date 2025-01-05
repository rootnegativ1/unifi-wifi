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
    UNIFI_CSRF_TOKEN,
    UNIFI_ID,
    UNIFI_NAME
)

_LOGGER = logging.getLogger(__name__)

# Useful for verbose debugging of http requests
# WARNING: This will expose usernames and passwords
EXTRA_DEBUG = False


class ApiAuthError(IntegrationError):
    """Raised when a status code of 401 HTTPUnauthorized or 403 Forbidden is received."""


class ApiError(IntegrationError):
    """Raised when a status code of 500 or greater is received."""


class UnifiWifiCoordinator(DataUpdateCoordinator):
    """Representation of a Unifi Wifi coordinator"""

    def __init__(self, hass: HomeAssistant, config: ConfigType):
        super().__init__(
            hass,
            _LOGGER,
            name=f"{config[CONF_NAME]} UniFi coordinator",
            update_interval=config[CONF_SCAN_INTERVAL],
        )

        self.networkconf = []
        self.sysinfo = []
        self.wlanconf = []
        self.name = config[CONF_NAME]
        self.verify_ssl = config[CONF_VERIFY_SSL]
        self.site = config[CONF_SITE]
        self._base_url = config[CONF_HOST]
        self._port = config[CONF_PORT]
        self._username = config[CONF_USERNAME]
        self._password = config[CONF_PASSWORD]
        self._force = config[CONF_FORCE_PROVISION]
        self._aps = config[CONF_MANAGED_APS]
        self._timeout = config[CONF_TIMEOUT]
        self._unifi_os = config[CONF_UNIFI_OS]
        if self._unifi_os:
            self._login_prefix = '/api/auth'
            self._api_prefix = '/proxy/network'
        else:
            self._login_prefix = '/api'
            self._api_prefix = ''

    async def _async_update_data(self) -> None:
        """Fetch the latest data from a UniFi controller."""
        try:
            async with asyncio.timeout(self._timeout):
                return await self._update_info()
        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator.
        except ApiAuthError as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            raise ConfigEntryAuthFailed from err
        except ApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def _request(self, session: aiohttp.ClientSession, method: str, path: str, **kwargs) -> aiohttp.ClientResponse:
        """Make a request."""

        fullpath = f"https://{self._base_url}:{self._port}{path}"
        response = await session.request(method, fullpath, **kwargs)

        _LOGGER.debug("_request method %s on path %s (status %s)", method, fullpath, response.status)

        if EXTRA_DEBUG:
            _LOGGER.debug("_request kwargs: %s", kwargs)
            _LOGGER.debug("%s response: %s", path, await response.json())
            _LOGGER.debug("%s response cookies: %s", path, response.cookies)
            _LOGGER.debug("%s response headers: %s", path, response.headers)

        status = response.status
        if status == 401 or status == 403:
            raise ApiAuthError(f"{await response.json()}")
        elif status >= 500:
            raise ApiError(f"{await response.json()}")
        elif not response.ok: # catch all other non 2xx status codes
            response.raise_for_status()
        else:
            pass

        return response

    async def _login(self, session: aiohttp.ClientSession) -> list[dict]:
        """log into a UniFi controller."""
        # Create headers for all requests to use with the current session
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}

        payload = {'username': self._username, 'password': self._password}
        kwargs = {'json': payload, 'headers': headers}
        path = f"{self._login_prefix}/login"
        response = await self._request(session, 'post', path, **kwargs)

        # Create a cookie from the current session response and add it to the headers
        headers['Cookie'] = '; '.join(response.headers.getall('Set-Cookie'))
        if self._unifi_os:
            headers[UNIFI_CSRF_TOKEN] = response.headers.get(UNIFI_CSRF_TOKEN)

        return headers

    async def _logout(self, session: aiohttp.ClientSession, headers: list[dict]):
        """log out of a UniFi controller."""
        headers['Content-Length'] = '0'
        kwargs = {'headers': headers}
        path = f"{self._login_prefix}/logout"
        await self._request(session, 'post', path, **kwargs)

    async def _force_provision(self, session: aiohttp.ClientSession, headers: list[dict]):
        """Force provision any access points adopted by a UniFi controller."""
        kwargs = {'headers': headers}

        aps = []
        if self._aps == []: # no access points listed in YAML config
            # GET info on adopted access points from controller
            path = f"{self._api_prefix}/api/s/{self.site}/stat/device-basic"
            response = await self._request(session, 'get', path, **kwargs)

            json = await response.json()

            conf = json['data']
            for device in conf:
                if device['type'] == 'uap' or (device['type'] == 'udm' and device['model'] == 'UDM'):
                    aps.append(device)
        else: # use the access points listed in YAML config
            aps = self._aps

        path = f"{self._api_prefix}/api/s/{self.site}/cmd/devmgr"
        for ap in aps:
            payload = {'cmd': 'force-provision', 'mac': ap[CONF_MAC]}
            kwargs['json'] = payload
            await self._request(session, 'post', path, **kwargs)

    async def _get_networkconf(self, session: aiohttp.ClientSession, headers: list[dict]):
        """Get networkconf info from a UniFi controller."""
        kwargs = {'headers': headers}
        path = f"{self._api_prefix}/api/s/{self.site}/rest/networkconf"
        response = await self._request(session, 'get', path, **kwargs)

        conf = await response.json()
        self.networkconf = conf['data']

    async def _get_sysinfo(self, session: aiohttp.ClientSession, headers: list[dict]):
        """Get system info from a UniFi controller."""
        kwargs = {'headers': headers}
        path = f"{self._api_prefix}/api/s/{self.site}/stat/sysinfo"
        response = await self._request(session, 'get', path, **kwargs)

        conf = await response.json()
        self.sysinfo = conf['data']

    async def _get_wlanconf(self, session: aiohttp.ClientSession, headers: list[dict]):
        """Get wlanconf info from a UniFi controller."""
        kwargs = {'headers': headers}
        path = f"{self._api_prefix}/api/s/{self.site}/rest/wlanconf"
        response = await self._request(session, 'get', path, **kwargs)

        conf = await response.json()
        self.wlanconf = conf['data']

    async def _get_restsetting(self, session: aiohttp.ClientSession, headers: list[dict]) -> list[dict]:
        """Get rest setting info from a UniFi controller."""
        kwargs = {'headers': headers}
        path = f"{self._api_prefix}/api/s/{self.site}/rest/setting"
        response = await self._request(session, 'get', path, **kwargs)

        conf = await response.json()

        # Return the data array instead of True (and saving the data to self.restsetting)
        # because there is a lot of unnecessary AND sensitive site/controller information
        return conf['data']

    async def _update_info(self) -> bool:
        """this function is only used in _async_update_data().

        It is called by the coordinator to keep itself and its entities updated.
        """
        async with aiohttp.ClientSession(
            # https://docs.aiohttp.org/en/stable/client_advanced.html#ssl-control-for-tcp-sockets
            connector=aiohttp.TCPConnector(ssl=False),
            # without unsafe=True the login response cookie must be explicitly passed in each request
            # https://docs.aiohttp.org/en/stable/client_advanced.html#cookie-safety
            #cookie_jar=aiohttp.CookieJar(unsafe=True)
        ) as session:
            _LOGGER.debug("_update_info Updating info for %s", self.name)

            headers = await self._login(session)

            await self._get_sysinfo(session, headers)
            await self._get_networkconf(session, headers)
            await self._get_wlanconf(session, headers)
            await self._logout(session, headers)

            del headers # not sure if this is necessary
            return await session.close()

    async def set_wlanconf(self, ssid: str, payload: str, force: bool = False) -> bool:
        """Update a wireless network setting."""
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False)
        ) as session:
            _LOGGER.debug("set_wlanconf Setting new conf value for %s for %s", ssid, self.name)

            headers = await self._login(session)

            # Find the unifi identification number for a specific SSID
            await self._get_wlanconf(session, headers)
            idssid = [wlan[UNIFI_NAME] for wlan in self.wlanconf].index(ssid)
            idno = self.wlanconf[idssid][UNIFI_ID]

            kwargs = {'headers': headers, 'json': payload}
            path = f"{self._api_prefix}/api/s/{self.site}/rest/wlanconf/{idno}"
            response = await self._request(session, 'put', path, **kwargs)

            if self._force or force:
                await self._force_provision(session, headers)

            await self._logout(session, headers)

            del headers
            await session.close()

            return await self.async_request_refresh()

    async def set_restsetting(self, key: str, payload: str, force: bool = False) -> bool:
        """Update a site setting."""
        # BE CAREFUL! This function is currently intended only to update hotspot credentials.
        # However, it is able to change many site settings when provided an existing key/payload combination
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False)
        ) as session:
            _LOGGER.debug("set_restsetting Setting new key (%s) value for %s", key, self.name)

            headers = await self._login(session)

            # download current site settings and read the _id value of the intended key
            data = await self._get_restsetting(session, headers)
            idkey = [d['key'] for d in data].index(key)
            idno = data[idkey][UNIFI_ID]

            kwargs = {'headers': headers, 'json': payload}
            path = f"{self._api_prefix}/api/s/{self.site}/rest/setting/{key}/{idno}"
            await self._request(session, 'put', path, **kwargs)

            if self._force or force:
                await self._force_provision(session, headers)

            await self._logout(session, headers)

            del headers
            await session.close()

            return await self.async_request_refresh()