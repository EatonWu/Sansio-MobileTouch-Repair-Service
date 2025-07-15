import os
import sys
import traceback
import zipfile
import shutil
import tempfile
import pytest
import time
import json
import datetime
import random
from pathlib import Path
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

import mobile_touch_log_parsing
import mobiletouch_tools
from mobile_touch_log_parsing import main_loop, setup_trigger_callbacks, TriggerString, register_trigger_callback, \
    LogEntry, setup_test_callbacks
from mobiletouch_tools import validate_mobiletouch, setup_chrome_driver

standard_path = os.path.dirname("C:\\ProgramData\\Physio-Control\\MobileTouch\\")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

# Path to the test archives
TEST_ARCHIVES_DIR = Path("test_archives")
# Path to the metadata file
METADATA_FILE = TEST_ARCHIVES_DIR / "metadata.json"
# Temporary directory for extracted archives
TEMP_DIR = Path(tempfile.gettempdir()) / "mobiletouch_test_archives"


def extract_archive(archive_path, extract_to=None):
    """
    Extract a ZIP archive to a temporary directory.

    Args:
        archive_path (Path): Path to the archive file
        extract_to (Path, optional): Directory to extract to. If None, uses a temporary directory.

    Returns:
        Path: Path to the extracted directory
    """
    if extract_to is None:
        # Create a unique directory name based on the archive name
        archive_name = archive_path.stem.replace(" ", "_")
        extract_to = TEMP_DIR / archive_name

    # Create the extraction directory if it doesn't exist
    os.makedirs(extract_to, exist_ok=True)

    logger.info(f"Extracting {archive_path} to {extract_to}")

    # Extract the archive
    with zipfile.ZipFile(archive_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

    return extract_to

def load_archive(archive_name):
    """
    Load a test archive by name.

    Args:
        archive_name (str): Name of the archive file (without path)

    Returns:
        Path: Path to the extracted directory
    """
    archive_path = TEST_ARCHIVES_DIR / archive_name
    if not archive_path.exists():
        logger.error(f"Archive not found: {archive_path}")
        return None

    return extract_archive(archive_path)

def clean_temp_directories():
    """Remove all temporary directories created for archive extraction."""
    if TEMP_DIR.exists():
        logger.info(f"Cleaning up temporary directory: {TEMP_DIR}")
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

def load_metadata():
    """Load the metadata file that maps archives to error types."""
    if not METADATA_FILE.exists():
        logger.error(f"Metadata file not found: {METADATA_FILE}")
        return {}

    try:
        with open(METADATA_FILE, 'r') as f:
            metadata = json.load(f)
        return metadata
    except Exception as e:
        logger.error(f"Error loading metadata file: {e}")
        return {}

def get_archive_metadata(archive_name):
    """Get metadata for a specific archive."""
    metadata = load_metadata()
    if not metadata:
        return None

    for archive in metadata.get('archives', []):
        if archive['filename'] == archive_name:
            return archive

    logger.warning(f"No metadata found for archive: {archive_name}")
    return None

def list_available_archives():
    """List all available test archives in the test_archives directory."""
    if not TEST_ARCHIVES_DIR.exists():
        logger.error(f"Test archives directory not found: {TEST_ARCHIVES_DIR}")
        return []

    archives = [f for f in TEST_ARCHIVES_DIR.iterdir() if f.is_file() and f.suffix.lower() == '.zip']
    return archives

def _with_archive(archive_name):
    """
    Test MobileTouch with a specific archive.

    Args:
        archive_name (str): Name of the archive file (without path)

    Returns:
        bool: True if test was successful, False otherwise
    """
    try:
        # Get metadata for this archive
        archive_metadata = get_archive_metadata(archive_name)
        if archive_metadata:
            logger.info(f"Archive metadata: {archive_metadata}")
            should_produce_alerts = archive_metadata.get('produces_alerts', True)
            error_type = archive_metadata.get('error_type', 'Unknown')
            logger.info(f"Archive {archive_name} has error type {error_type} and should_produce_alerts={should_produce_alerts}")
        else:
            # Default behavior if no metadata is found
            logger.warning(f"No metadata found for archive {archive_name}. Assuming it should produce alerts.")
            should_produce_alerts = True

        # Extract the archive
        extracted_path = load_archive(archive_name)
        if not extracted_path:
            return False

        # Find the MobileTouch directory in the extracted archive
        mobiletouch_dir = None
        for root, dirs, files in os.walk(extracted_path):
            if "MobileTouch" in dirs:
                mobiletouch_dir = Path(root) / "MobileTouch"
                break

        if not mobiletouch_dir:
            logger.error(f"MobileTouch directory not found in extracted archive: {archive_name}")
            return False

        logger.info(f"Found MobileTouch directory: {mobiletouch_dir}")

        # Set up Chrome driver with the extracted profile
        driver = setup_chrome_driver(user_data_dir=str(mobiletouch_dir))

        try:
            # Navigate to MobileTouch URL
            logger.info("Opening MobileTouch in Chrome")
            driver.get("https://mobiletouch.healthems.com")

            # Wait for alerts if the archive is expected to produce them
            if should_produce_alerts:
                logger.info("Waiting for alerts...")

                # Keep checking for alerts until none found for 5 seconds
                last_alert_time = time.time()
                alert_found = False
                wait_time = 10  # Initial wait time of 10 seconds

                while True:
                    try:
                        alert = WebDriverWait(driver, wait_time).until(EC.alert_is_present())
                        alert_text = alert.text
                        logger.info(f"Alert found: {alert_text}")
                        alert_found = True
                        alert.accept()
                        wait_time = max(1, min(wait_time - 1, 5))  # Decrease wait time, but keep between 1-5 seconds
                        last_alert_time = time.time()
                    except:
                        # If no alert found for 1 second, break the loop
                        if time.time() - last_alert_time > 1:
                            logger.info("No new alerts for 1 second, continuing...")
                            break

                # Get page title
                title = driver.title
                logger.info(f"Page title: {title}")

                # Get console logs
                logs = driver.get_log("browser")
                for log in logs:
                    logger.debug(f"Browser log: {log}")

                # Test is successful only if alerts were found (for archives that should produce alerts)
                if not alert_found:
                    logger.error(f"No alerts detected for archive {archive_name}. Expected alerts for error type {error_type}.")
                    return False

                logger.info(f"Test successful: Alerts detected for error type {error_type} in archive {archive_name}")
                return True
            else:
                # For archives that shouldn't produce alerts, we consider the test successful if no alerts are shown
                logger.info(f"Archive {archive_name} is not expected to produce alerts. Waiting briefly...")

                # Wait a short time to see if any unexpected alerts appear
                alert_found = False
                try:
                    alert = WebDriverWait(driver, 3).until(EC.alert_is_present())
                    alert_text = alert.text
                    logger.warning(f"Unexpected alert found: {alert_text}")
                    alert_found = True
                    alert.accept()
                except:
                    logger.info("No alerts found, as expected.")

                # Get page title
                title = driver.title
                logger.info(f"Page title: {title}")

                # Get console logs
                logs = driver.get_log("browser")
                for log in logs:
                    logger.debug(f"Browser log: {log}")

                # For archives that shouldn't produce alerts, success means no alerts were found
                if alert_found:
                    logger.error(f"Unexpected alerts detected for archive {archive_name}. This archive should not produce alerts.")
                    return False

                logger.info(f"Test successful: No alerts detected for error type {error_type} in archive {archive_name}, as expected")
                return True
        finally:
            driver.quit()

    except Exception as e:
        logger.error(f"Error testing with archive {archive_name}: {e}")
        return False

# Pytest fixtures
@pytest.fixture(scope="session")
def setup_temp_dir():
    """Fixture to set up and tear down the temporary directory."""
    # Setup
    clean_temp_directories()
    os.makedirs(TEMP_DIR, exist_ok=True)

    yield

@pytest.fixture
def available_archives():
    """Fixture to get available archives."""
    return list_available_archives()

# Pytest tests
def test_archives_exist():
    """Test that test archives exist."""
    archives = list_available_archives()
    assert len(archives) > 0, "No test archives found"

@pytest.mark.parametrize("archive", list_available_archives(), ids=lambda x: x.name)
def test_archive_loading(setup_temp_dir, archive):
    """Test loading each available archive."""
    logger.info(f"Testing archive: {archive.name}")
    result = _with_archive(archive.name)
    assert result, f"Failed to load archive: {archive.name}"

@pytest.mark.parametrize("archive", list_available_archives(), ids=lambda x: x.name)
def test_archive_parsing_fake_logs(setup_temp_dir, archive):
    """
    Test that archives can be loaded and that the mobile_touch_log_parsing loop
    correctly identifies and repairs issues by triggering the appropriate callbacks.

    This test uses fake logs injected into the log file to trigger callbacks.
    This is to differentiate issues with the MobileTouch application itself
    not generating appropriate logs/error messages.

    This test verifies that:
    1. The archive can be loaded successfully
    2. The main_loop function correctly processes log entries
    3. Callbacks are triggered only on subsequent log modifications, not on initial load
    """
    logger.info(f"Testing archive repair with fake logs for: {archive.name}")
    result, triggered_callbacks = _with_archive_parse_fake_logs(archive.name)
    assert result, f"Failed to load archive: {archive.name}"

    # The assertion for callbacks being triggered is now handled in _with_archive_repair_fake_logs
    # This ensures that the test fails if no callbacks are triggered

    # Log which callbacks were triggered
    for trigger, count in triggered_callbacks.items():
        if count > 0:
            logger.info(f"Callback for {trigger.name} was triggered {count} times")

    logger.info(f"Test completed successfully for archive: {archive.name}")

def test_epcr059_fake_logs():
    """
    Test the specific archive for EPCR059 error type.

    This test is designed to ensure that the archive with EPCR059 error type
    can be loaded and processed correctly.
    """
    clean_temp_directories()
    archive_name = "EPCR059 (CF-20) MobileTouch Unexpected Error.zip"
    logger.info(f"Testing specific archive: {archive_name}")
    result = _with_archive_parse_fake_logs(archive_name)
    assert result, f"Fake log test failed for archive: {archive_name}"


def test_epcr059_real_logs():
    """
    Test the specific archive for EPCR059 error type with real logs.

    This test is designed to ensure that the archive with EPCR059 error type
    can be loaded and processed correctly using real logs.
    """
    clean_temp_directories()
    archive_name = "EPCR059 (CF-20) MobileTouch Unexpected Error.zip"
    logger.info(f"Testing specific archive with real logs: {archive_name}")
    result, triggered_callbacks = _with_archive_parse_real_logs(archive_name)
    assert result, f"Real log test failed for archive: {archive_name}"

    # Log which callbacks were triggered
    for trigger, count in triggered_callbacks.items():
        if count > 0:
            logger.info(f"Callback for {trigger.name} was triggered {count} times")


def test_epcr059_repair_metadata():
    """
    Test the specific archive for EPCR059 error type with metadata repair.

    This test is designed to ensure that the archive with EPCR059 error type
    can be repaired using metadata and processed correctly.
    """
    clean_temp_directories()
    archive_name = "EPCR059 (CF-20) MobileTouch Unexpected Error.zip"
    logger.info(f"Testing specific archive repair from metadata: {archive_name}")
    result = _with_archive_repair_from_metadata(archive_name)
    assert result, f"Repair from metadata failed for archive: {archive_name}"

@pytest.mark.parametrize("archive", list_available_archives(), ids=lambda x: x.name)
def test_archive_parsing_real_logs(setup_temp_dir, archive):
    """
    Test that archives can be loaded and that the mobile_touch_log_parsing loop
    correctly identifies and repairs issues by triggering the appropriate callbacks.

    This test uses the real logs from the archive to trigger callbacks.

    This test verifies that:
    1. The archive can be loaded successfully
    2. The main_loop function correctly processes log entries
    3. Callbacks are triggered based on the actual log entries in the archive
    """
    logger.info(f"Testing archive repair with real logs for: {archive.name}")
    result, triggered_callbacks = _with_archive_parse_real_logs(archive.name)
    assert result, f"Failed to load archive: {archive.name}"

    # Log which callbacks were triggered
    callback_triggered = False
    for trigger, count in triggered_callbacks.items():
        if count > 0:
            callback_triggered = True
            logger.info(f"Callback for {trigger.name} was triggered {count} times")

    assert callback_triggered, f"No callbacks were triggered for archive: {archive.name}. This might indicate that the real logs with trigger strings were not generated or detected."


@pytest.mark.parametrize("archive", list_available_archives(), ids=lambda x: x.name)
def test_archive_repair_from_metadata(setup_temp_dir, archive):
    logger.info(f"Testing archive repair from metadata for: {archive.name}")
    result = _with_archive_repair_from_metadata(archive.name)
    assert result, f"Failed to repair archive: {archive.name}"


def _with_archive_parse_fake_logs(archive_name):
    """
    Test MobileTouch with a specific archive, including running the mobile_touch_log_parsing loop
    to validate that the correct callbacks are triggered.

    This version injects fake logs into the log file to trigger callbacks.

    Args:
        archive_name (str): Name of the archive file (without path)

    Returns:
        tuple: (bool, dict) where bool is True if test was successful, False otherwise,
               and dict maps TriggerString to the number of times its callback was triggered
    """
    try:
        # Get metadata for this archive
        archive_metadata = get_archive_metadata(archive_name)
        error_type_name = archive_metadata.get('error_type', 'UNKNOWN')

        # Get the TriggerString enum value directly by name
        try:
            error_type = getattr(TriggerString, error_type_name)
        except AttributeError:
            logger.warning(f"Unknown error type: {error_type_name}, using UNKNOWN")
            error_type = TriggerString.UNKNOWN

        logger.info(f"Archive {archive_name} has error type {error_type}")

        # Extract the archive first to find the log file
        extracted_path = load_archive(archive_name)
        if not extracted_path:
            return False, {}

        # Find the MobileTouch directory in the extracted archive
        mobiletouch_dir = None
        for root, dirs, files in os.walk(extracted_path):
            if "MobileTouch" in dirs:
                mobiletouch_dir = Path(root) / "MobileTouch"
                break

        if not mobiletouch_dir:
            logger.error(f"MobileTouch directory not found in extracted archive: {archive_name}")
            return False, {}

        # Look for the log file in the MobileTouch directory
        log_path = None
        for root, dirs, files in os.walk(mobiletouch_dir):
            for file in files:
                if file.lower() == "mobiletouch.log":
                    log_path = Path(root) / file
                    break
            if log_path:
                break

        if not log_path:
            logger.warning(f"No log file found in archive: {archive_name}. Creating an empty one.")
            # Create an empty log file in the MobileTouch directory
            log_path = mobiletouch_dir / "logging" / "mobiletouch.log"
            logger.info(f"Creating log file at {log_path}")
            os.makedirs(log_path.parent, exist_ok=True)
            with open(log_path, 'w') as f:
                # fake initial log entry so that it's not empty
                logging.info("Creating log file for testing purposes")
                f.write("2025-07-14 08:09:48,878 INFO [Console] [INFO] Starting application\n")
                time.sleep(1)
                f.write("2025-07-14 08:09:49,879 INFO [Console] [INFO] Application started successfully\n")

        logger.info(f"Using log file at {log_path}")

        # Initialize the triggered_callbacks dictionary
        triggered_callbacks = {trigger: 0 for trigger in TriggerString}

        # Set up test trigger callbacks that will update the triggered_callbacks dictionary
        logger.info("Setting up test trigger callbacks...")

        def temp_callback(entry):
            """
            Temporary callback function to update triggered_callbacks.
            This will be called when the trigger string is detected in a log entry.
            """
            logger.info(f"Callback triggered for {error_type.name} with entry: {entry}")
            triggered_callbacks[error_type] += 1


        setup_trigger_callbacks()
        # Register our callback for the specific error type, overwriting default one
        register_trigger_callback(error_type, temp_callback)

        # Start the main loop in a separate thread BEFORE loading the archive in Selenium
        logger.info("Starting mobile_touch_log_parsing main loop...")
        import threading
        stop_event = threading.Event()
        logs_loaded_event = threading.Event()
        # Override the standard_log_path in mobile_touch_log_parsing to use our test log file

        def run_main_loop():
            logging.info(f"Starting main loop with parameter log path: {log_path}")
            main_loop(stop_event=stop_event, logs_loaded_event=logs_loaded_event,log_file=log_path)

        main_thread = threading.Thread(target=run_main_loop)
        main_thread.start()

        # Inject a few more fake logs to ensure the main loop processes them
        for i in range(5):
            with open(log_path, 'a') as log_file:
                fake_log_entry = f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]} INFO Fake log entry {i}\n"
                log_file.write(fake_log_entry)
                logger.info(f"Injected fake log entry: {fake_log_entry.strip()}")
                time.sleep(0.5)

        logger.info("Injecting fake logs to trigger callbacks...")
        # Format should match: 2025-05-26 09:33:40,383 INFO JS API: getNativeVersion returned: 2023.2.208
        # The trigger string needs to be in the message part (after the log level)
        fake_log_entry = f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]} ERROR {error_type.value}\n"

        with open(log_path, 'a') as log_file:
            log_file.write(fake_log_entry)
            logger.info(f"Injected fake log entry: {fake_log_entry.strip()}")

        # Allow some time for the main loop to process the injected log
        time.sleep(5)
        stop_event.set()

        # Wait for the main loop to complete
        main_thread.join()

        logger.info(f"Main loop completed. Triggered callbacks: {triggered_callbacks}")

        # Verify that callbacks were triggered
        assert triggered_callbacks[error_type] > 0, f"No callbacks were triggered for error type {error_type}"

        return True, triggered_callbacks

    except Exception as e:
        logger.error(f"Error in _with_archive_repair_fake_logs for archive {archive_name}: {e}")
        return False, {}


