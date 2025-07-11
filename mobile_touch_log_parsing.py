import datetime
import enum
import os
import sys
import time
from pathlib import Path
from typing import Callable, List

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

    # response should be to do a hard clear (deletion of appdata)
    # this usually points to database corruption
    CORRUPT_SCHEMA = "init schema: error: Internal error"

    # response should be to do a hard clear (deletion of appdata)
    # this usually points to database corruption
    STORES_NOT_CORRECTLY_SET_UP = "Stores not correctly set up, db"


    def __init__(self, value):
        self._value_ = value

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
    :return: a list of lines from the log file
    """
    if not log_path.exists():
        raise FileNotFoundError(f"Log file does not exist: {log_path}")
    lines = []
    try :
        with log_path.open('r', encoding='utf-8') as file:
            for line in file:
                lines.append(line.strip())
    except Exception as e:
        print(f"Error reading log file: {e}", file=sys.stderr)

    return lines


def parse_standard_log() -> List[LogEntry]:
    """
    Example of a standard entry:
    2025-05-26 09:33:40,383 INFO JS API: getNativeVersion returned: 2023.2.208
    Parses the standard log file and extracts relevant information.
    
    Reads log entries from end to beginning, as the most recent entries are at the end.
    Returns a list of LogEntry objects in reverse chronological order (newest first).
    :return: List of LogEntry objects
    """
    log_entries = []
    lines = read_log_file(standard_log_path)
    cutoff_date = datetime.datetime.now() - datetime.timedelta(hours=2)
    for line in reversed(lines):
        try:
            entry = log_entry_from_line(line)
            # print(f"Processing log entry: {entry}")
            if entry.timestamp < cutoff_date:
                break
            log_entries.append(entry)
        except ValueError as e:
            print(f"Skipping invalid log entry: {e}", file=sys.stderr)

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
    :param log_entries:
    :return:
    """
    if not log_file.exists():
        raise FileNotFoundError(f"Log file does not exist: {log_file}")
    last_modified = log_file.stat().st_mtime
    last_modified_date = datetime.datetime.fromtimestamp(last_modified)
    return last_modified_date


def check_trigger_strings(entry: LogEntry):
    """
    Checks a log entry against all defined trigger strings.
    :param entry: LogEntry to check
    """
    for trigger in TriggerString:
        if trigger.value in entry.message:
            # TODO: Handle trigger string based on type
            print(f"Detected trigger string {trigger.name}: {entry}")


def main_loop():
    """
    Main loop for the log parsing script.
    Continuously checks the log file and processes new entries.
    Monitors for all defined trigger strings and handles them appropriately.
    """
    # set initial to unix epoch time
    last_modified = datetime.datetime.fromtimestamp(0)
    last_seen_log_entry = None
    while True:
        try:
            temp_last_modified = check_last_modified()
            if temp_last_modified > last_modified:
                last_modified = temp_last_modified
                entries = parse_standard_log()
                # initially, the newest entries will be on the end of the list
                if last_seen_log_entry is None and entries:
                    last_seen_log_entry = entries[0]  # Get the most recent entry
                    print("Initial log entries loaded")
                    print("Last seen log entry seen at:", last_seen_log_entry.timestamp)
                else:
                    print(f"Log file modified at {last_modified}. Parsing new entries...")
                    # Check for entries newer than last_seen_log_entry
                    new_entries = [entry for entry in entries if entry.timestamp > last_seen_log_entry.timestamp]
                    if new_entries:
                        last_seen_log_entry = new_entries[0]  # Update to most recent entry
                        for entry in new_entries:
                            print(entry)
                            check_trigger_strings(entry)
            else:
                # print("No new entries found.")
                pass
        except Exception as e:
            print(f"An error occurred: {e}", file=sys.stderr)
        finally:
            time.sleep(1)

def main():
    main_loop()
    check_last_modified()
    entries = parse_standard_log()

    for entry in entries:
        print(entry)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(1)