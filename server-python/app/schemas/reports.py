from pydantic import BaseModel


class ReportRequest(BaseModel):
    username: str
    pest_type: str
    severity: str
    province: str
    region: str
    date_spotted: str
    notes: str = ""


class ReportResponse(BaseModel):
    id: str
    submitted_at: str


class ReportRecord(ReportRequest):
    id: str
    submitted_at: str
