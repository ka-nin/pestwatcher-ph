"""SQLAlchemy ORM tables. These mirror the Pydantic schemas in
app/schemas/auth.py and app/schemas/reports.py — the data layer
(app/data/*.py) converts between the two so routers keep working against
the same Pydantic shapes as before this migration.
"""

from sqlalchemy import Boolean, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class MunicipalityDB(Base):
    """Canonical municipality/coordinate registry. Previously the app had no
    dedicated location table — weather-coordinate lookups and the mobile
    app's municipality picker both derived their list from whichever towns
    happened to have an LGU account, so a municipality with no LGU account
    yet was invisible to both. Seeded at startup from the LGU and farmer
    seed data (see app/data/municipalities.py) and grown automatically as
    superadmins add LGU accounts for new municipalities.
    """

    __tablename__ = "municipalities"

    municipality: Mapped[str] = mapped_column(String, primary_key=True)
    province: Mapped[str] = mapped_column(String, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)


class LguUserDB(Base):
    __tablename__ = "lgu_users"

    username: Mapped[str] = mapped_column(String, primary_key=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role_level: Mapped[str] = mapped_column(String, nullable=False)
    province: Mapped[str] = mapped_column(String, nullable=False)
    municipality: Mapped[str] = mapped_column(String, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class FarmerUserDB(Base):
    __tablename__ = "farmer_users"

    username: Mapped[str] = mapped_column(String, primary_key=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    province: Mapped[str] = mapped_column(String, nullable=False)
    municipality: Mapped[str] = mapped_column(String, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)


class SuperAdminDB(Base):
    __tablename__ = "superadmins"

    username: Mapped[str] = mapped_column(String, primary_key=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)


class ReportDB(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str] = mapped_column(String, nullable=False)
    pest_type: Mapped[str] = mapped_column(String, nullable=False)
    # Normalized BPH/RSB key (see app/decision/pest_matching.py), derived
    # server-side from pest_type at submission time. Nullable because a
    # farmer can pick "Others / Hindi Sigurado", which matches no ETL pest.
    # Existing rows from before this column existed are backfilled once at
    # startup — see app/data/reports_store.py:backfill_pest_codes().
    pest_code: Mapped[str | None] = mapped_column(String, nullable=True)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    province: Mapped[str] = mapped_column(String, nullable=False)
    municipality: Mapped[str] = mapped_column(String, nullable=False)
    crop_growth_stage: Mapped[str] = mapped_column(String, nullable=False)
    date_spotted: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str] = mapped_column(String, nullable=False, default="")
    area_affected: Mapped[float | None] = mapped_column(Float, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    submitted_at: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    verified_by: Mapped[str | None] = mapped_column(String, nullable=True)
    verified_at: Mapped[str | None] = mapped_column(String, nullable=True)
    verified_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String, nullable=True)
    ai_pest_detected: Mapped[str | None] = mapped_column(String, nullable=True)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Soft delete (audit trail): a deleted report keeps its row, but is hidden
    # from the forecast, the farmers' feed and the normal review tabs — see
    # app/data/reports_store.py. Added after the table first existed, so
    # app/db.py:init_db() also adds these columns to an already-created table.
    deleted_at: Mapped[str | None] = mapped_column(String, nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(String, nullable=True)
