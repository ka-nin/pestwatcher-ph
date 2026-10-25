import uuid
from dataclasses import replace
from typing import Literal
from datetime import date, timedelta
from pathlib import Path

from PIL import Image

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app.config import get_settings
from app.data.municipalities import municipality_coordinates
from app.decision.etl_thresholds import derive_risk_level
from app.decision.outlook import growth_outlook, project_affected_area, project_by_forecast_ratio, spread_summary
from app.decision.report_anchor import find_lagged_observation
from app.preprocessing.damage_pattern import CELL_AFFECTED_MIN_PCT, HopperburnReading, read_photo
from app.preprocessing.tiling import TILE_HIT_THRESHOLD
from app.preprocessing.photo_footprint import ground_area_by_cell, estimate_field_size_ha
from app.models.planthopper_detector import planthopper_detector
from app.models.resnet_model import _risk_level_for_confidence, resnet_classifier, resnet_regressors
from app.routers.weather import fetch_recent_daily_weather
from app.schemas.inference import (
    ExplanationResponse,
    FieldAssessmentDay,
    FieldAssessmentResponse,
    ForecastInferenceRequest,
    ForecastInferenceResponse,
    GrowthStage,
    ImageInferenceResponse,
    TrajectoryPoint,
    TrajectoryResponse,
)
from app.models.bilstm_model import DailyObservation, bilstm_forecaster
from ml.config import FORECAST_HORIZON_DAYS, GROWTH_STAGE_BUCKETS, PEST_PARAMS

# Imported lazily inside the /forecast/explain handler below, not here at
# module scope — shap pulls in sklearn.linear_model, whose compiled
# _cd_fast.pyd can be blocked by a locked-down machine's Application
# Control policy. Keeping it out of the startup import chain means that
# only the explain endpoint fails on such a machine, not the whole app.

