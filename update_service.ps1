# Update MobileTouch Repair Application Script
# This script builds the MobileTouch Repair Application
# NOTE: Requires you to download chrome-win32 and chromedriver into the root directory:
# Can be downloaded at: https://googlechromelabs.github.io/chrome-for-testing/

# Validate existence of chromedriver.exe and chrome-win32
if (!(Test-Path "./chromedriver.exe")) {
    Write-Host "Error: chromedriver.exe not found in the project root. Please download it before building." -ForegroundColor Red
    exit 1
}
if (!(Test-Path "./chrome-win32")) {
    Write-Host "Error: chrome-win32 directory not found in the project root. Please download it before building." -ForegroundColor Red
    exit 1
}

Write-Host "Rebuilding application executable with PyInstaller..."
try {
    # Activate the virtual environment
    Write-Host "Activating virtual environment..."
    & .\.venv\Scripts\Activate.ps1

    pyinstaller --runtime-tmpdir=. .\mt_windows_service.py --noconfirm --add-data="./chrome-win32/*;./chrome-win32" `
        --add-binary="./chromedriver.exe:." -w

    if (-not $?) {
        throw "PyInstaller failed to build the executable."
    }

    # Deactivate the virtual environment
    deactivate

    Write-Host "MobileTouch Repair Application has been successfully built." -ForegroundColor Green
    Write-Host "The executable is located at: .\dist\mt_windows_service\mt_windows_service.exe" -ForegroundColor Green
    Write-Host "You can run it directly or set it to start automatically with Windows." -ForegroundColor Green
} catch {
    Write-Host "Error: Failed to build application executable." -ForegroundColor Red
    Write-Host $_.Exception.Message
    exit 1
}
