"""Agreed scan-position rules. Unknown observations return None.

Floor mapping assumes the agreed scan pose; it is not a general geometric
estimate of an object's floor. Direction input must be the calibrated viewing
heading, with the target near the image center and stable, aligned telemetry.
"""
import json
import math
from pathlib import Path


def load_config():
    return json.loads(Path(__file__).with_name('telemetry-location.json').read_text(encoding='utf-8'))


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def floor_from_altitude(alt_rel, config=None):
    """Explicit scan bands; lower bounds inclusive, floor 1 strictly below 7 m."""
    if not _finite(alt_rel):
        return None
    config = load_config() if config is None else config
    matches = []
    for band in config['floor_ranges_m']:
        lower, upper = band['min'], band['max']
        lower_ok = lower is None or alt_rel >= lower
        upper_ok = (upper is None or alt_rel < upper or
                    (band['max_inclusive'] and alt_rel == upper))
        if lower_ok and upper_ok:
            matches.append(band['floor'])
    return matches[0] if len(matches) == 1 else None


def direction_from_heading(heading_deg, config=None):
    """Classify a calibrated heading; reject +/-10 degrees around boundaries."""
    if not _finite(heading_deg):
        return None
    config = load_config() if config is None else config
    angle = (heading_deg + 180) % 360 - 180
    sectors = config['direction_sectors']
    margin = config['direction_boundary_margin_deg']
    for sector in sectors:
        distance = abs((angle - sector['start_deg'] + 180) % 360 - 180)
        if distance <= margin:
            return None
    for sector in sectors:
        span = (sector['end_deg'] - sector['start_deg']) % 360
        if (angle - sector['start_deg']) % 360 < span:
            return sector['direction']
    return None
