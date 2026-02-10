import numpy as np
import librosa
from scipy.ndimage import maximum_filter, binary_erosion
import hashlib

class FFTEngine:
    def __init__(self):
        self.FAN_VALUE = 15
        self.PEAK_NEIGHBORHOOD = 20
        self.MIN_AMPLITUDE = 10

    def get_peaks(self, wav_path):
        y, _ = librosa.load(wav_path, sr=16000)
        S = np.abs(librosa.stft(y, n_fft=2048, hop_length=512))
        S_db = librosa.amplitude_to_db(S)

        struct = np.ones((self.PEAK_NEIGHBORHOOD, self.PEAK_NEIGHBORHOOD))
        local_max = maximum_filter(S_db, footprint=struct) == S_db
        background = (S_db < self.MIN_AMPLITUDE)
        eroded_background = binary_erosion(background, structure=struct, border_value=1)
        detected_peaks = local_max ^ eroded_background

        freqs, times = np.where(detected_peaks)
        amps = S_db[detected_peaks]
        return sorted(zip(freqs, times, amps), key=lambda x: x[1])

    def hash_peaks(self, peaks):
        hashes = []
        for i in range(len(peaks)):
            for j in range(1, self.FAN_VALUE):
                if (i + j) < len(peaks):
                    f1, t1, _ = peaks[i]
                    f2, t2, _ = peaks[i + j]
                    t_delta = t2 - t1
                    if 0 <= t_delta <= 200:
                        h = hashlib.sha1(f"{f1}|{f2}|{t_delta}".encode()).hexdigest()
                        hashes.append((h, t1))
        return hashes

# Singleton instance for the worker to use
fft_engine = FFTEngine()