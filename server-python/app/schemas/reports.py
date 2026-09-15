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


class ReportResponse(BaseModel):
    id: str
    submitted_at: str


class ReportRecord(ReportRequest):
    id: str
    submitted_at: str
    # Every report starts unverified — an LGU technician reviews it in
    # admin-web before it's allowed to nudge the forecast (see
    # app/decision/report_signal.py). Old records written before this field
    # existed default to "pending" on load.
    status: ReportStatus = "pending"
    verified_by: str | None = None
    verified_at: str | None = None
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


class ReportStatusUpdate(BaseModel):
    status: Literal["verified", "rejected"]
    verified_by: str
