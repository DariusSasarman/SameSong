import time

from celery import Celery
import os
from pathlib import Path
from processing.FFT.FFTWrapper import get_snippet_matches
from processing.CLAP.CLAPWrapper import get_vibe_matches
from processing.WavConverter import convert_to_wav
# Configuration for paths
UPLOAD_DIR = Path('/data/tmp')

celery = Celery(
    "samesong",
    broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("REDIS_URL", "redis://localhost:6379/0")
)

@celery.task(name="processing.tasks.process_audio")
def process_audio(tmp_filename, client_ip):
    input_path = UPLOAD_DIR / tmp_filename
    wav_path = None
    print(f"Processing audio file: {input_path}")
    try:
        if not input_path.exists():
            raise FileNotFoundError(f"Input file {tmp_filename} not found.")

        print(f"Converting file: {input_path}")
        # This converts AND deletes the original temp file
        wav_path = convert_to_wav(input_path, client_ip)

        if not wav_path.exists():
            raise Exception(f"Audio file {tmp_filename} not processed.")


        vibe_results = get_vibe_matches(wav_path)
        snippet_results = get_snippet_matches(wav_path)
        # --- Analysis Logic Starts Here ---
        print(f"Analyzing standardized file: {wav_path}")

        return {
            "vibe_matches": vibe_results,
            "snippet_matches": snippet_results
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        # If conversion failed before deleting original, clean up here
        if input_path.exists():
            input_path.unlink()
        raise e

    finally:
        # Final cleanup of the converted .wav file
        if wav_path and wav_path.exists():
            wav_path.unlink()
            print(f"Final .wav for {client_ip} cleaned up.")