import torch
import librosa
import numpy as np
import logging
from transformers import ClapModel, ClapProcessor

logger = logging.getLogger(__name__)

# Device selection
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MODEL_ID = "laion/clap-htsat-unfused"

# Lazy-loaded model and processor
_model = None
_processor = None

def _get_model():
    global _model
    if _model is None:
        logger.info(f"Loading CLAP model on {DEVICE}...")
        if DEVICE == "cuda":
            _model = ClapModel.from_pretrained(MODEL_ID).to(DEVICE, torch.float16)
        else:
            _model = ClapModel.from_pretrained(MODEL_ID)
    return _model

def _get_processor():
    global _processor
    if _processor is None:
        _processor = ClapProcessor.from_pretrained(MODEL_ID)
    return _processor

def create_embedding(wav_path):
    """Pure processing: WAV -> 512D Vector"""
    model = _get_model()
    processor = _get_processor()

    # Load and resample
    audio_data, _ = librosa.load(wav_path, sr=48000)

    # Preprocess
    inputs = processor(audio=audio_data, return_tensors="pt", sampling_rate=48000)

    # Move to device
    if DEVICE == "cuda":
        inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
        inputs = {k: v.to(torch.float16) if v.dtype == torch.float32 else v for k, v in inputs.items()}

    # Extract
    with torch.no_grad():
        audio_embeds = model.get_audio_features(**inputs)
        # Normalize
        audio_embeds = audio_embeds / audio_embeds.norm(p=2, dim=-1, keepdim=True)

    return audio_embeds.cpu().numpy().astype(np.float32)