import pandas as pd
import aiofiles
import os
import uuid
import json
import asyncio
import mlflow
import pickle
import numpy as np  # <-- Add this import
import tempfile
from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
from typing import List, Optional, Dict

import models
import schemas
import database

# --- Import your classes ---
from Content import ContentBasedRecommender
from Collaborative import CollaborativeFilteringRecommender
# --- Import the MLflow wrapper ---
from dynamic_recommender import MLflowRecommenderWrapper

# --- App Setup & MLflow Configuration (Unchanged) ---
os.makedirs("user_uploads", exist_ok=True)
os.makedirs("mlflow_artifacts", exist_ok=True)

MLFLOW_TRACKING_DB = "sqlite:///mlflow.db"
MLFLOW_ARTIFACT_LOCATION = "./mlflow_artifacts"
os.environ["MLFLOW_TRACKING_URI"] = MLFLOW_TRACKING_DB
mlflow.set_tracking_uri(MLFLOW_TRACKING_DB)

# try:
#     mlflow.create_experiment("recommender_projects", artifact_location=MLFLOW_ARTIFACT_LOCATION)
# except mlflow.exceptions.RestException:
#     pass 
# mlflow.set_experiment("recommender_projects")
# --- CONFIGURE MLFLOW ---
# ... (other lines) ...

# Check if the experiment already exists
experiment = mlflow.get_experiment_by_name("recommender_projects")

# If it doesn't exist, create it
if not experiment:
    print("Creating new MLflow experiment: recommender_projects")
    mlflow.create_experiment(
        "recommender_projects", 
        artifact_location=MLFLOW_ARTIFACT_LOCATION
    )

