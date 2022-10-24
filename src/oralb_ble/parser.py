"""Parser for OralB BLE advertisements.

This file is shamelessly copied from the following repository:
https://github.com/Ernst79/bleparser/blob/c42ae922e1abed2720c7fac993777e1bd59c0c93/package/bleparser/oral_b.py

MIT License applies.
"""
from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from bluetooth_data_tools import short_address
from bluetooth_sensor_state_data import BluetoothData
from home_assistant_bluetooth import BluetoothServiceInfo

# from sensor_state_data import SensorLibrary

_LOGGER = logging.getLogger(__name__)


UNPACK_BBHBBBB = struct.Struct(">BBHBBBB").unpack


class Models(Enum):

    IOSerial7 = auto()
    SmartSeries7000 = auto()


@dataclass
class ModelDescription:

    device_type: str
    modes: dict[int, str]


DEVICE_TYPES = {
    Models.IOSerial7: ModelDescription(
        device_type="IO Serial 7",
        modes={
            0: "daily clean",
            1: "sensitive",
            2: "gum care",
            3: "whiten",
            4: "intense",
            8: "settings",
        },
    ),
    Models.SmartSeries7000: ModelDescription(
        device_type="Smart Series 7000",
        modes={
            0: "off",
            1: "daily clean",
            2: "sensitive",
            3: "massage",
            4: "whitening",
            5: "deep clean",
            6: "tongue cleaning",
            7: "turbo",
            255: "unknown",
        },
    ),
}


STATES = {
    0: "unknown",
    1: "initializing",
    2: "idle",
    3: "running",
    4: "charging",
    5: "setup",
    6: "flight menu",
    8: "selection menu",
    113: "final test",
    114: "pcb test",
    115: "sleeping",
    116: "transport",
}

PRESSURE = {114: "normal", 118: "button pressed", 178: "high"}


ORALB_MANUFACTURER = {0x00DC}


class OralBBluetoothDeviceData(BluetoothData):
    """Data for OralB BLE sensors."""

    def _start_update(self, service_info: BluetoothServiceInfo) -> None:
        """Update from BLE advertisement data."""
        _LOGGER.debug("Parsing OralB BLE advertisement data: %s", service_info)
        manufacturer_data = service_info.manufacturer_data
        local_name = service_info.name
        address = service_info.address
        self.set_device_manufacturer("OralB")
        if ORALB_MANUFACTURER not in manufacturer_data:
            return None

        mfr_data = manufacturer_data[ORALB_MANUFACTURER]

        self._process_mfr_data(address, local_name, mfr_data)

    def _process_mfr_data(
        self,
        address: str,
        local_name: str,
        data: bytes,
    ) -> None:
        """Parser for OralB sensors."""
        _LOGGER.debug("Parsing OralB sensor: %s", data)
        msg_length = len(data)
        if msg_length != 11:
            return
        (
            state,
            pressure,
            counter,
            mode,
            sector,
            sector_timer,
            no_of_sectors,
        ) = UNPACK_BBHBBBB(data[3:11])

        result: dict[str, Any] = {}
        if state == 3:
            result.update({"toothbrush": 1})
        else:
            result.update({"toothbrush": 0})

        device_bytes = data[4:7]
        if device_bytes == b"\x062k":
            model = Models.IOSerial7
        else:
            model = Models.SmartSeries7000

        model_info = DEVICE_TYPES[model]
        modes = model_info.modes
        self.set_device_type(model_info.device_type)
        name = f"{model_info.device_type} {short_address(address)}"
        self.set_device_name(name)
        self.set_title(name)

        tb_state = STATES.get(state, "unknown state " + str(state))
        tb_mode = modes.get(mode, "unknown mode " + str(mode))
        tb_pressure = PRESSURE.get(pressure, "unknown pressure " + str(pressure))

        if sector == 254:
            tb_sector = "last sector"
        elif sector == 255:
            tb_sector = "no sector"
        else:
            tb_sector = "sector " + str(sector)

        result.update(
            {
                "toothbrush state": tb_state,
                "pressure": tb_pressure,
                "counter": counter,
                "mode": tb_mode,
                "sector": tb_sector,
                "sector timer": sector_timer,
                "number of sectors": no_of_sectors,
            }
        )
        _LOGGER.debug("OralB sensor data: %s", result)