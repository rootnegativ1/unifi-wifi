"""Services for Unifi Wifi integration."""

from __future__ import annotations

import logging, asyncio, json
import voluptuous as vol

from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.const import (
    CONF_ENABLED,
    CONF_ENTITY_ID,
    CONF_METHOD,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_TARGET
)
from homeassistant.core import HomeAssistant, ServiceCall, Context
from homeassistant.exceptions import InvalidEntityFormatError, ServiceValidationError, Unauthorized, IntegrationError
from homeassistant.helpers import config_validation as cv, entity_registry
from homeassistant.helpers import service
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType
from typing import List # required for type hinting (function annotation) using List
from .const import (
    DOMAIN,
    CONF_CHAR_COUNT,
    CONF_COORDINATOR,
    CONF_DATA,
    CONF_DELIMITER,
    CONF_DELIMITER_TYPES,
    CONF_HIDE_SSID,
    CONF_MAX_LENGTH,
    CONF_METHOD_TYPES,
    CONF_MIN_LENGTH,
    CONF_PPSK,
    CONF_RANDOM,
    CONF_SSID,
    CONF_WORD_COUNT,
    UNIFI_NAME,
    UNIFI_NETWORKCONF_ID,
    UNIFI_X_PASSPHRASE,
    UNIFI_PRESHARED_KEYS
)
from .coordinator import UnifiWifiCoordinator
from . import password as pw

SERVICE_CUSTOM_PASSWORD = 'custom_password' # DEPRECATED
SERVICE_RANDOM_PASSWORD = 'random_password' # DEPRECATED
SERVICE_ENABLE_WLAN = 'enable_wlan'
SERVICE_HIDE_SSID = 'hide_ssid'
SERVICE_WLAN_PASSWORD = 'wlan_password'

EXTRA_DEBUG = False


_LOGGER = logging.getLogger(__name__)


def _is_ascii(value: Any) -> str:
    """Verify a string is only ascii characters."""
    # password is already validated as a string in SERVICE_*_PASSWORD_SCHEMA
    # should it be further validated as ascii?
    #    https://stackoverflow.com/questions/196345/how-to-check-if-a-string-in-python-is-in-ascii
    #    https://docs.python.org/3/library/stdtypes.html#str.isascii
    if not value.isascii():
        raise ServiceValidationError("Password may only contain ASCII characters.")
    return value

def _check_custom_password(obj: ConfigType):
    """Override random setting when a custom password is provided."""
    try:
        if obj[CONF_PASSWORD]:
            obj[CONF_RANDOM] = False
    except:
        obj[CONF_RANDOM] = True
    return obj

def _check_word_lengths(obj: ConfigType):
    """Verify minimum and maximum word lengths are logical."""
    if obj[CONF_MIN_LENGTH] > obj[CONF_MAX_LENGTH]:
        msg = f"{CONF_MIN_LENGTH} ({obj[CONF_MIN_LENGTH]}) must be less than or equal to {CONF_MAX_LENGTH} ({obj[CONF_MAX_LENGTH]})"
        raise vol.Invalid(msg)
    return obj

TARGET_SCHEMA = vol.Any(
    vol.Schema({
        vol.Required(CONF_ENTITY_ID): vol.All(
            cv.ensure_list, cv.entity_ids
        )
    }),
    cv.entity_id
)

PASSWORD_SCHEMA = vol.Schema({
    vol.Optional(CONF_PASSWORD): vol.All(
        cv.string, vol.Length(min=8, max=63), _is_ascii
    ),
    vol.Optional(CONF_RANDOM, default=True): cv.boolean,
    vol.Optional(CONF_METHOD, default='word'): vol.In(CONF_METHOD_TYPES),
    vol.Optional(CONF_DELIMITER, default='dash'): vol.In(CONF_DELIMITER_TYPES),
    vol.Optional(CONF_MIN_LENGTH, default=5): vol.All(
        vol.Coerce(int), vol.Range(min=3, max=9)
    ),
    vol.Optional(CONF_MAX_LENGTH, default=8): vol.All(
        vol.Coerce(int), vol.Range(min=3, max=9)
    ),
    vol.Optional(CONF_WORD_COUNT, default=4): vol.All(
        vol.Coerce(int), vol.Range(min=3, max=6)
    ),
    vol.Optional(CONF_CHAR_COUNT, default=24): vol.All(
        vol.Coerce(int), vol.Range(min=8, max=63)
    )
})

