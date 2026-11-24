"""Profile-aware laser parameters on target."""

from beamforge.beams import (
    AirySpot,
    FlatTopSpot,
    GaussianSpot,
    Spot,
    TruncatedGaussianSpot,
)
from beamforge.calculator import FocusScan, Quantity, Result, Setup, calculate, through_focus
from beamforge.focus import FresnelSpot

__all__ = [
    "AirySpot",
    "FlatTopSpot",
    "FocusScan",
    "FresnelSpot",
    "GaussianSpot",
    "Quantity",
    "Result",
    "Setup",
    "Spot",
    "TruncatedGaussianSpot",
    "calculate",
    "through_focus",
]
__version__ = "0.1.0.dev0"
