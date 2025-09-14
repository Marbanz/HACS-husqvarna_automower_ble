"""The Husqvarna Autoconnect Bluetooth lawn mower platform."""

from __future__ import annotations

import asyncio
import logging

from husqvarna_automower_ble.protocol import MowerActivity, MowerState

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers import config_validation as cv, entity_platform

from . import HusqvarnaConfigEntry
from .coordinator import HusqvarnaCoordinator
from .entity import HusqvarnaAutomowerBleEntity

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HusqvarnaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AutomowerLawnMower integration from a config entry."""
    coordinator = config_entry.runtime_data
    address = coordinator.address

    async_add_entities(
        [
            AutomowerLawnMower(
                coordinator,
                address,
            ),
        ]
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "park_indefinitely",
        {},
        "async_park_indefinitely",
    )
    platform.async_register_entity_service(
        "resume_schedule",
        {},
        "async_resume_schedule",
    )


class AutomowerLawnMower(HusqvarnaAutomowerBleEntity, LawnMowerEntity):
    """Husqvarna Automower."""

    _attr_name = None
    _attr_supported_features = (
        LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.START_MOWING
        | LawnMowerEntityFeature.DOCK
    )

    def __init__(
        self,
        coordinator: HusqvarnaCoordinator,
        address: str,
    ) -> None:
        """Initialize the lawn mower."""
        super().__init__(coordinator)
        self._attr_unique_id = str(address)

    def _get_activity(self) -> LawnMowerActivity | None:
        """Return the current lawn mower activity."""
        if self.coordinator.data is None:
            return None

        state = self.coordinator.data["state"]
        activity = self.coordinator.data["activity"]

        if state is None or activity is None:
            return None

        if state == MowerState.PAUSED:
            return LawnMowerActivity.PAUSED
        if state in (MowerState.STOPPED, MowerState.OFF, MowerState.WAIT_FOR_SAFETYPIN):
            # This is actually stopped, but that isn't an option
            return LawnMowerActivity.ERROR
        if state == MowerState.PENDING_START and activity == MowerActivity.NONE:
            # This happens when the mower is safety stopped and we try to send a
            # command to start it.
            return LawnMowerActivity.ERROR
        if state in (
            MowerState.RESTRICTED,
            MowerState.IN_OPERATION,
            MowerState.PENDING_START,
        ):
            if activity in (
                MowerActivity.CHARGING,
                MowerActivity.PARKED,
                MowerActivity.NONE,
            ):
                return LawnMowerActivity.DOCKED
            if activity in (MowerActivity.GOING_OUT, MowerActivity.MOWING):
                return LawnMowerActivity.MOWING
            if activity == MowerActivity.GOING_HOME:
                return LawnMowerActivity.RETURNING
        return LawnMowerActivity.ERROR

    async def async_added_to_hass(self) -> None:
        """Handle when the entity is added to Home Assistant."""
        LOGGER.debug("AutomowerLawnMower: entity added to Home Assistant")

        self._attr_activity = self._get_activity()
        self._attr_available = self._attr_activity is not None and self.available
        await super().async_added_to_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug("AutomowerLawnMower: _handle_coordinator_update")

        self._attr_activity = self._get_activity()
        self._attr_available = self._attr_activity is not None and self.available
        super()._handle_coordinator_update()

    async def async_start_mowing(self) -> None:
        """Start mowing."""
        LOGGER.debug("Starting mower")

        try:
            await self.coordinator.async_execute_command(
                self.coordinator.mower.mower_resume
            )
            if self._attr_activity == LawnMowerActivity.DOCKED:
                await self.coordinator.async_execute_command(
                    self.coordinator.mower.mower_override
                )

            await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()

            self._attr_activity = self._get_activity()
            self.async_write_ha_state()
        except Exception as ex:
            LOGGER.error("Failed to start mowing: %s", ex)

    async def async_dock(self) -> None:
        """Start docking."""
        LOGGER.debug("Docking mower")

        try:
            await self.coordinator.async_execute_command(
                self.coordinator.mower.mower_park
            )

            await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()

            self._attr_activity = self._get_activity()
            self.async_write_ha_state()
        except Exception as ex:
            LOGGER.error("Failed to dock mower: %s", ex)

    async def async_pause(self) -> None:
        """Pause mower."""
        LOGGER.debug("Pausing mower")

        try:
            await self.coordinator.async_execute_command(
                self.coordinator.mower.mower_pause
            )

            await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()

            self._attr_activity = self._get_activity()
            self.async_write_ha_state()
        except Exception as ex:
            LOGGER.error("Failed to pause mower: %s", ex)

    async def async_park_indefinitely(self) -> None:
        """Park mower indefinitely."""
        LOGGER.debug("Parking mower indefinitely")

        try:
            await self.coordinator.async_execute_command(
                self.coordinator.mower.mower_park_indefinitely
            )

            await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()

            self._attr_activity = self._get_activity()
            self.async_write_ha_state()
        except Exception as ex:
            LOGGER.error("Failed to park mower indefinitely: %s", ex)

    async def async_resume_schedule(self) -> None:
        """Resume mower schedule."""
        LOGGER.debug("Resuming mower schedule")

        try:
            await self.coordinator.async_execute_command(
                self.coordinator.mower.mower_auto
            )

            await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()

            self._attr_activity = self._get_activity()
            self.async_write_ha_state()
        except Exception as ex:
            LOGGER.error("Failed to resume mower schedule: %s", ex)
