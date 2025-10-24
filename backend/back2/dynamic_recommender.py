import mlflow
import mlflow.pyfunc
import pandas as pd
import numpy as np
import pickle
import json
import os

# --- Import your recommender classes ---
from Content import ContentBasedRecommender
from Collaborative import CollaborativeFilteringRecommender
from Hybrid import HybridRecommender

class MLflowRecommenderWrapper(mlflow.pyfunc.PythonModel):
    """
    This is the new MLflow wrapper.
    It loads the specific artifacts for your Content, Collaborative,
    or Hybrid models and routes prediction requests.
    """
    
    def load_context(self, context):
        """
        This method is called by MLflow when loading the model.
        It loads all the artifacts saved during training.
        """
        print("Loading context for MLflowRecommenderWrapper...")
        
        # 1. Load config to see what model to build
        with open(context.artifacts["model_type_config"], 'r') as f:
            config = json.load(f)
        self.model_type = config["model_type"]
        self.schemas = config["schemas"]
        print(f"Loading model of type: {self.model_type}")

        # 2. Always load content data if it exists (for title lookups)
        self.content_df = pd.DataFrame()
        # --- UPDATED LOGIC ---
        # Get content schema if it exists in the config
        self.content_schema = self.schemas.get("content", {}) 
        
        # Check if cb_data artifact exists AND we have a schema for it
        if "cb_data" in context.artifacts and self.content_schema:
            self.content_df = pd.read_csv(context.artifacts["cb_data"])
            # Ensure the ID column is a string for matching
            if 'item_id' in self.content_schema:
                 self.content_df[self.content_schema['item_id']] = self.content_df[self.content_schema['item_id']].astype(str)
            print("Loaded content data for title lookups.")
        # --- END OF UPDATED LOGIC ---

        # 3. Load Content-Based Model components
        if self.model_type in ["content", "hybrid"]:
            print("Loading Content model artifacts...")
            self.content_model = ContentBasedRecommender()
            self.content_model.df = self.content_df
            with open(context.artifacts["cb_cosine_sim"], 'rb') as f:
                self.content_model.cosine_sim = pickle.load(f)
            with open(context.artifacts["cb_indices"], 'rb') as f:
                self.content_model.indices = pickle.load(f)
            self.content_model.schema_map = self.content_schema

        # 4. Load Collaborative Filtering Model components
        if self.model_type in ["collaborative", "hybrid"]:
            print("Loading Collaborative model artifacts...")
            self.collab_model = CollaborativeFilteringRecommender()
            self.collab_model.user_features = np.load(context.artifacts["cf_user_features"])
            self.collab_model.item_features = np.load(context.artifacts["cf_item_features"])
            with open(context.artifacts["cf_user_means"], 'rb') as f:
                self.collab_model.user_means = pickle.load(f)
            with open(context.artifacts["cf_item_ids"], 'rb') as f:
                self.collab_model.item_ids = pickle.load(f)
            with open(context.artifacts["cf_user_ids"], 'rb') as f:
                self.collab_model.user_ids = pickle.load(f)
            with open(context.artifacts["cf_pivot"], 'rb') as f:
                self.collab_model.original_ratings_pivot = pickle.load(f)
        
        # 5. Instantiate the final model (Hybrid or one of the components)
        if self.model_type == "hybrid":
            self.model = HybridRecommender(self.content_model, self.collab_model)
        elif self.model_type == "content":
            self.model = self.content_model
        elif self.model_type == "collaborative":
            self.model = self.collab_model
            
        print("✅ Model loading complete.")

    def _format_recs(self, raw_ids: list) -> list:
        """Helper to turn a list of IDs into a list of dicts with titles."""
        
        # This check will now pass if content_df and content_schema were loaded
        if self.content_df.empty or not self.content_schema:
            print("Warning: Content data or schema not found. Falling back to IDs.")
            return [{"item_id": id} for id in raw_ids]
        
        try:
            id_col = self.content_schema['item_id']
            title_col = self.content_schema['item_title']
            
            # --- UPDATED LOGIC ---
            # Ensure all raw IDs are strings for matching
            raw_ids_str = [str(rid) for rid in raw_ids]
            
            # Filter the dataframe to only include recommended IDs
            results_df = self.content_df[self.content_df[id_col].isin(raw_ids_str)]
            
            # Use .set_index().loc[] to maintain the order from raw_ids
            # This handles missing IDs gracefully by producing NaNs
            ordered_results = results_df.set_index(id_col).loc[raw_ids_str].reset_index()
            
            # Handle potential duplicates if raw_ids had them
            ordered_results = ordered_results.drop_duplicates(subset=[id_col])
            
            return ordered_results[[id_col, title_col]].to_dict('records')
        except Exception as e:
            print(f"Error formatting recommendations: {e}. Falling back to IDs.")
            # Fallback for any error (e.g., KeyError if title_col is missing)
            return [{"item_id": id} for id in raw_ids]


    def predict(self, context, model_input: pd.DataFrame):
        """
        This is the main prediction entry point for MLflow.
        """
        results = []
        for _, row in model_input.iterrows():
            try:
                user_id = row.get('user_id')
                item_title = row.get('item_title')
                n = int(row.get('n', 10))
                
                raw_ids = []
                if self.model_type == "content":
                    if not item_title: raise ValueError("item_title is required for content model.")
                    raw_ids = self.model.recommend(item_title, n)
                elif self.model_type == "collaborative":
                    if not user_id: raise ValueError("user_id is required for collaborative model.")
                    raw_ids = self.model.recommend(str(user_id), n) # Ensure user_id is string
                elif self.model_type == "hybrid":
                    if not user_id: raise ValueError("user_id is required for hybrid model.")
                    if not item_title: raise ValueError("item_title is required for hybrid model.")
                    raw_ids = self.model.recommend(str(user_id), item_title, n)
                
                # Format IDs into final JSON
                recommendations = self._format_recs(raw_ids)
                
                results.append({
                    "input_item_title": item_title,
                    "input_user_id": user_id,
                    "model_type": self.model_type,
                    "recommendations": recommendations,
                    "error": None
                })
            except Exception as e:
                results.append({
                    "input_item_title": item_title,
                    "input_user_id": user_id,
                    "model_type": self.model_type,
                    "recommendations": None,
                    "error": str(e)
                })
        
        return pd.Series([json.dumps(r) for r in results])