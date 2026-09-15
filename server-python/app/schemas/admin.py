from pydantic import BaseModel, ConfigDict, Field

from app.schemas.inference import ForecastInferenceResponse


class MunicipalityOverview(BaseModel):
    """One row in the superadmin's cross-municipality snapshot — the same
    /forecast/live pipeline an LGU technician sees for their own
    municipality, run for every municipality on file."""

    model_config = ConfigDict(populate_by_name=True)

    province: str
    municipality: str
    bph: ForecastInferenceResponse
    rsb: ForecastInferenceResponse


class OverviewResponse(BaseModel):
    growth_stage_used: str = Field(alias="growthStageUsed")
    municipalities: list[MunicipalityOverview]

    model_config = ConfigDict(populate_by_name=True)


class EtlThresholdBand(BaseModel):
    low_max: float = Field(alias="lowMax")
    high_min: float = Field(alias="highMin")

    model_config = ConfigDict(populate_by_name=True)


class EtlThresholdsResponse(BaseModel):
    """Read-only — these are fixed academic thresholds transcribed from the
    thesis's Table 2 (see app/decision/etl_thresholds.py), not an
    administrator preference, so there is no corresponding write endpoint."""

    thresholds: dict[str, dict[str, EtlThresholdBand]]
