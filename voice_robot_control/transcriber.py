import time
import math
import sounddevice as sd
import numpy as np
from scipy.signal import resample_poly
from transformers import pipeline

MIC_DEVICE_INDEX = 6
MIC_SAMPLE_RATE = 48000
SAMPLE_RATE = 16000  # Whisper's required input rate
MODEL_NAME = "openai/whisper-large-v3"

def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    if orig_sr == target_sr:
        return audio
    gcd = math.gcd(orig_sr, target_sr)
    up = target_sr // gcd
    down = orig_sr // gcd
    return resample_poly(audio, up, down).astype("float32")

class Transcriber:
    def __init__(self, model_name: str = MODEL_NAME):
        print(f"Loading Whisper model '{model_name}' on GPU (first run downloads the model)...")
        self.pipe = pipeline("automatic-speech-recognition", model=model_name, device=0)
        print("Model loaded.")

    def record(self, max_seconds=10.0, silence_threshold=0.02, silence_duration=1.0, chunk_duration=0.2):
        print("Listening... speak now.")
        chunks = []
        silence_time = 0.0
        speaking_started = False
        start_time = time.time()

        while time.time() - start_time < max_seconds:
            chunk = sd.rec(
                int(chunk_duration * MIC_SAMPLE_RATE),
                samplerate=MIC_SAMPLE_RATE,
                channels=1,
                dtype="float32",
                device=MIC_DEVICE_INDEX,
            )
            sd.wait()
            chunk = chunk.flatten()
            energy = np.sqrt(np.mean(chunk ** 2))

            if energy > silence_threshold:
                speaking_started = True
                silence_time = 0.0
                chunks.append(chunk)
            elif speaking_started:
                silence_time += chunk_duration
                chunks.append(chunk)
                if silence_time >= silence_duration:
                    break

        if not chunks:
            return np.array([], dtype="float32")

        full_audio = np.concatenate(chunks)
        return _resample(full_audio, MIC_SAMPLE_RATE, SAMPLE_RATE)

    def transcribe(self, audio: np.ndarray) -> str:
        result = self.pipe({"array": audio, "sampling_rate": SAMPLE_RATE})
        text = result["text"].strip()
        print(f'Transcript: "{text}"')
        return text
