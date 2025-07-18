import socket
import sys
import tempfile
from pathlib import Path
import traceback
import os.path
from threading import Event

import win11toast
import time
import logging.handlers
import sys
import os
import mobile_touch_log_parsing

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

# Define log directories - try multiple locations to ensure we can write logs
log_locations = [
    Path(tempfile.gettempdir()),  # Standard temp directory
    Path("C:/Logs"),              # Custom logs directory
    Path("C:/Windows/Temp"),      # Windows temp directory
]

# Find a writable location
writable_location = None
for location in log_locations:
    try:
        if not location.exists():
            try:
                location.mkdir(parents=True, exist_ok=True)
            except:
                continue

        # Test if we can write to this location
        test_file = location / "write_test.tmp"
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            test_file.unlink()  # Delete the test file
            writable_location = location
            break
        except:
            continue
    except:
        continue

# If no writable location found, fall back to temp directory
if writable_location is None:
    writable_location = Path(tempfile.gettempdir())

# Create a debug log file to help diagnose issues
debug_log_path = writable_location / 'mt-repair-service-debug.log'
try:
    with open(debug_log_path, 'a') as f:
        f.write(f"\n\n--- Service started at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        f.write(f"Python version: {sys.version}\n")
        f.write(f"Temp directory: {tempfile.gettempdir()}\n")
except Exception as e:
    # Can't do much if we can't write to the debug log
    pass

try:
    # Create a dedicated log directory within our writable location
    log_dir = writable_location / 'mt-repair-service'
    if not log_dir.exists():
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            with open(debug_log_path, 'a') as f:
                f.write(f"Created log directory: {log_dir}\n")
        except Exception as e:
            with open(debug_log_path, 'a') as f:
                f.write(f"Error creating log directory: {str(e)}\n")
                f.write(f"Using writable_location directly: {writable_location}\n")
            # Fall back to using the writable location directly
            log_dir = writable_location

    # Use absolute path for log file
    log_path = log_dir / 'mt-repair-service.log'

    # Write the log path to a known location for troubleshooting
    try:
        with open(writable_location / 'mt-repair-service-path.txt', 'w') as f:
            f.write(f"Log file path: {log_path}\n")
            f.write(f"Debug log path: {debug_log_path}\n")
            f.write(f"Writable location: {writable_location}\n")
    except Exception as e:
        # Ignore errors, this is just for troubleshooting
        pass

    # Write to debug log
    with open(debug_log_path, 'a') as f:
        f.write(f"Log path: {log_path}\n")
        f.write(f"Log path exists: {log_path.exists()}\n")

    # Try to write directly to the log file to test permissions
    try:
        with open(log_path, 'a') as f:
            f.write(f"Direct write test at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        with open(debug_log_path, 'a') as f:
            f.write("Successfully wrote directly to log file\n")
    except Exception as e:
        with open(debug_log_path, 'a') as f:
            f.write(f"Error writing directly to log file: {str(e)}\n")
            f.write(traceback.format_exc())

    # Set up the logger
    my_logger = logging.getLogger('MTRepairService')
    my_logger.setLevel(logging.INFO)

    # Remove all handlers associated with the logger object
    if my_logger.hasHandlers():
        my_logger.handlers.clear()
        with open(debug_log_path, 'a') as f:
            f.write("Cleared existing handlers\n")

    # Create formatter
    formatter = logging.Formatter('[MTRepairService] %(asctime)s - %(levelname)s - %(message)s')

    # Create file handler with absolute path
    try:
        handler = logging.handlers.RotatingFileHandler(
            filename=str(log_path),  # Convert to string to avoid any path issues
            maxBytes=1024 * 1024 * 5,
            backupCount=5,
            delay=False  # Open the file immediately
        )
        handler.setFormatter(formatter)
        my_logger.addHandler(handler)

        with open(debug_log_path, 'a') as f:
            f.write("Successfully added RotatingFileHandler\n")
    except Exception as e:
        with open(debug_log_path, 'a') as f:
            f.write(f"Error setting up RotatingFileHandler: {str(e)}\n")
            f.write(traceback.format_exc())

        # Fallback to a simple FileHandler if RotatingFileHandler fails
        try:
            handler = logging.FileHandler(str(log_path))
            handler.setFormatter(formatter)
            my_logger.addHandler(handler)
            with open(debug_log_path, 'a') as f:
                f.write("Successfully added fallback FileHandler\n")
        except Exception as e:
            with open(debug_log_path, 'a') as f:
                f.write(f"Error setting up fallback FileHandler: {str(e)}\n")
                f.write(traceback.format_exc())

    # Ensure logger doesn't buffer output
    my_logger.propagate = False  # Don't propagate to parent loggers

    # Helper function to flush logger
    def flush_logger(logger):
        try:
            for handler in logger.handlers:
                try:
                    # Flush the handler
                    handler.flush()

                    # If it's a file handler, also flush the underlying stream
                    if hasattr(handler, 'stream') and hasattr(handler.stream, 'flush'):
                        handler.stream.flush()

                        # Force the OS to write the file to disk
                        if hasattr(os, 'fsync') and hasattr(handler.stream, 'fileno'):
                            try:
                                os.fsync(handler.stream.fileno())
                            except (OSError, AttributeError):
                                # Some streams don't support fileno or fsync
                                pass
                except Exception as inner_e:
                    # Log the error but continue with other handlers
                    try:
                        with open(debug_log_path, 'a') as f:
                            f.write(f"Error flushing handler {handler}: {str(inner_e)}\n")
                    except:
                        pass

            with open(debug_log_path, 'a') as f:
                f.write("Flushed logger\n")
        except Exception as e:
            try:
                with open(debug_log_path, 'a') as f:
                    f.write(f"Error in flush_logger: {str(e)}\n")
                    f.write(traceback.format_exc())
            except:
                # If we can't write to the debug log, there's not much we can do
                pass

    # Test the logger
    try:
        my_logger.info("Logger initialization test")
        flush_logger(my_logger)
        with open(debug_log_path, 'a') as f:
            f.write("Successfully wrote test log entry\n")
    except Exception as e:
        with open(debug_log_path, 'a') as f:
            f.write(f"Error writing test log entry: {str(e)}\n")
            f.write(traceback.format_exc())

except Exception as e:
    # If anything fails during setup, write to the debug log
    try:
        with open(debug_log_path, 'a') as f:
            f.write(f"Error during logger setup: {str(e)}\n")
            f.write(traceback.format_exc())
    except:
        pass  # Can't do much if we can't write to the debug log

# Flush the logger initially
flush_logger(my_logger)

# No need for basicConfig as we're using a custom logger
# This can cause issues as basicConfig only has an effect the first time it's called



# Set up logging for the service
# logging.basicConfig(
#     handlers=[handler, stdout_handler],
#     level=logging.INFO,
#     format='[MTRepairService] %(asctime)s - %(levelname)s - %(message)s'
# )


# Global variables to control the application's running state
running = True
stop_event = Event()

def stop_application():
    """Stop the application"""
    global running
    try:
        my_logger.info("Stopping MobileTouch repair application")
        # Ensure log is flushed to disk
        flush_logger(my_logger)

        # Signal the main_loop to stop
        stop_event.set()

        # Close all handlers to ensure logs are written
        for handler in my_logger.handlers[:]:  # Make a copy of the list
            try:
                handler.flush()
                handler.close()
                my_logger.removeHandler(handler)
            except Exception as e:
                # Try to log the error, but don't raise exceptions
                try:
                    with open(debug_log_path, 'a') as f:
                        f.write(f"Error closing handler during stop: {str(e)}\n")
                except:
                    pass

        # Write directly to the debug log
        try:
            with open(debug_log_path, 'a') as f:
                f.write(f"Application stop requested at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        except:
            pass
    except Exception as e:
        # Try to log the error, but don't raise exceptions
        try:
            with open(debug_log_path, 'a') as f:
                f.write(f"Error during application stop: {str(e)}\n")
                f.write(traceback.format_exc())
        except:
            pass

    running = False

def run_application():
    """Start the application; does not return until stopped"""
    global running, stop_event
    my_logger.info("Starting MobileTouch repair application")
    # Ensure log is flushed to disk
    flush_logger(my_logger)

    # Configure mobile_touch_log_parsing to use our logger
    my_logger.info("Configuring mobile_touch_log_parsing logger")
    # Get the mobile_touch_log_parsing logger
    mtlp_logger = mobile_touch_log_parsing.logger
    # Remove any existing handlers
    if mtlp_logger.hasHandlers():
        mtlp_logger.handlers.clear()
    # Add our handlers to the mobile_touch_log_parsing logger
    for handler in my_logger.handlers:
        mtlp_logger.addHandler(handler)
    # Set the level to match our logger
    mtlp_logger.setLevel(my_logger.level)

    # Set up trigger callbacks for mobile_touch_log_parsing
    my_logger.info("Setting up trigger callbacks for mobile_touch_log_parsing")
    mobile_touch_log_parsing.setup_trigger_callbacks()

    # Create a logs_loaded_event to know when logs have been loaded
    logs_loaded_event = Event()

    # Counter for log rotation
    log_rotation_counter = 0

    # Start a thread to handle log rotation while main_loop is running
    def log_rotation_thread():
        nonlocal log_rotation_counter
        while not stop_event.is_set():
            # Sleep for 2 seconds
            time.sleep(2)

            # Ensure log is flushed to disk
            flush_logger(my_logger)

            # Every 30 iterations (about 1 minute), close and reopen the log file
            # This ensures logs are written to disk even if the process crashes
            log_rotation_counter += 1
            if log_rotation_counter >= 30:
                log_rotation_counter = 0
                try:
                    # Write to debug log
                    with open(debug_log_path, 'a') as f:
                        f.write(f"Rotating log handlers at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

                    # Close and remove all handlers
                    for handler in my_logger.handlers[:]:  # Make a copy of the list
                        try:
                            handler.flush()
                            handler.close()
                            my_logger.removeHandler(handler)
                            # Also remove from mobile_touch_log_parsing logger
                            if handler in mtlp_logger.handlers:
                                mtlp_logger.removeHandler(handler)
                        except Exception as e:
                            # Try to log the error, but don't raise exceptions
                            try:
                                with open(debug_log_path, 'a') as f:
                                    f.write(f"Error closing handler during rotation: {str(e)}\n")
                            except:
                                pass

                    # Create a new handler
                    try:
                        new_handler = logging.handlers.RotatingFileHandler(
                            filename=str(log_path),
                            maxBytes=1024 * 1024 * 5,
                            backupCount=5,
                            delay=False
                        )
                        new_handler.setFormatter(formatter)
                        my_logger.addHandler(new_handler)
                        # Also add to mobile_touch_log_parsing logger
                        mtlp_logger.addHandler(new_handler)

                        with open(debug_log_path, 'a') as f:
                            f.write("Successfully rotated log handlers\n")
                    except Exception as e:
                        # Try to log the error, but don't raise exceptions
                        try:
                            with open(debug_log_path, 'a') as f:
                                f.write(f"Error creating new handler during rotation: {str(e)}\n")
                                f.write(traceback.format_exc())
                        except:
                            pass

                        # Fallback to a simple FileHandler if RotatingFileHandler fails
                        try:
                            new_handler = logging.FileHandler(str(log_path))
                            new_handler.setFormatter(formatter)
                            my_logger.addHandler(new_handler)
                            # Also add to mobile_touch_log_parsing logger
                            mtlp_logger.addHandler(new_handler)

                            with open(debug_log_path, 'a') as f:
                                f.write("Successfully added fallback FileHandler during rotation\n")
                        except Exception as e:
                            # Try to log the error, but don't raise exceptions
                            try:
                                with open(debug_log_path, 'a') as f:
                                    f.write(f"Error creating fallback handler during rotation: {str(e)}\n")
                                    f.write(traceback.format_exc())
                            except:
                                pass
                except Exception as e:
                    # Try to log the error, but don't raise exceptions
                    try:
                        with open(debug_log_path, 'a') as f:
                            f.write(f"Error during log rotation: {str(e)}\n")
                            f.write(traceback.format_exc())
                    except:
                        pass

    # Start the log rotation thread
    import threading
    log_rotation_thread = threading.Thread(target=log_rotation_thread, daemon=True)
    log_rotation_thread.start()

    # Start the mobile_touch_log_parsing main_loop in the current thread
    my_logger.info("Starting mobile_touch_log_parsing main_loop")
    try:
        # Call the main_loop function with our stop_event
        mobile_touch_log_parsing.main_loop(stop_event, logs_loaded_event)
    except Exception as e:
        my_logger.error(f"Error in mobile_touch_log_parsing main_loop: {str(e)}")
        my_logger.error(traceback.format_exc())
        # Try to log the error to the debug log as well
        try:
            with open(debug_log_path, 'a') as f:
                f.write(f"Error in mobile_touch_log_parsing main_loop: {str(e)}\n")
                f.write(traceback.format_exc())
        except:
            pass



def init():
    """Initialize the application"""
    my_logger.info('Community Ambulance Mobile Touch Repair Application started')
    # Ensure log is flushed to disk
    flush_logger(my_logger)
    socket.setdefaulttimeout(60)


def main():
    """Main entry point for the application"""
    init()
    run_application()


# Register a shutdown hook to ensure logs are flushed when the process terminates
import atexit

def shutdown_hook():
    try:
        # Log the shutdown
        my_logger.info("Service process is shutting down")

        # Flush and close all handlers
        for handler in my_logger.handlers[:]:
            try:
                handler.flush()
                handler.close()
                my_logger.removeHandler(handler)
            except:
                pass

        # Write directly to the debug log
        try:
            with open(debug_log_path, 'a') as f:
                f.write(f"Process shutdown at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        except:
            pass
    except:
        pass

# Register the shutdown hook
atexit.register(shutdown_hook)

if __name__ == '__main__':
    main()
