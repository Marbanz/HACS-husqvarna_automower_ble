"""Support for Husqvarna BLE sensors."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from automower_ble.protocol import ModeOfOperation, MowerState, MowerActivity
from automower_ble.error_codes import ErrorCode

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant, callback
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
        unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=None,
        icon="mdi:battery",
    ),
    SensorEntityDescription(
        name="Is Charging",
        key="is_charging",
        unit_of_measurement=None,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,
        entity_category=None,
        icon="mdi:power-plug",
    ),
    SensorEntityDescription(
        name="Mode",
        key="mode",
        unit_of_measurement=None,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,
        entity_category=None,
        icon="mdi:robot",
    ),
    SensorEntityDescription(
        name="State",
        key="state",
        unit_of_measurement=None,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,
        entity_category=None,
        icon="mdi:state-machine",
    ),
    SensorEntityDescription(
        name="Activity",
        key="activity",
        unit_of_measurement=None,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,
        entity_category=None,
        icon="mdi:run",
    ),
    SensorEntityDescription(
        name="Error",
        key="error",
        unit_of_measurement=None,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,
        entity_category=None,
        icon="mdi:alert-circle",
    ),
    SensorEntityDescription(
        name="Next Start Time",
        key="next_start_time",
        unit_of_measurement=None,
        device_class=SensorDeviceClass.TIMESTAMP,
        state_class=None,
        entity_category=None,
        icon="mdi:timer",
    ),
    SensorEntityDescription(
        name="Total running time",
        key="totalRunningTime",
        unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timer",
    ),
    SensorEntityDescription(
        name="Total cutting time",
        key="totalCuttingTime",
        unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timer",
    ),
    SensorEntityDescription(
        name="Total charging time",
        key="totalChargingTime",
        unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timer",
    ),
    SensorEntityDescription(
        name="Total searching time",
        key="totalSearchingTime",
        unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timer",
    ),
    SensorEntityDescription(
        name="Total number of collisions",
        key="numberOfCollisions",
        unit_of_measurement=None,
        device_class=None,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:alert-circle",
    ),
    SensorEntityDescription(
        name="Total number of charging cycles",
        key="numberOfChargingCycles",
        unit_of_measurement=None,
        device_class=None,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:repeat-variant",
    ),
    SensorEntityDescription(
        name="Total cutting blade usage",
        key="cuttingBladeUsageTime",
        unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:blade",
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
        for description in MOWER_SENSORS
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

        self._attr_unique_id = f"{mower_id}_{description.key}"
        self._name = description.name
        self._key = description.key
        self._unit_of_measurement = description.unit_of_measurement
        self._device_class = description.device_class
        self._state = None
        self._state_class = description.state_class
        self._entity_category = description.entity_category
        self._description = description.name

        _LOGGER.debug(
            "Creating sensor entity: %s with unique_id: %s",
            self.entity_description.name,
            self._attr_unique_id,
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.entity_description.name

    @property
    def state(self):
        """Return the state of the sensor."""
        _LOGGER.debug("in state sensor code")
        self._attr_native_value = None
        try:
            self._attr_native_value = self.coordinator.data[self.entity_description.key]
            self._attr_available = self._attr_native_value is not None
            _LOGGER.debug(
                "Update sensor %s with value %s",
                self.entity_description.key,
                self._attr_native_value,
            )
            return self._attr_native_value
        except KeyError:
            self._attr_native_value = None
            _LOGGER.error(
                "%s not a valid attribute (in state)",
                self.entity_description.key,
            )
        return None

    @property
    def available(self) -> bool:
        """Return if the sensor is available."""
        last_update = self.coordinator._last_successful_update
        if last_update is None:
            return False
        return datetime.now() - last_update < timedelta(minutes=10)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this sensor."""
        return self.entity_description.unit_of_measurement

    @property
    def device_class(self):
        """Return the device class of this sensor."""
        return self.entity_description.device_class

    @property
    def state_class(self):
        """Return the state class of this sensor."""
        return self.entity_description.state_class

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def entity_category(self):
        """Return the entity category of this sensor."""
        return self.entity_description.entity_category

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self.entity_description.icon

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        self._update_attr()
        super()._handle_coordinator_update()

    @callback
    def _update_attr(self) -> None:
        """Update attributes for sensor."""
        _LOGGER.debug("in _update_attr code")
        self._attr_native_value = None
        try:
            self._attr_native_value = self.coordinator.data[self.entity_description.key]
            self._attr_available = self._attr_native_value is not None
            _LOGGER.debug(
                "Update sensor %s with value %s",
                self.entity_description.key,
                self._attr_native_value,
            )
            return self._attr_native_value
        except KeyError:
            self._attr_native_value = None
            _LOGGER.error(
                "%s not a valid attribute (in _update_attr)",
                self.entity_description.key,
            )
        return None

    @property
    def device_info(self) -> dict:
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.serial)},
            "manufacturer": self.coordinator.manufacturer,
            "model": self.coordinator.model,
        }
