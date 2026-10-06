"""Support for binary sensor entities."""

from __future__ import annotations

import logging
from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HusqvarnaConfigEntry
from .entity import HusqvarnaAutomowerBleDescriptorEntity

LOGGER = logging.getLogger(__name__)

DESCRIPTIONS = (
    BinarySensorEntityDescription(
        name="Is Charging",
        key="is_charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HusqvarnaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Husqvarna Automower Ble binary sensor based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        HusqvarnaAutomowerBleBinarySensor(coordinator, description)
        for description in DESCRIPTIONS
        if description.key in coordinator.data
    )


class HusqvarnaAutomowerBleBinarySensor(
    HusqvarnaAutomowerBleDescriptorEntity, BinarySensorEntity
):
    """Representation of a binary sensor."""

    entity_description: BinarySensorEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        try:
            key = self.entity_description.key
            # Check if key exists in coordinator data
            if key not in self.coordinator.data:
                LOGGER.debug("Key '%s' not found in coordinator data", key)
                return None

            value = self.coordinator.data[key]

            # Convert to boolean if not already
            if isinstance(value, bool):
                return value
            elif isinstance(value, (int, str)):
                return bool(value)
            else:
                LOGGER.warning(
                    "Unexpected value type for binary sensor %s: %s (%s)",
                    key,
                    value,
                    type(value),
                )
                return None

        except Exception as e:
            LOGGER.error(
                "Error processing state for binary sensor %s: %s",
                self.entity_description.key,
                e,
                exc_info=True,
            )
            return None
