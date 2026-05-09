"""
Constants API router — inflation scales and growth presets.

All endpoints are public (no auth required) — reference data
used by the frontend for selector UIs and preview calculations.
"""

from fastapi import APIRouter

from app.calculations.constants import (
    INFLATION_SCALES,
    GROWTH_PRESETS,
)

router = APIRouter(prefix="/constants", tags=["constants"])


def _serialise_decimal(obj: dict) -> dict:
    """Convert Decimal values to strings for JSON serialisation."""
    from decimal import Decimal
    result = {}
    for key, value in obj.items():
        if isinstance(value, Decimal):
            result[key] = str(value)
        elif isinstance(value, dict):
            result[key] = _serialise_decimal(value)
        else:
            result[key] = value
    return result


@router.get("/scales")
async def get_scales():
    """Return all 3 inflation scales with labels, rates, and descriptions."""
    return {
        "scales": {
            key: _serialise_decimal(scale)
            for key, scale in INFLATION_SCALES.items()
        }
    }


@router.get("/growth-presets")
async def get_growth_presets():
    """Return all 4 growth presets with labels, rates, and descriptions."""
    return {
        "presets": {
            key: _serialise_decimal(preset)
            for key, preset in GROWTH_PRESETS.items()
        }
    }