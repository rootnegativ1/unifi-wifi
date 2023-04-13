[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
# Unifi Wifi Home Assistant Integration

Change passwords and generate QR codes for wireless networks on UniFi controllers. The passwords can be custom or randomized using the included services.

## HACS Installation
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rootnegativ1&repository=unifi_wifi&category=integration) [^1]
1. Go to any of the sections (integrations, frontend, automation).
2. Click on the 3 dots in the top right corner.
3. Select "Custom repositories"
4. Add the URL ```https://github.com/rootnegativ1/unifi_wifi``` to the repository.
5. Select the ```integration``` category.
6. Click the "ADD" button.

## Manual Installation
Merge the ```custom_components``` folder with the one in your Home Assistant ```config``` folder

## Configuration
To enable this camera in your installation, add the following to your configuration.yaml file:
```yaml
# Example configuration.yaml entry
unifi_wifi:
  base_url: https://<controller-ip-address>
  username: admin
  password: NotARealPassword
  site: default
  unifi_os: true
  networks:
    - ssid: my-wireless-network
```

### Configuration Variables
**base_url** <sup><sub>string</sub></sup> *REQUIRED*

IP address of the UniFi controller. Do NOT include the port as this is automatically configured based on the *truthiness* of the ```unifi_os``` variable.
  > **Note**
  > This integration currently only supports standard ports (i.e. 443 and 8443) as they are hard-coded. Future revisions will ~include a ```port``` variable and the appropriate logic to support it~ require the port to be included in ```base_url```
___
**username** <sup><sub>string</sub></sup> *REQUIRED*

A valid username on the controller. At a minimum, this user should have Site Admin level permissions for the Network. It's recommended to create a separate local account to use with this integration.
___
**password** <sup><sub>string</sub></sup> *REQUIRED*

The password for the above username
___
**site** <sup><sub>string</sub></sup> (optional, default: default)

Only use this if you've renamed your site or have multiple sites managed by the controller
___
**unifi_os** <sup><sub>boolean</sub></sup> (optional, default: true)

Only use this if you're running controller software separately (i.e. Docker, Raspberry Pi, etc)
___
**networks** <sup><sub>list</sub></sup> (optional)

Using the ```ssid``` key, any wireless networks included here will have binary sensor and camera entities created. The binary sensor indicates whether the network is enabled (on) or disabled (off) and has additional ssid attributes including name, network id, and password. The camera uses the [local_file](https://www.home-assistant.io/integrations/local_file/) native integration to display a QR code for joining the wireless network
___

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
  - word --> 4-word string, generated from the [EFF large wordlist](https://www.eff.org/files/2016/07/18/eff_large_wordlist.txt) [^2]
  - xkcd --> 4-word string, generated using [xkcdpass](https://pypi.org/project/xkcdpass)

### ```unifi_wifi.refresh_networks```
  | Service data attribute | Optional | Description |
  |---|---|---|
  | none | | |

lorem ipsum --> needed to refresh changes made directly on the contoller
[^1]: https://my.home-assistant.io/create-link/
[^2]: https://www.eff.org/dice
