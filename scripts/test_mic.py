#!/usr/bin/env python3
"""Standalone mic check — no ROS, no Whisper.

Records a few seconds, saves a WAV, optionally plays it back.
"""

from __future__ import annotations

import argparse
import sys
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd


def list_devices() -> None:
    print("=== Audio devices ===")
    for i, d in enumerate(sd.query_devices()):
        tags = []
        if d["max_input_channels"] > 0:
            tags.append("IN")
        if d["max_output_channels"] > 0:
            tags.append("OUT")
        tag = f" [{'/'.join(tags)}]" if tags else ""
        print(f"  {i:2d}: {d['name']}{tag}  rate={d['default_samplerate']}")


def pick_input(index: int | None) -> int:
    if index is not None:
        return index
    devices = sd.query_devices()
    usb, any_in = [], []
    for i, d in enumerate(devices):
        if d["max_input_channels"] < 1:
            continue
        any_in.append(i)
        if "usb" in d["name"].lower() or "uac" in d["name"].lower():
            usb.append(i)
    if usb:
        return usb[0]
    if any_in:
        return any_in[0]
    raise SystemExit("No input device found")


def save_wav(path: Path, audio: np.ndarray, rate: int) -> None:
    # float32 [-1,1] → int16
    clipped = np.clip(audio, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def main() -> int:
    parser = argparse.ArgumentParser(description="Test microphone capture")
    parser.add_argument("--device", type=int, default=None, help="sounddevice input index")
    parser.add_argument("--seconds", type=float, default=4.0, help="record length")
    parser.add_argument("--gain", type=float, default=1.0, help="extra software gain")
    parser.add_argument("--out", type=str, default="/tmp/mic_test.wav")
    parser.add_argument("--no-playback", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    list_devices()
    if args.list:
        return 0

    idx = pick_input(args.device)
    info = sd.query_devices(idx)
    rate = int(round(float(info["default_samplerate"])))
    print(f"\nUsing INPUT device {idx}: {info['name']} @ {rate} Hz")
    print(f"Speak clearly for {args.seconds:.0f} seconds after the beep...\n")

    # Short beep on default output if available
    try:
        out_dev = sd.default.device[1]
        t = np.linspace(0, 0.15, int(0.15 * rate), endpoint=False)
        beep = (0.2 * np.sin(2 * np.pi * 880 * t)).astype(np.float32)
        sd.play(beep, rate, device=out_dev)
        sd.wait()
    except Exception:
        pass

    audio = sd.rec(
        int(args.seconds * rate),
        samplerate=rate,
        channels=1,
        dtype="float32",
        device=idx,
    )
    sd.wait()
    audio = audio.flatten()

    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(audio ** 2)))
    print(f"Raw  peak={peak:.5f}  rms={rms:.5f}")

    if peak < 1e-5:
        print("\nFAIL: mic is silent. Check:")
        print("  - USB mic plugged in")
        print("  - Settings → Sound → Input not muted")
        print("  - try: pactl set-source-mute @DEFAULT_SOURCE@ 0")
        return 1

    if peak < 0.005:
        print("WARN: very quiet mic — will amplify for the test WAV/playback")
        gain = min(0.35 / peak, 500.0) * args.gain
    else:
        gain = args.gain

    boosted = np.clip(audio * gain, -1.0, 1.0).astype(np.float32)
    print(f"Gain x{gain:.1f} → peak={float(np.max(np.abs(boosted))):.3f}")

    out = Path(args.out)
    save_wav(out, boosted, rate)
    print(f"Saved: {out}")
    print("Play with:  aplay /tmp/mic_test.wav")
    print("         or: paplay /tmp/mic_test.wav")

    if not args.no_playback:
        print("\nPlaying back recording...")
        try:
            sd.play(boosted, rate)
            sd.wait()
            print("Playback done. Did you hear your voice?")
        except Exception as e:
            print(f"Playback failed ({e}). Use: aplay {out}")

    if rms < 0.001 and peak < 0.01:
        print("\nRESULT: mic captures something but is VERY quiet.")
        print("Voice ASR will struggle unless you speak close to the mic.")
        return 2

    print("\nRESULT: mic is working.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
