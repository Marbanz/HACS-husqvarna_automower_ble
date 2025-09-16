"""Support for Husqvarna BLE sensors."""

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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN
from .coordinator import HusqvarnaCoordinator

_LOGGER = logging.getLogger(__name__)

MOWER_SENSORS = [
    SensorEntityDescription(
        name="Battery Level",
        key="battery_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=None,
        icon="mdi:battery",
    ),
    SensorEntityDescription(
        name="Is Charging",
        key="is_charging",
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
        entity_category=None,
        icon="mdi:power-plug",
    ),
    SensorEntityDescription(
        name="Mode",
        key="mode",
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
        entity_category=None,
        icon="mdi:robot",
    ),
    SensorEntityDescription(
        name="State",
        key="state",
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
        entity_category=None,
        icon="mdi:state-machine",
    ),
    SensorEntityDescription(
        name="Activity",
        key="activity",
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
        entity_category=None,
        icon="mdi:run",
    ),
    SensorEntityDescription(
        name="Error",
        key="error",
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
        entity_category=None,
        icon="mdi:alert-circle",
    ),
    SensorEntityDescription(
        name="Next Start Time",
        key="next_start_time",
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
        entity_category=None,
        icon="mdi:timer",
    ),
]

MOWER_STATISTICS_SENSORS = [
    SensorEntityDescription(
        name="Total running time",
        key="totalRunningTime",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timer",
    ),
    SensorEntityDescription(
        name="Total cutting time",
        key="totalCuttingTime",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timer",
    ),
    SensorEntityDescription(
        name="Total charging time",
        key="totalChargingTime",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timer",
    ),
    SensorEntityDescription(
        name="Total searching time",
        key="totalSearchingTime",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timer",
    ),
    SensorEntityDescription(
        name="Total number of collisions",
        key="numberOfCollisions",
        native_unit_of_measurement=None,
        device_class=None,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:alert-circle",
    ),
    SensorEntityDescription(
        name="Total number of charging cycles",
        key="numberOfChargingCycles",
        native_unit_of_measurement=None,
        device_class=None,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:repeat-variant",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AutomowerLawnMower sensor from a config entry."""
    coordinator: HusqvarnaCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    _LOGGER.debug("Creating mower sensors")
    sensors = [
        AutomowerSensorEntity(
            coordinator, description, "automower_" + format_mac(coordinator.address)
        )
        for description in MOWER_SENSORS + MOWER_STATISTICS_SENSORS
    ]
    if not sensors:
        _LOGGER.error("No sensors were created. Check MOWER_SENSORS.")
    async_add_entities(sensors)


class AutomowerSensorEntity(CoordinatorEntity, SensorEntity):
    """Representation of an Automower sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HusqvarnaCoordinator,
        description: SensorEntityDescription,
        mower_id: str,
    ) -> None:
        """Initialize the Automower sensor entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = description.name
        self._attr_native_value = None
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_entity_category = description.entity_category
        self._attr_icon = description.icon
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.serial)},
            manufacturer=coordinator.manufacturer,
            model=coordinator.model,
        )

        self._attr_unique_id = f"{mower_id}_{description.key}"
        _LOGGER.debug(
            "Creating sensor entity: %s with unique_id: %s",
            self.entity_description.name,
            self._attr_unique_id,
        )

    def _get_state(self) -> str | None:
        """Return the state of the sensor."""
        try:
            key = self.entity_description.key
            # Check if this sensor is a statistics sensor
            is_statistic_sensor = any(
                desc.key == key for desc in MOWER_STATISTICS_SENSORS
            )

            if is_statistic_sensor:
                # Access value from the nested 'statistics' dictionary
                stats_data = self.coordinator.data.get("statistics")
                if stats_data is None:
                    # Statistics are not available
                    return None
                value = stats_data.get(key)
            else:
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
                        value = value.replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        _LOGGER.warning(
                            "Expected datetime for next_start_time, got %s", type(value)
                        )
                        value = None

            _LOGGER.debug(
                "Update sensor %s with value %s",
                key,
                value,
            )
            return value
        except Exception as e:
            _LOGGER.error(
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
