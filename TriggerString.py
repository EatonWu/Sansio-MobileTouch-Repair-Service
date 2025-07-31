import enum
from pathlib import Path
from typing import Callable
import logging


class TriggerString(enum.Enum):
    """
    Enumeration of trigger strings used in the MobileTouch log file.
    These strings are used to identify specific events or actions in the log.
    """

    # response should be to clear reference tables
    # this usually points to a corrupt reference table
    FAILED_GET_REFERENCE_TABLES = "storeAction() fail: LoadAll:getAllReferenceTables"

    # response should be to clear device info, cookies, and service worker
    # this usually points a missing device info or a corrupt object store
    FAILED_GET_DEVICE_INFO = "storeAction() fail: LoadByKey:getDeviceInfo"

    # The ones below require a hard reset, which is fine since the chart/app data is likely lost anyway
    # response should be to do a hard clear (deletion of appdata)
    # this usually points to database corruption
    CORRUPT_SCHEMA = "init schema: error: Internal error"

    # response should be to do a hard clear (deletion of appdata)
    # this usually points to database corruption
    STORES_NOT_CORRECTLY_SET_UP = "Stores not correctly set up, db"

    MISSING_DEVICE_ID = "Device configuration corrupt - missing device ID (2)"

    DEVICE_ID_MISMATCH = "Error: Device configuration corrupt - device ID mismatch (3)"

    UNKNOWN = "UNKNOWN"


    def __init__(self, value):
        self._value_ = value
        self._callback = None

    @property
    def callback(self):
        """Get the callback function for this trigger string."""
        return self._callback

    @callback.setter
    def callback(self, func: Callable[['LogEntry', Path], None]):
        """
        Set a callback function to be called when this trigger string is detected.

        Args:
            func: A function that takes a LogEntry and Path as arguments and returns None.
        """
        self._callback = func

    @staticmethod
    def from_message(message: str):
        """
        Returns the TriggerString that matches the given message.
        :return: TriggerString if found, otherwise UNKNOWN.
        """
        for trigger in TriggerString:
            if trigger.name in message:
                return trigger
        # logger.debug(f"No matching trigger string found for message: {message}")
        return TriggerString.UNKNOWN