def _with_archive_parse_real_logs(archive_name):
    """
    Test MobileTouch with a specific archive, including running the mobile_touch_log_parsing loop
    to validate that the correct callbacks are triggered.

    This version doesn't inject fake logs but instead ensures that the test archives
    actually generate the required logs and trigger the desired callbacks.

    Args:
        archive_name (str): Name of the archive file (without path)

    Returns:
        tuple: (bool, dict) where bool is True if test was successful, False otherwise,
               and dict maps TriggerString to the number of times its callback was triggered
    """
    try:
        # Get metadata for this archive
        archive_metadata = get_archive_metadata(archive_name)
        if archive_metadata:
            error_type_name = archive_metadata.get('error_type', 'UNKNOWN')

            # Get the TriggerString enum value directly by name
            try:
                error_type = getattr(TriggerString, error_type_name)
            except AttributeError:
                logger.warning(f"Unknown error type: {error_type_name}, using UNKNOWN")
                error_type = TriggerString.UNKNOWN

            logger.info(f"Archive {archive_name} has error type {error_type}")
        else:
            logger.warning(f"No metadata found for archive {archive_name}, using UNKNOWN error type")
            error_type = TriggerString.UNKNOWN

        # Extract the archive first to find the log file
        extracted_path = load_archive(archive_name)
        if not extracted_path:
            return False, {}

        # Find the MobileTouch directory in the extracted archive
        mobiletouch_dir = None
        for root, dirs, files in os.walk(extracted_path):
            if "MobileTouch" in dirs:
                mobiletouch_dir = Path(root) / "MobileTouch"
                break

        if not mobiletouch_dir:
            logger.error(f"MobileTouch directory not found in extracted archive: {archive_name}")
            return False, {}

        # Look for the log file in the MobileTouch directory
        log_path = None
        for root, dirs, files in os.walk(mobiletouch_dir):
            for file in files:
                if file.lower() == "mobiletouch.log":
                    log_path = Path(root) / file
                    break
            if log_path:
                break

        if not log_path:
            logger.warning(f"No log file found in archive: {archive_name}. Creating an empty one.")
            # Create an empty log file in the MobileTouch directory
            log_path = mobiletouch_dir / "logging" / "mobiletouch.log"
            os.makedirs(log_path.parent, exist_ok=True)
            with open(log_path, 'w') as f:
                pass

        logger.info(f"Using log file at {log_path}")

        # Initialize the triggered_callbacks dictionary
        triggered_callbacks = {trigger: 0 for trigger in TriggerString}

        def temp_callback(entry):
            """
            Temporary callback function to update triggered_callbacks.
            This will be called when the trigger string is detected in a log entry.
            """
            logger.info(f"Callback triggered for {error_type.name} with entry: {entry}")
            triggered_callbacks[error_type] += 1

        setup_trigger_callbacks()
        # Register our callback for the specific error type, overwriting default one
        register_trigger_callback(error_type, temp_callback)

        # Start the main loop in a separate thread BEFORE loading the archive in Selenium
        logger.info("Starting mobile_touch_log_parsing main loop...")
        import threading
        stop_event = threading.Event()

        def run_main_loop():
            main_loop(stop_event, log_file=log_path)

        main_thread = threading.Thread(target=run_main_loop)
        main_thread.start()

        # Set up Chrome driver with the extracted profile
        logger.info("Setting up Chrome driver...")
        driver = setup_chrome_driver(user_data_dir=str(mobiletouch_dir), profile_directory="AppData")

        try:
            # Navigate to MobileTouch URL
            logger.info("Opening MobileTouch in Chrome")
            driver.get("https://mobiletouch.healthems.com")

            last_alert_time = time.time()
            wait_time = 10  # Initial wait time of 15 seconds
            logs = []
            while True:
                try:
                    alert = WebDriverWait(driver, wait_time).until(EC.alert_is_present())
                    print(f"Alert found: {alert.text}")
                    alert.accept()
                    wait_time = max(1, min(wait_time - 1, 5))  # Decrease wait time, but keep between 1-5 seconds
                    last_alert_time = time.time()
                except:
                    # If no alert found for 5 seconds, break the loop
                    if time.time() - last_alert_time > 1:
                        print("No new alerts for 5 seconds, continuing...")
                        logger.info("Retrieving browser logs...")
                        logs = driver.get_log("browser")
                        break
        finally:
            # Close the driver
            driver.quit()

        for log in logs:
            timestamp = datetime.datetime.fromtimestamp(log['timestamp'] / 1000.0)
            log_level = log['level']
            message = log['message']
            timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]  # Format to match log entry format
            try:
                log_entry = LogEntry(timestamp_str, log_level, message)
                logger.info(f"Log entry created: {log_entry}")
                with open(log_path, 'a') as log_file:
                    log_file.write(f"{str(log_entry)}\n")
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Error creating LogEntry: {e}")
                continue

        # Allow some time for the main loop to process the logs
        time.sleep(10)

        stop_event.set()
        main_thread.join()

        logger.info(f"Main loop completed. Triggered callbacks: {triggered_callbacks}")

        # Verify that callbacks were triggered
        callback_triggered = False
        for trigger, count in triggered_callbacks.items():
            if count > 0:
                callback_triggered = True
                logger.info(f"Callback for {trigger.name} was triggered {count} times")

        assert callback_triggered, f"No callbacks were triggered for archive {archive_name}. This might indicate that the real logs with trigger strings were not generated or detected."
        return True, triggered_callbacks
    except Exception as e:
        logger.error(f"Error in _with_archive_repair_real_logs for archive {archive_name}: {e}")
        return False, {}

