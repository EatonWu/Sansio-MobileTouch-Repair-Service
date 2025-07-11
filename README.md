# MobileTouch Tools

This project provides tools for working with MobileTouch application and fixing common issues.

## Overview

The MobileTouch Tools project includes several utilities to help diagnose and fix issues with the MobileTouch application:

1. **MobileTouch Tools** - Utilities for fixing various MobileTouch issues including corrupt reference tables
2. **Log Parser** - Analyzes MobileTouch logs to detect and respond to errors
3. **Test Archives Tools** - Tools for testing with saved application states (see [TESTING.md](TESTING.md))

## Tools

### mobiletouch_tools.py

This script provides tools for fixing common issues with the MobileTouch application:

- Clearing reference tables
- Deleting device info entries
- Performing hard resets of the MobileTouch profile
- Validating MobileTouch configuration

### mobile_touch_log_parsing.py

This script parses MobileTouch log files and can detect and respond to various error conditions:

- Monitors log files for specific error patterns
- Automatically triggers appropriate fixes based on detected errors
- Supports different error types with customizable responses

## Testing

For information about testing with MobileTouch test archives, please see the [TESTING.md](TESTING.md) file.

## Requirements

See `requirements.txt` for a list of dependencies.
