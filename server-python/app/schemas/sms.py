"""Request/response shapes for the SMS advisory endpoints (app/routers/sms.py)."""

from pydantic import BaseModel, Field


class SmsRecipient(BaseModel):
    """A farmer the technologist can pick in the compose screen."""

    username: str
    full_name: str
    municipality: str
    phone: str


class SmsSendRequest(BaseModel):
    """Either pick registered farmers, type raw numbers, or both.

    `to_all_farmers` is kept separate from `usernames` so the admin UI can
    offer a one-click "everyone in my municipality" without the client having
    to enumerate the list first — and so the server, not the browser, decides
    who that means.
    """

    body: str = Field(min_length=1, max_length=640)
    usernames: list[str] = Field(default_factory=list)
    phone_numbers: list[str] = Field(default_factory=list)
    to_all_farmers: bool = False


class SmsMessageRecord(BaseModel):
    id: str
    batch_id: str
    recipient_phone: str
    recipient_username: str | None = None
    recipient_name: str | None = None
    body: str
    municipality: str
    sent_by: str
    status: str
    provider: str
    provider_message_id: str | None = None
    error: str | None = None
    created_at: str
    sent_at: str | None = None


class SmsSendResponse(BaseModel):
    batch_id: str
    provider: str
    sent: int
    failed: int
    # Numbers that were rejected before any send was attempted (unparseable,
    # or a picked farmer with no number on file), so the technologist can see
    # the difference between "not attempted" and "attempted and failed".
    skipped: list[str] = Field(default_factory=list)
    messages: list[SmsMessageRecord] = Field(default_factory=list)


class SmsGatewayStatus(BaseModel):
    provider: str
    # True only for a real gateway that answered. Always False in simulation —
    # the simulator has nothing to reach.
    configured: bool
    reachable: bool | None = None
    detail: str
