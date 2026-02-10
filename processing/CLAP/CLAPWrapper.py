from .CLAPProcessor import create_embedding
from data.DBRequests import get_vibe_matches_from_db

def get_vibe_matches(wav_path):
    """
    Interface function: Takes a path, gets the vector, and queries the DB.
    """
    # 1. Use the simplified engine to get the embedding
    query_vector = create_embedding(wav_path)

    # 2. Use the DB helper to find matches
    return get_vibe_matches_from_db(query_vector)