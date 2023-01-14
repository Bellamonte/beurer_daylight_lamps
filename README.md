# ha-beurer
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/deadolus/ha-beurer)
![Hassfest](https://github.com/deadolus/ha-beurer/actions/workflows/hassfest.yaml/badge.svg)
![HACS](https://github.com/deadolus/ha-beurer/actions/workflows/hacs.yml/badge.svg)

Home Assistant integration for BLE based Beurer TL100/wellbeing/Daylight therapy lamp

Supports controlling BLE based lights controllable through the Beurer LightUp app.

## Installation

Note: Restart is always required after installation.

### [HACS](https://hacs.xyz/) (recommended)
Installation can be done through [HACS custom repository](https://hacs.xyz/docs/faq/custom_repositories).

### Manual installation
You can manually clone this repository inside `config/custom_components/beurer`.

For  example, from Terminal plugin:
```
cd /config/custom_components
git clone https://github.com/deadolus/ha-beurer beurer
```

## Setup
After installation, you should find Beurer under the Configuration -> Integrations -> Add integration.

The setup step includes discovery which will list out all Beurer lights discovered. The setup will validate connection by toggling the selected light. Make sure your light is in-sight to validate this.

The setup needs to be repeated for each light.

## Features
1. Discovery: Automatically discover Beurer based lights without manually hunting for Bluetooth MAC address
2. On/Off/RGB/Brightness support
3. Multiple light support
4. Light modes (Rainbow, Pulse, Forest, ..) as found in the app

## Known issues
1. Light connection may fail a few times after Home Assistant reboot. The integration will usually reconnect and the issue will resolve itself.
2. After toggling lights, Home Assistant may not reflect state changes for up to 30 seconds. This is due to a lag in Beurer status API.

## Debugging
Add the following to `configuration.yml` to show debugging logs. Please make sure to include debug logs when filing an issue.

See [logger intergration docs](https://www.home-assistant.io/integrations/logger/) for more information to configure logging.

```yml
logger:
  default: warn
  logs:
    custom_components.beurer: debug
```

## Credits
This integration will is a fork of [sysofwan ha-triones integration](https://github.com/sysofwan/ha-triones), whose framework I used for this Beurer integration
