[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/rootnegativ1/unifi-wifi?color=green&style=for-the-badge)
[![Github All Releases](https://img.shields.io/github/downloads/rootnegativ1/unifi-wifi/total.svg?&style=for-the-badge)]()

# Unifi Wifi Home Assistant Integration

Change passwords and generate QR codes for WLANs on UniFi Network controllers. Passwords can be custom or random strings using the included services. QR codes are represented as image entities and can be generated per network SSID. These images are located in ```/config/www```. If a password is changed through the controller-side web UI, the associated QR code in Home Assistant is automatically updated (based on scan_interval).

## Manual Installation
Download the contents of ```custom_components``` to your ```/config/custom_components``` directory

## HACS Installation
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rootnegativ1&repository=unifi-wifi&category=integration) [^1]
1. Go to any of the sections (integrations, frontend, automation).
2. Click on the 3 dots in the top right corner.
3. Select "Custom repositories"
4. Add the URL ```https://github.com/rootnegativ1/unifi-wifi``` to the repository.
5. Select the ```integration``` category.
6. Click the "ADD" button.

## Configuration
To enable this component in your installation, add the following to your configuration.yaml file:
```yaml
# Example configuration.yaml entry
unifi_wifi:
  - controller_name: myhouse
    site: default
    host: https://192.168.1.1:443
    port: 443
    username: local.admin
    password: NotARealPassword
    scan_interval: 300
    unifi_os: true
    verify_ssl: false
    networks:
      - name: my-wireless-network
```

### Configuration Variables
- **controller_name** <sup><sub>string</sub></sup> *REQUIRED*

  Unique name to identify each site + base_url combo (e.g. operating multiple sites on the same controller)

  ---

- **site** <sup><sub>string</sub></sup> (optional, default: default)

  Only necessary if you operate multiple sites on the same controller.

  ---

- **host** <sup><sub>string</sub></sup> *REQUIRED*

  IP address of the controller.
    > **Note**
    > Currently implemented regex validation: ```((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}``` [^2] [^3]

  ---

- **username** <sup><sub>string</sub></sup> *REQUIRED*

  A valid username on the controller. At a minimum, this user should have Site Admin level permissions for the Network. It's recommended to create a separate local account to use with this integration.

  ---

- **password** <sup><sub>string</sub></sup> *REQUIRED*

  The password for the above username

  ---

- **port** <sup><sub>string</sub></sup> (optional, default: 443)

  In combination with host, the port at which the controller can be reached. UniFi OS controllers must be accessed on 443.

  ---

- **scan_interval** <sup><sub>string</sub></sup> (optional, default: 600)

  How often, in seconds, Home Assistant should poll the controller.

  ---

- **unifi_os** <sup><sub>boolean</sub></sup> (optional, default: true)

  The *truthiness* of this variable is used to determine api url paths. Set to true (or omit) if your controller is running on UniFi OS; otherwise set to false. Only use this if you're running controller software separately (i.e. Docker, Raspberry Pi, etc).

  ---

- **verify_ssl** <sup><sub>boolean</sub></sup> (optional, default: false)

  The *truthiness* of this variable is used to enable or disable SSL certificate verification. Set to false (or omit) if your Home Assistant instance uses an http-only URL, or you have a self-signed SSL certificate and haven’t installed the CA certificate to enable verification. Otherwise set to true.

  ---

- **monitored_ssids** <sup><sub>list</sub></sup> (optional)

  Using the ```name``` key, any wireless networks included here will have image entities created. The image uses the [Image](https://www.home-assistant.io/integrations/image) native integration released in [2023.7](https://www.home-assistant.io/blog/2023/07/05/release-20237/#image-entities) to display a QR code for joining the wireless network and has attributes including enabled state, controller name, site name, ssid name, network id, password, QR code generation text, and timestamp of last update.

  ---

## Services
### ```unifi_wifi.custom_password```
  | Service data attribute | Optional | Description |
  |---|---|---|
  | controller_name | no | blah blah blah |
  | ssid | no | wireless network whose password you want to change |
  | password | no | set a user-provided password |

  Change WLAN password on UniFi network to a custom string

### ```unifi_wifi.random_password```
  | Service data attribute | Optional | Description |
  |---|---|---|
  | controller_name | no | blah blah blah |
  | ssid | no | wireless network whose password you want to change |
  | method | no | char = alphanumeric string (no spaces); word = diceware passphrase (space separated); xkcd = diceware passphrase using XKCD generator (delimiter separated) |
  | delimiter | yes | use spaces or dashes to separate passphrase words [xkcd only] (default=space) |
  | min_length | yes | minimum word length [xkcd only] (default=5, min=3, max=9) |
  | max_length | yes | maximum word length [xkcd only] (default=8, min=3, max=9) |
  | word_count | yes | number of words to generate [xkcd & word] (default=4, min=3, max=6) |
  | char_count | yes | number of alphanumeric characters to generate [char only] (default=24, min=8, max=63) |

  Change WLAN password on UniFi network to a randomly generated string
  - char --> 24-character alphanumeric string
  - word --> 4-word string, generated from the [EFF large wordlist](https://www.eff.org/files/2016/07/18/eff_large_wordlist.txt) [^4]. This wordfile is located in ```custom_components/unfi_wifi```
  - xkcd --> 4-word string, generated using [xkcdpass](https://pypi.org/project/xkcdpass). By default, xkcdpass only has access to the same wordfile as ```word```. The main benefit of xkcdpass is having more granular control over the length of words chosen and characters used. Currently, this must be changed in ```custom_components/unfi_wifi/password.py```

### ```unifi_wifi.enable_wlan```
  | Service data attribute | Optional | Description |
  |---|---|---|
  | controller_name | no | blah blah blah |
  | ssid | no | wireless network whose password you want to change |
  | enabled | no | enabled = true, disabled = false |

  Enable (or disable) a specific WLAN on a UniFi network controller

[^1]: https://my.home-assistant.io/create-link/
[^2]: https://stackoverflow.com/questions/5284147/validating-ipv4-addresses-with-regexp
[^3]: https://regexr.com/7c1b0
[^4]: https://www.eff.org/dice
