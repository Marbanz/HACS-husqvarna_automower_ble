"""Provides the DataUpdateCoordinator."""

from __future__ import annotations

from datetime import timedelta, datetime
import logging
from typing import Any

from husqvarna_automower_ble.mower import Mower
from bleak import BleakError
from bleak_retry_connector import close_stale_connections_by_address

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
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
        channel_id: str,
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

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and any connection."""
        _LOGGER.debug("Shutting down coordinator")
        await super().async_shutdown()
        if self.mower.is_connected():
            await self.mower.disconnect()

    async def _async_find_device(self) -> None:
        """Attempt to reconnect to the device."""
        _LOGGER.debug("Attempting to reconnect to the device")
        await close_stale_connections_by_address(self.address)

        device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if not device:
            _LOGGER.error("Failed to find device with address: %s", self.address)
            raise UpdateFailed("Can't find device")

        try:
            if not await self.mower.connect(device):
                _LOGGER.error("Failed to connect to the mower")
                raise UpdateFailed("Failed to connect")
        except (TimeoutError, BleakError) as ex:
            _LOGGER.error("Error during connection attempt: %s", ex)
            raise UpdateFailed("Failed to connect") from ex

    async def _async_update_data(self) -> dict[str, Any]:
        """Poll the device for updated data."""
        _LOGGER.debug("Polling device for data")

        data: dict[str, Any] = {}

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
            data.update(stats)

            self._last_successful_update = datetime.now()

            _LOGGER.debug("Successfully polled data: %s", data)

            await self.mower.disconnect()

        except (TimeoutError, BleakError) as ex:
            _LOGGER.error("Error fetching data from device: %s", ex)
            raise UpdateFailed("Error fetching data from device") from ex

        return data


class HusqvarnaAutomowerBleEntity(CoordinatorEntity[HusqvarnaCoordinator]):
    """Coordinator entity for Husqvarna Automower Bluetooth."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HusqvarnaCoordinator, context: Any = None) -> None:
        """Initialize coordinator entity."""
        super().__init__(coordinator, context)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if self.coordinator._last_successful_update is None:
            return False
        return datetime.now() - self.coordinator._last_successful_update < timedelta(
            minutes=12
        )
