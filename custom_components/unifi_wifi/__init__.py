"""The Unifi Wifi integration."""

import logging
import re
import voluptuous as vol

from datetime import datetime
from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_METHOD,
    CONF_ADDRESS,
    CONF_ENABLED
    )
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from . import password as pw
from . import qr_code as qr
from . import unifi_api as api

DOMAIN = 'unifi_wifi'
CONF_BASEURL = 'base_url'
CONF_BASEURL_REGEX = r"https:\/\/((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}:\d+"
CONF_SITE = 'site'
CONF_UNIFIOS = 'unifi_os'
CONF_SSID = 'ssid'
CONF_NETWORKS = 'networks'
CONF_UNIFIID = 'unifi_id'
SERVICE_CUSTOM_PASSWORD = 'custom_password'
SERVICE_RANDOM_PASSWORD = 'random_password'
SERVICE_REFRESH_NETWORKS = 'refresh_networks'

_LOGGER = logging.getLogger(__name__)


_NETWORKS_SCHEMA = vol.Schema({
    vol.Required(CONF_SSID): cv.string,
})


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_BASEURL): cv.matches_regex(CONF_BASEURL_REGEX),
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SITE, default="default"): cv.string,
        vol.Optional(CONF_UNIFIOS, default=True): cv.boolean,
        vol.Optional(CONF_NETWORKS, default=[]): vol.All(
            cv.ensure_list, [_NETWORKS_SCHEMA]
        ),
    })},
    extra=vol.ALLOW_EXTRA,
)

SERVICE_CUSTOM_PASSWORD_SCHEMA = vol.Schema({
    vol.Required(CONF_SSID): cv.string,
    vol.Required(CONF_PASSWORD): vol.All(
        cv.string, vol.Length(min=8, max=63)
    ),
})

SERVICE_RANDOM_PASSWORD_SCHEMA = vol.Schema({
    vol.Required(CONF_SSID): cv.string,
    vol.Required(CONF_METHOD): vol.In(['xkcd','word','char']),
})


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    x = api.Controller(
        config[DOMAIN][CONF_BASEURL],
        config[DOMAIN][CONF_USERNAME],
        config[DOMAIN][CONF_PASSWORD],
        config[DOMAIN][CONF_SITE],
        config[DOMAIN][CONF_UNIFIOS]
    )

    def index(ssid):
        x.get_wlanconf() # update x.wlanconf
        for network in x.wlanconf:
            if network["name"] == ssid:
                ind = x.wlanconf.index(network)
                #_LOGGER.debug("ssid %s found at index %u", ssid, ind)
                return ind
        _LOGGER.error("ssid %s does not exist", ssid)
        return -1

    def refresh_all():
        x.get_wlanconf()
        addresses = {}
        entities = []
        for network in config[DOMAIN][CONF_NETWORKS]:
            ssid = network[CONF_SSID]
            ind = index(ssid)
            password = x.wlanconf[ind]["x_passphrase"]
            qr.create(ssid, password)
            _LOGGER.debug("QR code created for ssid: %s", ssid)
            addresses[ssid] = config[DOMAIN][CONF_NETWORKS].index(network)
            entity = {
                CONF_ENABLED: x.wlanconf[ind]["enabled"],
                CONF_SSID: ssid,
                CONF_UNIFIID: x.wlanconf[ind]["_id"],
                CONF_PASSWORD: password
            }
            entities.append(entity)

        hass.data[DOMAIN] = {
            CONF_ADDRESS: addresses,
            CONF_NETWORKS: entities
        }

    # generate initial files and entities for desired SSIDs
    refresh_all()

    # INITIALIZE SENSORS
    hass.helpers.discovery.load_platform('binary_sensor', DOMAIN, {}, config)
    hass.helpers.discovery.load_platform('camera', DOMAIN, {}, config)


    def custom_password_service(call):
        """Set a custom password."""
        ssid = call.data.get(CONF_SSID)
        password = call.data.get(CONF_PASSWORD)

        ind = index(ssid)
        if ind >= 0:
            payload = {"x_passphrase": password}
            x.set_wlanconf(ssid, payload)
            qr.create(ssid, password)
            _LOGGER.debug("ssid %s has a new password", ssid)
            refresh_all()
            # SOMEHOW UPDATE SENSOR & CAMERA ENTITIES


    def random_password_service(call):
        """Set a randomized password."""
        ssid = call.data.get(CONF_SSID)
        method = call.data.get(CONF_METHOD)

        ind = index(ssid)
        if ind >= 0:
            password = pw.create(method)
            payload = {"x_passphrase": password}
            x.set_wlanconf(ssid, payload)
            qr.create(ssid, password)
            _LOGGER.debug("ssid %s has a new password generated using the %s method", ssid, method)
            refresh_all()
            # SOMEHOW UPDATE SENSOR & CAMERA ENTITIES


    def refresh_networks_service(call):
        """Refresh network info."""
        refresh_all()


    hass.services.register(
        DOMAIN,
        SERVICE_CUSTOM_PASSWORD,
        custom_password_service,
        schema=SERVICE_CUSTOM_PASSWORD_SCHEMA
    )

    hass.services.register(
        DOMAIN,
        SERVICE_RANDOM_PASSWORD,
        random_password_service,
        schema=SERVICE_RANDOM_PASSWORD_SCHEMA
    )

    hass.services.register(
        DOMAIN,
        SERVICE_REFRESH_NETWORKS,
        refresh_networks_service
    )

    return True
