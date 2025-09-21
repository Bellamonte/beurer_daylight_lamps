from typing import Tuple, Callable
from bleak import BleakClient, BleakScanner, BLEDevice, BleakGATTCharacteristic, BleakError
import traceback
import asyncio

# Assuming COLOR_MODE_RGB and COLOR_MODE_WHITE are defined,
# if not, you might need to define them or handle modes differently.
# from homeassistant.components.light import (COLOR_MODE_RGB, COLOR_MODE_WHITE)
# For standalone, let's define them simply if not available from HA context
try:
    from homeassistant.components.light import (COLOR_MODE_RGB, COLOR_MODE_WHITE)
except ImportError:
    COLOR_MODE_RGB = "rgb"
    COLOR_MODE_WHITE = "white"


# Assuming LOGGER is defined, e.g., from .const or basic logging setup
# from .const import LOGGER
import logging
LOGGER = logging.getLogger(__name__)
# Basic config if running standalone and LOGGER wasn't set up by HA
if not LOGGER.hasHandlers():
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


WRITE_CHARACTERISTIC_UUIDS = ["8b00ace7-eb0b-49b0-bbe9-9aee0a26e1a3"]
READ_CHARACTERISTIC_UUIDS  = ["0734594a-a8e7-4b1a-a6b1-cd5243059a57"]

async def discover():
    devices = await BleakScanner.discover()
    LOGGER.debug("Discovered devices: %s", [{"address": device.address, "name": device.name} for device in devices])
    return [device for device in devices if device.name and device.name.lower().startswith("tl100")]

async def get_device(mac: str) -> BLEDevice | None:
    # More robust get_device
    try:
        device = await BleakScanner.find_device_by_address(mac, timeout=10.0)
        if device:
            LOGGER.debug(f"Found device by MAC via find_device_by_address: {device.address} - {device.name}")
            return device
    except BleakError as e:
        LOGGER.debug(f"BleakError with find_device_by_address for {mac}: {e}. Falling back to full scan.")
    except Exception as e: # Catch other potential errors from find_device_by_address
        LOGGER.debug(f"Exception with find_device_by_address for {mac}: {e}. Falling back to full scan.")


    LOGGER.debug(f"Performing full scan to find MAC: {mac}")
    devices = await BleakScanner.discover(timeout=10.0)
    LOGGER.debug(f"Full scan discovered: {[{'address': d.address, 'name': d.name} for d in devices]}")
    return next((device for device in devices if device.address.lower()==mac.lower()),None)

