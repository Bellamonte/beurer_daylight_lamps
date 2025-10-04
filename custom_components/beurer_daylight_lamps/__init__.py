from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_MAC

from bleak import BleakScanner, BLEDevice

from .const import DOMAIN, LOGGER
from .beurer_daylight_lamps import BeurerInstance, get_device

PLATFORMS = ["light"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Beurer daylight lamp from a config entry."""
    LOGGER.debug(f"Setting up device from __init__")
    device = await get_device(entry.data[CONF_MAC])
    if device == None:
        LOGGER.error(f"Was not able to find device with mac {entry.data[CONF_MAC]}")
        return False  # Return False instead of continuing with None device

    try:
        instance = BeurerInstance(device)
    except ValueError as e:
        LOGGER.error(f"Failed to create BeurerInstance for {entry.data[CONF_MAC]}: {e}")
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = instance
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        instance = hass.data[DOMAIN].pop(entry.entry_id)
        await instance.disconnect()
    return unload_ok
