"""Suara untuk MODE VIDEO PANJANG: memakai ulang suara.py (Edge TTS, filter suara hantu/orang, musik, efek),
dengan tempo narasi lebih pelan, narator bisa perempuan, dan suara tokoh lain dibedakan per tokoh.
File suara.py asli TIDAK diubah."""
import os, subprocess
import suara

BATAS_SFX = 0.45     # puncak efek suara (termasuk jumpscare) selalu di bawah narator
AMAN = "aresample=44100"

# (suara Edge TTS, kecepatan, nada, filter). Semua lebih pelan dari video pendek.
NARATOR = {"laki": ("id-ID-ArdiNeural", "-14%", "-6Hz", AMAN),
           "perempuan": ("id-ID-GadisNeural", "-14%", "-4Hz", AMAN)}
JENIS = {
    "pria": ("id-ID-ArdiNeural", "-12%", "+4Hz", suara.FILTER_ORANG),
    "perempuan": ("id-ID-GadisNeural", "-12%", "+8Hz", suara.FILTER_ORANG),
    "perempuan_jawa": ("jv-ID-SitiNeural", "-12%", "+0Hz", suara.FILTER_ORANG),
    "hantu_pria": ("id-ID-ArdiNeural", "-32%", "-12Hz", suara.FILTER_HANTU),
    "hantu_perempuan": ("id-ID-GadisNeural", "-32%", "-12Hz", suara.FILTER_HANTU),
    "hantu_perempuan_jawa": ("jv-ID-SitiNeural", "-30%", "-10Hz", suara.FILTER_HANTU),
}
# bila suara Jawa gagal / terdengar aneh: pakai suara Indonesia dengan nada & tempo berbeda
CADANGAN = {"perempuan_jawa": "perempuan", "hantu_perempuan_jawa": "hantu_perempuan"}


def _pakai_jawa():
    return os.environ.get("SUARA_JAWA", "1") != "0"      # SUARA_JAWA=0 -> langsung pakai cadangan


def _spec(jenis, narator):
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


def narasi(teks, path, jenis=None, narator="laki"):
    """Narasi satu adegan. Kalimat dalam tanda kutip dibacakan dengan suara tokoh (jenis), sisanya oleh narator."""
    narator = narator if narator in NARATOR else "laki"
    bagian = suara.pecah_dialog(teks)
    sp_n = NARATOR[narator]
    if len(bagian) == 1 and bagian[0][1] == "narator":
        suara._tts(teks, path, *sp_n[:3]); return path
    potongan = []
    for k, (isi, peran) in enumerate(bagian):
        mentah = f"{path}.{k}.mp3"; jadi = f"{path}.{k}.wav"
        if peran == "narator":
            filt = sp_n[3]; suara._tts(isi, mentah, *sp_n[:3])
        else:
            j, sp = _spec(jenis, narator)
            sp = _sintesis(isi, mentah, j, sp); filt = sp[3]
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mentah, "-af",
                        f"{filt},aformat=sample_rates=44100:channel_layouts=mono,apad=pad_dur=0.25", jadi], check=True)
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
