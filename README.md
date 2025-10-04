# beurer_daylight_lamps
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/Bellamonte/beurer_daylight_lamps)
![Hassfest](https://github.com/Bellamonte/beurer_daylight_lamps/actions/workflows/hassfest.yaml/badge.svg)
![HACS](https://github.com/Bellamonte/beurer_daylight_lamps/actions/workflows/hacs.yml/badge.svg)

Home Assistant integration for BLE based Beurer daylight lamps

Supports controlling BLE based lights controllable through the Beurer LightUp app. Currently tested and directly supported with TL100 only.

## Installation

Note: Restart is always required after installation.

### [HACS](https://hacs.xyz/) (recommended)
Installation can be done through [HACS custom repository](https://hacs.xyz/docs/faq/custom_repositories).

### Manual installation
You can manually clone this repository and then copy the whole directory `custom_components/beurer_daylight_lamps` into `config/custom_components/`.

For example:
```
git clone https://github.com/Bellamonte/beurer_daylight_lamps beurer_daylight_lamps
cd beurer_daylight_lamps/custom_components/beurer_daylight_lamps
mkdir -p ~/homeassistant/config/custom_components/beurer_daylight_lamps
cp -r * ~/homeassistant/config/custom_components/beurer_daylight_lamps/
```

## Setup
After installation, you should find "Beurer Daylight Lamps" under the Configuration -> Integrations -> Add integration.

The setup step includes discovery which will list out all Beurer daylight lamps discovered. The setup will validate connection by toggling the selected light. Make sure your light is in-sight to validate this.

The setup needs to be repeated for each lamp.

## Features
1. Discovery: Automatically discover Beurer daylight lamps without manually hunting for Bluetooth MAC address
2. On/Off/RGB/Brightness support
3. Multiple lamp support
4. Light modes (Rainbow, Pulse, Forest, ..) as found in the app

## Known issues
1. Light connection may fail a few times after Home Assistant reboot. The integration will usually reconnect and the issue will resolve itself.
2. The rightmost LED, which signals Bluetooth connection, on the lamp will always be on.
   This is because HomeAssistant will always be connected to the lamp, use black duct tape if you want the lamp to be completely dark.

## Not supported
Timers for automatic turn off of the lamp are currently not supported. 
Use HomeAssistant automations if you need this functionality.

## Debugging
Add the following to `configuration.yml` to show debugging logs. Please make sure to include debug logs when filing an issue.

See [logger intergration docs](https://www.home-assistant.io/integrations/logger/) for more information to configure logging.

```yml
logger:
  default: warn
  logs:
    custom_components.beurer_daylight_lamps: debug
```

## Credits
This integration is a fork of [jmac83 ha-beurer integration](https://github.com/jmac83/ha-beurer), which itself is a fork of [deadolus ha-beurer integration](https://github.com/deadolus/ha-beurer), which itself is a fork of [sysofwan ha-triones integration](https://github.com/sysofwan/ha-triones), whose framework I used for this Beurer daylight lamp integration. 

Additional help on [deadolus ha-beurer integration](https://github.com/deadolus/ha-beurer) by: 
- [@pyromaniac2k](https://github.com/pyromaniac2k)
- [@ALandOfDodd](https://github.com/LandOfDodd)
