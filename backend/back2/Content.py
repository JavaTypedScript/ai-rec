import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

class ContentBasedRecommender:
    """Recommends items similar to a given item based on its content."""
    def __init__(self):
        self.cosine_sim = None
        self.indices = None
        self.df = None
        self.schema_map = {}

    def fit(self, df, schema_map):
        """
        Builds the TF-IDF and Cosine Similarity matrix from item features.

        Args:
            df (pd.DataFrame): The standardized dataframe.
            schema_map (dict): A dict with 'item_id' and 'feature_cols' keys.
        """
        self.df = df
        self.schema_map = schema_map
        content_feature_columns = schema_map.get('feature_cols', [])

        # Create a "soup" of all content features in a single string
        df['soup'] = df[content_feature_columns].fillna('').astype(str).agg(' '.join, axis=1)

        # Use TF-IDF to convert the text soup into a matrix of feature vectors
        tfidf = TfidfVectorizer(stop_words='english')
        tfidf_matrix = tfidf.fit_transform(df['soup'])

        # Calculate the cosine similarity between all items
        self.cosine_sim = linear_kernel(tfidf_matrix, tfidf_matrix)

        # Create a mapping from item_id to dataframe index for quick lookups
        # Create a mapping from item_title to dataframe index for quick lookups
        self.indices = pd.Series(df.index, index=df[schema_map['item_title']]).drop_duplicates()
        print("✅ Content-Based model fitted.")

    def recommend(self, item_id, n=10):
        """
        Gets the top n similar items for a given item_id.
        """
        if item_id not in self.indices:
            print(f"Item '{item_id}' not found in Content model indices.")
            return []

        # Get the index of the item that matches the ID
        idx = self.indices[item_id]

        # Get the pairwise similarity scores of all items with that item
        sim_scores = list(enumerate(self.cosine_sim[idx]))

        # Sort the items based on the similarity scores
        sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)

        # Get the scores of the n most similar items (excluding the item itself)
        sim_scores = sim_scores[1:n+1]

        # Get the item indices
        item_indices = [i[0] for i in sim_scores]

        # Return the top n most similar item IDs
        return self.df[self.schema_map['item_id']].iloc[item_indices].tolist()