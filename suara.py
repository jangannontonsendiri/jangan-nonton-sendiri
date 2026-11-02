"""Suara narator (Edge TTS) dan musik latar mencekam."""
import asyncio, subprocess, wave
import numpy as np

SUARA = "id-ID-ArdiNeural"
SR = 44100


def durasi(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def narasi(teks, path):
    import edge_tts
    async def _jalan():
        await edge_tts.Communicate(teks, SUARA, rate="-8%", pitch="-6Hz").save(path)
    for coba in range(3):
        try:
            asyncio.run(_jalan()); return path
        except Exception:
            if coba == 2: raise


def musik_latar(path, total, waktu_kaget):
    rng = np.random.default_rng(3)
    n = int(total * SR); t = np.arange(n) / SR
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * 0.09 * t)
    drone = (0.16 * np.sin(2 * np.pi * 55 * t) + 0.09 * np.sin(2 * np.pi * 58.2 * t)
             + 0.05 * np.sin(2 * np.pi * 110.4 * t))
    noise = np.convolve(rng.normal(0, 1, n), np.ones(500) / 500, mode="same") * 0.8
    out = (drone + noise) * lfo
    st = np.arange(int(2.2 * SR)) / SR
    sting = (np.sin(2 * np.pi * 41 * st) * 0.8 + rng.normal(0, 0.35, len(st))) * np.exp(-st * 1.6)
    for k in waktu_kaget:
        a = int(k * SR); b = min(n, a + len(sting)); out[a:b] += sting[:b - a]
    env = np.minimum(1, np.minimum(t / 1.5, (total - t) / 1.5))
    out = np.clip(out * env * 0.55, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((out * 32767).astype(np.int16).tobytes())
