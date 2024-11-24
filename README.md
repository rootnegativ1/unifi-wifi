[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/rootnegativ1/unifi-wifi?color=green&style=for-the-badge)](https://github.com/rootnegativ1/unifi-wifi/releases/latest)
[![Github All Releases](https://img.shields.io/github/downloads/rootnegativ1/unifi-wifi/total.svg?&style=for-the-badge)]()

# Unifi Wifi Home Assistant Integration
Change SSID passwords and private preshared keys (PPSKs) as well as generate QR codes for them on UniFi Network controllers. Passwords & PPSKs can be custom or random strings using the included actions. QR codes are represented as image entities and generated per network SSID. These images are located in ```/config/www```. If a password is changed through the controller-side web UI, the associated QR code is automatically updated in Home Assistant.

## Manual Installation
Download the contents of ```custom_components``` to your ```/config/custom_components``` directory

## HACS Installation
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rootnegativ1&repository=unifi-wifi&category=integration) [^1]
1. Go to any of the sections (integrations, frontend, automation)
2. Click on the 3 dots in the top right corner
3. Select "Custom repositories"
4. Add the URL ```https://github.com/rootnegativ1/unifi-wifi``` to the repository
5. Select the ```integration``` category
6. Click the "ADD" button

## Configuration
To enable this component, add the following to your configuration.yaml file:
```yaml
# Example configuration.yaml entry
unifi_wifi:
  - name: myhouse
    host: 192.168.1.1
    port: 443
    username: local.admin
    password: NotARealPassword
    site: default
    scan_interval: 300
    timeout: 20
    unifi_os: true
    verify_ssl: false
    force_provision: false
    managed_aps:
      - name: udm
        mac: !secret unifi_udm_mac
      - name: u6lite
        mac: !secret unifi_u6l_mac
    monitored_ssids:
      - name: LAN-of-the-living
        fill_color: '#aaaaaa' # omit for default value #000000
        back_color: '#bbbbbb' # omit for default value #ffffff
        file_output: false
      - name: my-ppsk-ssid
        # fill_color: '#a432a8' # does nothing; ignored by any preshared keys
        # back_color: '#32a852' # does nothing; ignored by any preshared keys
        # file_output: false # does nothing; ignored by any preshared keys
        preshared_keys:
          - name: Guest
            fill_color: '#cccccc'
            back_color: '#dddddd'
          - name: IoT
            fill_color: '#eeeeee'
          - name: NoT
            file_output: false
```

### Configuration Variables
- **name** <sup><sub>string</sub></sup> *REQUIRED* &nbsp; Unique name to identify each host + site combo (e.g. operating multiple sites on the same controller or managing multiple controllers)

- **host** <sup><sub>string</sub></sup> *REQUIRED* &nbsp; Hostname or IP address of the controller.

- **username** <sup><sub>string</sub></sup> *REQUIRED* &nbsp; A valid username on the controller. At a minimum, this user should have Site Admin level permissions for the Network. It's recommended to create a separate local account to use with this integration.

- **password** <sup><sub>string</sub></sup> *REQUIRED* &nbsp; The password for the above username

- **site** <sup><sub>string</sub></sup> (optional, default: default) &nbsp; Only necessary if you operate multiple sites on the same controller.

- **port** <sup><sub>string</sub></sup> (optional, default: 443) &nbsp; In combination with host, the port at which the controller can be reached. UniFi OS controllers must be accessed on 443.

- **scan_interval** <sup><sub>string</sub></sup> (optional, default: 600) &nbsp; How often, in seconds, Home Assistant should poll the controller.

  > *If you change a password through the controller UI multiple times before ```scan_interval``` triggers an update, only the last change will be detected.*

- **timeout** <sup><sub>string</sub></sup> (optional, default: 10) &nbsp; How many seconds an update request to the controller will wait before timing out.

- **unifi_os** <sup><sub>boolean</sub></sup> (optional, default: true) &nbsp; The *truthiness* of this variable is used to determine API url paths. Set to true (or omit) if your controller is running on UniFi OS; otherwise set to false. Only use this if you're running controller software separately (i.e. Docker, Raspberry Pi, etc).

- **verify_ssl** <sup><sub>boolean</sub></sup> (optional, default: false) &nbsp; The *truthiness* of this variable is used to enable or disable SSL certificate verification. Set to false (or omit) if your Home Assistant instance uses an http-only URL, or you have a self-signed SSL certificate and haven’t installed the CA certificate to enable verification. Otherwise set to true.

- **force_provision** <sup><sub>boolean</sub></sup> (optional, default: false) &nbsp; The *truthiness* of this variable is used to enable or disable automatic force provisioning of adopted access points. Used in combination with ```managed_aps```, only the access points listed with be re-provisioned. If ```managed_aps``` is omitted, all access points adopted by the controller at the site will be re-provisioned. If set to false (or omitted), provisioning will be handled by the controller.

- **managed_aps** <sup><sub>list</sub></sup> (optional) &nbsp; List of access points to force provision after changing an SSID password.
   - **name** <sup><sub>string</sub></sup> *REQUIRED* &nbsp; a user generated name which is mainly used for log output
   - **mac** <sup><sub>string</sub></sup> *REQUIRED* &nbsp; the MAC address of the access point which can be found in the contorller UI

- **monitored_ssids** <sup><sub>list</sub></sup> (optional) &nbsp; Any wireless networks included here will have image entities created. The image uses the [Image](https://www.home-assistant.io/integrations/image) native integration released in [2023.7](https://www.home-assistant.io/blog/2023/07/05/release-20237/#image-entities) to display a QR code for joining the wireless network and has attributes including enabled state, controller name, site name, ssid name, network id, password, ppsk status, QR code generation text, and timestamp of last update.
   - **name** <sup><sub>string</sub></sup> *REQUIRED* &nbsp; Name of the image entity to be created. This will be prefaced with the coordinator name
   - **fill_color** <sup><sub>hex</sub></sup> (optional, default: #000000 AKA black) &nbsp; The color of the QR code
   - **back_color** <sup><sub>hex</sub></sup> (optional, default: #ffffff AKA white) &nbsp; The background color of the QR code
   - **file_output** <sup><sub>boolean</sub></sup> (optional, default: true) &nbsp; control whether or not a PNG file is created in the ```www``` directory
   - **qr_quality** <sup><sub>char</sub></sup> (optional, default: M) &nbsp; control the amount of error correction in the generated QR code. Possible options are: L, M, Q, H
  
   - **preshared_keys** <sup><sub>list</sub></sup> (optional, default: image entities generated for all preshared keys) &nbsp; If you want to create images only for specific PPSK-enabled VLANs, then create a list of networks below.
      > *When adding a PPSK-enabled SSID, images for each __unique__ PPSK-connected VLAN will be created by default. This means if you have multiple passwords connecting to the same network, only the __first__ password will be used.
      - **name** <sup><sub>string</sub></sup> *REQUIRED* &nbsp; Name of the image entity to be created. This will be prefaced with the coordinator and parent SSID names
      - **fill_color** <sup><sub>hex</sub></sup> (optional, default: #000000 AKA black) &nbsp; The color of the QR code
      - **back_color** <sup><sub>hex</sub></sup> (optional, default: #ffffff AKA white) &nbsp; The background color of the QR code
      - **file_output** <sup><sub>boolean</sub></sup> (optional, default: true) &nbsp; control if a PNG file is created in the ```www``` directory
      - **qr_quality** <sup><sub>boolean</sub></sup> (optional, default: M) &nbsp; control the amount of error correction in the generated QR code. Possible options are: L, M, Q, H

## Actions

### ```unifi_wifi.custom_password```
#### *DEPRECRATED*
  | Action data attribute | Optional | Description |
  |---|---|---|
  | target | no | image entity of wireless network whose password you want to change. Multiple entities are possible using the ```entity_id``` key. |
  | password | no | user-provided password |

  Change SSID password(s) on UniFi network to a custom string. New passwords must contain only ASCII characters and be between 8 and 63 characters in length.

  ```yaml
    action: unifi_wifi.custom_password
    data:
      target:
        entity_id:
          - image.myhouse_guest_wifi
          - image.myhouse_testnetworkppsk_guest_wifi
      password: thisISaTesT
  ```
  
  > [!NOTE]
  > *If you try setting private preshared keys on the same SSID to the same password, ~~only the first VLAN (alphabetically) will have its password changed~~ the integration will create an error warning the user duplicate passwords are not allowed on the same SSID.*

### ```unifi_wifi.random_password```
#### *DEPRECRATED*
  | Action data attribute | Optional | Description |
  |---|---|---|
  | target | no | image entity of wireless network whose password you want to change. Multiple entities are possible using the ```entity_id``` key. |
  | method | yes | char = alphanumeric string (no spaces); word = diceware passphrase (delimiter separated); xkcd = diceware passphrase using XKCD generator (delimiter separated) (default=word) |
  | delimiter | yes | use spaces or dashes to separate passphrase words [xkcd & word] (default=dash) |
  | min_length | yes | minimum word length [xkcd only] (default=5, min=3, max=9) |
  | max_length | yes | maximum word length [xkcd only] (default=8, min=3, max=9) |
  | word_count | yes | number of words to generate [xkcd & word] (default=4, min=3, max=6) |
  | char_count | yes | number of alphanumeric characters to generate [char only] (default=24, min=8, max=63) |

  Change SSID password on UniFi network to a randomly generated string
  - char --> 24-character alphanumeric string
  - word --> 4-word string, generated from the [EFF large wordlist](https://www.eff.org/files/2016/07/18/eff_large_wordlist.txt) [^2]. This wordfile is located in ```custom_components/unfi_wifi```
  - xkcd --> 4-word string, generated using [xkcdpass](https://pypi.org/project/xkcdpass). By default, xkcdpass only has access to the same wordfile as ```word```. The benefit of xkcdpass is having control over the length of words chosen.

  ```yaml
    action: unifi_wifi.random_password
    data:
      target:
        entity_id:
          - image.myhouse_guest_wifi
          - image.myhouse_testnetworkppsk_guest_wifi
      method: word
  ```

  > [!NOTE]
  > *Randomizing multiple private preshared keys on the same SSID will result in multiple random passwords generated. In the unlikely event multiple randomly created passwords are identical, the integration will create an error and not complete the action.*

### ```unifi_wifi.enable_wlan```
  | Action data attribute | Optional | Description |
  |---|---|---|
  | target | no | image entity of wireless network whose password you want to change. Multiple entities are possible using the ```entity_id``` key. |
  | enabled | no | enabled = true, disabled = false |

  Enable (or disable) a specific SSID on a UniFi network controller. *For this change to take effect properly, all (managed) access points will be re-provisioned regardless of the value of ```force_provision```.*

  ```yaml
    action: unifi_wifi.enable_wlan
    data:
      target:
        entity_id:
          - image.myhouse_guest_wifi
          - image.myhouse_testnetworkppsk_guest_wifi
      enabled: false
  ```

  > [!IMPORTANT]
  > *Disabling a PPSK network will disable its SSID which will disable all other associated PPSK networks; the same applies when enabling.*

### ```unifi_wifi.hide_ssid```
  | Action data attribute | Optional | Description |
  |---|---|---|
  | target | no | image entity of wireless network whose password you want to change. Multiple entities are possible using the ```entity_id``` key. |
  | hide_ssid | no | enabled = true, disabled = false |

  Enable (or disable) hiding a specific SSID on a UniFi network controller. *For this change to take effect properly, all (managed) access points will be re-provisioned regardless of the value of ```force_provision```.*

  ```yaml
    action: unifi_wifi.hide_ssid
    data:
      target:
        entity_id:
          - image.myhouse_guest_wifi
          - image.myhouse_testnetworkppsk_guest_wifi
      hide_ssid: false
  ```

  > [!IMPORTANT]
  > *Hiding a PPSK network will hide its SSID which will also hide all other associated PPSK networks; the same applies when unhiding.*

### ```unifi_wifi.hotspot_password```
  | Action data attribute | Optional | Description |
  |---|---|---|
  | coordinator | no | coordinator whose hotspot password you want to change. Limited to one coordinator per action |
  | password | yes | user-provided password (min=8, max=63). If provided, this will override any random settings. |
  | random | yes | Should a randomly generated password be created (default=True) |
  | method | yes | char = alphanumeric string (no spaces); word = diceware passphrase (delimiter separated); xkcd = diceware passphrase using XKCD generator (delimiter separated) (default=word) |
  | delimiter | yes | use spaces or dashes to separate passphrase words [xkcd & word] (default=dash) |
  | min_length | yes | minimum word length [xkcd only] (default=5, min=3, max=9) |
  | max_length | yes | maximum word length [xkcd only] (default=8, min=3, max=9) |
  | word_count | yes | number of words to generate [xkcd & word] (default=4, min=3, max=6) |
  | char_count | yes | number of alphanumeric characters to generate [char only] (default=24, min=8, max=63) |

  Change hotspot password on UniFi network to a randomly generated string
  - char --> 24-character alphanumeric string
  - word --> 4-word string, generated from the [EFF large wordlist](https://www.eff.org/files/2016/07/18/eff_large_wordlist.txt) [^2]. This wordfile is located in ```custom_components/unfi_wifi```
  - xkcd --> 4-word string, generated using [xkcdpass](https://pypi.org/project/xkcdpass). By default, xkcdpass only has access to the same wordfile as ```word```. The benefit of xkcdpass is having control over the length of words chosen.

  ```yaml
    action: unifi_wifi.hotspot_password
    data:
      coordinator: myhouse
      password: Hell0WoLRditsM3
  ```

### ```unifi_wifi.wlan_password```
  | Action data attribute | Optional | Description |
  |---|---|---|
  | target | no | image entity of wireless network whose password you want to change. Multiple entities are possible using the ```entity_id``` key. |
  | password | yes | user-provided password (min=8, max=63). If provided, this will override any random settings. |
  | random | yes | Should a randomly generated password be created (default=True) |
  | method | yes | char = alphanumeric string (no spaces); word = diceware passphrase (delimiter separated); xkcd = diceware passphrase using XKCD generator (delimiter separated) (default=word) |
  | delimiter | yes | use spaces or dashes to separate passphrase words [xkcd & word] (default=dash) |
  | min_length | yes | minimum word length [xkcd only] (default=5, min=3, max=9) |
  | max_length | yes | maximum word length [xkcd only] (default=8, min=3, max=9) |
  | word_count | yes | number of words to generate [xkcd & word] (default=4, min=3, max=6) |
  | char_count | yes | number of alphanumeric characters to generate [char only] (default=24, min=8, max=63) |

  Change SSID password on UniFi network to a randomly generated string
  - char --> 24-character alphanumeric string
  - word --> 4-word string, generated from the [EFF large wordlist](https://www.eff.org/files/2016/07/18/eff_large_wordlist.txt) [^2]. This wordfile is located in ```custom_components/unfi_wifi```
  - xkcd --> 4-word string, generated using [xkcdpass](https://pypi.org/project/xkcdpass). By default, xkcdpass only has access to the same wordfile as ```word```. The benefit of xkcdpass is having control over the length of words chosen.

  ```yaml
    action: unifi_wifi.wlan_password
    data:
      target:
        entity_id:
          - image.myhouse_guest_wifi
          - image.myhouse_testnetworkppsk_guest_wifi
      method: word
  ```

## Logging
Debug logs can be enabled with the following in ```configuration.yaml```

```yaml
logger:
  logs:
    custom_components.unifi_wifi: debug
```

> [!WARNING]
> In addition to the above, there is extra level of debugging in each of ```coordinator.py```, ```image.py```, and ```services.py```. It can be enabled by setting ```EXTRA_DEBUG = True``` in whichever file(s) you want to debug. This will expose usernames and passwords! It is intended ONLY TO VERIFY message content to and from a controller. Only use when needed, and **disable immediately afterwards**.

[^1]: https://my.home-assistant.io/create-link/
[^2]: https://www.eff.org/dice
