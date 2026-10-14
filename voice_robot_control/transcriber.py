import os
import time
import math
import sounddevice as sd
import numpy as np
from scipy.signal import resample_poly
from transformers import pipeline

SAMPLE_RATE = 16000  # Whisper's required input rate

# Jetson / laptop friendly default. Override with VOICE_ASR_MODEL.
MODEL_NAME = os.environ.get("VOICE_ASR_MODEL", "openai/whisper-base")


def _resolve_device(device=None):
    """Prefer CUDA when available; fall back to CPU."""
    if device is not None:
        return device
    env = os.environ.get("VOICE_ASR_DEVICE")
    if env is not None:
        return int(env) if env.lstrip("-").isdigit() else env
    try:
        import torch
        return 0 if torch.cuda.is_available() else -1
    except ImportError:
        return -1


def _pick_mic(preferred=None):
    """Choose an input-capable mic. Prefer USB capture when present."""
    if preferred is not None:
        return int(preferred)
    env = os.environ.get("VOICE_MIC_DEVICE")
    if env is not None and env.strip() != "":
        return int(env)

    devices = sd.query_devices()
    usb_candidates = []
    any_input = []
    for idx, dev in enumerate(devices):
        if dev.get("max_input_channels", 0) < 1:
            continue
        any_input.append(idx)
        name = str(dev.get("name", "")).lower()
        if "usb" in name or "uac" in name:
            usb_candidates.append(idx)

    if usb_candidates:
        return usb_candidates[0]
    if any_input:
        return any_input[0]
    raise RuntimeError(
        "No microphone input device found. Plug in a mic or set VOICE_MIC_DEVICE."
    )


def _device_sample_rate(device_index: int) -> int:
    info = sd.query_devices(device_index)
    rate = int(round(float(info.get("default_samplerate", 16000))))
    return rate if rate > 0 else 16000


def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    if orig_sr == target_sr:
        return audio
    gcd = math.gcd(orig_sr, target_sr)
    up = target_sr // gcd
    down = orig_sr // gcd
    return resample_poly(audio, up, down).astype("float32")


def _normalize(audio: np.ndarray, target_peak: float = 0.35) -> np.ndarray:
    """Software gain — needed for very quiet USB mics (e.g. UACDemo)."""
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak < 1e-8:
        return audio
    gain = min(target_peak / peak, 500.0)  # cap to avoid insane boost of pure noise
    out = (audio * gain).astype("float32")
    print(f"Audio gain x{gain:.0f} (raw peak={peak:.5f} → {float(np.max(np.abs(out))):.3f})")
    return out


class Transcriber:
    def __init__(self, model_name: str = MODEL_NAME, device=None, mic_device=None):
        self.mic_device = _pick_mic(mic_device)
        self.mic_sample_rate = _device_sample_rate(self.mic_device)
        mic_name = sd.query_devices(self.mic_device)["name"]
        print(
            f"Using mic index {self.mic_device}: {mic_name} @ {self.mic_sample_rate} Hz"
        )

        self.silence_threshold = self._calibrate_threshold()

        asr_device = _resolve_device(device)
        where = "GPU" if asr_device not in (-1, "cpu") else "CPU"
        print(
            f"Loading ASR model '{model_name}' on {where} "
            f"(device={asr_device}; first run may download)..."
        )
        self.pipe = pipeline(
            "automatic-speech-recognition", model=model_name, device=asr_device
        )
        print("Model loaded.")

    def _calibrate_threshold(self, seconds: float = 0.8) -> float:
        """Measure ambient noise and set a speech threshold above it."""
        env = os.environ.get("VOICE_SILENCE_THRESHOLD")
        if env:
            thr = float(env)
            print(f"Silence threshold from env: {thr}")
            return thr

        print("Calibrating mic (stay quiet 1s)...")
        n = int(seconds * self.mic_sample_rate)
        audio = sd.rec(
            n,
            samplerate=self.mic_sample_rate,
            channels=1,
            dtype="float32",
            device=self.mic_device,
        )
        sd.wait()
        noise = float(np.sqrt(np.mean(audio.flatten() ** 2)))
        # Quiet USB dongles often sit around 1e-4; require speech ~3–5x noise
        thr = max(noise * 4.0, 1.5e-4)
        thr = min(thr, 0.02)
        print(f"Noise floor rms={noise:.5f} → speech threshold={thr:.5f}")
        if noise < 1e-5:
            print(
                "WARNING: mic looks silent/muted. Check USB mic is plugged in "
                "and not muted in Settings → Sound."
            )
        return thr

    def record(
        self,
        max_seconds=8.0,
        silence_duration=1.0,
        chunk_duration=0.2,
        min_speak_seconds=0.4,
    ):
        thr = self.silence_threshold
        print(f"Listening... speak now (threshold={thr:.5f}).")
        chunks = []
        silence_time = 0.0
        speaking_started = False
        spoken = 0.0
        start_time = time.time()

        while time.time() - start_time < max_seconds:
            chunk = sd.rec(
                int(chunk_duration * self.mic_sample_rate),
                samplerate=self.mic_sample_rate,
                channels=1,
                dtype="float32",
                device=self.mic_device,
            )
            sd.wait()
            chunk = chunk.flatten()
            energy = float(np.sqrt(np.mean(chunk ** 2)))
            print(f"  rms={energy:.5f}{' *' if energy > thr else ''}", flush=True)

            if energy > thr:
                speaking_started = True
                silence_time = 0.0
                spoken += chunk_duration
                chunks.append(chunk)
            elif speaking_started:
                silence_time += chunk_duration
                chunks.append(chunk)
                if silence_time >= silence_duration and spoken >= min_speak_seconds:
                    break

        # Fallback: if VAD never triggered, keep the whole buffer so soft speech still works
        if not chunks:
            print("No speech detected by VAD — using full recording window.")
            n = int(max_seconds * self.mic_sample_rate)
            # We already consumed time; record a short fixed clip instead
            audio = sd.rec(
                int(3.0 * self.mic_sample_rate),
                samplerate=self.mic_sample_rate,
                channels=1,
                dtype="float32",
                device=self.mic_device,
            )
            sd.wait()
            chunks = [audio.flatten()]

        full_audio = _normalize(np.concatenate(chunks))
        return _resample(full_audio, self.mic_sample_rate, SAMPLE_RATE)

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            print('Transcript: "" (no audio captured)')
            return ""
        result = self.pipe({"array": audio, "sampling_rate": SAMPLE_RATE})
        text = result["text"].strip()
        print(f'Transcript: "{text}"')
        return text
