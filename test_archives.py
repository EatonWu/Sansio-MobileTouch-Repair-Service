import os
import sys
import zipfile
import shutil
import tempfile
import pytest
import time
import json
from pathlib import Path
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

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

def setup_chrome_driver(user_data_dir=None, profile_directory=None):
    """
    Set up the Chrome driver with custom profile paths.

    Args:
        user_data_dir (str, optional): Path to the user data directory. 
                                      Defaults to C:\\ProgramData\\Physio-Control\\MobileTouch.
        profile_directory (str, optional): Profile directory name. Defaults to AppData.

    Returns:
        webdriver.Chrome: Configured Chrome WebDriver instance
    """
    chrome_options = Options()

    # Set the Chrome binary location
    chrome_options.binary_location = ".\\chrome-win32\\chrome.exe"
    service = Service(executable_path=".\\chromedriver.exe")

    # Set the user data directory and profile
    if user_data_dir:
        chrome_options.add_argument(f"user-data-dir={user_data_dir}")
    else:
        chrome_options.add_argument("user-data-dir=C:\\ProgramData\\Physio-Control\\MobileTouch")

    if profile_directory:
        chrome_options.add_argument(f"profile-directory={profile_directory}")
    else:
        chrome_options.add_argument("profile-directory=AppData")

    # Required for IndexedDB access
    chrome_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

    return webdriver.Chrome(service=service, options=chrome_options)

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
    os.makedirs(TEMP_DIR, exist_ok=True)

    yield

    # Teardown
    clean_temp_directories()

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

def main():
    """
    Main function to run the test script with interactive archive selection.
    Allows the user to select a specific archive to test or run all archives.
    """
    try:
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
                success = _with_archive(archive.name)
                logger.info(f"Test {'succeeded' if success else 'failed'} for {archive.name}")
        else:
            try:
                # Test selected archive
                index = int(choice) - 1
                if 0 <= index < len(archives):
                    selected_archive = archives[index]
                    logger.info(f"\n\n=== Testing with archive: {selected_archive.name} ===")
                    success = _with_archive(selected_archive.name)
                    logger.info(f"Test {'succeeded' if success else 'failed'} for {selected_archive.name}")
                else:
                    logger.error(f"Invalid selection. Please enter a number between 1 and {len(archives)}")
            except ValueError:
                logger.error("Invalid input. Please enter a number or 'a'")

    finally:
        # Clean up
        clean_temp_directories()

if __name__ == "__main__":
    main()
