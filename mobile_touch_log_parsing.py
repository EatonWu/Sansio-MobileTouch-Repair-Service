import datetime
import enum
import logging
import os
import sys
import time
from pathlib import Path
from typing import Callable, List
from threading import Event

# Configure logging
# This logging configuration replaces direct prints to stderr with a more flexible logging system.
# Benefits:
# 1. Different log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL) for different types of messages
# 2. Consistent formatting of log messages
# 3. Easy redirection of logs to a file instead of stdout/stderr
# 4. Control over log verbosity through the level setting
#
# To log to a file instead of stdout, uncomment the FileHandler line below.
# To change the log level, modify the level parameter (e.g., logging.DEBUG for more verbose logging).
logging.basicConfig(
    level=logging.DEBUG,  # Set to logging.DEBUG for more verbose output
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        # Uncomment the line below to log to a file instead of stdout
        # logging.FileHandler('mobile_touch_log_parsing.log'),
    ]
)
logger = logging.getLogger(__name__)

# Path to the standard log file. If this path doesn't exist, the program will use a linear falloff
# mechanism to retry with increasing delays.
standard_log_path = Path(r"C:\ProgramData\Physio-Control\MobileTouch\logging\mobiletouch.log")

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

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

    UNKNOWN = "UNKNOWN"


    def __init__(self, value):
        self._value_ = value
        self._callback = None

    @property
    def callback(self):
        """Get the callback function for this trigger string."""
        return self._callback

    @callback.setter
    def callback(self, func: Callable[['LogEntry'], None]):
        """
        Set a callback function to be called when this trigger string is detected.

        Args:
            func: A function that takes a LogEntry as its argument and returns None.
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
        logger.debug(f"No matching trigger string found for message: {message}")
        return TriggerString.UNKNOWN

class LogLevel(enum.Enum):
    """
    Enumeration of log levels used in the MobileTouch log file.
    """
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    def __init__(self, level):
        self._value_ = level


class LogEntry:
    """
    Represents a single log entry.
    """

    # init from a line in the log file

    def __init__(self, timestamp: str, level: str, message: str) -> None:
        # convert string to datetime
        try:
            self.timestamp = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S,%f')
        except ValueError as e:
            # print(f"Error parsing timestamp '{timestamp}': {e}", file=sys.stderr)
            raise ValueError(f"Invalid timestamp format: {timestamp}")
        self.level = LogLevel(level) if level in LogLevel.__members__ else LogLevel.INFO
        self.message = message

    def __str__(self):
        return f"{self.timestamp} {self.level} {self.message}"


def log_entry_from_line(line: str):
    """
    Parses a line from the log file and returns a log_entry object.
    There are four parts to the log entry:
    Example:
    2025-05-26 09:33:40,383 INFO JS API: getNativeVersion returned: 2023.2.208
    :param line: A single line from the log file
    :return: log_entry object
    """
    parts = line.split(' ', 3)
    if len(parts) < 4:
        raise ValueError(f"Invalid log entry format: {line}")

    timestamp = f"{parts[0]} {parts[1]}"
    level, message = parts[2], parts[3]
    return LogEntry(timestamp, level, message)

def read_log_file(log_path: Path=standard_log_path):
    """
    Reads the log file into memory and then immediately closes it.
    The largest log file I've observed is 10,241 KB, which is manageable to store in memory.
    :param log_path: Path to the log file
    :return: a list of lines from the log file, or an empty list if the file doesn't exist
    """
    if not log_path.exists():
        logger.debug(f"Log file does not exist: {log_path}")
        return []
    lines = []
    try:
        with log_path.open('r', encoding='utf-8') as file:
            for line in file:
                lines.append(line.strip())
    except Exception as e:
        logger.error(f"Error reading log file: {e}")

    return lines


def parse_log(log_path=standard_log_path) -> List[LogEntry]:
    """
    Example of a standard entry:
    2025-05-26 09:33:40,383 INFO JS API: getNativeVersion returned: 2023.2.208
    Parses the standard log file and extracts relevant information.

    Reads log entries from end to beginning, as the most recent entries are at the end.
    Returns a list of LogEntry objects in reverse chronological order (newest first).
    :return: List of LogEntry objects
    """
    log_entries = []
    lines = read_log_file(log_path)
    cutoff_date = datetime.datetime.now() - datetime.timedelta(hours=2)
    for line in reversed(lines):
        try:
            entry = log_entry_from_line(line)
            # logger.debug(f"Processing log entry: {entry}")
            if entry.timestamp < cutoff_date:
                break
            log_entries.append(entry)
        except ValueError as e:
            logger.warning(f"Skipping invalid log entry: {e}")

    return log_entries

def discard_log_on_condition(log_entries, condition: Callable[[LogEntry], bool]):
    """
    Discards log entries based on a condition.
    :param log_entries: List of log entries to filter
    :param condition: A callable that takes a LogEntry and returns True if it should be discarded
    :return: Filtered list of log entries
    """
    return [entry for entry in log_entries if not condition(entry)]

def discard_older_than(log_entries, days: int):
    """
    Discards log entries older than a specified number of days.
    :param log_entries: List of log entries to filter
    :param days: Number of days to keep
    :return: Filtered list of log entries
    """
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
    return discard_log_on_condition(log_entries, lambda entry: entry.timestamp < cutoff_date)


def check_last_modified(log_file: Path = standard_log_path):
    """
    Checks the last modified date of the log file
    :param log_file: Path to the log file
    :return: Last modified datetime or None if file doesn't exist
    """
    if not log_file.exists():
        return None
    last_modified = log_file.stat().st_mtime
    last_modified_date = datetime.datetime.fromtimestamp(last_modified)
    return last_modified_date


def check_trigger_strings(entry: LogEntry):
    """
    Checks a log entry against all defined trigger strings.
    If a trigger string is found and has a callback registered, the callback is called.
    :param entry: LogEntry to check
    :return: True if a trigger string was found, False otherwise
    """
    for trigger in TriggerString:
        if trigger.value in entry.message:
            logger.info(f"Detected trigger string {trigger.name}: {entry}")
            if trigger.callback:
                trigger.callback(entry)
            return True
    return False


def register_trigger_callback(trigger: TriggerString, callback: Callable[[LogEntry], None]):
    """
    Register a callback function for a specific trigger string.

    Args:
        trigger: The TriggerString to register the callback for
        callback: A function that takes a LogEntry as its argument and returns None
    """
    trigger.callback = callback


def register_trigger_callbacks(callbacks: dict):
    """
    Register multiple callback functions for trigger strings.

    Args:
        callbacks: A dictionary mapping TriggerString to callback functions
    """
    for trigger, callback in callbacks.items():
        register_trigger_callback(trigger, callback)


def main_loop(stop_event: Event = None, logs_loaded_event: Event = None,log_file: Path = standard_log_path):
    """
    Main loop for the log parsing script.
    Continuously checks the log file and processes new entries.
    Monitors for all defined trigger strings and handles them appropriately.
    Uses threading Event to allow for clean termination of the loop.
    Implements a linear falloff mechanism for retries when the log file doesn't exist.

    Args:
        stop_event: Threading Event used to signal the loop to stop
        :param stop_event:
        :param log_file:
    """
    # set initial to unix epoch time
    last_modified = datetime.datetime.fromtimestamp(0)
    last_seen_log_entry = None
    consecutive_failures = 0
    max_delay = 10  # Maximum delay in seconds
    base_delay = 1   # Base delay in seconds

    # validate existence of log file
    if not log_file.exists():
        logger.error(f"Log file does not exist: {log_file}.")
        return

    while stop_event is None or not stop_event.is_set():
        try:
            temp_last_modified = check_last_modified(log_file)

            # Handle case where log file doesn't exist
            if temp_last_modified is None:
                consecutive_failures += 1
                # Calculate delay with linear falloff (capped at max_delay)
                delay = min(base_delay * consecutive_failures, max_delay)
                logger.info(f"Log file not found. Retrying in {delay} seconds...")
                time.sleep(delay)
                continue

            # Reset failure counter if we successfully read the file
            consecutive_failures = 0

            if temp_last_modified > last_modified:
                last_modified = temp_last_modified
                entries = parse_log(log_file)

                if not entries:
                    logger.info(f"No entries found in the log file: {log_file}")
                    continue

                # initially, the newest entries will be on the end of the list
                if last_seen_log_entry is None and entries:
                    last_seen_log_entry = entries[0]  # Get the most recent entry
                    logger.info("Initial log entries loaded")
                    # Notify that logs have been loaded
                    if logs_loaded_event is not None:
                        logger.info("Logs have been loaded")
                        logs_loaded_event.set()
                else:
                    if last_seen_log_entry is None:
                        logger.warning("No previous log entry found, cannot compare timestamps.")
                        last_seen_log_entry = entries[0] if entries else None
                        continue
                    logger.info(f"Log file modified at {last_modified}. Old: {last_seen_log_entry.timestamp} Parsing new entries...")
                    # Check for entries newer than last_seen_log_entry
                    new_entries = [entry for entry in entries if entry.timestamp > last_seen_log_entry.timestamp]
                    if new_entries:
                        last_seen_log_entry = new_entries[0]  # Update to most recent entry
                        for entry in new_entries:
                            logger.info(str(entry))
                            check_trigger_strings(entry)
                    else:
                        logger.warning("No new entries found since last check despite file modification?")
            else:
                # logger.debug("No new entries found.")
                pass
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            consecutive_failures += 1
            # Calculate delay with linear falloff (capped at max_delay)
            delay = min(base_delay * consecutive_failures, max_delay)
            time.sleep(delay)
        else:
            # If no exception occurred, use the base delay
            time.sleep(base_delay)

def handle_failed_reference_tables(entry: LogEntry):
    """
    Example callback function for FAILED_GET_REFERENCE_TABLES trigger.
    In a real implementation, this would clear reference tables.
    """
    logger.info(f"ACTION: Clearing reference tables due to: {entry.message}")


def handle_failed_device_info(entry: LogEntry):
    """
    Example callback function for FAILED_GET_DEVICE_INFO trigger.
    In a real implementation, this would clear device info, cookies, and service worker.
    """
    logger.info(f"ACTION: Clearing device info, cookies, and service worker due to: {entry.message}")


def handle_corrupt_schema(entry: LogEntry):
    """
    Example callback function for CORRUPT_SCHEMA trigger.
    In a real implementation, this would perform a hard clear (deletion of appdata).
    """
    logger.info(f"ACTION: Performing hard clear (deletion of appdata) due to: {entry.message}")


def handle_stores_not_set_up(entry: LogEntry):
    """
    Example callback function for STORES_NOT_CORRECTLY_SET_UP trigger.
    In a real implementation, this would perform a hard clear (deletion of appdata).
    """
    logger.info(f"ACTION: Performing hard clear (deletion of appdata) due to: {entry.message}")


def setup_trigger_callbacks():
    """
    Set up callback functions for all trigger strings.
    """
    callbacks = {
        TriggerString.FAILED_GET_REFERENCE_TABLES: handle_failed_reference_tables,
        TriggerString.FAILED_GET_DEVICE_INFO: handle_failed_device_info,
        TriggerString.CORRUPT_SCHEMA: handle_corrupt_schema,
        TriggerString.STORES_NOT_CORRECTLY_SET_UP: handle_stores_not_set_up
    }
    register_trigger_callbacks(callbacks)


def main():
    # Set up callback functions for trigger strings
    setup_trigger_callbacks()

    # Create stop event for clean shutdown
    stop_event = Event()

    try:
        # Start the main loop
        main_loop(stop_event)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        stop_event.set()

    # check_last_modified()
    # entries = parse_standard_log()
    #
    # for entry in entries:
    #     print(entry)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        sys.exit(1)