router = APIRouter(prefix="/api/inference", tags=["inference"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}




# A photo with no insect is reported as showing damage only when the field model
# finds it in at least this share of cells AND it covers at least this share of
# the photo: tuned on held-out synthetic photos so healthy fields are not flagged
# (see ml/weights/rsb/field_damage_rsb_*_synthetic_test_metrics.json).
DAMAGE_RULES = {  # pest -> (min share of cells damaged, min severity in %)
    "RSB": (33.0, 0.8),
}


def _affected_area_m2(path: Path, cell_values: list[list[float]], has_damage: list[list[bool]], tilt_deg: float) -> tuple[float, float, float]:
    """(visible m2, damaged m2, spread m2) for the photo at an assumed camera tilt.

    damaged = each cell's ground area x the share of that cell the model says is
    damaged, i.e. the area the damage actually covers. spread = the ground area
    of every cell that contains any damage, i.e. how far it extends; counting
    whole cells as damaged would overstate the area (a cell with 1% damage is
    not 100% damaged)."""
    areas = ground_area_by_cell(path, len(has_damage), len(has_damage[0]), tilt_deg=tilt_deg)
    visible = sum(sum(r) for r in areas)
    damaged = sum(a * min(v, 100.0) / 100 for ra, rv in zip(areas, cell_values) for a, v in zip(ra, rv))
    spread = sum(a for ra, rd in zip(areas, has_damage) for a, d in zip(ra, rd) if d)
    return visible, damaged, spread


def _field_result(
    pest: str,
    target: str,
    cells: list[list[float]],
    field_size_ha: float | None,
    field_size_source: Literal["entered", "photo_metadata"] | None = None,
) -> FieldAssessmentResponse:
    meta = resnet_regressors.meta(pest, target)
    threshold = float(meta.get("cell_has_damage_threshold", 0.2))
    flat = [v for row in cells for v in row]
    affected = [v for v in flat if v >= threshold]
    cells_affected_pct = round(100 * len(affected) / len(flat), 1)
    return FieldAssessmentResponse(
        status="ok",
        pest=pest,
        target=target,
        rows=len(cells),
        cols=len(cells[0]),
        cell_values=[[round(v, 2) for v in row] for row in cells],
        cell_has_damage=[[v >= threshold for v in row] for row in cells],
        pct_affected=round(sum(flat) / len(flat), 2),
        cells_affected_pct=cells_affected_pct,
        severity_where_present_pct=round(sum(affected) / len(affected), 2) if affected else 0.0,
        field_size_ha=field_size_ha,
        field_size_source=field_size_source if field_size_ha else None,
        # 6 decimals, not 4: a small test plot (e.g. 100 m^2 = 0.01 ha) at a low
        # severity % easily works out to a true affected area under 0.0001 ha —
        # still a real, non-zero number of square metres once admin-web
        # converts it back for display, but 4 decimals would round it away to
        # a misleading 0.0.
        affected_hectares=round(sum(flat) / len(flat) / 100 * field_size_ha, 6) if field_size_ha else None,
        message=(
            "Field assessment complete. Estimated from synthetic-trained models; "
            "a technologist must confirm it before it counts as an observation."
        ),
    )



def _with_photo_area(result: FieldAssessmentResponse, path: Path) -> FieldAssessmentResponse:
    cells = result.cell_values
    visible, affected, spread = _affected_area_m2(path, cells, result.cell_has_damage, 35.0)
    _, affected_low, _ = _affected_area_m2(path, cells, result.cell_has_damage, 45.0)
    _, affected_high, _ = _affected_area_m2(path, cells, result.cell_has_damage, 30.0)
    result.visible_area_m2 = round(visible, 1)
    result.spread_area_m2 = round(spread, 1)
    result.affected_area_m2 = round(affected, 1)
    result.affected_area_m2_low = round(affected_low, 1)
    result.affected_area_m2_high = round(affected_high, 1)
    return result


def _project_field_assessment_days(result: FieldAssessmentResponse, trajectory: TrajectoryResponse) -> list[FieldAssessmentDay] | None:
    """Builds the panel-requested 14-day outlook: day 0 is this photo's own
    measured severity/spread/area; days 1-13 project those same fields by
    scaling with the BiLSTM's own forecast ratio for that day (see
    app/decision/outlook.py's project_by_forecast_ratio — the same
    assumption already used for projected_affected_ha). pest_level and
    risk_level are the BiLSTM's own trained forecast, not derived from the
    photo. Returns None if the trajectory itself didn't load (model_not_loaded)."""
    if trajectory.status != "ok" or not trajectory.points:
        return None

    severity_series = project_by_forecast_ratio(trajectory.points, result.pct_affected, max_growth_factor=100.0)
    spread_series = project_by_forecast_ratio(trajectory.points, result.cells_affected_pct, max_growth_factor=100.0)
    hectares_series = project_by_forecast_ratio(trajectory.points, result.affected_hectares, round_digits=6)

    # Percentages can't exceed 100 regardless of the forecast ratio — the cap
    # above only bounds the multiplier, not the final value.
    severity_series = [min(v, 100.0) if v is not None else None for v in severity_series]
    spread_series = [min(v, 100.0) if v is not None else None for v in spread_series]

    days = []
    for i, point in enumerate(trajectory.points):
        days.append(
            FieldAssessmentDay(
                date=point.date,
                is_measured=i == 0,
                pest_level=point.predicted_value,
                risk_level=point.risk_level,
                severity_pct=severity_series[i] if i > 0 else result.pct_affected,
                spread_pct=spread_series[i] if i > 0 else result.cells_affected_pct,
                affected_hectares=hectares_series[i] if i > 0 else result.affected_hectares,
            )
        )
    return days


def _hopperburn_result(reading: HopperburnReading, field_size_ha: float | None, source: str | None) -> FieldAssessmentResponse:
    """BPH field damage (hopperburn) from the colour-and-shape screen, in the same shape as the
    stem-borer field model's result. Severity is the dried share of the plant canopy in view;
    spread is the share of the 3x3 grid cells with at least CELL_AFFECTED_MIN_PCT dried."""
    cells = reading.cell_values
    flat = [v for row in cells for v in row]
    affected = [v for v in flat if v >= CELL_AFFECTED_MIN_PCT]
    severity = reading.dry_share_pct
    return FieldAssessmentResponse(
        status="ok",
        pest="BPH",
        target="field_damage_pct",
        rows=len(cells),
        cols=len(cells[0]),
        cell_values=[[round(v, 2) for v in row] for row in cells],
        cell_has_damage=[[v >= CELL_AFFECTED_MIN_PCT for v in row] for row in cells],
        pct_affected=severity,
        cells_affected_pct=round(100 * len(affected) / len(flat), 1),
        severity_where_present_pct=round(sum(affected) / len(affected), 2) if affected else 0.0,
        field_size_ha=field_size_ha,
        field_size_source=source if field_size_ha else None,
        affected_hectares=round(severity / 100 * field_size_ha, 6) if field_size_ha else None,
        message=(
            ("Hopperburn pattern: " if reading.hopperburn else "Not clearly hopperburn: ") + reading.reason + ". "
            "This is a colour-and-shape screen, not a trained model: a technologist must confirm it."
        ),
    )


def _damage_found(result: FieldAssessmentResponse) -> bool:
    if result.status != "ok" or result.pest not in DAMAGE_RULES:
        return False
    min_cells, min_severity = DAMAGE_RULES[result.pest]
    return (result.cells_affected_pct or 0) >= min_cells and (result.pct_affected or 0) >= min_severity


def _assess_photo(pest: str, path: Path, field_size_ha: float | None = None) -> FieldAssessmentResponse | None:
    cells = resnet_regressors.predict_grid(pest, "field_damage_pct", path)
    if cells is None:
        return None
    if field_size_ha is not None:
        result = _field_result(pest, "field_damage_pct", cells, field_size_ha, "entered")
    else:
        result = _field_result(pest, "field_damage_pct", cells, estimate_field_size_ha(path), "photo_metadata")
    return _with_photo_area(result, path)


@router.post("/field-assessment", response_model=FieldAssessmentResponse)
async def assess_field(
    file: UploadFile = File(...),
    pest: Literal["RSB", "BPH"] = Form(...),
    field_size_ha: float | None = Form(None, gt=0, le=1000),
    municipality: str | None = Form(
        None, description="Needed for the 14-day outlook (day field, below) — omit for a one-day-only result."
    ),
    growth_stage: GrowthStage | None = Form(
        None, description="Needed for the 14-day outlook, alongside municipality."
    ),
) -> FieldAssessmentResponse:
    """Severity and extent from a whole-field photo (panel concern: field
    level, not a close-up; regression, not classification).

    The caller names the pest, so no classifier gate runs. The photo is cut
    into the model's grid of cells and the pest's FIELD-level damage model
    estimates each one. Severity is the mean over cells (share of the photo
    covered); spread is the share of cells containing damage, and with the
    field size, the hectares those cells represent.

    The patch-level coverage/damage models are not used here: they were trained
    on collages of patches and measured (2026-10-22) to read the same value on
    a damaged and a healthy field.

    The RSB severity is the share of the image covered by whiteheads, a PROXY
    for the thesis's "% white ears", so it is deliberately not mapped to an
    ETL risk level. Nothing is stored and nothing reaches the forecast: this is an
    unverified estimate for a technologist to confirm.

    With municipality + growth_stage, the response's `daily` field also carries
    the panel-requested 14-day outlook: this photo's own reading becomes day 0
    of the same BiLSTM trajectory GET /forecast/trajectory uses (read-only —
    this still never writes to the database or any stored forecast), and
    severity/spread/affected-hectares for days 1-13 are PROJECTED by scaling
    day 0's photo reading with that forecast (see _project_field_assessment_days).
    Without both params, `daily` is null and the response is just today's photo.
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported image type; use JPEG, PNG or WebP.")

    target = "field_damage_pct"
    settings = get_settings()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / f"field_{uuid.uuid4().hex}{Path(file.filename or 'photo.jpg').suffix or '.jpg'}"
    destination.write_bytes(await file.read())
    _require_valid_image(destination)
    try:
        detected_ha = estimate_field_size_ha(destination) if field_size_ha is None else None
        if pest == "BPH":
            # No trained BPH field model exists (no field-level BPH data): hopperburn is read from
            # the photo's colours and shape (app/preprocessing/damage_pattern.py).
            result = _hopperburn_result(
                read_photo(destination),
                field_size_ha if field_size_ha is not None else detected_ha,
                "entered" if field_size_ha is not None else "photo_metadata",
            )
            cells = result.cell_values
        else:
            cells = resnet_regressors.predict_grid(pest, target, destination)
        if pest != "BPH" and cells is not None:
            result = (
                _field_result(pest, target, cells, field_size_ha, "entered")
                if field_size_ha is not None
                else _field_result(pest, target, cells, detected_ha, "photo_metadata")
            )
            result = _with_photo_area(result, destination)
    finally:
        destination.unlink(missing_ok=True)  # an assessment keeps nothing

    if cells is None:
        return FieldAssessmentResponse(
            status="model_not_loaded",
            message=(
                f"No field-level {pest} damage model is installed. It needs training on field photos "
                "(ml/resnet/train_field_damage.py); the patch-level models do not transfer to field photos."
            ),
        )

    if municipality and growth_stage:
        # Severity is % damage, the RSB forecast's own unit; BPH's unit is hoppers per hill, so a
        # hopperburn reading cannot be fed in as that observation.
        photo_features = (result.pct_affected, 0.0, 1.0) if pest == "RSB" and result.pct_affected is not None else None
        trajectory = _build_trajectory(municipality, pest, growth_stage, days=14, override_lagged_features=photo_features)
        result.daily = _project_field_assessment_days(result, trajectory)

    return result


@router.post("/image", response_model=ImageInferenceResponse)
async def infer_image(
    file: UploadFile = File(...),
    municipality: str | None = Form(
        None, description="Farmer's municipality — needed to fetch weather for the 14-day forecast."
    ),
    growth_stage: GrowthStage | None = Form(
        None, description="Current rice growth stage — needed for the forecast's ETL bucketing."
    ),
    field_size_ha: float | None = Form(
        None, gt=0, le=1000, description="Optional field size; otherwise the area is estimated from the photo."
    ),
) -> ImageInferenceResponse:
    """Receives an optical field photo from the mobile app, identifies which
    tracked pest (if any) is present via `resnet_classifier` (two independent
    binary models — see app/models/resnet_model.py), then — if a pest was
    detected — also runs `resnet_regressors` for that pest's quantitative
    estimate (count + coverage for BPH, damage % for RSB), and, if the
    caller supplied municipality/growth_stage, the 14-day BiLSTM forecast
    (GET /forecast/trajectory's same underlying logic) — so the mobile app
    gets one photo-in, full-picture-out response instead of orchestrating
    several separate calls.

    `municipality`/`growth_stage` are optional so a caller that only wants
    the raw classification (no forecast) can omit them — the response's
    `forecast` field is simply null in that case. The estimated_* fields ARE
    fed into this specific forecast (as a one-off override of the usual
    verified-reports lookup — see _build_trajectory's override_lagged_features
    and ImageInferenceResponse.forecast_reflects_this_photo), so the risk the
    farmer sees here can react to their own unverified photo. They still
    never touch the database or any other municipality's forecast; that only
    happens once a technologist confirms the resulting report.
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported content type: {file.content_type}",
        )

    destination = await _save_upload(file)
    _require_valid_image(destination)
    result = resnet_classifier.predict(destination)

    if result is None:
        return ImageInferenceResponse(
            status="model_not_loaded",
            message="ResNet-50 model not loaded yet — image saved for later training/inference",
        )
    # The box detector finds each planthopper itself, so a photo the classifier
    # missed (many small insects, a leaf close-up) can still be recognised as BPH.
    detections = planthopper_detector.detect(destination)
    if result.label is None and (
        planthopper_detector.confident(detections)
        or planthopper_detector.second_opinion(
            detections, result.pest_scores.get("BPH", 0.0), tiled=result.grid_tiles is not None
        )
    ):
        top = max(d.score for d in detections)
        result = replace(
            result, label="BPH", confidence=top, risk_level=_risk_level_for_confidence(top),
            pests_detected=["BPH"], unidentified=False,
        )
    if result.label is None:
        return _no_tracked_pest_response(result, destination, municipality, growth_stage, field_size_ha)
    return _pest_found_response(result, destination, municipality, growth_stage, field_size_ha, detections)



def _require_valid_image(path: Path) -> None:
    """The content type comes from the client and can lie: reject a file PIL cannot
    decode with a clear 422 instead of letting the models fail with a 500."""
    try:
        with Image.open(path) as img:
            img.verify()
    except Exception:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="The uploaded file is not a readable image.")


