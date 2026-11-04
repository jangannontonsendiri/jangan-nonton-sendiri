"""Suara untuk MODE VIDEO PANJANG: memakai ulang suara.py (Edge TTS, filter suara hantu/orang, musik, efek),
dengan tempo narasi lebih pelan, narator bisa perempuan, dan suara tokoh lain dibedakan per tokoh.
File suara.py asli TIDAK diubah."""
import os, re, subprocess
import suara

BATAS_SFX = 0.45     # puncak efek suara (termasuk jumpscare) selalu di bawah narator
AMAN = "aresample=44100"
# narator perempuan terpilih (N2): suara lebih hangat dan sedikit berbayang seperti di ruangan
HANGAT = "aresample=44100,highpass=f=80,lowpass=f=7500,equalizer=f=220:t=q:w=1:g=2,aecho=0.8:0.88:55:0.18,volume=1.1"

# (suara Edge TTS, kecepatan, nada, filter). Semua lebih pelan dari video pendek.
# Narator perempuan sekitar 1.25x lebih cepat dari sebelumnya (-10% -> +12%: 0.90 x 1.25 = 1.125)
NARATOR = {"laki": ("id-ID-ArdiNeural", "-14%", "-6Hz", AMAN),
           "perempuan": ("id-ID-GadisNeural", "+12%", "-2Hz", HANGAT)}
# Mas Dimas: nada TIDAK dipaksa diubah; hanya efek halus ala Mbak Rina (sedikit berat, sedikit gema, pelan)
DIMAS = ("aresample=44100,highpass=f=70,lowpass=f=6500,equalizer=f=150:t=q:w=1:g=3,"
         "aecho=0.8:0.85:75:0.2,volume=0.9")
# jeda alami (detik) setelah tiap potongan kalimat, menurut tanda bacanya
JEDA_TITIK, JEDA_TANYA, JEDA_TITIKTIGA, JEDA_SELA = 0.45, 0.5, 0.7, 0.25
JENIS = {
    "pria": ("id-ID-ArdiNeural", "-10%", "+0Hz", DIMAS),          # Mas Dimas (misterius, bukan nada paksaan)
    "narator": None,                                              # tokoh sampingan: diganti suara narator (lihat _spec)
    "perempuan": ("id-ID-GadisNeural", "-12%", "+8Hz", HANGAT),
    "perempuan_jawa": ("jv-ID-SitiNeural", "-12%", "+0Hz", suara.FILTER_ORANG),
    "hantu_pria": ("id-ID-ArdiNeural", "-32%", "-12Hz", suara.FILTER_HANTU),
    "hantu_perempuan": ("id-ID-GadisNeural", "-22%", "-8Hz", suara.FILTER_HANTU),   # suara Mbak Rina terpilih (R2)
    "hantu_perempuan_jawa": ("jv-ID-SitiNeural", "-30%", "-10Hz", suara.FILTER_HANTU),
}
# suara Jawa (jv-ID) terdengar kurang bagus -> TIDAK dipakai secara bawaan; SUARA_JAWA=1 untuk mencobanya lagi.
# Tokoh bersuara "..._jawa" otomatis memakai suara Indonesia yang terpilih
CADANGAN = {"perempuan_jawa": "perempuan", "hantu_perempuan_jawa": "hantu_perempuan"}


def _pakai_jawa():
    return os.environ.get("SUARA_JAWA", "0") == "1"


def _spec(jenis, narator):
    if jenis == "narator":
        return "narator", NARATOR[narator]
    if not jenis:
        jenis = "pria" if narator == "perempuan" else "perempuan"
    if jenis in CADANGAN and not _pakai_jawa():
        jenis = CADANGAN[jenis]
    return jenis, JENIS[jenis]


def _sintesis(teks, keluar, jenis, spec):
    try:
        suara._tts(teks, keluar, *spec[:3])
    except Exception as e:
        if jenis not in CADANGAN:
            raise
        print(f"  suara Jawa gagal ({str(e)[:80]}), pakai suara cadangan", flush=True)
        suara._tts(teks, keluar, *JENIS[CADANGAN[jenis]][:3])
        spec = JENIS[CADANGAN[jenis]]
    return spec


def _potong(teks):
    """Pecah narasi di tanda baca -> [(potongan, jeda_setelahnya)] supaya terdengar seperti orang bercerita."""
    hasil = []
    for kal in re.split(r"(?<=[.!?…])\s+", teks.strip()):
        for k, sub in enumerate(re.split(r"\s+[—–]\s+|;\s+|:\s+", kal)):
            sub = sub.strip()
            if not sub: continue
            hasil.append([sub, JEDA_SELA])
        if not hasil: continue
        akhir = kal.rstrip()
        hasil[-1][1] = (JEDA_TITIKTIGA if akhir.endswith(("...", "…")) else
                        JEDA_TANYA if akhir.endswith(("?", "!")) else JEDA_TITIK)
    return [(t, j) for t, j in hasil if re.search(r"\w", t)]


