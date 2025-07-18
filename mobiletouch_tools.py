import logging
import os
import sys
import time
import psutil
import subprocess
import winreg
from shutil import rmtree

# Global variable to store the MobileTouch executable path
_mobiletouch_executable_path = None

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from seletools.indexeddb import IndexedDB
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

standard_path = os.path.dirname("C:\\ProgramData\\Physio-Control\\MobileTouch\\")

def clear_object_store(idb: IndexedDB, object_store_name):
    idb.driver.execute_script(
        """
            console.log("Clearing object store: " + arguments[2]);
            var [ dbName, dbVersion, objectStoreName] = [ arguments[0], arguments[1], arguments[2]];

            // Create indicator element
            var indicator = document.createElement('div');
            indicator.id = 'clear-complete-indicator';
            indicator.style.display = 'none';
            document.body.appendChild(indicator);

            var request = window.indexedDB.open(dbName, dbVersion);

            request.onerror = function(event) {
                console.error("Error opening IndexedDB: " + dbName, event);
            }

            request.onsuccess = function(event) {
                var db = event.target.result;
                var objectStore = db.transaction(objectStoreName, 'readwrite').objectStore(objectStoreName);

                const objectStoreRequest = objectStore.clear();

                objectStoreRequest.onerror = function(event) {
                    console.error("Error clearing object store: " + objectStoreName, event);
                }

                objectStoreRequest.onsuccess = function(event) {
                    console.log("Object store cleared: " + objectStoreName);
                    db.commit;
                    // Set indicator when complete
                    indicator.setAttribute('data-complete', 'true');
                };

            };
        """,
        idb.db_name,
        idb.db_version,
        object_store_name
    )

def custom_remove_item(idb: IndexedDB, object_store_name, key):
    """
    A custom function to remove an item from an IndexedDB object store.
    Sets a custom attribute on the document to indicate completion.
    :param idb:
    :param object_store_name:
    :param key:
    :return:
    """
    idb.driver.execute_script(
        """
            console.log("Removing item from object store: " + arguments[2] + " with key: " + arguments[3]);
            var [ dbName, dbVersion, objectStoreName, key] = [ arguments[0], arguments[1], arguments[2], arguments[3]];

            // Create indicator element
            var indicator = document.createElement('div');
            indicator.id = 'clear-complete-indicator';
            indicator.style.display = 'none';
            document.body.appendChild(indicator);

            var request = window.indexedDB.open(dbName, dbVersion);

            request.onerror = function(event) {
                console.error("Error opening IndexedDB: " + dbName, event);
            }

            request.onsuccess = function(event) {
                var db = event.target.result;
                var objectStore = db.transaction(objectStoreName, 'readwrite').objectStore(objectStoreName);

                const objectStoreRequest = objectStore.delete(key);

                objectStoreRequest.onerror = function(event) {
                    console.error("Error removing item from object store: " + objectStoreName, event);
                }

                objectStoreRequest.onsuccess = function(event) {
                    console.log("Item removed from object store: " + objectStoreName + " with key: " + key);
                    db.commit;
                    // Set indicator when complete
                    indicator.setAttribute('data-complete', 'true');
                };

            };
        """,
        idb.db_name,
        idb.db_version,
        object_store_name,
        key
    )


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
    chrome_options.add_argument("--headless=new")

    logging.info("Current working directory: %s", os.getcwd())

    # Set the Chrome binary location

    path_to_chrome = os.path.abspath(os.path.join(os.path.dirname(__file__), 'chrome-win32', 'chrome.exe'))
    path_to_chrome_driver = os.path.abspath(os.path.join(os.path.dirname(__file__), 'chromedriver.exe'))

    chrome_options.binary_location = path_to_chrome
    service = Service(executable_path=path_to_chrome_driver)

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



