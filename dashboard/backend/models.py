from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Contact(BaseModel):
    id: Optional[str] = None
    business: Optional[str] = None
    owner: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    grade: Optional[str] = None
    opener: Optional[str] = None
    status: str = "new"
    call_attempts: int = 0
    last_called_at: Optional[datetime] = None
    last_disposition: Optional[str] = None
    notes: Optional[str] = None
    newsletter: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ContactUpdate(BaseModel):
    business: Optional[str] = None
    owner: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    grade: Optional[str] = None
    opener: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    newsletter: Optional[bool] = None
    client_id: Optional[int] = None


class BulkAction(BaseModel):
    ids: Optional[list[str]] = None      # specific contact IDs
    select_all: bool = False             # if True, applies to all matching filter
    filter_status: Optional[str] = None  # used when select_all=True
    filter_search: Optional[str] = None  # used when select_all=True
    action: str                          # "delete" | "add_tag" | "remove_tag" | "set_status"
    value: Optional[str] = None          # tag name or status value


class NoteAdd(BaseModel):
    text: str


class TagCreate(BaseModel):
    name: str
    color: Optional[str] = None


class TagUpdate(BaseModel):
    color: Optional[str] = None


class TagAssign(BaseModel):
    tag: str


class CallLog(BaseModel):
    id: int
    contact_id: str
    started_at: datetime
    duration_sec: Optional[int] = None
    disposition: Optional[str] = None
    notes: Optional[str] = None


class SmsMessage(BaseModel):
    id: int
    contact_id: Optional[str] = None
    phone: str
    direction: str
    body: str
    sent_at: datetime


class DispositionUpdate(BaseModel):
    disposition: str
    duration_sec: Optional[int] = None
    notes: Optional[str] = None


VALID_STATUSES = {
    "new", "dialer-lead", "sms-handoff", "email-handoff",
    "appointment-booked", "not-interested", "send-info", "voicemail",
    "gatekeeper-blocked", "manual-followup",
}


class CustomStatusCreate(BaseModel):
    key: str
    label: str
    color: Optional[str] = None


class CustomStatusUpdate(BaseModel):
    label: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None

DISPOSITION_TO_STATUS = {
    "Appointment Booked": "appointment-booked",
    "Follow Up 30 Day":   "dialer-lead",
    "Follow Up 90 Day":   "dialer-lead",
    "Not Interested":     "not-interested",
    "Send Info":          "send-info",
    "No Answer":          "dialer-lead",
    "SMS Handoff":        "sms-handoff",
    # Gatekeeper redirected outreach to email instead of a phone number.
    "Email Handoff":      "email-handoff",
    # Voicemail counts as a dial + 6h cooldown, then cycles back into the
    # queue (dialer/queue eligibility query includes 'voicemail' status).
    "Voicemail":          "voicemail",
    # Gatekeeper is terminal — never re-enters the dialer queue, unlike a
    # plain no-answer/voicemail. Distinct from "not-interested" for reporting.
    "Gatekeeper":         "gatekeeper-blocked",
    # Manual follow-up is terminal from the dialer's perspective — not in
    # _ELIGIBLE_WHERE's status list, so it never gets auto re-dialed. Dylan
    # follows up himself rather than the system re-queueing it.
    "Follow Up (Manual)": "manual-followup",
}


class ClientCreate(BaseModel):
    name: str
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    contact_id: Optional[str] = None
    is_test: bool = False
    calendly_url: Optional[str] = None
    booking_notification_enabled: bool = True


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    is_test: Optional[bool] = None
    calendly_url: Optional[str] = None
    booking_notification_enabled: Optional[bool] = None


class ClientLinkContact(BaseModel):
    contact_id: Optional[str] = None


class OnboardingVideoCreate(BaseModel):
    title: str
    description: Optional[str] = None
    embed_url: str
    sort_order: int = 0


class OnboardingVideoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    embed_url: Optional[str] = None
    sort_order: Optional[int] = None
    active: Optional[bool] = None


class OnboardingSectionSave(BaseModel):
    answers: dict
    completed: bool = False


class ActionItemCreate(BaseModel):
    title: str
    description: Optional[str] = None
    link_tab: Optional[str] = None
    link_url: Optional[str] = None
    sort_order: int = 0


class ActionItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    link_tab: Optional[str] = None
    link_url: Optional[str] = None
    sort_order: Optional[int] = None
    active: Optional[bool] = None


class ActionItemComplete(BaseModel):
    completed: bool


class LaunchChecklistItemCreate(BaseModel):
    title: str
    description: Optional[str] = None
    phase: str = "prelaunch"
    sort_order: int = 0


class LaunchChecklistItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    phase: Optional[str] = None
    sort_order: Optional[int] = None
    active: Optional[bool] = None


class LaunchChecklistStatusUpdate(BaseModel):
    completed: bool


ONBOARDING_SECTIONS = [
    "practice_snapshot",
    "ideal_patient",
    "offer_economics",
    "differentiation_voice",
    "current_marketing",
    "ops",
]