# DEPRECATED
SERVICE_CUSTOM_PASSWORD_SCHEMA = vol.Schema({
    vol.Required(CONF_TARGET): TARGET_SCHEMA,
    vol.Required(CONF_PASSWORD): vol.All(
        cv.string, vol.Length(min=8, max=63), _is_ascii
    ),
})

# DEPRECATED
SERVICE_RANDOM_PASSWORD_SCHEMA = vol.All(
    vol.Schema({
        vol.Required(CONF_TARGET): TARGET_SCHEMA,
        vol.Optional(CONF_METHOD,default='word'): vol.In(CONF_METHOD_TYPES),
        vol.Optional(CONF_DELIMITER, default='dash'): vol.In(CONF_DELIMITER_TYPES),
        vol.Optional(CONF_MIN_LENGTH, default=5): vol.All(
            vol.Coerce(int), vol.Range(min=3, max=9)
        ),
        vol.Optional(CONF_MAX_LENGTH, default=8): vol.All(
            vol.Coerce(int), vol.Range(min=3, max=9)
        ),
        vol.Optional(CONF_WORD_COUNT, default=4): vol.All(
            vol.Coerce(int), vol.Range(min=3, max=6)
        ),
        vol.Optional(CONF_CHAR_COUNT, default=24): vol.All(
            vol.Coerce(int), vol.Range(min=8, max=63)
        ),
    }),
    _check_word_lengths
)

SERVICE_ENABLE_WLAN_SCHEMA = vol.Schema({
    vol.Required(CONF_TARGET): TARGET_SCHEMA,
    vol.Required(CONF_ENABLED): cv.boolean,
})

SERVICE_HIDE_SSID_SCHEMA = vol.Schema({
    vol.Required(CONF_TARGET): TARGET_SCHEMA,
    vol.Required(CONF_HIDE_SSID): cv.boolean,
})

SERVICE_WLAN_PASSWORD_SCHEMA = vol.All(
    PASSWORD_SCHEMA.extend({
        vol.Required(CONF_TARGET): TARGET_SCHEMA,
    }),
    _check_custom_password,
    _check_word_lengths
)


