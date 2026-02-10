from .FFTProcessor import fft_engine
from data.DBRequests import get_snippet_matches_from_db


def get_snippet_matches(wav_path):
    """
    Interface: Orchestrates the extraction and DB lookup.
    """
    # 1. Extract peaks
    peaks = fft_engine.get_peaks(wav_path)

    # 2. Generate fingerprint hashes
    query_hashes = fft_engine.hash_peaks(peaks)
    # 3. Query the relational database (SQL)
    return get_snippet_matches_from_db(query_hashes)