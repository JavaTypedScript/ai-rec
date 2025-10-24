from pydantic import BaseModel
from typing import List, Dict, Optional
from models import ProjectStatus, ModelType, FileType

# --- SchemaMapping Schemas ---
class SchemaMappingBase(BaseModel):
    app_schema_key: str
    user_csv_column: str

class SchemaMapping(SchemaMappingBase):
    id: int
    file_id: int
    class Config:
        orm_mode = True

# --- UploadedFile Schemas ---
class UploadedFileBase(BaseModel):
    original_filename: str
    storage_path: str
    file_type: FileType

class UploadedFile(UploadedFileBase):
    id: int
    project_id: int
    schema_mappings: List[SchemaMapping] = []
    class Config:
        orm_mode = True

# --- RecommenderProject Schemas ---
class RecommenderProjectBase(BaseModel):
    project_name: str

class RecommenderProject(RecommenderProjectBase):
    id: int
    status: ProjectStatus
    model_type: Optional[ModelType]
    mlflow_model_name: Optional[str]
    mlflow_model_version: Optional[int]
    uploaded_files: List[UploadedFile] = []
    class Config:
        orm_mode = True

# --- API Response Schemas ---
class RecommendationResponse(BaseModel):
    input_item_title: Optional[str]
    input_user_id: Optional[str]
    model_type: ModelType
    recommendations: List[Dict]

class ProjectItemResponse(BaseModel):
    id: str
    title: str

class ProjectUserResponse(BaseModel):
    id: str