# Set the experiment as the active one for all runs
mlflow.set_experiment("recommender_projects")
# --- END MLFLOW CONFIG ---
# --- END MLFLOW CONFIG ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Server starting...")
    database.create_db_and_tables() 
    print("Database tables created.")
    yield
    print("Server shutting down.")

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000","http://localhost:8000","http://localhost:5000","http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Helper function (Unchanged) ---
async def save_file_and_schema(
    db: Session,
    project_id: int,
    file: UploadFile,
    schema_json: str,
    file_type: models.FileType
) -> models.UploadedFile:
    
    storage_filename = f"{uuid.uuid4()}_{file.filename}"
    storage_path = os.path.join("user_uploads", storage_filename)
    
    async with aiofiles.open(storage_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
        
    db_file = models.UploadedFile(
        project_id=project_id,
        original_filename=file.filename,
        storage_path=storage_path,
        file_type=file_type
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    
    try:
        schema_map = json.loads(schema_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail=f"Invalid schema JSON for {file_type} file.")
    
    for app_key, user_col in schema_map.items():
        if isinstance(user_col, list): 
            for col in user_col:
                db_schema = models.SchemaMapping(
                    app_schema_key='feature_col', 
                    user_csv_column=col,
                    file_id=db_file.id
                )
                db.add(db_schema)
        else:
             db_schema = models.SchemaMapping(
                app_schema_key=app_key,
                user_csv_column=user_col,
                file_id=db_file.id
            )
             db.add(db_schema)
            
    db.commit()
    return db_file

# --- Background Task for Model Training (Updated) ---

async def process_project(project_id: int, db: Session):
    """
    Background task to train models from Content.py and Collaborative.py
    and register them with MLflow.
    """
    print(f"[Task {project_id}]: Started processing...")
    db_project = None
    try:
        db_project = db.query(models.RecommenderProject).filter(models.RecommenderProject.id == project_id).first()
        if not db_project:
            raise Exception("Project not found in DB.")

        db_project.status = models.ProjectStatus.PROCESSING
        db.commit()

        # --- Load files and schemas (Unchanged) ---
        files = db_project.uploaded_files
        content_file = next((f for f in files if f.file_type == models.FileType.CONTENT), None)
        interaction_file = next((f for f in files if f.file_type == models.FileType.INTERACTION), None)

        df_content, df_interaction = None, None
        content_schema, interaction_schema = {}, {}
        all_schemas_map = {} 
        
        if content_file:
            df_content = pd.read_csv(content_file.storage_path)
            content_schema = {s.app_schema_key: s.user_csv_column for s in content_file.schema_mappings if s.app_schema_key != 'feature_col'}
            content_schema['feature_cols'] = [s.user_csv_column for s in content_file.schema_mappings if s.app_schema_key == 'feature_col']
            all_schemas_map['content'] = content_schema

        if interaction_file:
            df_interaction = pd.read_csv(interaction_file.storage_path)
            # Ensure user_id and item_id are strings for consistency
            schema_map = {s.app_schema_key: s.user_csv_column for s in interaction_file.schema_mappings}
            df_interaction[schema_map['user_id']] = df_interaction[schema_map['user_id']].astype(str)
            df_interaction[schema_map['item_id']] = df_interaction[schema_map['item_id']].astype(str)
            interaction_schema = schema_map
            all_schemas_map['interaction'] = interaction_schema
            
        # Ensure content item_ids are strings if they exist
        if df_content is not None and 'item_id' in content_schema:
            df_content[content_schema['item_id']] = df_content[content_schema['item_id']].astype(str)


        model_type = db_project.model_type
        print(f"[Task {project_id}]: Building model of type: {model_type}")

        # --- Artifacts will be saved here ---
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts = {}
            
            # --- Save model_type config (Unchanged) ---
            model_type_config_path = os.path.join(tmpdir, "model_type.json")
            with open(model_type_config_path, 'w') as f:
                json.dump({"model_type": model_type, "schemas": all_schemas_map}, f)
            artifacts["model_type_config"] = model_type_config_path
            
            # --- Train Content-Based Model (Updated) ---
            if model_type in [models.ModelType.CONTENT, models.ModelType.HYBRID]:
                print(f"[Task {project_id}]: Fitting ContentBasedRecommender...")
                cb_recommender = ContentBasedRecommender()
                cb_recommender.fit(df_content, content_schema)
                
                # Define and save CB artifacts
                artifacts["cb_cosine_sim"] = os.path.join(tmpdir, "cb_cosine_sim.pkl")
                artifacts["cb_indices"] = os.path.join(tmpdir, "cb_indices.pkl")
                artifacts["cb_data"] = os.path.join(tmpdir, "cb_data.csv")
                
                with open(artifacts["cb_cosine_sim"], 'wb') as f: pickle.dump(cb_recommender.cosine_sim, f)
                with open(artifacts["cb_indices"], 'wb') as f: pickle.dump(cb_recommender.indices, f)
                cb_recommender.df.to_csv(artifacts["cb_data"], index=False)
                print(f"[Task {project_id}]: Saved Content model artifacts.")

            # --- Train Collaborative Filtering Model (Updated) ---
            if model_type in [models.ModelType.COLLABORATIVE, models.ModelType.HYBRID]:
                print(f"[Task {project_id}]: Fitting CollaborativeFilteringRecommender...")
                cf_recommender = CollaborativeFilteringRecommender(n_components=50)
                cf_recommender.fit(df_interaction, interaction_schema)
                
                # Define and save CF artifacts
                artifacts["cf_user_features"] = os.path.join(tmpdir, "cf_user_features.npy")
                artifacts["cf_item_features"] = os.path.join(tmpdir, "cf_item_features.npy")
                artifacts["cf_user_means"] = os.path.join(tmpdir, "cf_user_means.pkl")
                artifacts["cf_item_ids"] = os.path.join(tmpdir, "cf_item_ids.pkl")
                artifacts["cf_user_ids"] = os.path.join(tmpdir, "cf_user_ids.pkl")
                artifacts["cf_pivot"] = os.path.join(tmpdir, "cf_pivot.pkl")

                np.save(artifacts["cf_user_features"], cf_recommender.user_features)
                np.save(artifacts["cf_item_features"], cf_recommender.item_features)
                with open(artifacts["cf_user_means"], 'wb') as f: pickle.dump(cf_recommender.user_means, f)
                with open(artifacts["cf_item_ids"], 'wb') as f: pickle.dump(cf_recommender.item_ids, f)
                with open(artifacts["cf_user_ids"], 'wb') as f: pickle.dump(cf_recommender.user_ids, f)
                with open(artifacts["cf_pivot"], 'wb') as f: pickle.dump(cf_recommender.original_ratings_pivot, f)
                print(f"[Task {project_id}]: Saved Collaborative model artifacts.")

            # --- Save content data for pure collaborative model (for lookups) ---
            if model_type == models.ModelType.COLLABORATIVE and df_content is not None:
                 artifacts["cb_data"] = os.path.join(tmpdir, "cb_data.csv")
                 df_content.to_csv(artifacts["cb_data"], index=False)
                 print(f"[Task {project_id}]: Saved Content data for Collaborative title lookups.")


            # --- Save and Register with MLflow (Unchanged) ---
# --- Save and Register with MLflow (Corrected) ---
            with mlflow.start_run() as run:
                print(f"[Task {project_id}]: MLflow run started: {run.info.run_id}")
                mlflow.log_param("model_type", model_type)
                
                model_name = f"project-{project_id}-recommender"
                artifact_path = "recommender_model" # This is the name of the artifact folder *inside* the run
                
                # Use log_model to save AND log the model as an artifact
                model_info = mlflow.pyfunc.log_model(
                    artifact_path=artifact_path,
                    python_model=MLflowRecommenderWrapper(),
                    artifacts=artifacts,
                    code_paths=["dynamic_recommender.py", "Content.py", "Collaborative.py", "Hybrid.py"]
                )
                
                # Register the model using the valid URI returned by log_model
                registered_model = mlflow.register_model(
                    model_uri=model_info.model_uri, # model_info.model_uri is the correct 'runs:/...' path
                    name=model_name
                )
                model_version = registered_model.version
                print(f"[Task {project_id}]: Model registered as '{model_name}' v{model_version}")

        # --- Update Project in DB (Unchanged) ---
        db_project.mlflow_model_name = model_name
        db_project.mlflow_model_version = model_version
        db_project.status = models.ProjectStatus.READY
        db.commit()
        print(f"[Task {project_id}]: Processing complete.")

    except Exception as e:
        print(f"[Task {project_id}]: ERROR processing project. {e}")
        if db_project:
            db_project.status = models.ProjectStatus.ERROR
            db.commit()
    finally:
        db.close()

# --- All API Endpoints (Unchanged) ---
# The /create-project, /projects, /project/{id}/status,
# /project/{id}/items, /project/{id}/users, and
# /project/{id}/recommendations endpoints are all
# IDENTICAL to the previous version. I am omitting them
# here for brevity, but you should use the exact code
# from the previous response for them.
#
# ... (all endpoints from saas_api.py go here) ...
#

# --- PASTE ALL OTHER ENDPOINTS FROM THE PREVIOUS RESPONSE BELOW ---

@app.post("/create-project/", response_model=schemas.RecommenderProject)
async def create_project(
    background_tasks: BackgroundTasks,
    project_name: str = Form(...),
    content_file: UploadFile = File(None),
    content_schema_json: str = Form(None),
    interaction_file: UploadFile = File(None),
    interaction_schema_json: str = Form(None),
    db: Session = Depends(database.get_db)
):
    if not content_file and not interaction_file:
        raise HTTPException(status_code=400, detail="At least one file (content or interaction) must be provided.")
    if content_file and not content_schema_json:
        raise HTTPException(status_code=400, detail="Content schema is required if content file is provided.")
    if interaction_file and not interaction_schema_json:
        raise HTTPException(status_code=400, detail="Interaction schema is required if interaction file is provided.")

    model_type = None
    if content_file and interaction_file:
        model_type = models.ModelType.HYBRID
    elif content_file:
        model_type = models.ModelType.CONTENT
    elif interaction_file:
        model_type = models.ModelType.COLLABORATIVE

    db_project = models.RecommenderProject(
        project_name=project_name,
        status=models.ProjectStatus.PENDING,
        model_type=model_type
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    
    try:
        if content_file:
            await save_file_and_schema(db, db_project.id, content_file, content_schema_json, models.FileType.CONTENT)
        if interaction_file:
            await save_file_and_schema(db, db_project.id, interaction_file, interaction_schema_json, models.FileType.INTERACTION)
    except Exception as e:
        db_project.status = models.ProjectStatus.ERROR
        db.commit()
        raise HTTPException(status_code=500, detail=f"Error processing files: {e}")

    background_db = database.SessionLocal()
    background_tasks.add_task(process_project, db_project.id, background_db)
    
    db.refresh(db_project)
    return db_project


@app.get("/projects/", response_model=List[schemas.RecommenderProject])
def get_projects(db: Session = Depends(database.get_db)):
    projects = db.query(models.RecommenderProject).all()
    return projects

@app.get("/project/{project_id}/status", response_model=schemas.RecommenderProject)
def get_project_status(project_id: int, db: Session = Depends(database.get_db)):
    db_project = db.query(models.RecommenderProject).filter(models.RecommenderProject.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return db_project

def get_project_data(project_id: int, db: Session, file_type: models.FileType):
    db_project = db.query(models.RecommenderProject).filter(models.RecommenderProject.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found.")
    if db_project.status != models.ProjectStatus.READY:
        raise HTTPException(status_code=400, detail="Project is not ready.")
    
    file = next((f for f in db_project.uploaded_files if f.file_type == file_type), None)
    if not file:
        raise HTTPException(status_code=404, detail=f"{file_type} file not found for this project.")
        
    df = pd.read_csv(file.storage_path)
    schema = {s.app_schema_key: s.user_csv_column for s in file.schema_mappings}
    return df, schema

@app.get("/project/{project_id}/items", response_model=List[schemas.ProjectItemResponse])
def get_project_items(project_id: int, db: Session = Depends(database.get_db)):
    try:
        df, schema = get_project_data(project_id, db, models.FileType.CONTENT)
        id_col, title_col = schema['item_id'], schema['item_title']
        # Ensure IDs are strings
        df[id_col] = df[id_col].astype(str)
        items = df[[id_col, title_col]].drop_duplicates().to_dict('records')
        return [{"id": item[id_col], "title": str(item[title_col])} for item in items]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading items: {e}")

@app.get("/project/{project_id}/users", response_model=List[schemas.ProjectUserResponse])
def get_project_users(project_id: int, db: Session = Depends(database.get_db)):
    try:
        df, schema = get_project_data(project_id, db, models.FileType.INTERACTION)
        user_col = schema['user_id']
        users = df[user_col].drop_duplicates().astype(str).tolist()
        return [{"id": user} for user in users]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading users: {e}")


@app.get("/project/{project_id}/recommendations", response_model=schemas.RecommendationResponse)
def get_recommendations(
    project_id: int,
    user_id: Optional[str] = None,
    item_title: Optional[str] = None,
    n: int = 10,
    db: Session = Depends(database.get_db)
):
    db_project = db.query(models.RecommenderProject).filter(models.RecommenderProject.id == project_id).first()
    
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found.")
    if db_project.status != models.ProjectStatus.READY:
        raise HTTPException(status_code=400, detail=f"Project status is {db_project.status}.")
    if not db_project.mlflow_model_name:
         raise HTTPException(status_code=404, detail="Model not found in registry.")

    model_type = db_project.model_type
    if model_type == models.ModelType.CONTENT and not item_title:
        raise HTTPException(status_code=400, detail="item_title is required for this content-based model.")
    if model_type == models.ModelType.COLLABORATIVE and not user_id:
        raise HTTPException(status_code=400, detail="user_id is required for this collaborative model.")
    if model_type == models.ModelType.HYBRID and (not user_id or not item_title):
        raise HTTPException(status_code=400, detail="user_id and item_title are required for this hybrid model.")

    try:
        model_uri = f"models:/{db_project.mlflow_model_name}/{db_project.mlflow_model_version}"
        print(f"Loading model from URI: {model_uri}")
        model = mlflow.pyfunc.load_model(model_uri)
        
        model_input = pd.DataFrame([{"user_id": user_id, "item_title": item_title, "n": n}])
        
        result_json = model.predict(model_input)[0]
        result = json.loads(result_json)
        
        if result["error"]:
            raise ValueError(result["error"])
            
        return schemas.RecommendationResponse(
            input_item_title=item_title,
            input_user_id=user_id,
            model_type=model_type,
            recommendations=result["recommendations"]
        )
        
    except ValueError as e: 
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"Error loading model or predicting: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating recommendations: {e}")