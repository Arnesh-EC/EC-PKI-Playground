"""Golden-image settings are validated and exposed with stable wire names."""

import os

import pytest
from pydantic import ValidationError

os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault(
    "SETTINGS_ENC_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
)

from app.core.db.models import SettingsDoc  # noqa: E402
from app.routers.settings import SettingsUpdate  # noqa: E402


def test_golden_image_settings_use_camel_case_wire_fields():
    update = SettingsUpdate(
        cloneBase="ws-2025-patched",
        cloneDatastore="fast-store",
        cloneGuestOs="windows2022srvNext-64",
        cloneMaxUsagePct=75,
    )

    assert update.model_dump(by_alias=True, exclude_unset=True) == {
        "cloneBase": "ws-2025-patched",
        "cloneDatastore": "fast-store",
        "cloneGuestOs": "windows2022srvNext-64",
        "cloneMaxUsagePct": 75.0,
    }


@pytest.mark.parametrize("limit", [0, 100.1])
def test_golden_image_usage_limit_must_be_a_percentage(limit):
    with pytest.raises(ValidationError):
        SettingsUpdate(cloneMaxUsagePct=limit)


def test_settings_document_has_safe_golden_image_defaults():
    doc = SettingsDoc(updatedAt=1)

    assert doc.clone_base == "ws-2025-base"
    assert doc.clone_datastore == "datastore1"
    assert doc.clone_guest_os == "windows2022srvNext-64"
    assert doc.clone_max_usage_pct == 80.0
