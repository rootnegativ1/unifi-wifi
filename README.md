[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/rootnegativ1/unifi_wifi?color=green&style=for-the-badge)

# Unifi Wifi Home Assistant Integration

Change passwords and generate QR codes for WLANs on UniFi Network controllers. Passwords can be custom or random strings using the included services. QR codes are located in ```/config/www```

## HACS Installation
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rootnegativ1&repository=unifi_wifi&category=integration) [^1]
1. Go to any of the sections (integrations, frontend, automation).
2. Click on the 3 dots in the top right corner.
3. Select "Custom repositories"
4. Add the URL ```https://github.com/rootnegativ1/unifi_wifi``` to the repository.
5. Select the ```integration``` category.
6. Click the "ADD" button.

## Configuration
To enable this component in your installation, add the following to your configuration.yaml file:
```yaml
# Example configuration.yaml entry
unifi_wifi:
  base_url: https://192.168.1.1:443
  username: local.admin
  password: NotARealPassword
  site: unclebuckshouse
  unifi_os: false
  networks:
    - ssid: my-wireless-network
```

### Configuration Variables
- **base_url** <sup><sub>string</sub></sup> *REQUIRED*

  IP address and port of the controller. Should be of the form ```https://<ip-address>:<port>```. UniFi OS based controllers must use port 443.
    > **Note**
    > Currently implemented regex validation: ```https:\/\/((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}:\d+``` [^2] [^3]

  ---

- **username** <sup><sub>string</sub></sup> *REQUIRED*

  A valid username on the controller. At a minimum, this user should have Site Admin level permissions for the Network. It's recommended to create a separate local account to use with this integration.

  ---

- **password** <sup><sub>string</sub></sup> *REQUIRED*

  The password for the above username

  ---

- **site** <sup><sub>string</sub></sup> (optional, default: default)

  Only use this if you've renamed your site or have multiple sites managed by the controller

  ---

- **unifi_os** <sup><sub>boolean</sub></sup> (optional, default: true)

  The *truthiness* of this variable is used to determine api url paths. Set to true (or omit) if your controller is running on UniFi OS; otherwise set to false. Only use this if you're running controller software separately (i.e. Docker, Raspberry Pi, etc).

  ---

- **networks** <sup><sub>list</sub></sup> (optional)

  Using the ```ssid``` key, any wireless networks included here will have binary sensor and camera entities created. The binary sensor indicates whether the network is enabled (on) or disabled (off) and has additional attributes including ssid name, network id, and password. The camera uses the [local_file](https://www.home-assistant.io/integrations/local_file/) native integration to display a QR code for joining the wireless network.

  ---

## Services
### ```unifi_wifi.custom_password```
  | Service data attribute | Optional | Description |
  |---|---|---|
  | SSID | no | STRING wireless network whose password you want to change  |
  | password | no | STRING set a user-provided password |

### ```unifi_wifi.random_password```
  | Service data attribute | Optional | Description |
  |---|---|---|
  | SSID | no | STRING wireless network whose password you want to change  |
  | method | no | STRING method to generate password. One of: char, word, or xkcd |

  - char --> 24-character alphanumeric string
  - word --> 4-word string, generated from the [EFF large wordlist](https://www.eff.org/files/2016/07/18/eff_large_wordlist.txt) [^4]. This wordfile is located in ```custom_components/unfi_wifi```
  - xkcd --> 4-word string, generated using [xkcdpass](https://pypi.org/project/xkcdpass). By default, xkcdpass only has access to the same wordfile as ```word```. The main benefit of xkcdpass is having more granular control over the types of words chosen and characters used. Currently, this must be changed in ```custom_components/unfi_wifi/password.py```

### ```unifi_wifi.refresh_networks```
  | Service data attribute | Optional | Description |
  |---|---|---|
  | none | | |

  Whenever WLAN settings (i.e. passwords) are changed directly on the controller, use this service to update the binary sensor and camera entities

[^1]: https://my.home-assistant.io/create-link/
[^2]: https://stackoverflow.com/questions/5284147/validating-ipv4-addresses-with-regexp
[^3]: https://regexr.com/7c1b0
[^4]: https://www.eff.org/dice
