# Testing Documentation

This document provides information about testing MobileTouch error handling using test archives.

## Security Notice

**Important:** For security reasons, the `test_archives` directory in the repository is intentionally kept empty. The actual test archives are stored in `test_archives.zip`, which is encrypted with AES-256.
This is to prevent unauthorized access to potentially sensitive data contained in the test archives.

To use the test archives:

1. Obtain the password for the encrypted archive from an authorized team member
2. Extract the contents of `test_archives.zip` to the `test_archives` directory:
   ```bash
   # Using 7-Zip (Windows)
   7z x test_archives.zip -otest_archives

   # Using unzip (Linux/macOS)
   unzip test_archives.zip -d test_archives
   ```
3. When prompted, enter the password

After extraction, the test archives will be available in the `test_archives` directory and can be used as described in this documentation.
In the archives, there will be a "MobileTouch" directory containing the application data.
Yours, in theory, should contain directories like:
AppData, archive, attachments, failed, failedSerial, logging, rawdata, startlog, and temp.
AppData is basically just trimmed down Chrome profile directory, and should contain directories like Cache, Code Cache, IndexedDB, and more.


## Test Archives Loader

The project provides two ways to load and test MobileTouch archives:

1. Using the standalone script (`test_archives.py` directly)
2. Using pytest framework (`pytest test_archives.py`)

These archives contain saved states of the MobileTouch application that can be used for testing and debugging.


### Usage

#### Standalone Script

To run the standalone test archives loader:

```bash
python test_archives.py
```

This will:
1. List all available test archives in the `test_archives` directory
2. Prompt you to select a specific archive to test or run all archives
3. Extract the selected archive(s) to a temporary directory
4. Set up Chrome with the extracted profile
5. Load the MobileTouch application
6. Log the results
7. Clean up temporary files

The interactive prompt allows you to:
- View a numbered list of all available test archives
- Select a specific archive by entering its number
- Test all archives by entering 'a'

#### Using Pytest

To run tests using pytest:

```bash
pytest test_archives.py -v
```

This provides more detailed test reporting and better test management. You can also:

- Run tests for a specific archive:
  ```bash
  pytest test_archives.py --archive "MobileTouch RefTables Error.zip" -v
  ```

- Generate test reports:
  ```bash
  pytest test_archives.py --html=report.html
  ```
  (requires pytest-html plugin)

- Run tests with different verbosity levels:
  ```bash
  pytest test_archives.py -v  # verbose
  pytest test_archives.py -q  # quiet
  ```

## Structure of Test Archives

Test archives should contain a MobileTouch directory with the application's profile data. The script will automatically locate this directory within the archive.

## Test Archives Metadata

The `test_archives/metadata.json` file maps each archive to its corresponding error type and contains additional information:

```json
{
  "archives": [
    {
      "filename": "EPCR062 MobileTouch Loading.zip",
      "error_type": "STORES_NOT_CORRECTLY_SET_UP",
      "produces_alerts": false,
      "description": "Database corruption where stores are not correctly set up"
    }
  ]
}
```

Each archive entry includes:
- `filename`: The name of the archive file
- `error_type`: The type of error (corresponds to TriggerString enums in mobile_touch_log_parsing.py)
- `produces_alerts`: Whether the error produces alerts in the browser (some errors don't)
- `description`: A brief description of the error

When adding new test archives, update this file to include metadata for the new archive.

## Adding New Test Archives

To add a new test archive:

1. Extract the `test_archives.zip` file as described in the [Security Notice](#security-notice) section
2. Copy the new ZIP file to the extracted `test_archives` directory
3. Update the `metadata.json` file with information about the new archive
4. Run the script to test the new archive
5. Re-encrypt the `test_archives` directory:
   ```bash
   # Using 7-Zip (Windows)
   7z a -tzip -p -mem=AES256 test_archives.zip test_archives/*

   # Using zip (Linux/macOS)
   zip -e -r test_archives.zip test_archives/
   ```
6. When prompted, enter the password (use the same password as before)
7. After confirming the archive works correctly, remove the unencrypted files from the `test_archives` directory