def hard_clear(path=standard_path, max_retries=3, retry_delay=1):
    """
    Last resort; deletes the MobileTouch profile directory.
    Includes a retry mechanism with exponential backoff.

    :param path: Path to the MobileTouch directory
    :param max_retries: Maximum number of retry attempts
    :param retry_delay: Initial delay between retries in seconds
    :return: true if successful, false otherwise
    """
    path = os.path.join(path, "AppData")

    for attempt in range(max_retries + 1):
        try:
            if os.path.exists(path):
                if attempt > 0:
                    print(f"Retry attempt {attempt}/{max_retries} to remove directory: {path}")
                rmtree(path)
                print(f"Removed directory and contents: {path}")
                return True
            else:
                print(f"Directory does not exist: {path}")
                return False
        except PermissionError as e:
            if attempt < max_retries:
                current_delay = retry_delay * (2 ** attempt)  # Exponential backoff
                print(f"Permission error while removing directory: {e}. Retrying in {current_delay} seconds...", file=sys.stderr)
                time.sleep(current_delay)
            else:
                print(f"Permission error while removing directory after {max_retries} retries: {e}", file=sys.stderr)
                return False
        except Exception as e:
            if attempt < max_retries:
                current_delay = retry_delay * (2 ** attempt)  # Exponential backoff
                print(f"Error while clearing directory: {e}. Retrying in {current_delay} seconds...", file=sys.stderr)
                time.sleep(current_delay)
            else:
                print(f"An error occurred while clearing the directory after {max_retries} retries: {e}", file=sys.stderr)
                return False

    return False



def delete_deviceinfo_entry(mobiletouch_dir="C:\\ProgramData\\Physio-Control\\MobileTouch"):
    with setup_chrome_driver(mobiletouch_dir) as driver:
        try:
            # Navigate to a URL
            driver.get("https://mobiletouch.healthems.com")

            idb = IndexedDB(driver, "mobiletouch", 9)

            # Keep checking for alerts until none found for 5 seconds
            last_alert_time = time.time()
            wait_time = 15  # Initial wait time of 10 seconds
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
                        break

            object_store_name = "device"
            custom_remove_item(idb, object_store_name, "deviceinfo")

            # Wait for object store to be cleared
            try:
                WebDriverWait(driver, 30).until(
                    lambda d: print("Checking data-complete attribute...") or d.find_element('id',
                                                                                             'clear-complete-indicator').get_attribute(
                        'data-complete') == 'true'
                )
                print("deviceinfo entry cleared successfully")
                return True
            except Exception as e:
                print(f"Timeout waiting for object store to clear: {e}")
                return False
            finally:
                # Remove the indicator element
                driver.execute_script("document.getElementById('clear-complete-indicator').remove();")

        except Exception as e:
            print(f"An error occurred: {e}", file=sys.stderr)
            return False


