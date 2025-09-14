"""Provides the DataUpdateCoordinator."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any
from typing import TYPE_CHECKING

from husqvarna_automower_ble.mower import Mower
from husqvarna_automower_ble.protocol import ResponseResult
from bleak import BleakError
from bleak_retry_connector import close_stale_connections_by_address

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from . import HusqvarnaConfigEntry

SCAN_INTERVAL = timedelta(seconds=600)


class HusqvarnaCoordinator(DataUpdateCoordinator[dict[str, str | int]]):
    """Class to manage fetching data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HusqvarnaConfigEntry,
        mower: Mower,
        address: str,
        channel_id: str,
        model: str,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.address = address
        self.channel_id = channel_id
        self.model = model
        self.mower = mower
        self._last_successful_update: datetime | None = None
        self._connection_lock = asyncio.Lock()

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and any connection."""
        LOGGER.debug("Shutdown")
        await super().async_shutdown()
        # Acquire the lock to ensure no operations are in progress during shutdown
        async with self._connection_lock:
            if self.mower.is_connected():
                try:
                    await self.mower.disconnect()
                    LOGGER.debug("Disconnected mower during shutdown")
                except Exception as ex:
                    LOGGER.warning("Error disconnecting during shutdown: %s", ex)

    async def _async_find_device(self):
        LOGGER.debug("Trying to reconnect")
        await close_stale_connections_by_address(self.address)

        device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )

        try:
            if await self.mower.connect(device) is not ResponseResult.OK:
                raise UpdateFailed("Failed to connect")
        except (TimeoutError, BleakError) as err:
            raise UpdateFailed("Failed to connect") from err

    async def _async_update_data(self) -> dict[str, str | int]:
        """Poll the device."""
        LOGGER.debug("Polling device")

        data: dict[str, str | int] = {}

        async with self._connection_lock:
            try:
                if not self.mower.is_connected():
                    await self._async_find_device()
            except BleakError as err:
                self.async_update_listeners()
                raise UpdateFailed("Failed to connect") from err

            try:
                data["battery_level"] = await self.mower.battery_level()
                data["is_charging"] = await self.mower.is_charging()
                data["mode"] = await self.mower.mower_mode()
                data["state"] = await self.mower.mower_state()
                data["activity"] = await self.mower.mower_activity()
                data["error"] = await self.mower.mower_error()
                data["next_start_time"] = await self.mower.mower_next_start_time()

                # Fetch mower statistics
                stats = await self.mower.mower_statistics()
                data["total_running_time"] = stats["totalRunningTime"]
                data["total_cutting_time"] = stats["totalCuttingTime"]
                data["total_charging_time"] = stats["totalChargingTime"]
                data["total_searching_time"] = stats["totalSearchingTime"]
                data["number_of_collisions"] = stats["numberOfCollisions"]
                data["number_of_charging_cycles"] = stats["numberOfChargingCycles"]

                self._last_successful_update = datetime.now()

            except BleakError as err:
                LOGGER.error("Error getting data from device")
                self.async_update_listeners()
                raise UpdateFailed("Error getting data from device") from err
            except Exception as ex:
                LOGGER.exception("Unexpected error while fetching data: %s", ex)
                self.async_update_listeners()
                raise UpdateFailed("Unexpected error fetching data") from ex
            finally:
                # Ensure the mower is disconnected after polling
                if self.mower.is_connected():
                    await self.mower.disconnect()

        return data

    async def async_execute_command(self, command_func, *args, **kwargs) -> Any:
        """Execute a command on the mower with connection locking."""
        LOGGER.debug("Executing command: %s", command_func.__name__)

        async with self._connection_lock:
            try:
                if not self.mower.is_connected():
                    await self._async_find_device()

                # Execute the command
                result = await command_func(*args, **kwargs)

                LOGGER.debug("Command %s executed successfully", command_func.__name__)
                return result

            except BleakError as ex:
                LOGGER.error(
                    "Error executing command %s: %s", command_func.__name__, ex
                )
                raise
            except Exception as ex:
                LOGGER.exception(
                    "Unexpected error executing command %s: %s",
                    command_func.__name__,
                    ex,
                )
                raise
