from datetime import date, datetime

from pydantic import BaseModel


# --- Plan definitions ---

PLAN_LIMITS = {
    "trial": {
        "live_hours": 5,
        "products": 20,
        "scripts_per_month": 10,
        "dh_videos": 0,
        "voice_clones": 0,
        "team_seats": 1,
    },
    "starter": {
        "live_hours": 30,
        "products": 100,
        "scripts_per_month": 50,
        "dh_videos": 5,
        "voice_clones": 1,
        "team_seats": 3,
    },
    "pro": {
        "live_hours": -1,  # unlimited
        "products": 500,
        "scripts_per_month": -1,
        "dh_videos": 20,
        "voice_clones": 3,
        "team_seats": 10,
    },
    "enterprise": {
        "live_hours": -1,
        "products": -1,
        "scripts_per_month": -1,
        "dh_videos": -1,
        "voice_clones": -1,
        "team_seats": -1,
    },
}


# --- Responses ---


class SubscriptionResponse(BaseModel):
    id: int
    shop_id: int
    plan: str
    status: str
    provider: str
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    trial_start: datetime | None
    trial_end: datetime | None
    amount: float | None
    currency: str
    created_at: datetime

    model_config = {"from_attributes": True}


class InvoiceResponse(BaseModel):
    id: int
    invoice_number: str
    amount: float
    currency: str
    status: str
    pdf_url: str | None
    issued_at: datetime
    due_at: datetime | None
    paid_at: datetime | None

    model_config = {"from_attributes": True}


class UsageMeter(BaseModel):
    resource_type: str
    used: float
    limit: int  # -1 = unlimited
    unit: str


class UsageSummaryResponse(BaseModel):
    billing_period: date
    meters: list[UsageMeter]


class PlanLimitsResponse(BaseModel):
    plan: str
    limits: dict[str, int]
