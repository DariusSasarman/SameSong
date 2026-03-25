import os
import pickle
import requests
import random
import logging
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from processing.FFT.FFTProcessor import fft_engine
from processing.CLAP.CLAPProcessor import create_embedding

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
DATABASE_FILE = Path("data/database/database.dat")
TEMP_DIR = Path("data/tmp")

class InternetArchiveScraper:
    def __init__(self):
        self.search_url = "https://archive.org/advancedsearch.php"
        self.download_base_url = "https://archive.org/download"
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)

    def fetch_random_tracks(self, limit=10):
        """Search for random audio tracks on Internet Archive."""
        params = {
            'q': 'mediatype:audio AND format:VBR MP3',
            'fl[]': 'identifier,title,creator',
            'sort[]': 'random',
            'rows': limit,
            'output': 'json'
        }
        
        try:
            response = requests.get(self.search_url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get('response', {}).get('docs', [])
        except Exception as e:
            logger.error(f"Error fetching tracks: {e}")
            return []

    def download_track(self, identifier):
        """Download the first available MP3 for a given identifier."""
        metadata_url = f"https://archive.org/metadata/{identifier}"
        try:
            resp = requests.get(metadata_url)
            resp.raise_for_status()
            metadata = resp.json()
            
            # Find an MP3 file
            mp3_file = None
            for file in metadata.get('files', []):
                if file.get('format') == 'VBR MP3' or file.get('name', '').endswith('.mp3'):
                    mp3_file = file.get('name')
                    break
            
            if not mp3_file:
                return None

            download_url = f"{self.download_base_url}/{identifier}/{mp3_file}"
            local_path = TEMP_DIR / f"{identifier}.mp3"
            
            logger.info(f"Downloading: {download_url}")
            with requests.get(download_url, stream=True) as r:
                r.raise_for_status()
                with open(local_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            return local_path
        except Exception as e:
            logger.error(f"Error downloading {identifier}: {e}")
            return None

    def process_song(self, file_path, title, artist):
        """Process a single song file and return its features."""
        try:
            logger.info(f"Processing: {title} by {artist}")
            
            # 1. FFT Fingerprinting
            peaks = fft_engine.get_peaks(str(file_path))
            hashes = fft_engine.hash_peaks(peaks)
            
            # 2. CLAP Embedding
            embedding = create_embedding(str(file_path))
            
            return {
                'title': title,
                'artist': artist,
                'hashes': hashes,
                'embedding': embedding
            }
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            return None
        finally:
            if file_path.exists():
                file_path.unlink()

def _process_track(scraper, track, existing_titles):
    """Download and process a single track. Returns song_data dict or None."""
    identifier = track.get('identifier')
    title = track.get('title', 'Unknown Title')
    artist = track.get('creator', 'Unknown Artist')

    if (title, artist) in existing_titles:
        logger.info(f"Skipping already processed: {title} - {artist}")
        return None

    file_path = scraper.download_track(identifier)
    if file_path:
        return scraper.process_song(file_path, title, artist)
    return None


def main():
    parser = argparse.ArgumentParser(description="Scrape and process music from Internet Archive")
    parser.add_argument("--limit", type=int, default=5, help="Number of songs to scrape")
    parser.add_argument("--workers", type=int, default=1, help="Number of parallel download workers")
    args = parser.parse_args()

    scraper = InternetArchiveScraper()
    tracks = scraper.fetch_random_tracks(limit=args.limit)

    processed_songs = []

    # Load existing data if file exists
    if DATABASE_FILE.exists():
        try:
            with open(DATABASE_FILE, 'rb') as f:
                processed_songs = pickle.load(f)
            logger.info(f"Loaded {len(processed_songs)} existing songs from {DATABASE_FILE}")
        except Exception as e:
            logger.error(f"Error loading existing database: {e}")

    existing_titles = {(s['title'], s['artist']) for s in processed_songs}

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(_process_track, scraper, track, existing_titles): track
            for track in tracks
        }
        for future in as_completed(futures):
            song_data = future.result()
            if song_data:
                processed_songs.append(song_data)
                existing_titles.add((song_data['title'], song_data['artist']))
                # Save after each success to be safe
                with open(DATABASE_FILE, 'wb') as f:
                    pickle.dump(processed_songs, f)
                logger.info(f"Saved {song_data['title']} to {DATABASE_FILE}")

    logger.info(f"Finished. Total songs in {DATABASE_FILE}: {len(processed_songs)}")


if __name__ == "__main__":
    main()
