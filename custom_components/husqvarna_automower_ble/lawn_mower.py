"""The Husqvarna Autoconnect Bluetooth lawn mower platform."""

from __future__ import annotations

import asyncio
import logging

from husqvarna_automower_ble.protocol import MowerActivity, MowerState

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,  # type: ignore
    LawnMowerEntity,
    LawnMowerEntityFeature,  # type: ignore
)
from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers import entity_platform

from . import HusqvarnaConfigEntry
from .const import INTEGRATION_TITLE
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

    async def _async_refresh_activity(self) -> None:
        """Refresh mower state after a successful command."""
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()

        self._attr_activity = self._get_activity()
        self.async_write_ha_state()

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

        if self._attr_activity == LawnMowerActivity.DOCKED:
            success = await self.coordinator.async_execute_command(
                self.coordinator.mower.mower_override
            )
            if not success:
                LOGGER.warning(
                    "Failed to start mowing: mower_override was not accepted"
                )
                persistent_notification.async_create(
                    self.hass,
                    "The mower did not accept the start mowing override. The mower state will still be updated.",
                    title=INTEGRATION_TITLE,
                    notification_id=f"{self._attr_unique_id}_mower_override",
                )
        else:
            success = await self.coordinator.async_execute_command(
                self.coordinator.mower.mower_resume
            )
            if not success:
                LOGGER.warning("Failed to start mowing: mower_resume was not accepted")
                persistent_notification.async_create(
                    self.hass,
                    "The mower did not accept the start mowing command. The mower state will still be updated.",
                    title=INTEGRATION_TITLE,
                    notification_id=f"{self._attr_unique_id}_mower_resume",
                )

        await self._async_refresh_activity()

    async def async_dock(self) -> None:
        """Start docking."""
        LOGGER.debug("Docking mower")

        success = await self.coordinator.async_execute_command(
            self.coordinator.mower.mower_park
        )
        if not success:
            LOGGER.warning("Failed to dock mower: mower_park was not accepted")
            persistent_notification.async_create(
                self.hass,
                "The mower did not accept the docking command. The mower state will still be updated.",
                title=INTEGRATION_TITLE,
                notification_id=f"{self._attr_unique_id}_mower_park",
            )

        await self._async_refresh_activity()

    async def async_pause(self) -> None:
        """Pause mower."""
        LOGGER.debug("Pausing mower")

        success = await self.coordinator.async_execute_command(
            self.coordinator.mower.mower_pause
        )
        if not success:
            LOGGER.warning("Failed to pause mower: mower_pause was not accepted")
            persistent_notification.async_create(
                self.hass,
                "The mower did not accept the pause command. The mower state will still be updated.",
                title=INTEGRATION_TITLE,
                notification_id=f"{self._attr_unique_id}_mower_pause",
            )

        await self._async_refresh_activity()

    async def async_park_indefinitely(self) -> None:
        """Park mower indefinitely."""
        LOGGER.debug("Parking mower indefinitely")

        success = await self.coordinator.async_execute_command(
            self.coordinator.mower.mower_park_indefinitely
        )
        if not success:
            LOGGER.warning(
                "Failed to park mower indefinitely: mower_park_indefinitely was not accepted"
            )
            persistent_notification.async_create(
                self.hass,
                "The mower did not accept the park indefinitely command. The mower state will still be updated.",
                title=INTEGRATION_TITLE,
                notification_id=f"{self._attr_unique_id}_mower_park_indefinitely",
            )

        await self._async_refresh_activity()

    async def async_resume_schedule(self) -> None:
        """Resume mower schedule."""
        LOGGER.debug("Resuming mower schedule")

        success = await self.coordinator.async_execute_command(
            self.coordinator.mower.mower_auto
        )
        if not success:
            LOGGER.warning(
                "Failed to resume mower schedule: mower_auto was not accepted"
            )
            persistent_notification.async_create(
                self.hass,
                "The mower did not accept the resume schedule command. The mower state will still be updated.",
                title=INTEGRATION_TITLE,
                notification_id=f"{self._attr_unique_id}_mower_auto",
            )

        await self._async_refresh_activity()
