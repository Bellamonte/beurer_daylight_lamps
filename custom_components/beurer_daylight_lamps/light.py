import asyncio
import voluptuous as vol
from typing import Any, Optional, Tuple

from custom_components.beurer_daylight_lamps.beurer import BeurerInstance
from custom_components.beurer_daylight_lamps.const import DOMAIN

from homeassistant.const import CONF_MAC
import homeassistant.helpers.config_validation as cv
from homeassistant.components.light import (COLOR_MODE_RGB, PLATFORM_SCHEMA,
                                            LightEntity, ATTR_RGB_COLOR, ATTR_BRIGHTNESS, ATTR_EFFECT, COLOR_MODE_WHITE, ATTR_WHITE, LightEntityFeature)
from homeassistant.util.color import (match_max_scale)
from homeassistant.helpers import device_registry
from custom_components.beurer_daylight_lamps.const import LOGGER

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MAC): cv.string
})

async def async_setup_entry(hass, config_entry, async_add_devices):
    LOGGER.debug(f"Setting up device from lamp")
    instance = hass.data[DOMAIN][config_entry.entry_id]
    async_add_devices([BeurerLight(instance, config_entry.data["name"], config_entry.entry_id)])

class BeurerLight(LightEntity):
    def __init__(self, beurerInstance: BeurerInstance, name: str, entry_id: str) -> None:
        self._instance = beurerInstance
        self._entry_id = entry_id
        self._attr_supported_color_modes = {COLOR_MODE_RGB, COLOR_MODE_WHITE}
        self._color_mode = None
        self._attr_name = name
        self._attr_unique_id = self._instance.mac

    async def async_added_to_hass(self) -> None:
        """Add update callback after being added to hass."""
        self._instance.set_update_callback(self.update_callback)
        await self._instance.update()

    def update_callback(self) -> None:
        """Schedule a state update."""
        #self.async_schedule_update_ha_state(False)
        self.schedule_update_ha_state(False)

    @property
    def available(self):
        return self._instance.is_on != None

    #We handle update triggers manually, do not poll
    @property
    def should_poll(self) -> Optional[bool]:
        return False

    @property
    def brightness(self):
        if self._instance.color_mode == COLOR_MODE_WHITE:
            return self._instance.white_brightness
        else:
            return self._instance.color_brightness
        return None

    @property
    def is_on(self) -> Optional[bool]:
        return self._instance.is_on

    @property
    # RGB color/brightness based on https://github.com/home-assistant/core/issues/51175
    def rgb_color(self):
        if self._instance.rgb_color:
            return match_max_scale((255,), self._instance.rgb_color)
        return None

    @property
    def effect(self):
        if self._instance.color_mode == COLOR_MODE_WHITE:
            return "Off"
        else:
            return self._instance.effect

    @property
    def effect_list(self):
        return self._instance.supported_effects

    @property
    def supported_features(self):
        return LightEntityFeature.EFFECT

    @property
    def color_mode(self):
        return self._instance.color_mode

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self._instance.mac)
            },
            "name": self.name,
            "connections": {(device_registry.CONNECTION_NETWORK_MAC, self._instance.mac)}
        }

    def _transform_color_brightness(self, color: Tuple[int, int, int], set_brightness: int):
        rgb = match_max_scale((255,), color)
        res = tuple(int(color_val * set_brightness // 255) for color_val in rgb)
        return res

    async def async_turn_on(self, **kwargs: Any) -> None:
        LOGGER.debug(f"Turning lamp on with args: {kwargs}")

        # Handle the case where no arguments are provided - just turn on
        if len(kwargs) == 0:
            await self._instance.turn_on()
            return

        # HYBRID FIX: Use the existing methods but with smart mode switching
        current_mode = self._instance.color_mode

        # Determine target mode based on parameters
        target_mode = None
        if ATTR_RGB_COLOR in kwargs or ATTR_EFFECT in kwargs:
            target_mode = COLOR_MODE_RGB
        elif ATTR_BRIGHTNESS in kwargs and ATTR_RGB_COLOR not in kwargs and ATTR_EFFECT not in kwargs:
            target_mode = COLOR_MODE_WHITE

        # Force mode switch by updating internal state if needed
        if target_mode and target_mode != current_mode:
            LOGGER.debug(f"Mode switch required: {current_mode} -> {target_mode}")
            # Update internal mode first
            self._instance._mode = target_mode
            # Reset relevant state flags
            if target_mode == COLOR_MODE_WHITE:
                self._instance._light_on = False
                self._instance._color_on = False
            else:
                self._instance._light_on = False
                self._instance._color_on = False

        # Handle white mode using existing method but with forced mode
        if target_mode == COLOR_MODE_WHITE:
            brightness = kwargs[ATTR_BRIGHTNESS]
            LOGGER.debug(f"Setting white mode with brightness {brightness}")
            # Force the mode and use existing method
            self._instance._mode = COLOR_MODE_WHITE
            await self._instance.set_white(brightness)
            return

        # Handle RGB/effect mode using existing methods
        if target_mode == COLOR_MODE_RGB:
            # Force the mode first
            self._instance._mode = COLOR_MODE_RGB

            # Set color first if provided
            if ATTR_RGB_COLOR in kwargs:
                color = kwargs[ATTR_RGB_COLOR]
                LOGGER.debug(f"Setting RGB color {color}")
                await self._instance.set_color(color)

                # Then handle brightness if provided with color
                if ATTR_BRIGHTNESS in kwargs:
                    brightness = kwargs[ATTR_BRIGHTNESS]
                    LOGGER.debug(f"Setting color brightness {brightness}")
                    await asyncio.sleep(0.2)  # Small delay between operations
                    await self._instance.set_color_brightness(brightness)

            # Handle effect last
            if ATTR_EFFECT in kwargs:
                effect = kwargs[ATTR_EFFECT]
                LOGGER.debug(f"Setting effect {effect}")
                await asyncio.sleep(0.2)  # Small delay before effect
                await self._instance.set_effect(effect)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._instance.turn_off()

    async def async_update(self) -> None:
        await self._instance.update()
