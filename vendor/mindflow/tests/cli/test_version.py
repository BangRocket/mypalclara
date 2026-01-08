"""Test for version management."""

from mindflow import __version__
from mindflow.cli.version import get_mindflow_version


def test_dynamic_versioning_consistency():
    """Test that dynamic versioning provides consistent version across all access methods."""
    cli_version = get_mindflow_version()
    package_version = __version__

    # Both should return the same version string
    assert cli_version == package_version

    # Version should not be empty
    assert package_version is not None
    assert len(package_version.strip()) > 0
