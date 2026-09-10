from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LguUser(BaseModel):
    username: str
    password: str
    role_level: str
    province: str
    municipality: str
    latitude: float
    longitude: float


class FarmerUser(BaseModel):
    username: str
    password: str
    full_name: str
    province: str
    municipality: str
    latitude: float
    longitude: float


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


class LoginResponse(BaseModel):
    user: LguAccountResponse | FarmerAccountResponse
