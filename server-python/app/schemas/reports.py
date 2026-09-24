from typing import Literal

from pydantic import BaseModel

ReportStatus = Literal["pending", "verified", "rejected"]


class ReportRequest(BaseModel):
    """Shape of a farmer sighting. Documents the fields only — the POST
    endpoint actually receives these as multipart/form-data (a report can
    carry a photo), not a JSON body, so this model isn't bound directly to
    the route; see app/routers/reports.py:submit_report.
    """

    # No farmer accounts exist — this is just a display name typed into the
    # report form (or "Anonymous Farmer"), not an authenticated identity.
    username: str = "Anonymous Farmer"
    pest_type: str
    severity: str
    province: str
    municipality: str
    # Free-text to match ReportRequest's existing looseness (severity is
    # also a plain str, not the GrowthStage Literal from schemas/inference.py)
    # — the mobile form constrains the actual choices.
    crop_growth_stage: str = "Tillering"
    date_spotted: str
    notes: str = ""
    area_affected: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    # Optional numeric count/damage estimate in the same units the ETL table
    # uses for this pest (hoppers/hill for BPH, % dead hearts or white ears
    # for RSB) — most farmers won't have an exact count, so this is
    # supplementary to `severity`, not a replacement for it.
    estimated_value: float | None = None


class ReportResponse(BaseModel):
    id: str
    submitted_at: str


class ReportRecord(ReportRequest):
    id: str
    submitted_at: str
    # Normalized BPH/RSB key derived server-side from pest_type at
    # submission time (see app/decision/pest_matching.py) — never set
    # directly by a client. None when pest_type matches neither ETL pest
    # (e.g. "Others / Hindi Sigurado").
    pest_code: str | None = None
    # Every report starts unverified — an LGU technician reviews it in
    # admin-web before it's allowed to nudge the forecast (see
    # app/decision/report_anchor.py). Old records written before this field
    # existed default to "pending" on load.
    status: ReportStatus = "pending"
    verified_by: str | None = None
    verified_at: str | None = None
    # The technologist's confirmed count/damage value, in the same units as
    # estimated_value above. Set when a report is verified — defaults to the
    # farmer's own estimated_value unless the technologist overrides it with
    # a correction (see ReportStatusUpdate.verified_value). Stays null for a
    # pending or rejected report.
    verified_value: float | None = None
    # Set only when the farmer attached a photo. photo_path is the on-disk
    # filename under settings.upload_dir (persisted); photo_url is the
    # /uploads-mounted path the frontend can actually load an <img> from —
    # computed at read time in app/routers/reports.py, never persisted,
    # since it depends on the static mount, not on anything about the report.
    photo_path: str | None = None
    photo_url: str | None = None
    # Populated by running resnet_classifier.predict() on the attached photo
    # at submission time — see app/models/resnet_model.py. Both stay null
    # for a manual (no-photo) report, or if the ResNet weights aren't loaded
    # yet ("model_not_loaded" is a normal state elsewhere in this API too).
    ai_pest_detected: str | None = None
    ai_confidence: float | None = None
    # Set when an LGU technician deletes the report (soft delete, kept as an
    # audit trail). A deleted report never feeds the forecast or the farmers'
    # feed and is only listed by GET /api/reports/deleted.
    deleted_at: str | None = None
    deleted_by: str | None = None


class ReportStatusUpdate(BaseModel):
    status: Literal["verified", "rejected"]
    verified_by: str
    # Only meaningful when status is "verified". Lets the technologist
    # correct the farmer's estimated_value instead of just rubber-stamping
    # it; omit to accept the farmer's own estimate as-is.
    verified_value: float | None = None