def _with_archive_repair_from_metadata(archive_name):
    """
    Loads the specified archive, extracts it, and processes the log file, performs the
    repair mapped from the metadata file. It should be fixed at this point, which we
    can validate using the validate_mobiletouch() function from mobiletouch_tools.py

    Args:
        archive_name (str): Name of the archive file (without path)

    Returns:
        bool: True if test was successful, False otherwise
    """
    try:
        # Get metadata for this archive
        archive_metadata = get_archive_metadata(archive_name)
        if not archive_metadata:
            logger.error(f"No metadata found for archive {archive_name}")
            return False

        error_type_name = archive_metadata.get('error_type', 'UNKNOWN')

        # Get the TriggerString enum value directly by name
        try:
            error_type = getattr(TriggerString, error_type_name)
        except AttributeError:
            logger.warning(f"Unknown error type: {error_type_name}, using UNKNOWN")
            error_type = TriggerString.UNKNOWN

        logger.info(f"Archive {archive_name} has error type {error_type}")

        # Extract the archive first to find the log file
        extracted_path = load_archive(archive_name)
        if not extracted_path:
            return False

        mobiletouch_dir = None
        for root, dirs, files in os.walk(extracted_path):
            if "MobileTouch" in dirs:
                mobiletouch_dir = Path(root) / "MobileTouch"
                break

        if not mobiletouch_dir:
            logger.error(f"MobileTouch directory not found in extracted archive: {archive_name}")
            return False, {}

        # Look for the log file in the MobileTouch directory
        log_path = None
        for root, dirs, files in os.walk(mobiletouch_dir):
            for file in files:
                if file.lower() == "mobiletouch.log":
                    log_path = Path(root) / file
                    break
            if log_path:
                break

        if not log_path:
            logger.warning(f"No log file found in archive: {archive_name}. Creating an empty one.")
            # Create an empty log file in the MobileTouch directory
            log_path = mobiletouch_dir / "logging" / "mobiletouch.log"
            os.makedirs(log_path.parent, exist_ok=True)
            with open(log_path, 'w') as f:
                pass


        driver = setup_chrome_driver(user_data_dir=str(mobiletouch_dir), profile_directory="AppData")
        with driver:
            result = validate_mobiletouch(driver)
            assert not result, f"Validation failed before repair for archive {archive_name}"


        callbacks_dict = mobile_touch_log_parsing.get_default_callback_dict()
        function_to_call = callbacks_dict.get(error_type, None)
        assert function_to_call is not None, f"No callback function found for error type {error_type}"

        # Call the function to repair the archive
        logger.info(f"Calling repair function for error type {error_type}")
        try:
            function_to_call(None, mobiletouch_dir)
            logger.info(f"Repair function for error type {error_type} completed successfully")
        except Exception as e:
            logger.error(f"Error calling repair function for error type {error_type}: {e}")
            return False

        with setup_chrome_driver(user_data_dir=str(mobiletouch_dir), profile_directory="AppData") as driver:
            # Validate the MobileTouch application after repair
            logger.info("Validating MobileTouch application after repair...")
            result = validate_mobiletouch(driver)
            assert result, f"Validation failed after repair for archive {archive_name}"
            return True

    except Exception as e:
        logger.error(f"Error in _with_archive_repair_from_metadata for archive {archive_name}: {e}")
        logger.error(f"Stack trace: {traceback.format_exc()}")
        return False


