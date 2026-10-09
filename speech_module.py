"""
speech_module.py — VivaLens AI
==============================
Offline audio recording and speech-to-text transcription pipeline.
Uses Vosk for offline STT, sounddevice for mic capture, and soundfile
for WAV I/O. All imports are wrapped in try/except so the module
never crashes -- it degrades gracefully with clear status messages.

Dependencies (all free, pip-installable):
    sounddevice, soundfile, numpy, vosk
"""

from __future__ import annotations

import os
import json
import wave
import sys
import tempfile
from pathlib import Path
from typing import Optional

# Windows consoles default to cp1252, which cannot encode emoji/symbols.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Safe imports — each dependency is optional at runtime
# ---------------------------------------------------------------------------

_HAS_SOUNDDEVICE = False
_HAS_SOUNDFILE = False
_HAS_NUMPY = False
_HAS_VOSK = False

try:
    import sounddevice as sd
    _HAS_SOUNDDEVICE = True
except ImportError:
    sd = None  # type: ignore[assignment]

try:
    import soundfile as sf
    _HAS_SOUNDFILE = True
except ImportError:
    sf = None  # type: ignore[assignment]

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore[assignment]

try:
    from vosk import Model, KaldiRecognizer
    _HAS_VOSK = True
except ImportError:
    Model = None  # type: ignore[assignment,misc]
    KaldiRecognizer = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Recordings folder helper
# ---------------------------------------------------------------------------

def _recordings_dir() -> Path:
    """
    Resolve the 'voice recordings' folder inside the parent project
    (mega_project), creating it on first use.

    Falls back to the system temp directory if the folder cannot be created.
    """
    base = Path(__file__).resolve().parents[1]  # mega_project (parent of VivaLens_AI)
    rec_dir = base / "voice recordings"
    try:
        rec_dir.mkdir(parents=True, exist_ok=True)
        return rec_dir
    except OSError:
        return Path(tempfile.gettempdir())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_speech_available() -> dict:
    """
    Check which speech-related capabilities are available on this system.

    Returns
    -------
    dict
        {
            "mic_available": bool,
            "vosk_available": bool,
            "status_msg": str
        }
    """
    mic_ok = _HAS_SOUNDDEVICE and _HAS_NUMPY
    vosk_ok = _HAS_VOSK

    # Build a human-readable status message
    parts: list[str] = []
    if mic_ok:
        parts.append("Microphone recording is available.")
    else:
        missing = []
        if not _HAS_SOUNDDEVICE:
            missing.append("sounddevice")
        if not _HAS_NUMPY:
            missing.append("numpy")
        parts.append(
            f"Microphone recording unavailable (missing: {', '.join(missing)}). "
            f"Use manual text input instead."
        )

    if vosk_ok:
        parts.append("Vosk offline STT is available.")
    else:
        parts.append(
            "Vosk STT unavailable (missing: vosk). "
            "Install with: pip install vosk"
        )

    status_msg = " ".join(parts)

    return {
        "mic_available": mic_ok,
        "vosk_available": vosk_ok,
        "status_msg": status_msg,
    }