async def register_services(hass: HomeAssistant, coordinators: List[UnifiWifiCoordinator]) -> bool:

    def _coordinator_index(_coordinator: str):
        """Find the index of a specific coordinator."""
        try:
            #return [x[CONF_NAME] for x in coordinators].index(_coordinator)
            return [x.name for x in coordinators].index(_coordinator)
        except ValueError as err:
            raise ServiceValidationError(f"Coordinator {_coordinator} is not configured in YAML: {err}")


    def _ssid_index(_index: int, _ssid: str):
        """Find the index of an ssid on a specific coordinator."""
        hass.add_job(coordinators[_index].async_request_refresh())

        try:
            return [x[UNIFI_NAME] for x in coordinators[_index].wlanconf].index(_ssid)
        except ValueError as err:
            raise ServiceValidationError(f"SSID {_ssid} does not exist on coordinator {coordinators[_index].name}: {err}")


    async def _random_password(call: ServiceCall) -> str:
        """SOMETHING DESCRIPTIVE."""
        method = call.data.get(CONF_METHOD)
        delimiter_raw = call.data.get(CONF_DELIMITER)
        min_length = call.data.get(CONF_MIN_LENGTH)
        max_length = call.data.get(CONF_MAX_LENGTH)
        word_count = call.data.get(CONF_WORD_COUNT)
        char_count = call.data.get(CONF_CHAR_COUNT)
        if delimiter_raw == 'dash':
            delimiter = '-'
        elif delimiter_raw == 'space':
            delimiter = ' '
        elif delimiter_raw == 'underscore':
            delimiter = '_'
        else:
            delimiter = ''
        
        password = await hass.async_add_executor_job(pw.create, method, delimiter, min_length, max_length, word_count, char_count)

        return password


    async def _valid_entity_states(_target: str | List[str], _context: Context) -> List[str]:
        """Return a list of states filtered by entity IDs belonging to the platform."""
        try:
            entities = _target[CONF_ENTITY_ID]
        except:
            entities = [_target]

        ent_reg = entity_registry.async_get(hass)
        valid_entities = []
        for entity_id in entities:
            entity = ent_reg.async_get(entity_id)
            try:
                entity_dict = entity.as_partial_dict
                if EXTRA_DEBUG: _LOGGER.debug("registry entry: %s", entity_dict)
                if entity_dict[CONF_PLATFORM] == DOMAIN:
                    valid_entities.append(entity_id)
                else:
                    #_LOGGER.debug("Entity ID %s does not belong to platform %s", entity_id, DOMAIN)
                    raise ServiceValidationError(f"Entity ID {entity_id} does not belong to platform {DOMAIN}")
            except AttributeError as err:
                #_LOGGER.debug("Entity ID %s is not valid: %s", entity_id, err)
                raise InvalidEntityFormatError(f"Entity ID {entity_id} is not valid: {err}")

        states = []
        for entity_id in valid_entities:
            # check entity permissions for the current user
            if _context.user_id:
                user = await hass.auth.async_get_user(_context.user_id)
                if user is None:
                    raise UnknownUser(context = _context, entity_id = entity_id, permission = POLICY_CONTROL)
                if not user.permissions.check_entity(entity_id, POLICY_CONTROL):
                    raise Unauthorized(context =_context, entity_id = entity_id, permission = POLICY_CONTROL)

            state = hass.states.get(entity_id)
            states.append(state)

        if EXTRA_DEBUG: _LOGGER.debug("valid_states: %s", states)
        return states

    # DEPRECATED
    async def _change_password(call: ServiceCall, _random: bool = False):
        """Send custom or randomly generated password to a coordinator."""
        states = await _valid_entity_states(call.data.get(CONF_TARGET), call.context)

        if not _random:
            password = call.data.get(CONF_PASSWORD)

        # create list of wlan configurations to be sent to controllers
        requests = []
        for entity in states:
            idcoord = _coordinator_index(entity.attributes.get(CONF_COORDINATOR))
            coordinator = coordinators[idcoord]
            ssid = entity.attributes.get(CONF_SSID)

            if _random:
                password = await _random_password(call)

            ppsk = bool(entity.attributes.get(CONF_PPSK))
            if ppsk:
                keys = coordinator.wlanconf[_ssid_index(idcoord, ssid)][UNIFI_PRESHARED_KEYS]
                network_id = entity.attributes.get(UNIFI_NETWORKCONF_ID)
                idkey = [x[UNIFI_NETWORKCONF_ID] for x in keys].index(network_id)

            try:
                idrequestcoord = [x[CONF_COORDINATOR] for x in requests].index(entity.attributes.get(CONF_COORDINATOR))
                if EXTRA_DEBUG: _LOGGER.debug("found coordinator entry in requests list")
                try:
                    idrequestssid = [y[CONF_SSID] for y in requests[idrequestcoord][CONF_DATA]].index(entity.attributes.get(CONF_SSID))
                    if EXTRA_DEBUG: _LOGGER.debug("found ssid entry in requests list")
                    if ppsk:
                        # check for unique ppsk passwords on a found ssid request
                        if password in [x[CONF_PASSWORD] for x in requests[idrequestcoord][CONF_DATA][idrequestssid][UNIFI_PRESHARED_KEYS]]:
                            raise IntegrationError("Networks on the same PPSK-enabled SSID cannot have the same password")

                        requests[idrequestcoord][CONF_DATA][idrequestssid][UNIFI_PRESHARED_KEYS][idkey] = {
                            CONF_PASSWORD: password,
                            UNIFI_NETWORKCONF_ID: network_id
                        }
                        if EXTRA_DEBUG: _LOGGER.debug("ppsk entry updated in requests list")
                    else:
                        # this condition should not be possible unless somehow two or more entities
                        # with the same coordinator AND ssid AND no private preshared keys
                        # are created and selected
                        requests[idrequestcoord][CONF_DATA][idrequestssid][CONF_PASSWORD] = password
                except ValueError:
                    if ppsk:
                        keys[idkey] = {
                            CONF_PASSWORD: password,
                            UNIFI_NETWORKCONF_ID: network_id
                        }
                        entry = {
                            CONF_SSID: ssid,
                            UNIFI_PRESHARED_KEYS: keys
                        }
                    else:
                        entry = {
                            CONF_SSID: ssid,
                            CONF_PASSWORD: password
                        }
                    requests[idrequestcoord][CONF_DATA].append(entry)
                    if EXTRA_DEBUG: _LOGGER.debug("new ssid entry created in requests list")
            except ValueError:
                if ppsk:
                    keys[idkey] = {
                        CONF_PASSWORD: password,
                        UNIFI_NETWORKCONF_ID: network_id
                    }
                    entry = {
                        CONF_COORDINATOR: entity.attributes.get(CONF_COORDINATOR),
                        CONF_DATA: [{
                            CONF_SSID: ssid,
                            UNIFI_PRESHARED_KEYS: keys
                        }]
                    }
                else:
                    entry = {
                        CONF_COORDINATOR: entity.attributes.get(CONF_COORDINATOR),
                        CONF_DATA: [{
                            CONF_SSID: ssid,
                            CONF_PASSWORD: password
                        }]
                    }
                requests.append(entry)
                if EXTRA_DEBUG: _LOGGER.debug("new coordinator entry created in requests list")

    # DEPRECATED
    async def custom_password_service(call: ServiceCall):
        """Set a custom password."""
        await _change_password(call, False)

    # DEPRECATED
    async def random_password_service(call: ServiceCall):
        """Set a randomized password."""
        await _change_password(call, True)


    async def _ssid_requests(states: List[str], key: str, value: str, force: bool = False):
        """Used to make SSID level API changes."""
        """This does not work (yet?) for PPSK level changes."""

        requests = []
        for entity in states:
            idcoord = _coordinator_index(entity.attributes.get(CONF_COORDINATOR))
            coordinator = coordinators[idcoord]
            ssid = entity.attributes.get(CONF_SSID)

            try:
                idrequestcoord = [x[CONF_COORDINATOR] for x in requests].index(entity.attributes.get(CONF_COORDINATOR))
                if EXTRA_DEBUG: _LOGGER.debug("found coordinator entry in the requests list")
                try:
                    idrequestssid = [y[CONF_SSID] for y in requests[idrequestcoord][CONF_DATA]].index(entity.attributes.get(CONF_SSID))
                    if EXTRA_DEBUG: _LOGGER.debug("found ssid entry in the requests list")
                    # do nothing since editing the same SSID multiple times is redundant
                    # requests[idrequestcoord][CONF_DATA][idrequestssid][key] = value
                except ValueError:
                    entry = {
                        CONF_SSID: ssid,
                        key: value
                    }
                    requests[idrequestcoord][CONF_DATA].append(entry)
                    if EXTRA_DEBUG: _LOGGER.debug("new ssid entry created in the requests list")
            except ValueError:
                entry = {
                    CONF_COORDINATOR: entity.attributes.get(CONF_COORDINATOR),
                    CONF_DATA: [{
                        CONF_SSID: ssid,
                        key: value
                    }]
                }
                requests.append(entry)
                if EXTRA_DEBUG: _LOGGER.debug("new coordinator entry created in the requests list")

        # send wlanconf change requests to controllers
        if EXTRA_DEBUG: _LOGGER.debug("requests: %s", requests)
        for request in requests:
            idcoord = _coordinator_index(request[CONF_COORDINATOR])
            coordinator = coordinators[idcoord]
            for r in request[CONF_DATA]:
                # boolean python values (uppercase) need to be json serialized (lowercase)
                # payload = json.dumps({key: y[key]})
                # apparently, the capitalized boolean value is actually REQUIRED ... weird
                payload ={key: r[key]}
                if EXTRA_DEBUG: _LOGGER.debug("ssid %s with payload %s", r[CONF_SSID], payload)
                await coordinator.set_wlanconf(r[CONF_SSID], payload, force)


    async def enable_wlan_service(call: ServiceCall):
        """Enable or disable an SSID."""
        states = await _valid_entity_states(call.data.get(CONF_TARGET), call.context)

        enabled = call.data.get(CONF_ENABLED)

        await _ssid_requests(states, CONF_ENABLED, enabled, True)


    async def hide_ssid_service(call: ServiceCall):
        """Toggle hiding an SSID."""
        states = await _valid_entity_states(call.data.get(CONF_TARGET), call.context)

        hide_ssid = call.data.get(CONF_HIDE_SSID)

        await _ssid_requests(states, CONF_HIDE_SSID, hide_ssid, True)


    async def wlan_password_service(call: ServiceCall):
        """Set a new wlan password."""
        states = await _valid_entity_states(call.data.get(CONF_TARGET), call.context)

        random = call.data.get(CONF_RANDOM)
        if not random:
            password = call.data.get(CONF_PASSWORD)

        # create list of wlan configurations to be sent to controllers
        requests = []
        for entity in states:
            idcoord = _coordinator_index(entity.attributes.get(CONF_COORDINATOR))
            coordinator = coordinators[idcoord]
            ssid = entity.attributes.get(CONF_SSID)

            if random:
                password = await _random_password(call)

            ppsk = bool(entity.attributes.get(CONF_PPSK))
            if ppsk:
                keys = coordinator.wlanconf[_ssid_index(idcoord, ssid)][UNIFI_PRESHARED_KEYS]
                network_id = entity.attributes.get(UNIFI_NETWORKCONF_ID)
                idkey = [x[UNIFI_NETWORKCONF_ID] for x in keys].index(network_id)

            try:
                idrequestcoord = [x[CONF_COORDINATOR] for x in requests].index(entity.attributes.get(CONF_COORDINATOR))
                if EXTRA_DEBUG: _LOGGER.debug("found coordinator entry in requests list")
                try:
                    idrequestssid = [y[CONF_SSID] for y in requests[idrequestcoord][CONF_DATA]].index(entity.attributes.get(CONF_SSID))
                    if EXTRA_DEBUG: _LOGGER.debug("found ssid entry in requests list")
                    if ppsk:
                        # check for unique ppsk passwords on a found ssid request
                        if password in [x[CONF_PASSWORD] for x in requests[idrequestcoord][CONF_DATA][idrequestssid][UNIFI_PRESHARED_KEYS]]:
                            raise IntegrationError("Networks on the same PPSK-enabled SSID cannot have the same password")

                        requests[idrequestcoord][CONF_DATA][idrequestssid][UNIFI_PRESHARED_KEYS][idkey] = {
                            CONF_PASSWORD: password,
                            UNIFI_NETWORKCONF_ID: network_id
                        }
                        if EXTRA_DEBUG: _LOGGER.debug("ppsk entry updated in requests list")
                    else:
                        # this condition should not be possible unless somehow two or more entities
                        # with the same coordinator AND ssid AND no private preshared keys
                        # are created and selected
                        requests[idrequestcoord][CONF_DATA][idrequestssid][CONF_PASSWORD] = password
                except ValueError:
                    if ppsk:
                        keys[idkey] = {
                            CONF_PASSWORD: password,
                            UNIFI_NETWORKCONF_ID: network_id
                        }
                        entry = {
                            CONF_SSID: ssid,
                            UNIFI_PRESHARED_KEYS: keys
                        }
                    else:
                        entry = {
                            CONF_SSID: ssid,
                            CONF_PASSWORD: password
                        }
                    requests[idrequestcoord][CONF_DATA].append(entry)
                    if EXTRA_DEBUG: _LOGGER.debug("new ssid entry created in requests list")
            except ValueError:
                if ppsk:
                    keys[idkey] = {
                        CONF_PASSWORD: password,
                        UNIFI_NETWORKCONF_ID: network_id
                    }
                    entry = {
                        CONF_COORDINATOR: entity.attributes.get(CONF_COORDINATOR),
                        CONF_DATA: [{
                            CONF_SSID: ssid,
                            UNIFI_PRESHARED_KEYS: keys
                        }]
                    }
                else:
                    entry = {
                        CONF_COORDINATOR: entity.attributes.get(CONF_COORDINATOR),
                        CONF_DATA: [{
                            CONF_SSID: ssid,
                            CONF_PASSWORD: password
                        }]
                    }
                requests.append(entry)
                if EXTRA_DEBUG: _LOGGER.debug("new coordinator entry created in requests list")

        # send wlanconf change requests to controllers
        if EXTRA_DEBUG: _LOGGER.debug("requests: %s", requests)
        for request in requests:
            idcoord = _coordinator_index(request[CONF_COORDINATOR])
            coordinator = coordinators[idcoord]
            for r in request[CONF_DATA]:
                try:
                    payload = {UNIFI_PRESHARED_KEYS: r[UNIFI_PRESHARED_KEYS]}
                except:
                    payload = {UNIFI_X_PASSPHRASE: r[CONF_PASSWORD]}
                if EXTRA_DEBUG: _LOGGER.debug("ssid %s with payload %s", r[CONF_SSID], payload)
                await coordinator.set_wlanconf(r[CONF_SSID], payload, False)


    # DEPRECATED
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_CUSTOM_PASSWORD,
        custom_password_service,
        schema=SERVICE_CUSTOM_PASSWORD_SCHEMA
    )

    # DEPRECATED
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RANDOM_PASSWORD,
        random_password_service,
        schema=SERVICE_RANDOM_PASSWORD_SCHEMA
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_ENABLE_WLAN,
        enable_wlan_service,
        schema=SERVICE_ENABLE_WLAN_SCHEMA
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_HIDE_SSID,
        hide_ssid_service,
        schema=SERVICE_HIDE_SSID_SCHEMA
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_WLAN_PASSWORD,
        wlan_password_service,
        schema=SERVICE_WLAN_PASSWORD_SCHEMA
    )

    return True