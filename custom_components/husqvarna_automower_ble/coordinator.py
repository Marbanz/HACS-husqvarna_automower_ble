"""Provides the DataUpdateCoordinator."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any
from typing import TYPE_CHECKING

from husqvarna_automower_ble.mower import Mower
from husqvarna_automower_ble.protocol import MowerActivity, ResponseResult
from bleak import BleakError
from bleak_retry_connector import close_stale_connections_by_address

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from . import HusqvarnaConfigEntry

IDLE_SCAN_INTERVAL = timedelta(seconds=1800)  # 30 minutes
ACTIVE_SCAN_INTERVAL = timedelta(seconds=120)  # 2 minutes


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
            update_interval=IDLE_SCAN_INTERVAL,
        )
        self.address = address
        self.channel_id = channel_id
        self.model = model
        self.mower = mower
        self._last_successful_update: datetime | None = None
        self._connection_lock = asyncio.Lock()
        self._consecutive_update_failures = 0
        self._first_runtime_poll_pending = True

    def _register_update_failure(self) -> None:
        """Track failed update attempts and handle first runtime poll failure."""
        self._consecutive_update_failures += 1
        if (
            self._first_runtime_poll_pending
            and self._last_successful_update is not None
        ):
            LOGGER.debug("First runtime poll failed after restart; forcing unavailable")
            self._consecutive_update_failures = max(
                self._consecutive_update_failures,
                2,
            )
            self._first_runtime_poll_pending = False

    def _get_dynamic_update_interval(self, data: dict[str, str | int]) -> timedelta:
        """Return poll interval based on mower activity and next start time."""
        activity = data.get("activity")
        try:
            mower_activity = MowerActivity(activity)
        except (ValueError, TypeError):
            mower_activity = None

        if mower_activity in (
            MowerActivity.MOWING,
            MowerActivity.GOING_OUT,
            MowerActivity.GOING_HOME,
        ):
            return ACTIVE_SCAN_INTERVAL

        next_start_time = data.get("next_start_time")
        if isinstance(next_start_time, datetime):
            if next_start_time.tzinfo is None:
                next_start_time = dt_util.as_local(next_start_time)

            delay_seconds = (
                dt_util.as_utc(next_start_time) - dt_util.utcnow()
            ).total_seconds()
            idle_seconds = IDLE_SCAN_INTERVAL.total_seconds()
            # Keep regular idle polling unless next start is sooner.
            if 0 < delay_seconds < idle_seconds:
                buffered_delay_seconds = min(idle_seconds, delay_seconds + 60)
                return timedelta(seconds=buffered_delay_seconds)

        return IDLE_SCAN_INTERVAL

    def _update_scan_interval(self, data: dict[str, str | int]) -> None:
        """Update coordinator interval if mower activity changed."""
        new_interval = self._get_dynamic_update_interval(data)
        if self.update_interval == new_interval:
            return

        LOGGER.debug(
            "Changing scan interval from %s to %s (activity=%s, next_start_time=%s)",
            self.update_interval,
            new_interval,
            data.get("activity"),
            data.get("next_start_time"),
        )
        self.update_interval = new_interval

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
            except (BleakError, UpdateFailed) as err:
                self._register_update_failure()
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

                # Fetch mower statistics with error handling
                try:
                    stats = await self.mower.mower_statistics()
                    if stats is not None:
                        data["total_running_time"] = stats["totalRunningTime"]
                        data["total_cutting_time"] = stats["totalCuttingTime"]
                        data["total_charging_time"] = stats["totalChargingTime"]
                        data["total_searching_time"] = stats["totalSearchingTime"]
                        data["number_of_collisions"] = stats["numberOfCollisions"]
                        data["number_of_charging_cycles"] = stats[
                            "numberOfChargingCycles"
                        ]
                except Exception as ex:
                    LOGGER.warning("Failed to fetch mower statistics: %s", ex)
                    # Continue without statistics data

                self._first_runtime_poll_pending = False
                self._consecutive_update_failures = 0
                self._update_scan_interval(data)
                self._last_successful_update = datetime.now()

            except BleakError as err:
                LOGGER.error("Error getting data from device")
                self._register_update_failure()
                self.async_update_listeners()
                raise UpdateFailed("Error getting data from device") from err
            except Exception as ex:
                LOGGER.exception("Unexpected error while fetching data: %s", ex)
                self._register_update_failure()
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
