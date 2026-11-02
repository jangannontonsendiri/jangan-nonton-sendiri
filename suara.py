"""Suara narator (Edge TTS), musik latar, dan efek suara horor buatan sendiri (bebas hak cipta)."""
import asyncio, re, subprocess, wave
import numpy as np

SUARA = "id-ID-ArdiNeural"
SR = 44100
JENIS_SFX = ["langkah", "pintu", "ketukan", "petir", "bisikan", "detak", "getar_hp", "kaca", "pukulan"]
SUASANA = ["hujan", "angin", "sunyi", "jangkrik"]
_rng = np.random.default_rng(5)


# ---------- narator ----------
def durasi(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def narasi(teks, path):
    import edge_tts
    async def _jalan():
        await edge_tts.Communicate(teks, SUARA, rate="-4%", pitch="-6Hz").save(path)
    for coba in range(3):
        try:
            asyncio.run(_jalan()); return path
        except Exception:
            if coba == 2: raise


# ---------- alat bantu ----------
def _t(d): return np.arange(int(d * SR)) / SR


def _band(x, lo=None, hi=None):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    if lo: X[f < lo] = 0
    if hi: X[f > hi] = 0
    return np.fft.irfft(X, len(x))


def _norm(x, g=1.0):
    m = np.max(np.abs(x)) or 1
    return x / m * g


def _damped(f, d, decay):
    t = _t(d); return np.sin(2 * np.pi * f * t) * np.exp(-t * decay)


# ---------- efek suara ----------
def sfx_langkah():
    out = np.zeros(int(3.2 * SR))
    for k in range(6):
        t0 = int((0.15 + k * 0.5 + _rng.uniform(-0.04, 0.04)) * SR)
        n = _band(_rng.normal(0, 1, int(0.09 * SR)), 80, 1800) * np.exp(-_t(0.09) * 45)
        thump = _damped(70, 0.12, 30) * 1.4
        s = np.zeros(len(thump)); s[:len(n)] += _norm(n); s += thump
        g = (0.55 if k % 2 else 0.75) * (0.6 + 0.4 * k / 5)          # makin dekat
        out[t0:t0 + len(s)] += s[:len(out) - t0] * g
    return _norm(out, 0.8)


def sfx_pintu():
    d = 2.0; n = int(d * SR); pulsa = np.zeros(n)
    t = 0.05
    while t < d - 0.3:                                   # gesekan "stick-slip" engsel
        pulsa[int(t * SR)] = _rng.uniform(0.5, 1.0)
        t += 1 / (55 + 40 * np.sin(t * 2.2) + _rng.uniform(-8, 8))
    res = _damped(820, 0.03, 160) + 0.7 * _damped(1550, 0.03, 220) + 0.4 * _damped(2900, 0.03, 300)
    creak = np.convolve(pulsa, res)[:n]
    creak *= np.minimum(1, np.minimum(_t(d) / 0.1, (d - _t(d)) / 0.4)).clip(0)
    return _norm(creak, 0.55)


def sfx_ketukan():
    out = np.zeros(int(1.6 * SR))
    for k, t0 in enumerate([0.1, 0.45, 0.8]):
        s = _damped(170, 0.25, 26) + 0.5 * _damped(330, 0.25, 40)
        s[:300] += _rng.normal(0, 0.6, 300)
        a = int(t0 * SR); out[a:a + len(s)] += s
    return _norm(out, 0.9)


def sfx_petir():
    d = 4.0; n = int(d * SR)
    crack = _rng.normal(0, 1, int(0.25 * SR)) * np.exp(-_t(0.25) * 18)
    brown = np.cumsum(_rng.normal(0, 1, n)); brown -= np.convolve(brown, np.ones(4000) / 4000, "same")
    rumble = _band(brown, 20, 180) * np.exp(-_t(d) * 0.9) * (1 + 0.5 * np.sin(_t(d) * 9))
    out = _norm(rumble, 0.9); out[:len(crack)] += crack * 0.8
    return _norm(out, 0.95)


def sfx_bisikan():
    d = 2.0; n = int(d * SR); env = np.zeros(n); t = 0.1
    while t < d - 0.3:
        dur = _rng.uniform(0.1, 0.24); a, b = int(t * SR), int((t + dur) * SR)
        env[a:b] = np.sin(np.linspace(0, np.pi, b - a)) * _rng.uniform(0.5, 1)
        t += dur + _rng.uniform(0.02, 0.12)
    x = _band(_rng.normal(0, 1, n), 1800, 6500) * env
    return _norm(x, 0.45)


def sfx_detak():
    out = np.zeros(int(4.0 * SR))
    for k in range(5):
        for off, g in [(0, 1), (0.2, 0.65)]:
            a = int((0.1 + k * 0.78 + off) * SR); s = _damped(48, 0.2, 20) * g
            out[a:a + len(s)] += s[:len(out) - a]
    return _norm(out, 0.9)


def sfx_getar_hp():
    out = np.zeros(int(2.4 * SR)); t = _t(0.4)
    buzz = np.sign(np.sin(2 * np.pi * 165 * t)) * 0.5 * (1 - np.exp(-t * 60))
    for k in range(3):
        a = int(k * 0.8 * SR); out[a:a + len(buzz)] += buzz
    return _norm(_band(out, 60, 1200), 0.5)


def sfx_kaca():
    out = np.zeros(int(1.4 * SR))
    for t0 in [0.1, 0.5, 0.9]:
        s = _damped(2600, 0.3, 30) + 0.6 * _damped(3700, 0.3, 45) + 0.3 * _damped(5200, 0.3, 60)
        a = int(t0 * SR); out[a:a + len(s)] += s[:len(out) - a]
    return _norm(out, 0.5)


def sfx_pukulan():
    s = _damped(55, 0.6, 9) * 1.2 + _band(_rng.normal(0, 1, int(0.6 * SR)), 30, 900) * np.exp(-_t(0.6) * 14)
    return _norm(s, 1.0)


SFX = {"langkah": sfx_langkah, "pintu": sfx_pintu, "ketukan": sfx_ketukan, "petir": sfx_petir,
       "bisikan": sfx_bisikan, "detak": sfx_detak, "getar_hp": sfx_getar_hp, "kaca": sfx_kaca,
       "pukulan": sfx_pukulan}

# kata kunci di narasi -> efek suara (cadangan bila penulis cerita tidak memilih)
KATA_KUNCI = [
    (r"langkah|jejak kaki|menyeret|berjalan mendekat", "langkah"),
    (r"pintu.*(terbuka|berderit|dibuka|membuka)|derit", "pintu"),
    (r"ketuk|tok", "ketukan"),
    (r"petir|guntur|geledek|kilat", "petir"),
    (r"bisik", "bisikan"),
    (r"jantung|deg", "detak"),
    (r"ponsel|hp |handphone|getar|berdering", "getar_hp"),
    (r"jendela|kaca", "kaca"),
    (r"brak|dobrak|dibanting|banting|jatuh", "pukulan"),
]


def tebak_sfx(teks):
    teks = teks.lower(); hasil = []
    for pola, jenis in KATA_KUNCI:
        if re.search(pola, teks) and jenis not in hasil: hasil.append(jenis)
    return hasil[:2]


def tebak_suasana(cerita):
    semua = " ".join(a["narasi"] for p in cerita["part"] for a in p["adegan"]).lower()
    if re.search(r"hujan|gerimis", semua): return "hujan"
    if re.search(r"hutan|kebun|sawah|desa|kampung", semua): return "jangkrik"
    if re.search(r"angin|gunung|puncak", semua): return "angin"
    return "sunyi"


def _suasana(jenis, n):
    if jenis == "hujan":
        x = _band(_rng.normal(0, 1, n), 900, 9000) * 0.5
        tetes = np.zeros(n); idx = _rng.integers(0, n, n // 600); tetes[idx] = _rng.uniform(0.3, 1, len(idx))
        x += np.convolve(tetes, _damped(3000, 0.01, 400))[:n] * 0.4
        return _norm(x, 0.22)
    if jenis == "angin":
        b = np.cumsum(_rng.normal(0, 1, n)); b -= np.convolve(b, np.ones(8000) / 8000, "same")
        lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.07 * np.arange(n) / SR + 1)
        return _norm(_band(b, 80, 900) * lfo, 0.22)
    if jenis == "jangkrik":
        t = np.arange(n) / SR
        chirp = np.sin(2 * np.pi * 4300 * t) * (np.sin(2 * np.pi * 28 * t) > 0.3) * (np.sin(2 * np.pi * 0.9 * t) > -0.2)
        return chirp * 0.035
    return np.zeros(n)


def musik_latar(path, total, waktu_kaget, kejadian=(), suasana="sunyi"):
    """kejadian = daftar (detik, jenis_sfx)."""
    rng = np.random.default_rng(3)
    n = int(total * SR); t = np.arange(n) / SR
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * 0.09 * t)
    drone = (0.16 * np.sin(2 * np.pi * 55 * t) + 0.09 * np.sin(2 * np.pi * 58.2 * t)
             + 0.05 * np.sin(2 * np.pi * 110.4 * t))
    noise = _band(rng.normal(0, 1, n), 30, 260) * 2.0
    out = (drone + noise) * lfo * 0.55
    out += _suasana(suasana, n)
    st = np.arange(int(2.2 * SR)) / SR
    sting = (np.sin(2 * np.pi * 41 * st) * 0.8 + rng.normal(0, 0.35, len(st))) * np.exp(-st * 1.6)
    for k in waktu_kaget:
        a = int(k * SR); b = min(n, a + len(sting)); out[a:b] += sting[:b - a] * 0.7
    cache = {}
    for k, jenis in kejadian:
        if jenis not in SFX: continue
        s = cache.setdefault(jenis, SFX[jenis]())
        a = int(k * SR); b = min(n, a + len(s))
        if a < n: out[a:b] += s[:b - a] * 0.75
    env = np.minimum(1, np.minimum(t / 1.0, (total - t) / 1.5))
    out = np.clip(out * env, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((out * 32767).astype(np.int16).tobytes())
