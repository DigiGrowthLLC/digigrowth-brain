from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Contact(BaseModel):
    id: str
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
    email: Optional[str] = None
    grade: Optional[str] = None
    opener: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    newsletter: Optional[bool] = None


class NoteAdd(BaseModel):
    text: str


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
    "new", "dialer-lead", "sms-handoff",
    "appointment-booked", "not-interested", "send-info", "voicemail"
}

DISPOSITION_TO_STATUS = {
    "Appointment Booked": "appointment-booked",
    "Follow Up": "dialer-lead",
    "Not Interested": "not-interested",
    "Send Info": "send-info",
    "No Answer": "dialer-lead",
    "SMS Handoff": "sms-handoff",
    "Voicemail": "voicemail",
}