class BeurerInstance:
    def __init__(self, device: BLEDevice) -> None:
        if device is None:
            LOGGER.error("BeurerInstance initialized with None device object.")
            # Potentially raise an error here or handle this state carefully
            # For now, we'll let it proceed but it will likely fail on connect
            self._mac = "UNKNOWN (None Device)"
            self._device = None # Mark that we don't have a valid BleakClient target
            return

        self._mac = device.address
        self._device_ble_object = device # Store the original BLEDevice
        self._device = BleakClient(device, disconnected_callback=self.disconnected_callback)
        self._trigger_update = None
        self._is_on = False
        self._light_on = False # Initialize explicitly
        self._color_on = False # Initialize explicitly
        self._rgb_color = (0,0,0)
        self._brightness = None
        self._color_brightness = None
        self._effect = "Off" # Initialize to "Off"
        self._write_uuid = None
        self._read_uuid = None
        self._mode = COLOR_MODE_WHITE # Default to a mode, e.g., white
        self._supported_effects = ["Off", "Random", "Rainbow", "Rainbow Slow", "Fusion", "Pulse", "Wave", "Chill", "Action", "Forest", "Summer"]
        
        # Defer connection to an explicit call rather than __init__ for more control
        # asyncio.create_task(self.connect())

    def disconnected_callback(self, client):
        LOGGER.debug(f"Disconnected callback called for {self._mac}")
        self._is_on = False
        self._light_on = False
        self._color_on = False
        self._write_uuid = None
        self._read_uuid = None
        if self._trigger_update: # Check if callback is set
            asyncio.create_task(self.trigger_entity_update())

    def set_update_callback(self, trigger_update: Callable):
        LOGGER.debug(f"Setting update callback to {trigger_update}")
        self._trigger_update = trigger_update

    async def _write(self, data: bytearray):
        if not self._device or not self._device.is_connected:
            LOGGER.warning(f"_write called but device not connected or not initialized. Attempting connect for {self._mac}.")
            if not await self.connect(): # connect() should handle self._device being None
                LOGGER.error(f"Failed to connect in _write for {self._mac}. Cannot write.")
                return
        
        if not self._write_uuid:
            LOGGER.error(f"Write UUID not set for {self._mac}. Cannot write. Please ensure connection and characteristic discovery succeeded.")
            return

        LOGGER.debug("Sending in write: " + ''.join(format(x, '02x') for x in data)+f" to characteristic {self._write_uuid}")
        try:
            await self._device.write_gatt_char(self._write_uuid, data)
        except BleakError as error:
            track = traceback.format_exc()
            LOGGER.debug(f"BleakError track for write: {track}")
            LOGGER.warning(f"BleakError while trying to write to device {self._mac}: {error}")
            await self.disconnect() # Disconnect on write error
        except Exception as e:
            track = traceback.format_exc()
            LOGGER.debug(f"Exception track for write: {track}")
            LOGGER.error(f"Unexpected error during write to {self._mac}: {e}")
            await self.disconnect()


    @property
    def mac(self): return self._mac
    @property
    def is_on(self): return self._is_on
    @property
    def rgb_color(self): return self._rgb_color
    @property
    def color_brightness(self): return self._color_brightness
    @property
    def white_brightness(self): return self._brightness
    @property
    def effect(self): return self._effect
    @property
    def color_mode(self): return self._mode
    @property
    def supported_effects(self): return self._supported_effects

    def find_effect_position(self, effect: str | None) -> int:
        if effect is None:
            LOGGER.debug("find_effect_position received None, defaulting to 'Off'.")
            effect_to_find = "Off"
        else:
            effect_to_find = effect
        try:
            return self._supported_effects.index(effect_to_find)
        except ValueError:
            LOGGER.warning(f"Effect '{effect_to_find}' not found in supported_effects. Defaulting to 'Off' (index 0).")
            return 0

    def makeChecksum(self, b: int, bArr: list[int]) -> int:
        for b2 in bArr:
            b = b ^ b2
        return b

    async def sendPacket(self, message: list[int]):
        if not self._device or not self._device.is_connected: # Check self._device too
            LOGGER.warning(f"sendPacket: Device not connected for {self._mac}. Attempting connect.")
            if not await self.connect():
                LOGGER.error(f"sendPacket: Failed to connect for {self._mac}. Cannot send.")
                return

        length=len(message)
        checksum = self.makeChecksum(length+2,message)
        packet_data=bytearray([0xFE,0xEF,0x0A,length+7,0xAB,0xAA,length+2]+message+[checksum,0x55,0x0D,0x0A])
        # Using print for HA logs is not ideal, prefer LOGGER.debug
        LOGGER.debug("Sending message (packet): "+''.join(format(x, '02x') for x in packet_data))
        await self._write(packet_data)

    async def set_color(self, rgb: Tuple[int, int, int]):
        r, g, b = rgb
        LOGGER.debug(f"Setting to color: R={r}, G={g}, B={b} for {self._mac}")
        self._mode = COLOR_MODE_RGB
        self._rgb_color = (r,g,b)
        if not self._is_on or not self._color_on: # If not on, or not in color mode, turn_on will handle it
            await self.turn_on() # turn_on will set the mode to RGB if it's not already
        await self.sendPacket([0x32,r,g,b])
        await asyncio.sleep(0.15) # Slightly increased delay
        await self.triggerStatus()

    async def set_color_brightness(self, brightness: int | None):
        LOGGER.debug(f"set_color_brightness called with: {brightness} for {self._mac}")
        actual_brightness_to_set = brightness
        if actual_brightness_to_set is None:
            LOGGER.warning(f"set_color_brightness for {self._mac} received None, defaulting to 255 (100%).")
            actual_brightness_to_set = 255
        
        self._mode = COLOR_MODE_RGB
        self._color_brightness = actual_brightness_to_set

        if not self._is_on or not self._color_on:
            await self.turn_on()
        
        brightness_0_100 = max(0, min(100, int(actual_brightness_to_set / 255 * 100)))
        await self.sendPacket([0x31,0x02, brightness_0_100])
        await asyncio.sleep(0.15)
        await self.triggerStatus()

    async def set_white(self, intensity: int | None):
        LOGGER.debug(f"Setting white to intensity: {intensity} for {self._mac}")
        actual_intensity_to_set = intensity
        if actual_intensity_to_set is None:
            LOGGER.warning(f"set_white for {self._mac} received None, defaulting to 255 (100%).")
            actual_intensity_to_set = 255

        self._mode = COLOR_MODE_WHITE
        self._brightness = actual_intensity_to_set

        if not self._is_on or not self._light_on:
            await self.turn_on()
        
        intensity_0_100 = max(0, min(100, int(actual_intensity_to_set / 255 * 100)))
        await self.sendPacket([0x31,0x01, intensity_0_100])
        await asyncio.sleep(0.2)
        await self.set_effect("Off") # This also calls triggerStatus
        # await self.triggerStatus() # Not needed as set_effect calls it

    async def set_effect(self, effect: str | None):
        actual_effect = effect
        if actual_effect is None:
            LOGGER.debug(f"set_effect for {self._mac} received None, defaulting to 'Off'.")
            actual_effect = "Off"
        
        LOGGER.debug(f"Setting effect to '{actual_effect}' for {self._mac}")
        self._mode = COLOR_MODE_RGB # Effects are for color mode
        self._effect = actual_effect # Store the effect we are setting

        if not self._is_on or not self._color_on:
            await self.turn_on()
            
        await self.sendPacket([0x34, self.find_effect_position(actual_effect)])
        await asyncio.sleep(0.15)
        await self.triggerStatus()

    async def turn_on(self):
        LOGGER.debug(f"Turning ON for {self._mac}. Current mode: {self._mode}, is_on: {self._is_on}, light_on: {self._light_on}, color_on: {self._color_on}")
        if not self._device or not self._device.is_connected:
            if not await self.connect():
                LOGGER.error(f"Failed to connect in turn_on for {self._mac}. Cannot turn on.")
                return

        if self._mode == COLOR_MODE_WHITE:
            await self.sendPacket([0x37,0x01])
            self._light_on = True
            self._color_on = False # Explicitly set other mode off
        else: # COLOR_MODE_RGB or default
            self._mode = COLOR_MODE_RGB # Ensure mode is RGB if not white
            await self.sendPacket([0x37,0x02])
            self._color_on = True
            self._light_on = False # Explicitly set other mode off
            
            # Only restore state if it was truly off before this call, to avoid command loops
            if not self._is_on: # Check overall _is_on state before it's set to True
                LOGGER.debug(f"Restoring last known color state for {self._mac} as it was previously off.")
                await asyncio.sleep(0.2) # Give time for mode switch
                
                effect_to_restore = self._effect if self._effect is not None else "Off"
                LOGGER.debug(f"Restoring effect: {effect_to_restore}")
                await self.set_effect(effect_to_restore) # set_effect handles None
                await asyncio.sleep(0.2)

                rgb_to_restore = self._rgb_color if self._rgb_color != (0,0,0) else (255,255,255) # Default to white if (0,0,0)
                LOGGER.debug(f"Restoring color: {rgb_to_restore}")
                await self.set_color(rgb_to_restore)
                await asyncio.sleep(0.2)
                
                brightness_to_restore = self._color_brightness
                LOGGER.debug(f"Restoring color brightness: {brightness_to_restore}")
                await self.set_color_brightness(brightness_to_restore) # set_color_brightness handles None

        self._is_on = True # Set overall on state
        await asyncio.sleep(0.2)
        await self.triggerStatus()

    async def turn_off(self):
        LOGGER.debug(f"Turning OFF for {self._mac}")
        await self.sendPacket([0x35,0x01])
        await asyncio.sleep(0.1)
        await self.sendPacket([0x35,0x02])
        self._is_on = False
        self._light_on = False
        self._color_on = False
        await asyncio.sleep(0.15)
        await self.triggerStatus()

    async def triggerStatus(self):
        LOGGER.debug(f"Requesting status update from device {self._mac}")
        await self.sendPacket([0x30,0x01])
        await asyncio.sleep(0.2)
        await self.sendPacket([0x30,0x02])
        LOGGER.info(f"Status update request sent for {self._mac}")

    async def trigger_entity_update(self):
        if self._trigger_update:
            LOGGER.debug(f"Triggering Home Assistant entity update for {self._mac}")
            self._trigger_update()
        else:
            LOGGER.debug(f"No Home Assistant entity update callback set for {self._mac}")

    async def notification_handler(self, characteristic: BleakGATTCharacteristic, res: bytearray):
        LOGGER.debug(f"Notification for {self._mac} from {characteristic.uuid}: {''.join(format(x, '02x') for x in res)}")
        if len(res) < 9:
            LOGGER.warning(f"Received short notification for {self._mac}: {len(res)} bytes. Ignoring.")
            return
        
        reply_version = res[8]
        LOGGER.debug(f"Reply version for {self._mac} is {reply_version}")
        
        trigger_ha_update = False

        if reply_version == 1:
            new_light_on = res[9] == 1
            new_brightness = None
            if new_light_on:
                new_brightness = int(res[10]*255/100) if res[10] > 0 else 0 # Default to 0 if res[10] is 0
            
            if self._light_on != new_light_on or self._brightness != new_brightness:
                trigger_ha_update = True
            self._light_on = new_light_on
            self._brightness = new_brightness
            if self._light_on: self._mode = COLOR_MODE_WHITE # Update mode if white light is on
            LOGGER.debug(f"Status v1 (White) for {self._mac}: On={self._light_on}, Brightness={self._brightness}, Mode={self._mode}")

        elif reply_version == 2:
            new_color_on = res[9] == 1
            new_effect = self._effect # Keep current if not updated
            new_color_brightness = None
            new_rgb_color = self._rgb_color # Keep current if not updated

            if new_color_on:
                new_effect = self._supported_effects[res[16]] if res[16] < len(self._supported_effects) else "Off"
                new_color_brightness = int(res[10]*255/100) if res[10] > 0 else 0 # Default to 0
                new_rgb_color = (res[13], res[14], res[15])
            
            if (self._color_on != new_color_on or 
                self._effect != new_effect or 
                self._color_brightness != new_color_brightness or 
                self._rgb_color != new_rgb_color):
                trigger_ha_update = True

            self._color_on = new_color_on
            self._effect = new_effect
            self._color_brightness = new_color_brightness
            self._rgb_color = new_rgb_color
            if self._color_on: self._mode = COLOR_MODE_RGB # Update mode if color light is on
            LOGGER.debug(f"Status v2 (Color) for {self._mac}: On={self._color_on}, Brightness={self._color_brightness}, RGB={self._rgb_color}, Effect='{self._effect}', Mode={self._mode}")
        
        elif reply_version == 255:
            if self._is_on or self._light_on or self._color_on: trigger_ha_update = True
            self._is_on = False
            self._light_on = False
            self._color_on = False
            LOGGER.debug(f"Device Off notification for {self._mac}")

        elif reply_version == 0:
            LOGGER.debug(f"Device {self._mac} is going to shut down")
            await self.disconnect()
            return
        else:
            LOGGER.debug(f"Received unknown notification version for {self._mac}: {reply_version}")
            return

        new_is_on = self._light_on or self._color_on
        if self._is_on != new_is_on:
            trigger_ha_update = True
        self._is_on = new_is_on
        
        if trigger_ha_update:
            await self.trigger_entity_update()

    async def connect(self) -> bool:
        if not self._device: # self._device would be None if __init__ received a None device
            LOGGER.error(f"Cannot connect: BeurerInstance for {self._mac} was not properly initialized with a device object.")
            return False
            
        LOGGER.debug(f"Attempting to connect to device {self._mac}")
        try:
            if not self._device.is_connected:
                # Ensure we use the original BLEDevice object if reconnecting client
                # This assumes self._device_ble_object was stored in __init__
                if not isinstance(self._device, BleakClient) or self._device.address != self._device_ble_object.address:
                    self._device = BleakClient(self._device_ble_object, disconnected_callback=self.disconnected_callback)

                await self._device.connect(timeout=20.0)
                LOGGER.info(f"Successfully connected to {self._mac}")
                await asyncio.sleep(0.1)

                self._write_uuid = None
                self._read_uuid = None
                for service in self._device.services: # Use self._device (BleakClient)
                    for char_obj in service.characteristics: # Iterate over BleakGATTCharacteristic objects
                        if char_obj.uuid in WRITE_CHARACTERISTIC_UUIDS:
                            self._write_uuid = char_obj.uuid
                        if char_obj.uuid in READ_CHARACTERISTIC_UUIDS:
                            self._read_uuid = char_obj.uuid
                
                if not self._read_uuid or not self._write_uuid:
                    LOGGER.error(f"No supported read/write UUIDs found for {self._mac}. Disconnecting.")
                    await self.disconnect() # Call disconnect to clean up
                    return False
                LOGGER.info(f"For {self._mac}: Read UUID={self._read_uuid}, Write UUID={self._write_uuid}")

            await asyncio.sleep(0.1)
            LOGGER.info(f"Starting notifications for {self._mac} on {self._read_uuid}")
            await self._device.start_notify(self._read_uuid, self.notification_handler)
            LOGGER.info(f"Notifications started for {self._mac}")

            await self.triggerStatus() # Get initial status
            await asyncio.sleep(0.1) # Allow status to be processed
            return True
        except BleakError as error:
            track = traceback.format_exc()
            LOGGER.debug(f"BleakError track for connect {self._mac}: {track}")
            LOGGER.error(f"BleakError connecting to {self._mac}: {error}")
        except Exception as error:
            track = traceback.format_exc()
            LOGGER.debug(f"Exception track for connect {self._mac}: {track}")
            LOGGER.error(f"Unexpected error connecting to {self._mac}: {error}")
        
        await self.disconnect() # Ensure disconnected on any error during connect
        return False

    async def update(self):
        LOGGER.debug(f"Update called for {self._mac}")
        try:
            if not self._device or not self._device.is_connected:
                LOGGER.info(f"Device {self._mac} not connected for update, attempting connect.")
                if not await self.connect():
                    LOGGER.warning(f"Was not able to connect to device {self._mac} for updates.")
                    # await self.disconnect() # connect() already handles disconnect on failure
                    return
            
            # Assuming notifications are started by connect() if successful
            # If not, you might need:
            # await self._device.start_notify(self._read_uuid, self.notification_handler)

            LOGGER.info(f"Triggering status request for {self._mac} during update.")
            await self.triggerStatus()
        except Exception as error:
            track = traceback.format_exc()
            LOGGER.debug(f"Exception track for update {self._mac}: {track}")
            LOGGER.error(f"Error during update for {self._mac}: {error}")
            await self.disconnect()

    async def disconnect(self):
        LOGGER.debug(f"Disconnecting from {self._mac}")
        if self._device and self._device.is_connected: # Check if self._device exists
            try:
                if self._read_uuid: # Check if read_uuid was found
                    await self._device.stop_notify(self._read_uuid)
                    LOGGER.debug(f"Notifications stopped for {self._mac}")
            except BleakError as e:
                LOGGER.warning(f"BleakError stopping notifications for {self._mac}: {e}")
            except Exception as e: # Catch other potential errors
                LOGGER.warning(f"Error stopping notifications for {self._mac}: {e}")
            
            await self._device.disconnect()
            LOGGER.info(f"Disconnected from {self._mac}")
        else:
            LOGGER.debug(f"Device {self._mac} already disconnected or not initialized.")
            
        self._is_on = False
        self._light_on = False
        self._color_on = False
        # Don't call trigger_entity_update here if it's a full disconnect,
        # let the disconnected_callback handle it if it was an unexpected disconnect.
        # If it's an intentional disconnect, HA will know the entity is unavailable.