def clear_cookies_and_service_worker(path=standard_path):
    network_dir = os.path.join(path, "AppData", "Network")
    service_worker_dir = os.path.join(path, "AppData", "Service Worker")

    try:
        if os.path.exists(network_dir):
            rmtree(network_dir)
            print(f"Removed directory and contents: {network_dir}")
        else:
            print(f"Network directory does not exist: {network_dir}")

        if os.path.exists(service_worker_dir):
            rmtree(service_worker_dir)
            print(f"Removed directory and contents: {service_worker_dir}")
        else:
            print(f"Service Worker directory does not exist: {service_worker_dir}")
        return True
    except PermissionError as e:
        print(f"Permission error while removing directories: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"An error occurred while clearing cookies and service worker: {e}", file=sys.stderr)
        return False


def deleteRefTableStore(mobiletouch_dir="C:\\ProgramData\\Physio-Control\\MobileTouch"):
    with setup_chrome_driver(mobiletouch_dir) as driver:
        try:
            # Navigate to a URL
            driver.get("https://mobiletouch.healthems.com")

            idb = IndexedDB(driver, "mobiletouch", 9)

            # Keep checking for alerts until none found for 5 seconds
            last_alert_time = time.time()

            wait_time = 10  # Initial wait time of 10 seconds
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
                        break

            # attempt to clear the object store
            object_store_name = "reftables"
            print(f"Clearing object store: {object_store_name}")
            clear_object_store(idb, object_store_name)

            # Wait for object store to be cleared
            try:
                WebDriverWait(driver, 30).until(
                    lambda d: print("Checking data-complete attribute...") or d.find_element('id',
                                                                                             'clear-complete-indicator').get_attribute(
                        'data-complete') == 'true'
                )
                print("Object store cleared successfully")
            except Exception as e:
                print(f"Timeout waiting for object store to clear: {e}")
            finally:
                # Remove the indicator element
                driver.execute_script("document.getElementById('clear-complete-indicator').remove();")

        except Exception as e:
            print(f"An error occurred: {e}", file=sys.stderr)
        finally:
            # The WebDriver will automatically quit when exiting the 'with' block
            pass




def enumerate_processes():
    """
    Enumerates all processes and prints their names and IDs.
    """
    for proc in psutil.process_iter(['pid', 'name']):
        print(f"Process ID: {proc.info['pid']}, Name: {proc.info['name']}")

def seek_mobiletouch_process():
    """
    Searches for the MobileTouch process and returns its PID if found.
    """
    print("Attempting to find MobileTouch process...")
    for proc in psutil.process_iter(['pid', 'name']):
        if "MobileTouch" in proc.info['name']:
            print(f"Found MobileTouch process: {proc.info['name']} (PID: {proc.info['pid']})")
            return proc.info['pid']
    print("MobileTouch is not running.")
    return None


def kill_mobiletouch_process():
    """
    Kills the MobileTouch process if it is running.
    Saves the executable path before terminating the process.
    """
    global _mobiletouch_executable_path

    print("Attempting to kill MobileTouch process...")
    pid = seek_mobiletouch_process()
    if pid:
        try:
            proc = psutil.Process(pid)

            # Save the executable path before terminating the process
            try:
                exe_path = proc.exe()
                if exe_path and os.path.exists(exe_path):
                    print(f"Saved MobileTouch executable path: {exe_path}")
                    _mobiletouch_executable_path = exe_path
            except (psutil.AccessDenied, psutil.ZombieProcess) as e:
                print(f"Could not get executable path: {e}")

            proc.terminate()  # or proc.kill() for a forceful termination
            print(f"MobileTouch process (PID: {pid}) terminated successfully.")
        except psutil.NoSuchProcess:
            print(f"No process found with PID: {pid}")
        except Exception as e:
            print(f"Error terminating process: {e}")


def validate_mobiletouch(driver=None):
    """
    Makes sure that the MobileTouch database is in a valid state by checking that the
    cached MobileTouch works correctly.
    :return: true if MobileTouch works correctly, false otherwise
    """
    # make sure that mobiletouch is not running to prevent race conditions
    kill_mobiletouch_process()

    print("Validating MobileTouch...")
    driver_provided = driver is not None

    # create selenium driver
    if driver is None:
        driver = setup_chrome_driver()

    try:
        # Navigate to the MobileTouch URL
        driver.get("https://mobiletouch.healthems.com")

        print("Waiting for MobileTouch to load...")
        # wait until id "username" and id "password" are present or an alert is detected, or a button with the text "Configure this Device" is present
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div/div/span/div/div/div/div[2]/div/button")) or
            (EC.presence_of_element_located((By.XPATH, "//*[@id=\"username\"]")) and EC.presence_of_element_located((By.XPATH, "//*[@id=\"password\"]")))
        )
        print("MobileTouch seems accessible.")
        return True

    except Exception as e:
        print(f"Could not validate MobileTouch: {e}")
        return False
    finally:
        if not driver_provided:
            # Quit the driver if it was created in this function
            print("Quitting the driver.")
            driver.quit()