def _ucap(isi, wav, spec, jeda_akhir=0.25, dasar=None):
    """Ucapkan isi dengan spec (suara, rate, nada, filter), jeda di tanda baca, hasil WAV mono 44.1 kHz."""
    dasar = dasar or wav
    bagian = _potong(isi) or [(isi, JEDA_TITIK)]
    potongan = []
    for k, (t, jeda) in enumerate(bagian):
        mentah = f"{dasar}.s{k}.mp3"; jadi = f"{dasar}.s{k}.wav"
        suara._tts(t, mentah, *spec[:3])
        pad = jeda if k < len(bagian) - 1 else jeda_akhir
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mentah, "-af",
                        f"{spec[3]},aformat=sample_rates=44100:channel_layouts=mono,apad=pad_dur={pad}", jadi], check=True)
        potongan.append(jadi)
    if len(potongan) == 1:
        os.replace(potongan[0], wav); return wav
    ins = sum([["-i", p] for p in potongan], [])
    filt = "".join(f"[{i}:a]" for i in range(len(potongan))) + f"concat=n={len(potongan)}:v=0:a=1[a]"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex", filt, "-map", "[a]", wav], check=True)
    return wav


def narasi(teks, path, jenis=None, narator="laki"):
    """Narasi satu adegan. Kalimat dalam tanda kutip dibacakan dengan suara tokoh (jenis), sisanya oleh narator."""
    narator = narator if narator in NARATOR else "laki"
    bagian = suara.pecah_dialog(teks)
    sp_n = NARATOR[narator]
    potongan = []
    for k, (isi, peran) in enumerate(bagian):
        jadi = f"{path}.{k}.wav"
        if peran == "narator":
            _ucap(isi, jadi, sp_n, dasar=f"{path}.{k}")
        else:
            j, sp = _spec(jenis, narator)
            if j == "narator":                                     # tokoh sampingan: suara narator biasa
                _ucap(isi, jadi, sp, dasar=f"{path}.{k}")
            else:
                mentah = f"{path}.{k}.mp3"
                sp = _sintesis(isi, mentah, j, sp)
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mentah, "-af",
                                f"{sp[3]},aformat=sample_rates=44100:channel_layouts=mono,apad=pad_dur=0.25", jadi], check=True)
        potongan.append(jadi)
    ins = sum([["-i", p] for p in potongan], [])
    filt = "".join(f"[{i}:a]" for i in range(len(potongan))) + f"concat=n={len(potongan)}:v=0:a=1[a]"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex", filt, "-map", "[a]",
                    "-c:a", "libmp3lame", "-b:a", "160k", path], check=True)
    return path


def campur(audio_list, durasi_list, awal, akhir, musik, keluar):
    """Gabungkan narasi tiap adegan + musik latar (mengecil saat narator bicara) + efek suara.
    awal/akhir = detik hening untuk kartu pembuka dan kartu penutup."""
    masukan, filt = [], []
    for k, (au, d) in enumerate(zip(audio_list, durasi_list)):
        masukan += ["-i", au]
        filt.append(f"[{k}:a]aresample=44100,aformat=channel_layouts=mono,apad,atrim=0:{d:.3f}[n{k}]")
    nn = len(audio_list)
    filt.append(f"anullsrc=r=44100:cl=mono,atrim=0:{awal}[buka]")
    filt.append(f"anullsrc=r=44100:cl=mono,atrim=0:{akhir}[tutup]")
    filt.append("[buka]" + "".join(f"[n{k}]" for k in range(nn)) + f"[tutup]concat=n={nn + 2}:v=0:a=1[narasi]")
    filt.append(f"[{nn}:a]aformat=channel_layouts=mono,volume=0.7[musik]")
    filt.append(f"[{nn + 1}:a]aformat=channel_layouts=mono,volume=0.5,alimiter=limit={BATAS_SFX}:level=disabled[sfx]")
    filt.append("[narasi]volume=1.5,asplit=2[nv][kunci];"
                "[musik][kunci]sidechaincompress=threshold=0.05:ratio=4:attack=40:release=900[mk];"
                "[nv][mk][sfx]amix=inputs=3:duration=first:normalize=0,alimiter=limit=0.95[aout]")
    masukan += ["-i", musik, "-i", musik.replace(".wav", "_sfx.wav")]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *masukan, "-filter_complex", ";".join(filt),
                    "-map", "[aout]", "-c:a", "aac", "-b:a", "160k", keluar], check=True)
    return keluar
