"""Suara untuk MODE VIDEO PANJANG: memakai ulang suara.py (narator, suara tokoh lain, musik, efek),
hanya tempo narasinya dibuat lebih pelan dan campuran suaranya dibuat lebih tenang.
File suara.py asli TIDAK diubah."""
import re, subprocess
import suara

TAMBAH_PELAN = -10   # tempo narasi lebih lambat 10 poin persen dibanding video pendek
BATAS_SFX = 0.45     # puncak efek suara (termasuk jumpscare) selalu di bawah narator
_TTS_ASLI = suara._tts


def _lambatkan(rate, tambah):
    m = re.fullmatch(r"([+-]?\d+)%", rate)
    if not m:
        return rate
    return f"{max(-60, int(m.group(1)) + tambah):+d}%"


def _tts_pelan(teks, path, nama_suara, rate, pitch):
    return _TTS_ASLI(teks, path, nama_suara, _lambatkan(rate, TAMBAH_PELAN), pitch)


def narasi(teks, path, dialog=None):
    """Sama seperti suara.narasi (narator + suara tokoh lain berbeda), tetapi lebih pelan."""
    suara._tts = _tts_pelan
    try:
        return suara.narasi(teks, path, dialog)
    finally:
        suara._tts = _TTS_ASLI


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
