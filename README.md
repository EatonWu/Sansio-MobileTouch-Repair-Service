# MobileTouch Repair Service 

This project provides tools for working with Sansio's MobileTouch application and fixing common issues (database corruptions)
while preserving user data (EPCR charts and the like)

## Overview

The MobileTouch Tools project includes several utilities to help diagnose and fix issues with the MobileTouch application:

1. **MobileTouch Tools** - Utilities for fixing various MobileTouch issues including corrupt reference tables
2. **Log Parser** - Analyzes MobileTouch logs to detect and respond to errors
3. **Test Archives Tools** - Tools for testing with saved application states (see [TESTING.md](TESTING.md))

## Relevant files

### mobiletouch_tools.py

This script provides tools for fixing common issues with the MobileTouch application:

- Clearing reference tables
- Deleting device info entries
- Performing hard resets of the MobileTouch profile 
- Validating that MobileTouch runs correctly

### mobile_touch_log_parsing.py

This script parses MobileTouch log files and can detect and respond to various error conditions:

- Monitors log files for specific error patterns
- Automatically triggers appropriate fixes based on detected errors
- Supports different error types with customizable responses

### test_archives.py

test_archives.py contains automated tests that utilize the sample MobileTouch log archives found in the test_archives/ directory. These tests help ensure that the log parsing and repair tools work correctly with real-world data. You can run this script to validate changes to the log parsing or repair logic against a variety of known MobileTouch error scenarios.

## Testing

For information about testing with MobileTouch test archives, please see the [TESTING.md](TESTING.md) file.

## Requirements

See `requirements.txt` for a list of dependencies.
