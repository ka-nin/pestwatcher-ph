from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LguUser(BaseModel):
    username: str
    password_hash: str
    role_level: str
    province: str
    municipality: str
    latitude: float
    longitude: float
    is_active: bool = True


class FarmerUser(BaseModel):
    username: str
    password_hash: str
    full_name: str
    province: str
    municipality: str
    latitude: float
    longitude: float


class SuperAdminUser(BaseModel):
    username: str
    password_hash: str
    full_name: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LguAccountResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    account_type: Literal["lgu"] = Field(default="lgu", alias="accountType")
    username: str
    role_level: str = Field(alias="roleLevel")
    province: str
    municipality: str
    latitude: float
    longitude: float


class FarmerAccountResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    account_type: Literal["farmer"] = Field(default="farmer", alias="accountType")
    username: str
    full_name: str = Field(alias="fullName")
    province: str
    municipality: str
    latitude: float
    longitude: float


class SuperAdminAccountResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    account_type: Literal["superadmin"] = Field(default="superadmin", alias="accountType")
    username: str
    full_name: str = Field(alias="fullName")


class LoginResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user: LguAccountResponse | FarmerAccountResponse | SuperAdminAccountResponse
    access_token: str = Field(alias="accessToken")
    token_type: Literal["bearer"] = Field(default="bearer", alias="tokenType")


# --- Superadmin-managed LGU account CRUD ---


class LguAccountAdminResponse(BaseModel):
    """Same shape as LguAccountResponse but without the accountType
    discriminator — used in the superadmin's account-management list, not
    the login response."""

    model_config = ConfigDict(populate_by_name=True)

    username: str
    role_level: str = Field(alias="roleLevel")
    province: str
    municipality: str
    latitude: float
    longitude: float
    is_active: bool = Field(alias="isActive")


class CreateLguUserRequest(BaseModel):
    username: str
    password: str
    role_level: str = Field(default="LGU_Tech", alias="roleLevel")
    province: str
    municipality: str
    latitude: float
    longitude: float

    model_config = ConfigDict(populate_by_name=True)


class UpdateLguUserRequest(BaseModel):
    """All fields optional — only supplied fields are changed. Password, if
    given, replaces the stored hash."""

    model_config = ConfigDict(populate_by_name=True)

    password: str | None = None
    role_level: str | None = Field(default=None, alias="roleLevel")
    province: str | None = None
    municipality: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_active: bool | None = Field(default=None, alias="isActive")
