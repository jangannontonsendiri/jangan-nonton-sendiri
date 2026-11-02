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


SUARA_LAIN = {"pria": "id-ID-ArdiNeural", "wanita": "id-ID-GadisNeural"}
# suara hantu: lebih berat & lambat, bergema, sedikit bergetar — bukan suara narator biasa
# PENTING: aresample=44100 dulu (Edge TTS keluar 24 kHz), baru asetrate — kalau tidak, suara jadi kecepetan
FILTER_HANTU = ("aresample=44100,asetrate=44100*0.86,aresample=44100,atempo=1.04,highpass=f=90,lowpass=f=6500,"
                "tremolo=f=4:d=0.12,aecho=0.8:0.85:45|95|180:0.4|0.28|0.18,volume=1.5")
FILTER_ORANG = "aresample=44100,highpass=f=120,volume=1.1"
_KUTIP = re.compile(r"[\"“”]([^\"“”]+)[\"“”]|[‘']([^‘’']{6,})[’']")


def _tts(teks, path, suara, rate, pitch):
    import edge_tts
    async def _jalan():
        await edge_tts.Communicate(teks, suara, rate=rate, pitch=pitch).save(path)
    for coba in range(3):
        try:
            asyncio.run(_jalan()); return path
        except Exception:
            if coba == 2: raise


def pecah_dialog(teks):
    """Pisahkan narasi dan kalimat dalam tanda kutip -> [(teks, 'narator'|'dialog'), ...]."""
    hasil, pos = [], 0
    for m in _KUTIP.finditer(teks):
        sebelum = teks[pos:m.start()].strip(" ,:")
        if sebelum: hasil.append((sebelum, "narator"))
        hasil.append(((m.group(1) or m.group(2)).strip(), "dialog"))
        pos = m.end()
    sisa = teks[pos:].strip(" ,:")
    if sisa: hasil.append((sisa, "narator"))
    return hasil or [(teks, "narator")]


def narasi(teks, path, dialog=None):
    """dialog = {"siapa": "hantu"|"orang", "kelamin": "pria"|"wanita"} untuk kalimat dalam tanda kutip."""
    dialog = dialog or {}
    bagian = pecah_dialog(teks)
    if len(bagian) == 1 and bagian[0][1] == "narator":
        return _tts(teks, path, SUARA, "-4%", "-6Hz")
    hantu = dialog.get("siapa", "hantu") == "hantu"
    kelamin = dialog.get("kelamin", "wanita" if hantu else "pria")
    potongan = []
    for k, (isi, jenis) in enumerate(bagian):
        mentah = f"{path}.{k}.mp3"; jadi = f"{path}.{k}.wav"
        if jenis == "narator":
            _tts(isi, mentah, SUARA, "-4%", "-6Hz"); filt = "aresample=44100"
        elif hantu:
            _tts(isi, mentah, SUARA_LAIN.get(kelamin, SUARA_LAIN["wanita"]), "-22%", "-12Hz"); filt = FILTER_HANTU
        else:
            lain = "id-ID-GadisNeural" if kelamin == "wanita" else "id-ID-ArdiNeural"
            _tts(isi, mentah, lain, "-2%", "+4Hz" if kelamin == "pria" else "+0Hz"); filt = FILTER_ORANG
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mentah, "-af",
                        f"{filt},aformat=sample_rates=44100:channel_layouts=mono,apad=pad_dur=0.18", jadi], check=True)
        potongan.append(jadi)
    ins = sum([["-i", p] for p in potongan], [])
    filt = "".join(f"[{i}:a]" for i in range(len(potongan))) + f"concat=n={len(potongan)}:v=0:a=1[a]"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex", filt, "-map", "[a]",
                    "-c:a", "libmp3lame", "-b:a", "160k", path], check=True)
    return path


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
    (r"bergetar|berdering|notifikasi|pesan masuk|telepon masuk|ada (yang )?nelpon", "getar_hp"),
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


def _simpan(path, x):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def musik_latar(path, total, waktu_kaget, kejadian=(), suasana="sunyi"):
    """Menulis 2 trek: `path` = musik latar (nanti dikecilkan otomatis saat narator bicara),
    `path`_sfx.wav = efek suara (volumenya tetap). kejadian = daftar (detik, jenis_sfx)."""
    rng = np.random.default_rng(3)
    n = int(total * SR); t = np.arange(n) / SR
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * 0.09 * t)
    drone = (0.16 * np.sin(2 * np.pi * 55 * t) + 0.09 * np.sin(2 * np.pi * 58.2 * t)
             + 0.05 * np.sin(2 * np.pi * 110.4 * t))
    noise = _band(rng.normal(0, 1, n), 30, 260) * 2.0
    latar = (drone + noise) * lfo * 0.32 + _suasana(suasana, n) * 0.55
    env = np.minimum(1, np.minimum(t / 1.0, (total - t) / 1.5))
    _simpan(path, latar * env)

    efek = np.zeros(n)
    st = np.arange(int(2.2 * SR)) / SR
    sting = (np.sin(2 * np.pi * 41 * st) * 0.8 + rng.normal(0, 0.35, len(st))) * np.exp(-st * 1.6)
    for k in waktu_kaget:
        a = int(k * SR); b = min(n, a + len(sting)); efek[a:b] += sting[:b - a] * 0.55
    cache = {}
    for k, jenis in kejadian:
        if jenis not in SFX: continue
        s = cache.setdefault(jenis, SFX[jenis]())
        a = int(k * SR); b = min(n, a + len(s))
        if a < n: efek[a:b] += s[:b - a] * 0.6
    _simpan(path.replace(".wav", "_sfx.wav"), efek)
