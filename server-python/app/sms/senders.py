"""The two SMS senders and the phone-number normalisation they share."""

import logging
import re
from dataclasses import dataclass
from typing import Protocol

import requests

from app.config import get_settings

logger = logging.getLogger("pestwatcher.sms")
# uvicorn configures only its own loggers and leaves the root one without a
# handler, so an app logger that merely propagates is silently dropped. The
# simulated sender exists to be *seen* in the console during a demo, so give
# this logger its own handler when nothing else has.
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:     %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


@dataclass(frozen=True)
class SendOutcome:
    """What happened for one recipient. `error` is surfaced to the technologist
    verbatim, so it carries the gateway's own wording rather than a generic
    'send failed' that would leave them guessing."""

    ok: bool
    provider: str
    provider_message_id: str | None = None
    error: str | None = None


class Sender(Protocol):
    name: str

    def send(self, phone: str, body: str) -> SendOutcome: ...


# --------------------------------------------------------------------------
# phone numbers
# --------------------------------------------------------------------------
_NON_DIGITS = re.compile(r"[^\d+]")


def normalise_phone(raw: str, country_code: str | None = None) -> str | None:
    """Philippine mobile numbers arrive written several ways — 09171234567,
    +639171234567, 0917 123 4567, (0917) 123-4567. The gateway wants one
    E.164 string, so everything is folded to +639XXXXXXXXX here rather than at
    each call site. Returns None if the result can't be a mobile number, so a
    typo is rejected at compose time instead of silently failing at send time.
    """
    if not raw:
        return None
    cc = country_code or get_settings().sms_default_country_code
    cleaned = _NON_DIGITS.sub("", raw.strip())
    if not cleaned:
        return None

    if cleaned.startswith("+"):
        digits = cleaned[1:]
    elif cleaned.startswith("00"):
        digits = cleaned[2:]
    elif cleaned.startswith("0"):
        # Local trunk-prefixed form: 0917... -> <cc>917...
        digits = cc.lstrip("+") + cleaned[1:]
    else:
        digits = cleaned
        # A bare subscriber number (9171234567) still needs the country code.
        if not digits.startswith(cc.lstrip("+")):
            digits = cc.lstrip("+") + digits

    if not digits.isdigit() or not (10 <= len(digits) <= 15):
        return None
    return "+" + digits


# --------------------------------------------------------------------------
# senders
# --------------------------------------------------------------------------
class ConsoleSender:
    """Simulation. Records the message and logs it; never touches a network."""

    name = "console"

    def send(self, phone: str, body: str) -> SendOutcome:
        logger.info("[SMS simulated] to %s: %s", phone, body)
        return SendOutcome(ok=True, provider=self.name, provider_message_id=None)


class AndroidGatewaySender:
    """Relays through SMS Gateway for Android in Local Server mode.

    The handset must be reachable from this server. On a shared Wi-Fi its LAN
    address is enough; across networks, put the phone on the same Tailscale
    network and use its 100.x address, which is what SMS_GATEWAY_URL expects.
    """

    name = "android_gateway"

    def __init__(self, base_url: str, username: str, password: str, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.auth = (username, password)
        self.timeout = timeout

    def send(self, phone: str, body: str) -> SendOutcome:
        url = f"{self.base_url}/message"
        try:
            response = requests.post(
                url,
                json={"textMessage": {"text": body}, "phoneNumbers": [phone]},
                auth=self.auth,
                timeout=self.timeout,
            )
        except requests.exceptions.ConnectTimeout:
            return SendOutcome(False, self.name, error=f"Gateway did not respond within {self.timeout:.0f}s — is the phone awake and on the network?")
        except requests.exceptions.ConnectionError as exc:
            return SendOutcome(False, self.name, error=f"Could not reach the gateway at {self.base_url}: {exc.__class__.__name__}")
        except requests.exceptions.RequestException as exc:
            return SendOutcome(False, self.name, error=f"{exc.__class__.__name__}: {exc}")

        if response.status_code == 401:
            return SendOutcome(False, self.name, error="Gateway rejected the credentials (401) — check SMS_GATEWAY_USERNAME / PASSWORD against the app's Local Server screen.")
        if response.status_code >= 400:
            return SendOutcome(False, self.name, error=f"Gateway returned HTTP {response.status_code}: {response.text[:300]}")

        message_id = None
        try:
            payload = response.json()
            if isinstance(payload, dict):
                message_id = payload.get("id") or payload.get("messageId")
        except ValueError:
            # A 2xx with a non-JSON body still means it was accepted.
            pass
        return SendOutcome(True, self.name, provider_message_id=message_id)


def get_sender() -> Sender:
    """Builds the configured sender. Falls back to the simulator — loudly —
    rather than raising, so a half-configured gateway degrades to a working
    demo instead of a 500 in front of a panel."""
    settings = get_settings()
    provider = (settings.sms_provider or "console").strip().lower()

    if provider == "android_gateway":
        if not settings.sms_gateway_url:
            logger.warning("SMS_PROVIDER=android_gateway but SMS_GATEWAY_URL is empty; falling back to the console simulator.")
            return ConsoleSender()
        return AndroidGatewaySender(
            base_url=settings.sms_gateway_url,
            username=settings.sms_gateway_username,
            password=settings.sms_gateway_password,
            timeout=settings.sms_gateway_timeout_seconds,
        )

    if provider != "console":
        logger.warning("Unknown SMS_PROVIDER %r; falling back to the console simulator.", provider)
    return ConsoleSender()