def record_audio(
    duration_sec: int = 15,
    sample_rate: int = 16000,
) -> Optional[str]:
    """
    Record audio from the default microphone and save to a temporary WAV file.

    Parameters
    ----------
    duration_sec : int
        Recording duration in seconds (default 15).
    sample_rate : int
        Sample rate in Hz (default 16000, required by Vosk).

    Returns
    -------
    str | None
        Absolute path to the saved WAV file on success, or None if
        recording is not possible (missing deps or no mic).
    """
    if not _HAS_SOUNDDEVICE:
        print("[speech_module] Cannot record: 'sounddevice' is not installed.")
        return None

    if not _HAS_NUMPY:
        print("[speech_module] Cannot record: 'numpy' is not installed.")
        return None

    try:
        # Check if a default input device exists
        default_input = sd.default.device[0]
        if default_input is None or default_input < 0:
            print("[speech_module] No default microphone found.")
            return None

        print(f"[speech_module] Recording for {duration_sec}s at {sample_rate} Hz ...")
        audio_data = sd.rec(
            frames=int(duration_sec * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
        )
        sd.wait()  # Block until recording is finished
        print("[speech_module] Recording complete.")

        # Save to the project 'voice recordings' folder
        wav_path = str(_recordings_dir() / "vivalens_recording.wav")

        if _HAS_SOUNDFILE:
            # soundfile handles the WAV header automatically
            sf.write(wav_path, audio_data, sample_rate, subtype="PCM_16")
        else:
            # Fallback: write WAV manually using the standard library
            _write_wav_manual(wav_path, audio_data, sample_rate)

        return wav_path

    except Exception as exc:
        print(f"[speech_module] Recording failed: {exc}")
        return None


def transcribe_audio(
    audio_path: str,
    model_path: str = "model",
) -> str:
    """
    Transcribe a WAV audio file to text using an offline Vosk model.

    Parameters
    ----------
    audio_path : str
        Path to a 16 kHz mono PCM WAV file.
    model_path : str
        Path to the Vosk model directory (e.g. "model" or
        "vosk-model-small-en-us-0.15"). Download models from
        https://alphacephei.com/vosk/models

    Returns
    -------
    str
        The transcribed text. Returns an empty string if transcription
        fails for any reason (missing model, bad file, etc.).
    """
    if not _HAS_VOSK:
        print("[speech_module] Cannot transcribe: 'vosk' is not installed.")
        return ""

    if not os.path.isfile(audio_path):
        print(f"[speech_module] Audio file not found: {audio_path}")
        return ""

    if not os.path.isdir(model_path):
        print(
            f"[speech_module] Vosk model directory not found: '{model_path}'. "
            f"Download a model from https://alphacephei.com/vosk/models "
            f"and place it in a folder named 'model' in the project root."
        )
        return ""

    try:
        # Load the Vosk model (suppress verbose log output)
        import logging
        logging.getLogger("vosk").setLevel(logging.WARNING)

        model = Model(model_path)
        recognizer = KaldiRecognizer(model, 16000)

        # Read the WAV file and feed chunks to the recognizer
        with wave.open(audio_path, "rb") as wf:
            # Validate format
            if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
                print(
                    "[speech_module] Warning: WAV should be 16-bit mono "
                    "for best Vosk results."
                )

            full_text_parts: list[str] = []

            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text_chunk = result.get("text", "")
                    if text_chunk:
                        full_text_parts.append(text_chunk)

            # Get any remaining partial result
            final_result = json.loads(recognizer.FinalResult())
            final_text = final_result.get("text", "")
            if final_text:
                full_text_parts.append(final_text)

        transcript = " ".join(full_text_parts).strip()
        print(f"[speech_module] Transcription complete ({len(transcript)} chars).")
        return transcript

    except Exception as exc:
        print(f"[speech_module] Transcription failed: {exc}")
        return ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _write_wav_manual(
    filepath: str,
    audio_data: "np.ndarray",  # type: ignore[name-defined]
    sample_rate: int,
) -> None:
    """
    Write a numpy int16 array to a WAV file using only the standard library.
    Used as a fallback when soundfile is not installed.
    """
    import struct

    # Flatten to 1-D if needed
    if audio_data.ndim > 1:
        audio_data = audio_data.flatten()

    num_samples = len(audio_data)
    num_channels = 1
    sample_width = 2  # 16-bit
    byte_rate = sample_rate * num_channels * sample_width
    block_align = num_channels * sample_width
    data_size = num_samples * sample_width

    with open(filepath, "wb") as f:
        # RIFF header
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")

        # fmt sub-chunk
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))          # sub-chunk size
        f.write(struct.pack("<H", 1))            # PCM format
        f.write(struct.pack("<H", num_channels))
        f.write(struct.pack("<I", sample_rate))
        f.write(struct.pack("<I", byte_rate))
        f.write(struct.pack("<H", block_align))
        f.write(struct.pack("<H", sample_width * 8))

        # data sub-chunk
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(audio_data.tobytes())


# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 55)
    print("  VivaLens AI — speech_module.py Test Suite")
    print("=" * 55)

    # --- Test 1: Availability check ---
    print("\n[TEST 1] is_speech_available()")
    status = is_speech_available()
    for key, val in status.items():
        print(f"  {key}: {val}")

    # --- Test 2: Recording (only if mic is available) ---
    print("\n[TEST 2] record_audio(duration_sec=3)")
    if status["mic_available"]:
        wav_path = record_audio(duration_sec=3, sample_rate=16000)
        if wav_path and os.path.isfile(wav_path):
            file_size = os.path.getsize(wav_path)
            print(f"  ✅ Saved to: {wav_path} ({file_size} bytes)")
        else:
            print("  ⚠️  Recording returned None (no mic detected?).")
    else:
        print("  ⏭️  Skipped — microphone not available.")

    # --- Test 3: Transcription (only if Vosk is available) ---
    print("\n[TEST 3] transcribe_audio()")
    if status["vosk_available"]:
        test_wav = str(_recordings_dir() / "vivalens_recording.wav")
        if os.path.isfile(test_wav):
            transcript = transcribe_audio(test_wav, model_path="model")
            if transcript:
                print(f"  ✅ Transcript: '{transcript}'")
            else:
                print("  ⚠️  Empty transcript (model folder missing or silent audio).")
        else:
            print("  ⏭️  No WAV file to transcribe. Run Test 2 first.")
    else:
        print("  ⏭️  Skipped — Vosk not installed.")

    print("\n" + "=" * 55)
    print("  All tests finished.")
    print("=" * 55)