"""Constants for the Unifi Wifi integration."""

DOMAIN = 'unifi_wifi'

CONF_BACK_COLOR = 'back_color'
CONF_CHAR_COUNT = 'char_count'
CONF_COORDINATOR = 'coordinator'
CONF_DATA = 'data'
CONF_DELIMITER = 'delimiter'
CONF_DELIMITER_TYPES = ['dash','space','underscore','none']
CONF_FILL_COLOR = 'fill_color'
CONF_FORCE_PROVISION = 'force_provision'
CONF_HIDE_SSID = 'hide_ssid'
CONF_MANAGED_APS = 'managed_aps'
CONF_MAX_LENGTH = 'max_length'
CONF_METHOD_TYPES = ['xkcd','word','char']
CONF_MIN_LENGTH = 'min_length'
CONF_MONITORED_SSIDS = 'monitored_ssids'
CONF_NETWORK_NAME = 'network_name'
CONF_PPSK = 'ppsk'
CONF_PRESHARED_KEYS = 'preshared_keys'
CONF_QRTEXT = 'qr_text'
CONF_SITE = 'site'
CONF_SSID = 'ssid'
CONF_TIMESTAMP = 'timestamp'
CONF_UNIFI_OS = 'unifi_os'
CONF_WORD_COUNT = 'word_count'
CONF_WPA3_SUPPORT = 'wpa3_support'
CONF_WPA3_TRANSITION = 'wpa3_transition'

# Some of the below values are duplicates of homeassistant.const values
# This is done to allow for changes in UniFi API keys
UNIFI_ID = '_id'
UNIFI_NAME = 'name' # duplicate
UNIFI_NETWORKCONF_ID = 'networkconf_id'
UNIFI_PASSPHRASE = 'x_passphrase'
UNIFI_PASSWORD = 'password' # duplicate
UNIFI_PRESHARED_KEYS = 'private_preshared_keys'