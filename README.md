# MobileTouch Repair Application

This application is designed to repair Mobile Touch issues for Community Ambulance. It runs as a windowless application that can be started manually or set to run at Windows startup.

## Logging

The application logs information to the following files:
- Main log file: Located in one of these directories (in order of preference):
  - `C:\Users\<Username>\AppData\Local\Temp\mt-repair-service\mt-repair-service.log`
  - `C:\Logs\mt-repair-service\mt-repair-service.log`
  - `C:\Windows\Temp\mt-repair-service\mt-repair-service.log`
  - `C:\ProgramData\MobileTouchRepairService\mt-repair-service\mt-repair-service.log`

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

## Troubleshooting

If logs are not being written:

1. Find where the logs are being written by checking the path file:
   ```
   # Check all possible locations for the path file
   $locations = @(
       "$env:TEMP",
       "C:\Logs",
       "C:\Windows\Temp",
       "C:\ProgramData\MobileTouchRepairService"
   )

   foreach ($loc in $locations) {
       $pathFile = Join-Path $loc "mt-repair-service-path.txt"
       if (Test-Path $pathFile) {
           Write-Host "Found path file at: $pathFile"
           Get-Content $pathFile
           break
       }
   }
   ```

2. Check the debug log file for errors:
   ```
   # Check all possible locations for the debug log
   $locations = @(
       "$env:TEMP",
       "C:\Logs",
       "C:\Windows\Temp",
       "C:\ProgramData\MobileTouchRepairService"
   )

   foreach ($loc in $locations) {
       $debugLog = Join-Path $loc "mt-repair-service-debug.log"
       if (Test-Path $debugLog) {
           Write-Host "Found debug log at: $debugLog"
           Get-Content $debugLog -Tail 50
           break
       }
   }
   ```

3. Try running the test_logging.py script to verify that Python can write to the log file:
   ```
   python test_logging.py
   ```

4. Check if your user account has permission to write to the log directories:
   ```
   # For your current user account
   $currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
   icacls "C:\Logs" /grant "$currentUser:(OI)(CI)F"
   icacls "C:\ProgramData\MobileTouchRepairService" /grant "$currentUser:(OI)(CI)F"
   ```

5. Try running the application with administrator privileges by right-clicking the executable and selecting "Run as administrator"

## Recent Changes

The logging system has been enhanced with the following improvements:

1. Added a debug log file to help diagnose issues with the main log file
2. Added extensive error handling and logging throughout the setup process
3. Added direct file writing tests to verify permissions
4. Added fallback to a simple FileHandler if RotatingFileHandler fails
5. Enhanced the flush_logger function with better error handling
6. Added a test log entry during initialization to verify the logger is working
7. Added multiple log file locations with automatic detection of writable locations
8. Added a log path file to help locate where logs are being written
9. Implemented periodic log file rotation to ensure logs are written to disk
10. Added an atexit shutdown hook to ensure logs are flushed when the process terminates
11. Improved the service stop method to properly close all handlers
12. Added os.fsync calls to force the OS to write logs to disk
13. Added comprehensive error handling throughout the logging system

These changes should help ensure that logs are written properly when running as a Windows service, even in environments with restricted permissions or unusual configurations.