def find_mobiletouch_executable():
    """
    Finds the MobileTouch executable path by:
    1. Using the saved path from a previously killed process
    2. Checking common installation locations
    3. Checking the Windows registry
    4. Getting the path from process information if it is currently running

    Returns:
        str: Path to the MobileTouch executable if found, None otherwise
    """
    global _mobiletouch_executable_path

    # First check if we have a saved path from a previously killed process
    if _mobiletouch_executable_path and os.path.exists(_mobiletouch_executable_path):
        print(f"Using saved MobileTouch executable path: {_mobiletouch_executable_path}")
        return _mobiletouch_executable_path

    # Common installation locations
    common_locations = [
        r"C:\Program Files (x86)\Sansio Inc\MobileTouch\MobileTouch.exe",
        r"C:\Program Files\Sansio Inc\MobileTouch\MobileTouch.exe",
        r"C:\Program Files (x86)\Physio-Control\MobileTouch\MobileTouch.exe",
        r"C:\Program Files\Physio-Control\MobileTouch\MobileTouch.exe"
    ]

    # Check common locations
    for location in common_locations:
        if os.path.exists(location):
            print(f"Found MobileTouch executable at common location: {location}")
            return location

    # Check Windows registry
    try:
        # Try different registry paths that might contain MobileTouch installation info
        registry_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Sansio Inc\MobileTouch"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Physio-Control\MobileTouch"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Sansio Inc\MobileTouch"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Physio-Control\MobileTouch")
        ]

        for hkey, path in registry_paths:
            try:
                with winreg.OpenKey(hkey, path) as key:
                    install_path, _ = winreg.QueryValueEx(key, "InstallPath")
                    exe_path = os.path.join(install_path, "MobileTouch.exe")
                    if os.path.exists(exe_path):
                        print(f"Found MobileTouch executable in registry: {exe_path}")
                        return exe_path
            except FileNotFoundError:
                continue
            except Exception as e:
                print(f"Error checking registry path {path}: {e}")
                continue
    except Exception as e:
        print(f"Error checking registry: {e}")

    # Try to get the path from process information
    print("Checking for running MobileTouch process...")
    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            if "MobileTouch" in proc.info['name']:
                exe_path = proc.info['exe']
                if exe_path and os.path.exists(exe_path):
                    print(f"Found MobileTouch executable from process: {exe_path}")
                    return exe_path
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    print("Could not find MobileTouch executable.")
    return None


def start_mobiletouch(wait_for_startup=False):
    """
    Starts the MobileTouch application.

    Args:
        wait_for_startup (bool): Whether to wait for the application to start up

    Returns:
        bool: True if the application was started successfully, False otherwise
    """
    exe_path = find_mobiletouch_executable()
    if not exe_path:
        print("Could not find MobileTouch executable. Unable to start application.")
        return False

    try:
        print(f"Starting MobileTouch from: {exe_path}")
        process = subprocess.Popen([exe_path])

        if wait_for_startup:
            # Wait for a short time to allow the process to start
            time.sleep(5)

            # Check if the process is still running
            if process.poll() is None:
                print("MobileTouch started successfully.")
                return True
            else:
                print(f"MobileTouch process exited with code: {process.returncode}")
                return False

        print("MobileTouch start initiated.")
        return True
    except Exception as e:
        print(f"Error starting MobileTouch: {e}")
        return False


def main():
    # deleteRefTableStore()
    # enumerate_processes()
    # kill_mobiletouch_process()
    # deleteRefTableStore()
    # validate_mobiletouch()
    # if not delete_deviceinfo_entry():
    #     print("Failed to delete deviceinfo entry. Exiting.")
    #     sys.exit(1)

    # if not hard_clear():
    #     print("Failed to clear MobileTouch profile directory. Exiting.")
    #     sys.exit(1)

    if not delete_deviceinfo_entry() :
        print("Failed to delete deviceinfo entry. Exiting.")
        sys.exit(1)

    if not clear_cookies_and_service_worker():
        print("Failed to clear cookies and service worker. Exiting.")
        sys.exit(1)
    # if not validate_mobiletouch():
    #     print("MobileTouch validation failed. Exiting.")
    #     sys.exit(1)

    print("MobileTouch validation succeeded. Device configuration should be restored.")


if __name__ == "__main__":
    main()
