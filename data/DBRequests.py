
from data.db_manager import find_matches, find_vibe_matches

def get_snippet_matches_from_db(query_hashes):
    return find_matches(query_hashes)


def get_vibe_matches_from_db(query_vector):
    return {"vibe_matches": find_vibe_matches(query_vector)} 