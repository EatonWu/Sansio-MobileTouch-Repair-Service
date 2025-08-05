# MobileTouch Repair Application

## Testing Suite

This project includes a comprehensive testing suite to ensure reliability and correctness of the MobileTouch Repair Application. The tests are written in Python and use the `pytest` framework. Key points about the testing suite:

- **Test Files:** Test scripts are located in files such as `test_logging.py`, `test_archives.py`, and others in the project root.
- **How to Run Tests:**
  1. Ensure all dependencies are installed (see `requirements.txt`).
  2. Run tests using the command:
     ```
     pytest
     ```
- **Test Data:** The `test_archives/` directory contains sample data and archives used by the tests.
- **Testing Documentation:** See `TESTING.md` for more details on test coverage and guidelines.

## Logging

The application logs information to the following files:
- `C:\Users\<Username>\AppData\Local\Temp\mt-repair-service\mt-repair-service.log`

- Debug log file: Located in the same parent directory as the main log file, named `mt-repair-service-debug.log`

- Log path file: The application writes the actual log file path to a file named `mt-repair-service-path.txt` in the writable location it finds. Check this file to determine where logs are being written.

If you're experiencing issues with logging, check the debug log file for detailed information about what might be going wrong. The application tries multiple locations to ensure it can write logs, and includes extensive error handling and debugging information.

## Building and Running the Application

To build and run the application, follow these steps:

1. Run the update_service.ps1 script to build the application:
   ```
   .\update_service.ps1
   ```

2. Run the application:
   ```
   .\dist\mt_windows_service\mt_windows_service.exe
   ```

3. To set the application to run at Windows startup, create a shortcut to the executable in the Windows Startup folder:
   ```
   $startupFolder = [Environment]::GetFolderPath('Startup')
   $shortcutPath = Join-Path $startupFolder "MobileTouchRepair.lnk"
   $WshShell = New-Object -ComObject WScript.Shell
   $Shortcut = $WshShell.CreateShortcut($shortcutPath)
   $Shortcut.TargetPath = (Resolve-Path ".\dist\mt_windows_service\mt_windows_service.exe").Path
   $Shortcut.Save()
   ```

4. Check if logs are being written to the log file:
   ```
   Get-Content -Path "$env:TEMP\mt-repair-service\mt-repair-service.log" -Tail 20
   ```

5. If no logs are appearing, check the debug log file for errors:
   ```
   Get-Content -Path "$env:TEMP\mt-repair-service-debug.log" -Tail 50
   ```