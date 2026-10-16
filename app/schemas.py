from datetime import datetime
from pydantic import BaseModel, Field
class DeviceRegister(BaseModel):
    device_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._:-]+$")
    name: str = Field(default="Demo device", min_length=1, max_length=120)
class ImageOut(BaseModel):
    id: int; device_id: str; original_filename: str; stored_filename: str; image_format: str; mime_type: str; file_size: int; width: int; height: int; uploaded_at: datetime
    class Config: from_attributes = True
