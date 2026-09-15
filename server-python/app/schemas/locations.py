from pydantic import BaseModel


class MunicipalityOption(BaseModel):
    municipality: str
    province: str
    latitude: float
    longitude: float
