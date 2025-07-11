import datetime
import enum
import logging
import os
import sys
import time
import threading
from pathlib import Path
from typing import Callable, List, Dict, Optional, Union

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

# using PyInstaller in windowed mode will cause sys.stdout and sys.stderr to be None
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
    # this usually points to missing device info or a corrupt object store
    FAILED_GET_DEVICE_INFO = "storeAction() fail: LoadByKey:getDeviceInfo"

    # The ones below require a hard reset, which is fine since the chart/app data is likely lost anyway

    # response should be to do a hard clear (deletion of appdata)
    # this usually points to database corruption
    CORRUPT_SCHEMA = "init schema: error: Internal error"

    # response should be to do a hard clear (deletion of appdata)
    # this usually points to database corruption
    STORES_NOT_CORRECTLY_SET_UP = "Stores not correctly set up, db"


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


def parse_standard_log(log_path: Path = standard_log_path) -> List[LogEntry]:
    """
    Example of a standard entry:
    2025-05-26 09:33:40,383 INFO JS API: getNativeVersion returned: 2023.2.208
    Parses the standard log file and extracts relevant information.

    Reads log entries from end to beginning, as the most recent entries are at the end.
    Returns a list of LogEntry objects in reverse chronological order (newest first).

    Args:
        log_path (Path, optional): Path to the log file. If None, uses standard_log_path.

    Returns:
        List[LogEntry]: List of LogEntry objects in reverse chronological order (newest first)
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


def main_loop(max_runtime=None, log_path=None, track_callbacks=False):
    """
    Main loop for the log parsing script.
    Continuously checks the log file and processes new entries.
    Monitors for all defined trigger strings and handles them appropriately.
    Implements a linear falloff mechanism for retries when the log file doesn't exist.

    Uses multithreading to separate the monitoring of the log file from the processing of log entries.
    Does not process log entries on initial load, only on subsequent modifications.

    Args:
        max_runtime (float, optional): Maximum time to run in seconds. If None, runs indefinitely.
        log_path (Path, optional): Path to the log file. If None, uses standard_log_path.
        track_callbacks (bool, optional): Whether to track which callbacks are triggered.

    Returns:
        dict: If track_callbacks is True, returns a dictionary mapping TriggerString to the number of times
              its callback was triggered. Otherwise, returns an empty dictionary.
    """
    if log_path is None:
        log_path = standard_log_path

    # For tracking callbacks
    triggered_callbacks = {trigger: 0 for trigger in TriggerString}

    # Thread-safe variables
    stop_event = threading.Event()
    callback_lock = threading.Lock()

    # Function to process log entries
    def process_entries(entries, is_initial_load=False):
        for entry in entries:
            if not is_initial_load:  # Skip processing on initial load
                logger.info(str(entry))
                if track_callbacks:
                    # Track which callbacks are triggered
                    with callback_lock:
                        for trigger in TriggerString:
                            if trigger.value in entry.message and trigger.callback:
                                triggered_callbacks[trigger] += 1
                check_trigger_strings(entry)

    # Function to monitor log file in a separate thread
    def monitor_log_file():
        # set initial to unix epoch time
        last_modified = datetime.datetime.fromtimestamp(0)
        last_seen_log_entry = None
        consecutive_failures = 0
        max_delay = 10  # Maximum delay in seconds
        base_delay = 1   # Base delay in seconds
        initial_load_done = False

        start_time = time.time()

        while not stop_event.is_set():
            # Check if we've exceeded the maximum runtime
            if max_runtime is not None and time.time() - start_time > max_runtime:
                logger.info(f"Maximum runtime of {max_runtime} seconds reached. Exiting monitor thread.")
                break

            try:
                temp_last_modified = check_last_modified(log_path)

                # Handle case where log file doesn't exist
                if temp_last_modified is None:
                    consecutive_failures += 1
                    # Calculate delay with linear falloff (capped at max_delay)
                    delay = min(base_delay * consecutive_failures, max_delay)
                    logger.debug(f"Log file not found. Retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue

                # Reset failure counter if we successfully read the file
                consecutive_failures = 0

                if temp_last_modified > last_modified:
                    last_modified = temp_last_modified
                    entries = parse_standard_log(log_path)

                    # Initially, the newest entries will be on the end of the list
                    if last_seen_log_entry is None and entries:
                        last_seen_log_entry = entries[0]  # Get the most recent entry
                        logger.info("Initial log entries loaded")
                        logger.info(f"Last seen log entry seen at: {last_seen_log_entry.timestamp}")

                        # Process initial entries but don't trigger callbacks
                        process_entries(entries, is_initial_load=True)
                        initial_load_done = True
                    elif initial_load_done:
                        logger.info(f"Log file modified at {last_modified}. Parsing new entries...")
                        # Check for entries newer than last_seen_log_entry
                        new_entries = [entry for entry in entries if entry.timestamp > last_seen_log_entry.timestamp]
                        if new_entries:
                            last_seen_log_entry = new_entries[0]  # Update to most recent entry
                            # Process new entries and trigger callbacks
                            process_entries(new_entries, is_initial_load=False)
                else:
                    # logger.debug("No new entries found.")
                    pass
            except Exception as e:
                logger.error(f"An error occurred in monitor thread: {e}")
                consecutive_failures += 1
                # Calculate delay with linear falloff (capped at max_delay)
                delay = min(base_delay * consecutive_failures, max_delay)
                time.sleep(delay)
            else:
                # If no exception occurred, use the base delay
                time.sleep(base_delay)

    # Start the monitor thread
    monitor_thread = threading.Thread(target=monitor_log_file, daemon=True)
    monitor_thread.start()

    try:
        # Wait for the monitor thread to complete or for max_runtime to be reached
        if max_runtime is not None:
            monitor_thread.join(max_runtime + 1)  # Add 1 second buffer
        else:
            monitor_thread.join()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Stopping monitor thread.")
    finally:
        # Signal the monitor thread to stop
        stop_event.set()
        # Wait for the monitor thread to finish
        if monitor_thread.is_alive():
            monitor_thread.join(timeout=2)

    return triggered_callbacks if track_callbacks else {}

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

    # Example of registering a single callback
    # register_trigger_callback(TriggerString.FAILED_GET_REFERENCE_TABLES, handle_failed_reference_tables)

    # Start the main loop
    # When running as the main program, we want to run indefinitely
    main_loop(max_runtime=None, log_path=standard_log_path, track_callbacks=False)

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
