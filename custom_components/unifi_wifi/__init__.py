"""The Unifi Wifi integration."""

import logging, asyncio
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    CONF_VERIFY_SSL
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify
from .const import (
    DOMAIN,
    CONF_FORCE_PROVISION,
    CONF_MANAGED_APS,
    CONF_MONITORED_SSIDS,
    CONF_PPSK,
    CONF_SITE,
    CONF_SSID,
    CONF_UNIFI_OS
)
from .services import register_services
from .coordinator import UnifiWifiCoordinator

_LOGGER = logging.getLogger(__name__)


_AP_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_MAC): cv.string
})

_SSID_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    # provide a way to list specific ppsk vlans
})

_SITE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_SITE, default='default'): cv.string,
    vol.Optional(CONF_PORT, default=443): cv.port,
    vol.Optional(CONF_SCAN_INTERVAL, default=600): cv.time_period,
    vol.Optional(CONF_UNIFI_OS, default=True): cv.boolean,
    vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
    vol.Optional(CONF_FORCE_PROVISION, default=False): cv.boolean,
    vol.Optional(CONF_MANAGED_APS, default=[]): vol.All(
        cv.ensure_list, [_AP_SCHEMA]
    ),
    vol.Optional(CONF_MONITORED_SSIDS, default=[]): vol.All(
        cv.ensure_list, [_SSID_SCHEMA]
    ),
})

def _unique_names(obj: ConfigType):
    """Verify each host + site name is unique."""
    names = [slugify(conf[CONF_NAME]) for conf in obj]
    msg = f"Duplicate name values are not allowed: {names}"
    vol.Unique(msg)(names)
    return obj

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(
        cv.ensure_list, [_SITE_SCHEMA], _unique_names,
    )},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:

    coordinators = [UnifiWifiCoordinator(hass, conf) for conf in config[DOMAIN]]
    hass.data[DOMAIN] = config[DOMAIN]

    hass.async_create_task(async_load_platform(hass, 'image', DOMAIN, coordinators, config))

    await register_services(hass, coordinators)

    return True