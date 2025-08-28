"""Support for sensor entities."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from husqvarna_automower_ble.protocol import ModeOfOperation, MowerState, MowerActivity
from husqvarna_automower_ble.error_codes import ErrorCodes

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HusqvarnaConfigEntry
from .entity import HusqvarnaAutomowerBleDescriptorEntity

LOGGER = logging.getLogger(__name__)

DESCRIPTIONS = (
    SensorEntityDescription(
        key="battery_level",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        name="Is Charging",
        key="is_charging",
        icon="mdi:power-plug",
    ),
    SensorEntityDescription(
        name="Mode",
        key="mode",
        icon="mdi:robot",
    ),
    SensorEntityDescription(
        name="State",
        key="state",
        icon="mdi:state-machine",
    ),
    SensorEntityDescription(
        name="Activity",
        key="activity",
        icon="mdi:run",
    ),
    SensorEntityDescription(
        name="Error",
        key="error",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:alert-circle",
    ),
    SensorEntityDescription(
        name="Next Start Time",
        key="next_start_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:timer",
    ),
    SensorEntityDescription(
        name="Total running time",
        key="total_running_time",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        icon="mdi:timer",
    ),
    SensorEntityDescription(
        name="Total cutting time",
        key="total_cutting_time",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        icon="mdi:timer",
    ),
    SensorEntityDescription(
        name="Total charging time",
        key="total_charging_time",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        icon="mdi:timer",
    ),
    SensorEntityDescription(
        name="Total searching time",
        key="total_searching_time",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        icon="mdi:timer",
    ),
    SensorEntityDescription(
        name="Total number of collisions",
        key="number_of_collisions",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:alert-circle",
    ),
    SensorEntityDescription(
        name="Total number of charging cycles",
        key="number_of_charging_cycles",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:repeat-variant",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HusqvarnaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Husqvarna Automower Ble sensor based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        HusqvarnaAutomowerBleSensor(coordinator, description)
        for description in DESCRIPTIONS
        if description.key in coordinator.data
    )


class HusqvarnaAutomowerBleSensor(HusqvarnaAutomowerBleDescriptorEntity, SensorEntity):
    """Representation of a sensor."""

    entity_description: SensorEntityDescription

    def _get_state(self) -> str | None:
        """Return the state of the sensor."""
        try:
            key = self.entity_description.key
            value = self.coordinator.data[key]

            if key == "mode":
                value = ModeOfOperation(value).name
            elif key == "state":
                value = MowerState(value).name
            elif key == "activity":
                value = MowerActivity(value).name
            elif key == "error":
                value = ErrorCodes(value).name
            elif key == "next_start_time" and value is not None:
                # Ensure value is a datetime object before formatting
                if isinstance(value, datetime):
                    value = value.replace(tzinfo=None).isoformat()
                else:
                    LOGGER.warning(
                        "Expected datetime for next_start_time, got %s", type(value)
                    )
                    value = None

            return value
        except Exception as e:
            LOGGER.error(
                "Error processing state for sensor %s: %s",
                self.entity_description.key,
                e,
                exc_info=True,
            )
            return None

    @property
    def available(self) -> bool:
        """Return if the sensor is available."""
        last_update = self.coordinator._last_successful_update
        if last_update is None:
            return False
        return datetime.now() - last_update < timedelta(minutes=12)

    async def async_added_to_hass(self) -> None:
        """Handle when the entity is added to Home Assistant."""
        self._attr_native_value = self._get_state()
        self._attr_available = self.available
        await super().async_added_to_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        self._attr_native_value = self._get_state()
        self._attr_available = self.available
        super()._handle_coordinator_update()
