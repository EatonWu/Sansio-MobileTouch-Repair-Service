import logging
import sys
import pytest

# Configure pytest
@pytest.hookimpl
def pytest_configure(config):
    """Configure pytest logging and custom markers."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )

    # Configure custom markers
    config.addinivalue_line("markers", "archive: mark test to run only on specific archives")

# Add command line options
@pytest.hookimpl
def pytest_addoption(parser):
    """Add command line options to pytest."""
    parser.addoption(
        "--archive", action="store", default=None, help="Run tests only for the specified archive"
    )

# Filter tests based on command line options
@pytest.hookimpl
def pytest_collection_modifyitems(config, items):
    """Filter tests based on command line options."""
    archive_name = config.getoption("--archive")
    if archive_name is None:
        return

    selected = []
    deselected = []

    for item in items:
        # Check if the test is parametrized with an archive
        if hasattr(item, 'callspec') and hasattr(item.callspec, 'params') and 'archive' in item.callspec.params:
            archive = item.callspec.params['archive']
            if archive.name == archive_name:
                selected.append(item)
            else:
                deselected.append(item)
        else:
            # Keep non-archive tests
            selected.append(item)

    config.hook.pytest_deselected(items=deselected)
    items[:] = selected