def main():
    """
    Main function to run the test script with interactive archive selection.
    Allows the user to select a specific archive to test or run all archives.
    """
    try:

        clean_temp_directories()
        # Create temp directory if it doesn't exist
        os.makedirs(TEMP_DIR, exist_ok=True)

        # List available archives
        archives = list_available_archives()
        if not archives:
            logger.error("No test archives found")
            return

        # Display available archives with numbers
        logger.info(f"Found {len(archives)} test archives:")
        for i, archive in enumerate(archives):
            logger.info(f"{i+1}. {archive.name}")

        # Prompt user to select an archive
        print("\nSelect an archive to test (or enter 'a' to test all archives):")
        for i, archive in enumerate(archives):
            print(f"{i+1}. {archive.name}")

        choice = input("\nEnter your choice (number or 'a'): ")

        # Process user choice
        if choice.lower() == 'a':
            # Test all archives
            logger.info("Testing all archives...")
            for archive in archives:
                logger.info(f"\n\n=== Testing with archive: {archive.name} ===")
                success = _with_archive_parse_real_logs(archive.name)
                logger.info(f"Test {'succeeded' if success else 'failed'} for {archive.name}")
        else:
            try:
                # Test selected archive
                index = int(choice) - 1
                if 0 <= index < len(archives):
                    selected_archive = archives[index]
                    logger.info(f"\n\n=== Testing with archive: {selected_archive.name} ===")
                    success = _with_archive_parse_fake_logs(selected_archive.name)
                    logger.info(f"Test {'succeeded' if success else 'failed'} for {selected_archive.name}")
                else:
                    logger.error(f"Invalid selection. Please enter a number between 1 and {len(archives)}")
            except ValueError:
                logger.error("Invalid input. Please enter a number or 'a'")
    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
