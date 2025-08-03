"""Provides the DataUpdateCoordinator."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from bleak_retry_connector import get_device
from husqvarna_automower_ble.mower import Mower
from husqvarna_automower_ble.protocol import ResponseResult
from bleak import BleakError

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=300)


class HusqvarnaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data."""

    def __init__(
        self,
        hass: HomeAssistant,
        mower: Mower,
        address: str,
        manufacturer: str,
        model: str,
        channel_id: int,
        serial: str,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.address = address
        self.manufacturer = manufacturer
        self.model = model
        self.mower = mower
        self.channel_id = channel_id
        self.serial = serial
        self._last_successful_update: datetime | None = None
        self._connection_lock = asyncio.Lock()

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and any connection."""
        _LOGGER.debug("Shutting down coordinator")

        # Acquire the lock to ensure no operations are in progress during shutdown
        async with self._connection_lock:
            if self.mower.is_connected():
                try:
                    await self.mower.disconnect()
                    _LOGGER.debug("Disconnected mower during shutdown")
                except Exception as ex:
                    _LOGGER.warning("Error disconnecting during shutdown: %s", ex)

        await super().async_shutdown()

    async def _async_find_device(self) -> None:
        """Attempt to reconnect to the device."""
        _LOGGER.debug("Attempting to reconnect to the device")

        device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        ) or await get_device(self.address)
        if not device:
            _LOGGER.error("Failed to find device with address: %s", self.address)
            raise UpdateFailed("Can't find device")

        try:
            if await self.mower.connect(device) != ResponseResult.OK:
                _LOGGER.error("Failed to connect to the mower")
                raise UpdateFailed("Failed to connect")
        except (TimeoutError, BleakError) as ex:
            _LOGGER.error("Error during connection attempt: %s", ex)
            raise UpdateFailed("Failed to connect") from ex

    async def _async_update_data(self) -> dict[str, Any]:
        """Poll the device for updated data."""
        _LOGGER.debug("Polling device for data")

        data: dict[str, Any] = {}

        async with self._connection_lock:
            try:
                if not self.mower.is_connected():
                    await self._async_find_device()

                # Fetch data from the mower
                data["battery_level"] = await self.mower.battery_level()
                data["is_charging"] = await self.mower.is_charging()
                data["mode"] = await self.mower.mower_mode()
                data["state"] = await self.mower.mower_state()
                data["activity"] = await self.mower.mower_activity()
                data["error"] = await self.mower.mower_error()
                data["next_start_time"] = await self.mower.mower_next_start_time()

                # Fetch mower statistics
                stats = await self.mower.mower_statistics()
                data["statistics"] = stats

                self._last_successful_update = datetime.now()

                _LOGGER.debug("Successfully polled data: %s", data)

            except (TimeoutError, BleakError) as ex:
                _LOGGER.error("Error fetching data from device: %s", ex)
                self.async_update_listeners()
                raise UpdateFailed("Error fetching data from device") from ex
            except Exception as ex:
                _LOGGER.exception("Unexpected error while fetching data: %s", ex)
                self.async_update_listeners()
                raise UpdateFailed("Unexpected error fetching data") from ex
            finally:
                # Ensure the mower is disconnected after polling
                if self.mower.is_connected():
                    await self.mower.disconnect()

        return data

    async def async_execute_command(self, command_func, *args, **kwargs) -> Any:
        """Execute a command on the mower with connection locking."""
        _LOGGER.debug("Executing command: %s", command_func.__name__)

        async with self._connection_lock:
            try:
                if not self.mower.is_connected():
                    await self._async_find_device()

                # Execute the command
                result = await command_func(*args, **kwargs)

                _LOGGER.debug("Command %s executed successfully", command_func.__name__)
                return result

            except (TimeoutError, BleakError) as ex:
                _LOGGER.error(
                    "Error executing command %s: %s", command_func.__name__, ex
                )
                raise
            except Exception as ex:
                _LOGGER.exception(
                    "Unexpected error executing command %s: %s",
                    command_func.__name__,
                    ex,
                )
                raise
