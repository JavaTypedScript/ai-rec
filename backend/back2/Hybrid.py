import pandas as pd
class HybridRecommender:
    """
    Combines recommendations from content-based and collaborative models
    to provide a more robust and diverse recommendation list.
    """
    def __init__(self, content_model, collab_model):
        self.content_model = content_model
        self.collab_model = collab_model
        print("🤖 HybridRecommender initialized.")

    def recommend(self, user_id, item_id_for_content, n=10):
        """
        Generates a hybrid list of recommendations.
        """
        # 1. Get content-based recommendations
        content_recs = self.content_model.recommend(item_id_for_content, n)

        # 2. Get collaborative filtering recommendations
        collab_recs = self.collab_model.recommend(user_id, n)

        # 3. Combine the lists (prioritizing content, filling with collaborative)
        combined_recs = list(dict.fromkeys(content_recs + collab_recs))

        # 4. Return the final list
        return combined_recs[:n]