import os
import sys
import time
import psutil
from shutil import rmtree

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


def setup_chrome_driver():
    chrome_options = Options()

    # headless
    # chrome_options.add_argument("--headless=new")
    chrome_options.binary_location = ".\\chrome-win32\\chrome.exe"
    service = Service(executable_path=".\\chromedriver.exe")

    # attempt to open chrome using mobiletouch's profile and data
    chrome_options.add_argument("user-data-dir=C:\\ProgramData\\Physio-Control\\MobileTouch")
    chrome_options.add_argument("profile-directory=AppData")

    # required for IndexedDB access
    chrome_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

    return webdriver.Chrome(service=service, options=chrome_options)



def hard_clear(path=standard_path):
    """
    Last resort; deletes the MobileTouch profile directory.
    :return: true if successful, false otherwise
    """
    path = os.path.join(path, "AppData")
    try:
        if os.path.exists(path):
            rmtree(path)
            print(f"Removed directory and contents: {path}")
            return True
        else:
            print(f"Directory does not exist: {path}")
            return False
    except PermissionError as e:
        print(f"Permission error while removing directory: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"An error occurred while clearing the directory: {e}", file=sys.stderr)
        return False



def delete_deviceinfo_entry():
    with setup_chrome_driver() as driver:
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
    """
    Deletes the Network and Service Worker directories from the MobileTouch profile.
    This seems to resolve the "Device configuration corrupt - missing device ID (2)" error
    This also seems to resolve FAILED_GET_DEVICE_INFO error
    """
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


def deleteRefTableStore():
    with setup_chrome_driver() as driver:
        try:
            # Navigate to a URL
            driver.get("https://mobiletouch.healthems.com")

            idb = IndexedDB(driver, "mobiletouch", 9)

            # Keep checking for alerts until none found for 5 seconds
            last_alert_time = time.time()
            alert_found = False

            wait_time = 10  # Initial wait time of 10 seconds
            while True:
                try:
                    alert = WebDriverWait(driver, wait_time).until(EC.alert_is_present())
                    print(f"Alert found: {alert.text}")
                    alert_found = True
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

            # # print console logs
            # logs = driver.get_log("browser")
            # for log in logs:
            #     print(log)

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
    """
    print("Attempting to kill MobileTouch process...")
    pid = seek_mobiletouch_process()
    if pid:
        try:
            proc = psutil.Process(pid)
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

    # create selenium driver
    if driver is None:
        driver = setup_chrome_driver()

    try:
        # Navigate to the MobileTouch URL
        driver.get("https://mobiletouch.healthems.com")

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
        driver.quit()


def main():
    # deleteRefTableStore()
    # enumerate_processes()
    # kill_mobiletouch_process()
    # deleteRefTableStore()
    # validate_mobiletouch()
    # if not delete_deviceinfo_entry():
    #     print("Failed to delete deviceinfo entry. Exiting.")
    #     sys.exit(1)

    if not hard_clear():
        print("Failed to clear MobileTouch profile directory. Exiting.")
        sys.exit(1)
    if not clear_cookies_and_service_worker():
        print("Failed to clear cookies and service worker. Exiting.")
        sys.exit(1)
    if not validate_mobiletouch():
        print("MobileTouch validation failed. Exiting.")
        sys.exit(1)

    print("MobileTouch validation succeeded. Device configuration should be restored.")


if __name__ == "__main__":
    main()
