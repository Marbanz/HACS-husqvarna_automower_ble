"""Support for sensor entities."""

from __future__ import annotations

import logging
from datetime import datetime

from husqvarna_automower_ble.protocol import ModeOfOperation, MowerState, MowerActivity
from husqvarna_automower_ble.error_codes import ErrorCodes

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

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
        name="Mode",
        key="mode",
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:robot",
        options=[mode.name for mode in ModeOfOperation],
    ),
    SensorEntityDescription(
        name="State",
        key="state",
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:state-machine",
        options=[state.name for state in MowerState],
    ),
    SensorEntityDescription(
        name="Activity",
        key="activity",
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:run",
        options=[activity.name for activity in MowerActivity],
    ),
    SensorEntityDescription(
        name="Error",
        key="error",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:alert-circle",
        options=[error.name for error in ErrorCodes],
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

    @property
    def native_value(self) -> str | datetime | int | None:
        """Return the state of the sensor."""
        try:
            key = self.entity_description.key
            # Check if key exists in coordinator data
            if key not in self.coordinator.data:
                LOGGER.debug("Key '%s' not found in coordinator data", key)
                return None
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
                # Ensure value is a datetime object for TIMESTAMP device class
                if isinstance(value, datetime):
                    value = dt_util.as_local(value)
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
