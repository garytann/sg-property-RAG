from typing import Optional

from pydantic import BaseModel


class Property(BaseModel):
    id: str
    source_url: Optional[str]
    project_name: str
    district: Optional[int]
    address: Optional[str]
    property_type: Optional[str]
    tenure: Optional[str]
    top_year: Optional[int]
    asking_price: Optional[float]
    floor_area_sqft: Optional[float]
    bedrooms: Optional[int]
    bathrooms: Optional[int]
    floor_level: Optional[str]
    monthly_rent_estimate: Optional[float]
    listing_description: Optional[str]
    status: Optional[str]
    created_at: Optional[str]


class PropertyNote(BaseModel):
    id: str
    property_id: str
    note_type: str
    note_text: str
    noted_at: Optional[str]

