"""SMS advisories composed and sent by an agricultural technologist.

Sending is deliberately manual. The system does not text farmers on its own
when a forecast crosses a threshold: a forecast is a model output, and an
unattended broadcast would put an unreviewed number in front of a farmer. A
technologist reads the forecast, decides it warrants an advisory, writes it
and sends it — which is the same trust gate the report pipeline applies in
the other direction.

Every send is scoped to the technologist's own municipality, matching the
rule already enforced on report review (app/routers/reports.py).
"""

import uuid

import requests
from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.data import sms_store
from app.data.farmer_users import list_farmers
from app.data.lgu_users import find_lgu_user
from app.dependencies import require_lgu
from app.schemas.sms import (
    SmsGatewayStatus,
    SmsMessageRecord,
    SmsRecipient,
    SmsSendRequest,
    SmsSendResponse,
)
from app.security import TokenPayload
from app.sms import get_sender, normalise_phone

router = APIRouter(prefix="/api/sms", tags=["sms"])


def _municipality_of(lgu: TokenPayload) -> str:
    account = find_lgu_user(lgu.username)
    if account is None:
        raise HTTPException(status_code=403, detail="LGU account not found")
    return account.municipality


@router.get("/recipients", response_model=list[SmsRecipient])
def list_recipients(lgu: TokenPayload = Depends(require_lgu)) -> list[SmsRecipient]:
    """Registered farmers in this technologist's municipality who have a mobile
    number on file. Farmers without one are omitted rather than listed and
    disabled, so the picker only ever shows people who can actually be reached.
    """
    municipality = _municipality_of(lgu)
    recipients = []
    for farmer in list_farmers(municipality):
        phone = normalise_phone(farmer.phone or "")
        if phone:
            recipients.append(
                SmsRecipient(
                    username=farmer.username,
                    full_name=farmer.full_name,
                    municipality=farmer.municipality,
                    phone=phone,
                )
            )
    return recipients


@router.get("/gateway-status", response_model=SmsGatewayStatus)
def gateway_status(lgu: TokenPayload = Depends(require_lgu)) -> SmsGatewayStatus:
    """Lets the technologist confirm the handset is reachable *before*
    composing, rather than discovering it is asleep on the first send."""
    settings = get_settings()
    provider = (settings.sms_provider or "console").strip().lower()

    if provider != "android_gateway":
        return SmsGatewayStatus(
            provider="console",
            configured=True,
            reachable=None,
            detail="Simulation mode: messages are recorded in the outbox and logged, but no SMS leaves the server.",
        )

    if not settings.sms_gateway_url:
        return SmsGatewayStatus(
            provider=provider,
            configured=False,
            reachable=False,
            detail="SMS_GATEWAY_URL is not set, so sends fall back to simulation.",
        )

    url = settings.sms_gateway_url.rstrip("/")
    try:
        response = requests.get(
            f"{url}/health",
            auth=(settings.sms_gateway_username, settings.sms_gateway_password),
            timeout=min(settings.sms_gateway_timeout_seconds, 8.0),
        )
        # 401/404 still prove something is listening and routable; only the
        # connection failing means the phone is unreachable.
        reachable = response.status_code < 500
        detail = f"Gateway answered with HTTP {response.status_code}."
    except requests.exceptions.RequestException as exc:
        reachable = False
        detail = f"Could not reach {url}: {exc.__class__.__name__}. Check the phone is awake, the app's Local Server is running, and the address is right."

    return SmsGatewayStatus(provider=provider, configured=True, reachable=reachable, detail=detail)


@router.get("", response_model=list[SmsMessageRecord])
def list_outbox(limit: int = 200, lgu: TokenPayload = Depends(require_lgu)) -> list[SmsMessageRecord]:
    """This municipality's sent advisories, newest first."""
    return sms_store.list_messages(_municipality_of(lgu), limit=limit)


@router.post("/send", response_model=SmsSendResponse)
def send_sms(payload: SmsSendRequest, lgu: TokenPayload = Depends(require_lgu)) -> SmsSendResponse:
    municipality = _municipality_of(lgu)
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=422, detail="Message body is empty.")

    farmers = list_farmers(municipality)
    by_username = {f.username: f for f in farmers}

    # Resolve every requested recipient to one E.164 number, keeping the
    # farmer's name where we know it so the outbox reads as people, not digits.
    targets: dict[str, tuple[str | None, str | None]] = {}
    skipped: list[str] = []

    def add_farmer(farmer) -> None:
        phone = normalise_phone(farmer.phone or "")
        if phone:
            targets.setdefault(phone, (farmer.username, farmer.full_name))
        else:
            skipped.append(f"{farmer.full_name} (no mobile number on file)")

    if payload.to_all_farmers:
        for farmer in farmers:
            add_farmer(farmer)

    for username in payload.usernames:
        farmer = by_username.get(username)
        if farmer is None:
            skipped.append(f"{username} (not a farmer in {municipality})")
            continue
        add_farmer(farmer)

    for raw in payload.phone_numbers:
        phone = normalise_phone(raw)
        if phone:
            targets.setdefault(phone, (None, None))
        else:
            skipped.append(f"{raw} (not a valid mobile number)")

    if not targets:
        raise HTTPException(
            status_code=422,
            detail="No reachable recipients. " + ("; ".join(skipped) if skipped else "Pick a farmer or type a number."),
        )

    sender = get_sender()
    batch_id = uuid.uuid4().hex
    results: list[SmsMessageRecord] = []
    sent = failed = 0

    for phone, (username, name) in targets.items():
        message_id = uuid.uuid4().hex
        # Written before the attempt so a crash mid-batch leaves evidence.
        sms_store.queue_message(
            message_id=message_id,
            batch_id=batch_id,
            recipient_phone=phone,
            recipient_username=username,
            recipient_name=name,
            body=body,
            municipality=municipality,
            sent_by=lgu.username,
            provider=sender.name,
        )
        outcome = sender.send(phone, body)
        record = sms_store.mark_result(
            message_id,
            ok=outcome.ok,
            provider_message_id=outcome.provider_message_id,
            error=outcome.error,
        )
        if record:
            results.append(record)
        if outcome.ok:
            sent += 1
        else:
            failed += 1

    return SmsSendResponse(
        batch_id=batch_id,
        provider=sender.name,
        sent=sent,
        failed=failed,
        skipped=skipped,
        messages=results,
    )
