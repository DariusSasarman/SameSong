import pickle
import logging
from pathlib import Path
from data import db_manager

logger = logging.getLogger(__name__)

DATABASE_FILE = Path("data/database/database.dat")

def load_data_from_file_and_ingest():
    """Loads processed data from database.dat and ingests it into PostgreSQL."""
    if not DATABASE_FILE.exists():
        logger.warning(f"Data file not found: {DATABASE_FILE}")
        return

    try:
        with open(DATABASE_FILE, 'rb') as f:
            songs_data = pickle.load(f)
    except Exception as e:
        logger.error(f"Error loading {DATABASE_FILE}: {e}")
        return

    logger.info(f"Loaded {len(songs_data)} songs from file. Starting ingestion...")

    for song in songs_data:
        title = song['title']
        artist = song['artist']
        hashes = song['hashes']
        embedding = song['embedding']

        try:
            # Check if song already exists in DB
            if db_manager.check_song_exists(title, artist):
                logger.info(f"Song already in database: {artist} - {title}")
                continue

            logger.info(f"Ingesting: {artist} - {title}")
            
            # 1. Add song and FFT fingerprints
            song_id = db_manager.add_song(title, artist, hashes)
            
            # 2. Add CLAP embedding
            db_manager.add_vibe(song_id, embedding)
            
            logger.info(f"Successfully ingested ID {song_id}")
            
        except Exception as e:
            logger.error(f"Error ingesting {artist} - {title}: {e}")

    logger.info("Ingestion process complete.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    load_data_from_file_and_ingest()
