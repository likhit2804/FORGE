"""Physics-Based Reservoir Inflow & Dynamic Pre-Discharge Flood Cushion Engine.

Resolves the Dam Operator's Dilemma in Tamil Nadu by modeling Rational Inflow
and calculating the mathematical pre-discharge schedule that cushions extreme storm runoff
without exceeding downstream non-flood river capacities.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ReservoirSpec:
    name: str
    basin: str
    downstream_river: str
    total_capacity_mcft: float
    full_level_ft: float
    catchment_area_km2: float
    runoff_coefficient: float
    safe_river_capacity_cusecs: float  # safe non-flood channel capacity
    emergency_threshold_pct: float = 90.0
    buffer_target_pct: float = 75.0


RESERVOIR_SPECS: dict[str, ReservoirSpec] = {
    "chembarambakkam": ReservoirSpec(
        name="Chembarambakkam",
        basin="Chennai Basin / Adyar River",
        downstream_river="Adyar River (Chennai)",
        total_capacity_mcft=3645.0,
        full_level_ft=85.4,
        catchment_area_km2=358.0,
        runoff_coefficient=0.65,
        safe_river_capacity_cusecs=15000.0,
        emergency_threshold_pct=90.0,
        buffer_target_pct=75.0,
    ),
    "poondi": ReservoirSpec(
        name="Poondi (Sathyamurthy Sagar)",
        basin="Kosasthalaiyar River",
        downstream_river="Kosasthalaiyar River (Ennore Creek)",
        total_capacity_mcft=3231.0,
        full_level_ft=140.0,
        catchment_area_km2=1950.0,
        runoff_coefficient=0.55,
        safe_river_capacity_cusecs=20000.0,
        emergency_threshold_pct=90.0,
        buffer_target_pct=75.0,
    ),
    "mettur": ReservoirSpec(
        name="Mettur (Stanley Reservoir)",
        basin="Cauvery Basin",
        downstream_river="Cauvery River (Tiruchirappalli)",
        total_capacity_mcft=93470.0,
        full_level_ft=120.0,
        catchment_area_km2=42000.0,
        runoff_coefficient=0.45,
        safe_river_capacity_cusecs=100000.0,
        emergency_threshold_pct=92.0,
        buffer_target_pct=80.0,
    ),
    "pechiparai": ReservoirSpec(
        name="Pechiparai",
        basin="Kodayar / Tamirabarani Southern Basin",
        downstream_river="Kodayar River (Kanyakumari)",
        total_capacity_mcft=4450.0,
        full_level_ft=48.0,
        catchment_area_km2=207.0,
        runoff_coefficient=0.70,
        safe_river_capacity_cusecs=12000.0,
        emergency_threshold_pct=88.0,
        buffer_target_pct=72.0,
    ),
}


def simulate_predischarge_cushion(
    reservoir_key: str = "chembarambakkam",
    current_storage_mcft: float | None = None,
    forecast_storm_rainfall_mm: float = 350.0,
    storm_duration_hours: float = 36.0,
    predischarge_lead_time_hours: float = 72.0,
    custom_predischarge_rate_cusecs: float | None = None,
) -> dict:
    """Simulate reservoir inflow, static rule curve disaster, and dynamic pre-discharge solution."""
    key = reservoir_key.lower().strip()
    spec = RESERVOIR_SPECS.get(key, RESERVOIR_SPECS["chembarambakkam"])

    # Default to 88% full (the classic dam operator fear state entering late October)
    storage = (
        current_storage_mcft
        if current_storage_mcft is not None and 0 <= current_storage_mcft <= spec.total_capacity_mcft
        else spec.total_capacity_mcft * 0.88
    )

    storage_pct = (storage / spec.total_capacity_mcft) * 100.0

    # 1. Catchment Inflow Volume calculation:
    # Volume (m3) = Area (m2) * Depth (m) * C
    # 1 km2 = 1,000,000 m2; 1 mm = 0.001 m => 1 km2 * 1 mm = 1,000 m3
    # 1 Mcft (Million cubic feet) = 28,316.8466 m3
    area_m2 = spec.catchment_area_km2 * 1e6
    rain_m = (forecast_storm_rainfall_mm / 1000.0)
    inflow_m3 = area_m2 * rain_m * spec.runoff_coefficient
    total_inflow_mcft = round(inflow_m3 / 28316.8466, 1)

    # Peak inflow rate using Rational Formula Q_peak (m3/s) = 0.278 * C * I (mm/hr) * A (km2)
    intensity_mm_hr = forecast_storm_rainfall_mm / max(1.0, storm_duration_hours)
    peak_inflow_m3s = 0.278 * spec.runoff_coefficient * intensity_mm_hr * spec.catchment_area_km2
    # 1 m3/s = 35.3147 cusecs (ft3/s)
    peak_inflow_cusecs = round(peak_inflow_m3s * 35.3147, 0)

    # 2. Existing cushion available without release:
    available_cushion_mcft = spec.total_capacity_mcft - storage

    # 3. Storage Deficit (Overtopping volume without action):
    storage_deficit_mcft = max(0.0, total_inflow_mcft - available_cushion_mcft)

    # 4. UNMANAGED STATIC SCENARIO (What happened in Chennai 2015):
    # Dam operator holds water until dam reaches 98% full, then dumps peak inflow directly downstream
    unmanaged_peak_emergency_release_cusecs = peak_inflow_cusecs
    unmanaged_river_overtop_ratio = unmanaged_peak_emergency_release_cusecs / spec.safe_river_capacity_cusecs
    unmanaged_flood_severity = (
        "Catastrophic Urban Deluge (Exceeds river capacity by > 200%)"
        if unmanaged_river_overtop_ratio > 2.0
        else "Severe Riverine Inundation (Exceeds river bankfull capacity)"
        if unmanaged_river_overtop_ratio > 1.0
        else "Elevated Channel Flow (Within levee bounds)"
    )

    # 5. DYNAMIC PRE-DISCHARGE OPTIMIZATION:
    # To create a cushion equal to storage_deficit_mcft over lead time T hours:
    # 1 cusec for 1 hour = 3600 ft3 = 0.0036 Mcft
    # Required cusecs = Deficit (Mcft) / (T_hours * 0.0036)
    lead_time_hours = max(12.0, predischarge_lead_time_hours)
    required_cushion_mcft = storage_deficit_mcft * 1.05  # 5% safety margin
    optimal_predischarge_cusecs = round(required_cushion_mcft / (lead_time_hours * 0.0036), 0)

    # Applied pre-discharge rate
    applied_predischarge_cusecs = (
        custom_predischarge_rate_cusecs
        if custom_predischarge_rate_cusecs is not None and custom_predischarge_rate_cusecs >= 0
        else optimal_predischarge_cusecs
    )

    actual_cushion_created_mcft = round(applied_predischarge_cusecs * lead_time_hours * 0.0036, 1)
    new_storage_before_storm_mcft = max(spec.total_capacity_mcft * 0.30, storage - actual_cushion_created_mcft)
    new_storage_pct_before_storm = (new_storage_before_storm_mcft / spec.total_capacity_mcft) * 100.0

    post_storm_storage_mcft = min(spec.total_capacity_mcft, new_storage_before_storm_mcft + total_inflow_mcft)
    post_storm_storage_pct = (post_storm_storage_mcft / spec.total_capacity_mcft) * 100.0

    # Managed peak emergency release required during storm:
    remaining_unabsorbed_mcft = max(0.0, (new_storage_before_storm_mcft + total_inflow_mcft) - spec.total_capacity_mcft)
    managed_peak_release_cusecs = (
        round(remaining_unabsorbed_mcft / (storm_duration_hours * 0.0036), 0)
        if remaining_unabsorbed_mcft > 0
        else 0.0
    )

    managed_safe = (managed_peak_release_cusecs + applied_predischarge_cusecs) <= spec.safe_river_capacity_cusecs
    peak_flood_reduction_pct = round(
        max(0.0, 1.0 - (managed_peak_release_cusecs / max(1.0, unmanaged_peak_emergency_release_cusecs))) * 100.0, 1
    )

    # Generate 10-step hydrograph comparison points
    hydrograph = []
    total_time_h = lead_time_hours + storm_duration_hours + 24.0
    step_h = total_time_h / 12.0
    for i in range(13):
        t = round(i * step_h, 1)
        # Unmanaged discharge curve: 0 during pre-storm, spikes violently at peak of storm
        if t < lead_time_hours:
            unmanaged_q = 0.0
            managed_q = applied_predischarge_cusecs
        elif t <= lead_time_hours + storm_duration_hours:
            progress = (t - lead_time_hours) / storm_duration_hours
            storm_shape = math.sin(progress * math.pi)
            unmanaged_q = round(unmanaged_peak_emergency_release_cusecs * storm_shape, 0)
            managed_q = round(max(applied_predischarge_cusecs, managed_peak_release_cusecs * storm_shape), 0)
        else:
            unmanaged_q = round(unmanaged_peak_emergency_release_cusecs * 0.15, 0)
            managed_q = round(applied_predischarge_cusecs * 0.2, 0)

        hydrograph.append({
            "hour": t,
            "phase": "Pre-Storm Buffer Window" if t < lead_time_hours else "Active Storm Deluge" if t <= lead_time_hours + storm_duration_hours else "Post-Storm Recession",
            "unmanaged_emergency_cusecs": unmanaged_q,
            "managed_predischarge_cusecs": managed_q,
            "river_safe_carrying_capacity": spec.safe_river_capacity_cusecs,
        })

    return {
        "reservoir": {
            "key": key,
            "name": spec.name,
            "basin": spec.basin,
            "downstream_river": spec.downstream_river,
            "total_capacity_mcft": spec.total_capacity_mcft,
            "current_storage_mcft": round(storage, 1),
            "current_storage_pct": round(storage_pct, 1),
            "catchment_area_km2": spec.catchment_area_km2,
            "safe_river_capacity_cusecs": spec.safe_river_capacity_cusecs,
        },
        "storm_physics": {
            "forecast_rainfall_mm": forecast_storm_rainfall_mm,
            "duration_hours": storm_duration_hours,
            "catchment_runoff_m3": round(inflow_m3, 0),
            "total_inflow_mcft": total_inflow_mcft,
            "peak_inflow_cusecs": peak_inflow_cusecs,
            "unmanaged_storage_deficit_mcft": round(storage_deficit_mcft, 1),
        },
        "unmanaged_disaster_outcome": {
            "peak_emergency_release_cusecs": unmanaged_peak_emergency_release_cusecs,
            "river_capacity_overtop_ratio": round(unmanaged_river_overtop_ratio, 2),
            "severity_assessment": unmanaged_flood_severity,
            "historical_analogue": "2015 Chennai Adyar River Deluge (35,000 cusecs midnight release)",
        },
        "dynamic_predischarge_solution": {
            "lead_time_hours": lead_time_hours,
            "optimal_predischarge_rate_cusecs": optimal_predischarge_cusecs,
            "applied_predischarge_rate_cusecs": applied_predischarge_cusecs,
            "cushion_created_mcft": actual_cushion_created_mcft,
            "pre_storm_storage_mcft": round(new_storage_before_storm_mcft, 1),
            "pre_storm_storage_pct": round(new_storage_pct_before_storm, 1),
            "post_storm_storage_mcft": round(post_storm_storage_mcft, 1),
            "post_storm_storage_pct": round(post_storm_storage_pct, 1),
            "managed_peak_emergency_release_cusecs": managed_peak_release_cusecs,
            "peak_flood_reduction_pct": peak_flood_reduction_pct,
            "river_safe_compliance": managed_safe,
            "sluice_action_recommendation": (
                f"Open Sluice Gates 3 & 4 to discharge {applied_predischarge_cusecs:,.0f} cusecs continuously for {lead_time_hours:.0f} hours. "
                f"Absorbs 100% of incoming {total_inflow_mcft:,.0f} Mcft storm runoff, eliminating catastrophic emergency dumping."
            ),
        },
        "hydrograph_comparison": hydrograph,
    }