async def _save_upload(file: UploadFile) -> Path:
    """Keeps the photo on disk (uploads/) so it can be reviewed or used for training later."""
    upload_dir = Path(get_settings().upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / f"{uuid.uuid4().hex}{Path(file.filename or '').suffix or '.jpg'}"
    destination.write_bytes(await file.read())
    return destination


def _grid_fields(result) -> dict:
    return dict(
        pest_scores=result.pest_scores,
        grid_used=result.grid_tiles is not None,
        grid_tiles=result.grid_tiles,
        bph_grid_count=result.grid_count,
    )


def _detection_fields(photo: Path, detections: list | None) -> dict:
    if not detections:
        return {}
    from PIL import Image

    with Image.open(photo) as img:
        width, height = img.size
    return dict(detections=[d.__dict__ for d in detections], image_width=width, image_height=height)


def _no_tracked_pest_response(
    result, photo: Path, municipality: str | None, growth_stage: GrowthStage | None, field_size_ha: float | None = None
) -> ImageInferenceResponse:
    """The classifiers found neither BPH nor RSB. In order: the photo shows RSB damage
    (checked first: on 100 real stem-borer photos the unknown-insect detector fired on 64%
    of whitehead photos and 24% of healthy ones, so it cannot outrank the damage check);
    another insect was seen (unidentified); nothing."""
    # The classifiers look for the insect, so a photo of whiteheads with no insect
    # in frame scores near zero: check the photo for damage before answering "none".
    # But not when the BPH classifier already saw something insect-like: a tile that fired
    # strongly means planthoppers are the likelier reading, and the damage model (trained
    # on synthetic whiteheads) must not relabel such a photo as stem borer.
    bph_signal = result.pest_scores.get("BPH", 0.0) >= TILE_HIT_THRESHOLD
    # A large solid dried patch with green around it is brown planthopper damage (hopperburn);
    # the stem-borer model would also fire on it, so the pattern is checked first.
    reading = None if bph_signal else read_photo(photo)
    if reading is not None and reading.hopperburn:
        burn = _hopperburn_result(
            reading, field_size_ha if field_size_ha is not None else estimate_field_size_ha(photo),
            "entered" if field_size_ha is not None else "photo_metadata",
        )
        forecast = _build_trajectory(municipality, "BPH", growth_stage, days=14) if municipality and growth_stage else None
        if forecast is not None:
            burn.daily = _project_field_assessment_days(burn, forecast)
        return ImageInferenceResponse(
            status="damage_detected",
            pest_detected="BPH",
            message=(
                "No insect is visible, but the photo shows a large dried patch with green plants around it, "
                "the pattern of brown planthopper damage (hopperburn). This is a colour-and-shape screen, "
                "not a trained model: please have a technologist confirm it."
            ),
            pest_scores=result.pest_scores,
            field_assessment=burn,
            forecast=forecast,
            forecast_reflects_this_photo=False,
        )
    assessment = None if bph_signal else _assess_photo("RSB", photo, field_size_ha)
    if assessment is not None and _damage_found(assessment):
        # The photo's severity stands in for the RSB observation (% damage, the
        # forecast's own unit), so the trajectory reacts to this photo like a BPH count does.
        photo_features = (assessment.pct_affected, 0.0, 1.0) if assessment.pct_affected is not None else None
        forecast = (
            _build_trajectory(municipality, "RSB", growth_stage, days=14, override_lagged_features=photo_features)
            if municipality and growth_stage
            else None
        )
        if forecast is not None:
            assessment.daily = _project_field_assessment_days(assessment, forecast)
        return ImageInferenceResponse(
            status="damage_detected",
            pest_detected=assessment.pest,
            message=(
                "No insect is visible, but the photo shows damage consistent with whiteheads (stem borer). "
                "This is an unverified estimate: please have a technologist confirm it."
            ),
            pest_scores=result.pest_scores,
            field_assessment=assessment,
            forecast=forecast,
            forecast_reflects_this_photo=forecast is not None and photo_features is not None,
        )

    if result.unidentified:
        return ImageInferenceResponse(
            status="unidentified_pest_detected",
            message=(
                "An insect appears to be present, but it did not match our trained BPH/RSB models. "
                "It may be a different pest — please consult your local agricultural technologist."
            ),
            **_grid_fields(result),
        )

    return ImageInferenceResponse(
        status="no_pest_detected",
        message=(
            "Possible planthoppers were seen but not clearly enough to confirm. Try a closer, sharper photo."
            if bph_signal
            else "No tracked pest (BPH/RSB) was detected in this photo with sufficient confidence."
        ),
        **_grid_fields(result),
    )


def _quantity_estimates(pest: str, photo: Path, detections: list | None = None) -> dict[str, float | None]:
    """The pest's own photo estimate: count + coverage for BPH, damage % for RSB.
    When the box detector ran and found insects, the count is the number of boxes."""
    if pest == "BPH" and detections:
        return {
            "estimated_count": float(len(detections)),
            "estimated_coverage_pct": resnet_regressors.predict("BPH", "coverage_pct", photo),
        }
    if pest == "BPH":
        return {
            "estimated_count": resnet_regressors.predict("BPH", "count", photo),
            "estimated_coverage_pct": resnet_regressors.predict("BPH", "coverage_pct", photo),
        }
    return {"estimated_damage_pct": resnet_regressors.predict("RSB", "damage_pct", photo)}


def _photo_lagged_features(pest: str, estimates: dict[str, float | None]) -> tuple[float, float, float] | None:
    """This photo's estimate as the forecast's one-off verified-observation input.
    The unit must match the pest's ETL/BiLSTM target: hoppers/hill for BPH (the
    count, not the coverage, which is affected area rather than density) and %
    damage for RSB. Age 0 / recency 1.0: "observed today" for this preview only."""
    value = estimates.get("estimated_count" if pest == "BPH" else "estimated_damage_pct")
    return None if value is None else (value, 0.0, 1.0)


def _pest_found_response(
    result, photo: Path, municipality: str | None, growth_stage: GrowthStage | None,
    field_size_ha: float | None = None, detections: list | None = None
) -> ImageInferenceResponse:
    pest = result.label
    # The estimate is computed BEFORE the forecast so this photo's own number can feed
    # the trajectory below. The photo also gets the field-level severity and spread.
    field_assessment = _assess_photo(pest, photo, field_size_ha) if pest in DAMAGE_RULES else None
    estimates = _quantity_estimates(pest, photo, detections)
    photo_features = _photo_lagged_features(pest, estimates)

    forecast: TrajectoryResponse | None = None
    if municipality and growth_stage:
        forecast = _build_trajectory(
            municipality, pest, growth_stage, days=14, override_lagged_features=photo_features
        )
        if forecast is not None and field_assessment is not None:
            field_assessment.daily = _project_field_assessment_days(field_assessment, forecast)

    return ImageInferenceResponse(
        status="ok",
        pest_detected=pest,
        **estimates,
        confidence=result.confidence,
        risk_level=result.risk_level,
        message="Prediction successful",
        forecast=forecast,
        forecast_reflects_this_photo=photo_features is not None,
        **_detection_fields(photo, detections if pest == "BPH" else None),
        pests_detected=result.pests_detected,
        field_assessment=field_assessment,
        **_grid_fields(result),
    )


def _window_for_target(
    pest: str, target_date: date, growth_stage: GrowthStage, weather_by_date: dict[str, dict]
) -> list[DailyObservation] | None:
    """The 14-day weather window the model needs to predict `target_date`
    (it ends FORECAST_HORIZON_DAYS before it). None if the fetched weather
    doesn't reach back far enough."""
    window_days = PEST_PARAMS[pest].crf_window_days
    window_end = target_date - timedelta(days=FORECAST_HORIZON_DAYS)
    window_dates = [(window_end - timedelta(days=window_days - 1 - i)).isoformat() for i in range(window_days)]

    if not all(d in weather_by_date for d in window_dates):
        return None

    return [
        DailyObservation(
            tmax=weather_by_date[d]["tmax"],
            tmin=weather_by_date[d]["tmin"],
            relative_humidity=weather_by_date[d]["relative_humidity"],
            rainfall=weather_by_date[d]["rainfall"],
            growth_stage=growth_stage,
        )
        for d in window_dates
    ]


def _run_forecast(
    pest: str, window: list[DailyObservation], municipality: str | None = None
) -> ForecastInferenceResponse:
    """Shared by both endpoints below: predict, then apply the (separate,
    non-learned) ETL bucketing — see app/decision/etl_thresholds.py.

    A verified report still never DIRECTLY overwrites predicted_value the
    way the old report-anchor fade did — there is no post-hoc shift here.
    What changed (the panel's redesign): the model itself now has a lagged-
    observation INPUT (app/decision/report_anchor.py's
    find_lagged_observation(), trained via ml/bilstm/build_sequences.py
    --features lagged), so a recent verified report legitimately influences
    the forecast by being part of what the model was asked to reason about —
    the same way a weather input does — rather than by adjusting its output
    afterward. `municipality` is optional because POST /forecast (raw
    observations, no municipality in the payload) has no report context to
    look up; it gets the model's own "no recent observation" default instead
    of an error.
    """
    growth_stage_bucket = GROWTH_STAGE_BUCKETS[window[-1].growth_stage]
    lagged_features = None
    if municipality is not None:
        lagged_features = find_lagged_observation(municipality, pest, date.today(), growth_stage_bucket)

    result = bilstm_forecaster.predict(pest, window, lagged_features)

    if result is None:
        return ForecastInferenceResponse(
            status="model_not_loaded",
            message=f"BiLSTM model for {pest} not loaded yet — placeholder response",
        )

    value = result.predicted_value
    risk_level = derive_risk_level(pest, growth_stage_bucket, value)

    return ForecastInferenceResponse(
        status="ok",
        predicted_value=value,
        unit=result.unit,
        risk_level=risk_level,
        message="Forecast successful",
        adjusted_by_reports=lagged_features is not None and lagged_features[2] == 1.0,
        verified_report_count=1 if lagged_features is not None and lagged_features[2] == 1.0 else 0,
    )


@router.post("/forecast", response_model=ForecastInferenceResponse)
def infer_forecast(payload: ForecastInferenceRequest) -> ForecastInferenceResponse:
    """Takes a window of raw daily weather + growth stage observations and
    returns a continuous outbreak forecast (hoppers/hill for BPH, % damage
    for RSB), plus the ETL-derived Low/Medium/High level applied to it.

    The forecast itself is learned (bilstm_forecaster, app/models/bilstm_model.py);
    the risk level is not (app/decision/etl_thresholds.py) — kept as two
    separate steps per the panel's fix #1, so the model can't drift from the
    fixed PhilRice/DA-RCPC decision thresholds.

    Caller supplies the daily observations directly — use this when weather
    has already been fetched/logged elsewhere. For a live fetch from
    today's weather, see GET /forecast/live below.
    """
    expected_days = PEST_PARAMS[payload.pest].crf_window_days
    if len(payload.daily_observations) != expected_days:
        raise HTTPException(
            status_code=422,
            detail=(
                f"{payload.pest} requires exactly {expected_days} consecutive daily "
                f"observations, got {len(payload.daily_observations)}."
            ),
        )

    window = [
        DailyObservation(
            tmax=obs.tmax,
            tmin=obs.tmin,
            relative_humidity=obs.relative_humidity,
            rainfall=obs.rainfall,
            growth_stage=obs.growth_stage,
        )
        for obs in payload.daily_observations
    ]

    return _run_forecast(payload.pest, window)


def _live_forecast(municipality: str, pest: str, growth_stage: GrowthStage) -> ForecastInferenceResponse:
    """Shared by GET /forecast/live and the superadmin cross-municipality
    overview (app/routers/admin.py) so both run the exact same pipeline.

    See _run_forecast's docstring for how a verified report now reaches the
    model (as a lagged-observation input, looked up here by municipality) —
    only the weather window itself is fetched below.
    """
    coordinates = municipality_coordinates(municipality)
    if coordinates is None:
        raise HTTPException(
            status_code=404,
            detail=f"No coordinates on file for municipality '{municipality}'.",
        )
    latitude, longitude = coordinates

    window_days = PEST_PARAMS[pest].crf_window_days
    daily_weather = fetch_recent_daily_weather(latitude, longitude, days=window_days)

    window = [
        DailyObservation(
            tmax=day["tmax"],
            tmin=day["tmin"],
            relative_humidity=day["relative_humidity"],
            rainfall=day["rainfall"],
            growth_stage=growth_stage,
        )
        for day in daily_weather[-window_days:]
    ]

    return _run_forecast(pest, window, municipality)


@router.get("/forecast/live", response_model=ForecastInferenceResponse)
def infer_forecast_live(
    municipality: str = Query(..., description="Must match a municipality in app/data/lgu_users.py"),
    pest: str = Query(..., pattern="^(BPH|RSB)$"),
    growth_stage: GrowthStage = Query(
        ...,
        description=(
            "Current rice growth stage for this field. Applied to every day in "
            "the fetched window — weather APIs have no concept of crop growth "
            "stage, so this has to come from LGU/farmer-reported data, not "
            "from the live fetch."
        ),
    ),
) -> ForecastInferenceResponse:
    """Live version of /forecast: fetches the actual past N days of weather
    for `municipality` from Open-Meteo (N = ml.config.PEST_PARAMS[pest].crf_window_days,
    currently 14) instead of requiring the caller to supply it, then runs
    the same predict + ETL-bucket pipeline as /forecast.
    """
    return _live_forecast(municipality, pest, growth_stage)


def _build_trajectory(
    municipality: str,
    pest: str,
    growth_stage: GrowthStage,
    days: int,
    override_lagged_features: tuple[float, float, float] | None = None,
) -> TrajectoryResponse:
    """Shared by GET /forecast/trajectory and POST /image (once a pest is
    detected in a photo, its 14-day trajectory is fetched the same way) so
    both run the exact same pipeline.

    Key trick: because the model's forecast horizon (FORECAST_HORIZON_DAYS,
    currently 14) is >= the number of future days requested here, EVERY
    window this needs — even the one whose target is `days` days from now —
    ends on or before today. So the whole trajectory can be built from
    already-observed weather; no forecast-weather API is needed, only the
    same past-days fetch /forecast/live uses, just a longer stretch of it.

    `override_lagged_features` lets POST /image feed THIS photo's own
    just-computed regression estimate (count/damage_pct — see infer_image)
    into the lagged-observation slot instead of looking one up by
    municipality. It never touches the database and it never affects
    GET /forecast/trajectory (which always passes None and keeps using
    find_lagged_observation's verified-only lookup) — it exists only so the
    one-off trajectory shown back to the farmer who just took this photo can
    react to their own unverified estimate, per the panel's ask that the
    predicted risk actually depend on the photo's count/coverage, not just
    weather. The number only becomes a real, system-of-record input (and
    something every other municipality view can see) once a technologist
    confirms the report it came from.
    """
    coordinates = municipality_coordinates(municipality)
    if coordinates is None:
        raise HTTPException(
            status_code=404,
            detail=f"No coordinates on file for municipality '{municipality}'.",
        )
    latitude, longitude = coordinates

    today = date.today()

    # Generous on purpose: the last target's window could start as far back
    # as (today - horizon - window_days + 1); this fetch covers that plus
    # margin rather than computing the minimum.
    fetch_days = PEST_PARAMS[pest].crf_window_days + days + FORECAST_HORIZON_DAYS
    daily_weather = fetch_recent_daily_weather(latitude, longitude, days=fetch_days)
    weather_by_date = {day["date"]: day for day in daily_weather}

    growth_stage_bucket = GROWTH_STAGE_BUCKETS[growth_stage]
    # Looked up once per trajectory (not once per point): the lagged
    # observation is relative to `today`, same reference point regardless of
    # which future day each trajectory point targets — see _run_forecast's
    # docstring for what this represents. An override (this photo's own
    # fresh, unverified estimate) always wins over the verified-reports
    # lookup when the caller supplies one.
    lagged_features = override_lagged_features
    if lagged_features is None:
        lagged_features = find_lagged_observation(municipality, pest, today, growth_stage_bucket)

    points: list[TrajectoryPoint] = []
    for offset in range(days):
        target_date = today + timedelta(days=offset)
        window = _window_for_target(pest, target_date, growth_stage, weather_by_date)
        if window is None:
            continue  # not enough fetched history for this point — skip rather than fail the whole trajectory

        result = bilstm_forecaster.predict(pest, window, lagged_features)
        if result is None:
            return TrajectoryResponse(
                status="model_not_loaded",
                points=[],
                message=f"BiLSTM model for {pest} not loaded yet",
            )

        value = result.predicted_value

        points.append(
            TrajectoryPoint(
                date=target_date.isoformat(),
                predicted_value=value,
                unit=result.unit,
                risk_level=derive_risk_level(pest, growth_stage_bucket, value),
                adjusted_by_reports=lagged_features[2] == 1.0,
                predicted_low=result.low,
                predicted_high=result.high,
            )
        )

    spread = spread_summary(municipality, pest, today)
    for point, hectares in zip(points, project_affected_area(points, spread["recent_hectares"])):
        point.projected_affected_ha = hectares

    return TrajectoryResponse(
        status="ok",
        points=points,
        outlook=growth_outlook(points, pest),
        spread=spread,
        message="Trajectory forecast successful",
    )


@router.get("/forecast/trajectory", response_model=TrajectoryResponse)
def infer_forecast_trajectory(
    municipality: str = Query(..., description="Must match a municipality in app/data/lgu_users.py"),
    pest: str = Query(..., pattern="^(BPH|RSB)$"),
    growth_stage: GrowthStage = Query(
        ...,
        description="Applied to every day across every window — see /forecast/live for why.",
    ),
    days: int = Query(13, ge=1, le=14, description="How many future days to forecast, starting today."),
) -> TrajectoryResponse:
    """Multi-day forecast trajectory, for charting a projected outbreak curve
    (e.g. May 17 -> May 29) rather than a single point. See _build_trajectory
    for the actual logic, shared with POST /image.
    """
    return _build_trajectory(municipality, pest, growth_stage, days)


@router.get("/forecast/explain", response_model=ExplanationResponse)
def infer_forecast_explain(
    municipality: str = Query(..., description="Must match a municipality in app/data/lgu_users.py"),
    pest: str = Query(..., pattern="^(BPH|RSB)$"),
    growth_stage: GrowthStage = Query(..., description="Same growth-stage semantics as /forecast/live."),
    top_n: int = Query(7, ge=1, le=20),
) -> ExplanationResponse:
    """SHAP feature attributions for today's live forecast — explains why
    the model produced the value /forecast/live returns for the same
    municipality/pest/growth_stage, not a separate prediction.

    Post-hoc explanation only (ml/explainability/shap_report.py) — this
    never feeds back into the model or the ETL thresholds.
    """
    if not bilstm_forecaster.is_loaded(pest):
        return ExplanationResponse(
            status="model_not_loaded",
            features=[],
            message=f"BiLSTM model for {pest} not loaded yet",
        )

    coordinates = municipality_coordinates(municipality)
    if coordinates is None:
        raise HTTPException(
            status_code=404,
            detail=f"No coordinates on file for municipality '{municipality}'.",
        )
    latitude, longitude = coordinates

    window_days = PEST_PARAMS[pest].crf_window_days
    daily_weather = fetch_recent_daily_weather(latitude, longitude, days=window_days)

    window = [
        DailyObservation(
            tmax=day["tmax"],
            tmin=day["tmin"],
            relative_humidity=day["relative_humidity"],
            rainfall=day["rainfall"],
            growth_stage=growth_stage,
        )
        for day in daily_weather
    ]

    from ml.explainability.shap_report import compute_top_attributions

    growth_stage_bucket = GROWTH_STAGE_BUCKETS[growth_stage]
    lagged_features = find_lagged_observation(municipality, pest, date.today(), growth_stage_bucket)
    X_sequence_scaled, X_static_scaled = bilstm_forecaster.build_model_inputs(pest, window, lagged_features)
    attributions = compute_top_attributions(pest, X_sequence_scaled, X_static_scaled, top_n=top_n)

    return ExplanationResponse(status="ok", features=attributions, message="Explanation successful")
