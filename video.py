"""Menggabungkan gambar + gerakan + subtitle + suara menjadi video vertikal 1080x1920."""
import math, os, random, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

W, H, FPS = 1080, 1920, 30
JEDA = 0.6          # jeda setelah narasi tiap adegan (detik)
AKHIR = 3.0         # durasi kartu penutup
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")


def _font(nama, ukuran, cadangan="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
    p = os.path.join(FONT_DIR, nama)
    return ImageFont.truetype(p if os.path.exists(p) else cadangan, ukuran)


F_SUB = _font("Montserrat-ExtraBold.ttf", 64)
F_LABEL = _font("Anton-Regular.ttf", 40)
F_BESAR = _font("Anton-Regular.ttf", 150)
F_SEDANG = _font("Montserrat-ExtraBold.ttf", 54)
F_CCTV = _font("DejaVuSansMono-Bold.ttf", 40, "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf")
MERAH = (224, 49, 43)

_yy, _xx = np.mgrid[0:H, 0:W]
_d = np.sqrt(((_xx - W / 2) / (W / 2)) ** 2 + ((_yy - H / 2) / (H / 2)) ** 2)
VIGNET = np.clip(1.12 - 0.62 * _d ** 1.7, 0.18, 1.0)[..., None].astype(np.float32)
_rng = np.random.default_rng(11)
GRAIN = [_rng.normal(0, 8, (H // 2, W // 2)).astype(np.float32) for _ in range(8)]
SCAN = np.where((_yy % 4) < 2, 0.9, 1.0)[..., None].astype(np.float32)
del _yy, _xx, _d


def _siapkan(path):
    """Gambar dibesarkan 18% supaya ada ruang untuk zoom/geser."""
    im = Image.open(path).convert("RGB")
    sw, sh = int(W * 1.18), int(H * 1.18)
    r = max(sw / im.width, sh / im.height)
    im = im.resize((int(im.width * r + 1), int(im.height * r + 1)), Image.LANCZOS)
    x0, y0 = (im.width - sw) // 2, (im.height - sh) // 2
    return im.crop((x0, y0, x0 + sw, y0 + sh))


def _ease(x):
    return x * x * (3 - 2 * x)


def _jendela(big, gerak, p):
    bw, bh = big.size
    e = _ease(p)
    if gerak == "zoom_in":
        s = 1.0 + 0.15 * e; cx, cy = bw / 2, bh / 2
    elif gerak == "zoom_out":
        s = 1.15 - 0.15 * e; cx, cy = bw / 2, bh / 2
    else:
        s = 1.0
        mx, my = (bw - W) / 2, (bh - H) / 2
        cx, cy = bw / 2, bh / 2
        if gerak == "pan_up": cy = bh / 2 + my * (1 - 2 * e)
        if gerak == "pan_down": cy = bh / 2 - my * (1 - 2 * e)
        if gerak == "pan_left": cx = bw / 2 + mx * (1 - 2 * e)
        if gerak == "pan_right": cx = bw / 2 - mx * (1 - 2 * e)
    # s=1 → jendela seukuran layar (gambar dasar sudah 18% lebih besar); s>1 → lebih dekat
    dasar = 1.16 if gerak.startswith("zoom") else 1.0
    cw, ch = min(W * dasar / s, bw), min(H * dasar / s, bh)
    x0 = min(max(cx - cw / 2, 0), bw - cw); y0 = min(max(cy - ch / 2, 0), bh - ch)
    return big.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((W, H), Image.BILINEAR)


def _potong_subtitle(teks, maks=6):
    kata = teks.split(); hasil = []
    while kata:
        hasil.append(" ".join(kata[:maks])); kata = kata[maks:]
    if len(hasil) > 1 and len(hasil[-1].split()) <= 2:
        hasil[-2] += " " + hasil.pop()
    return hasil


def _bungkus(teks, font, maks_lebar):
    dr = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    baris, cur = [], ""
    for k in teks.split():
        t = (cur + " " + k).strip()
        if dr.textlength(t, font=font) <= maks_lebar: cur = t
        else: baris.append(cur); cur = k
    baris.append(cur); return baris


def _tulis_tengah(dr, teks, font, y, isi=(245, 240, 235), garis=8, jarak=80):
    for i, b in enumerate(_bungkus(teks, font, 940)):
        x = (W - dr.textlength(b, font=font)) / 2
        dr.text((x, y + i * jarak), b, font=font, fill=isi, stroke_width=garis, stroke_fill=(0, 0, 0))


def _judul_pas(dr, teks, y, isi, maks=940, ukuran=150):
    """Tulisan besar satu baris yang otomatis mengecil supaya muat di layar."""
    nama = "Anton-Regular.ttf"
    f = _font(nama, ukuran)
    while dr.textlength(teks, font=f) > maks and ukuran > 40:
        ukuran -= 6; f = _font(nama, ukuran)
    dr.text(((W - dr.textlength(teks, font=f)) / 2, y), teks, font=f, fill=isi)
    return y + ukuran * 1.25


def _label(dr, label):
    x = (W - dr.textlength(label, font=F_LABEL)) / 2
    dr.text((x, 140), label, font=F_LABEL, fill=(235, 228, 222), stroke_width=4, stroke_fill=(0, 0, 0))


def _efek_array(a, efek, t, i, rnd):
    a = a.astype(np.float32)
    if "cctv" in efek:
        g = a.mean(axis=2, keepdims=True)
        a = np.concatenate([g * 0.78, g * 0.98, g * 0.92], axis=2) * SCAN
    if "flicker" in efek:
        r = random.Random(int(t * 11) + i)
        if r.random() < 0.2: a *= 0.38
    if "kabut" in efek:
        a = a * 0.85 + 30
    a *= VIGNET
    a += GRAIN[i % 8].repeat(2, 0).repeat(2, 1)[..., None]
    return np.clip(a, 0, 255).astype(np.uint8)


def _cctv_teks(img, t):
    dr = ImageDraw.Draw(img)
    detik = 48 * 60 + 10 + int(t)
    jam = f"2026-11-02  23:{detik // 60 % 60:02d}:{detik % 60:02d}"
    dr.text((60, 250), jam, font=F_CCTV, fill=(220, 240, 230))
    if int(t * 2) % 2 == 0:
        dr.ellipse([W - 190, 255, W - 160, 285], fill=MERAH)
    dr.text((W - 145, 250), "REC", font=F_CCTV, fill=(220, 240, 230))
    dr.text((60, 305), "CAM 03", font=F_CCTV, fill=(220, 240, 230))


def _render_adegan(pipe, adegan, gambar, dur, label, idx):
    big = _siapkan(gambar)
    efek = adegan.get("efek", [])
    potongan = _potong_subtitle(adegan["narasi"])
    bobot = [len(p) for p in potongan]; total_b = sum(bobot)
    narr = dur - JEDA
    batas, acc = [], 0
    for b in bobot:
        acc += b; batas.append(narr * acc / total_b)
    n = int(round(dur * FPS))
    for i in range(n):
        t = i / FPS
        img = _jendela(big, adegan.get("gerak", "zoom_in"), t / dur)
        a = _efek_array(np.asarray(img), efek, t, i + idx * 1000, None)
        guncang = 0
        if "shake" in efek: guncang = 6
        if "kaget" in efek and t < 0.6: guncang = 22
        if guncang:
            a = np.roll(np.roll(a, random.randint(-guncang, guncang), 0), random.randint(-guncang, guncang), 1)
        if "kaget" in efek and t < 0.12:
            a = np.clip(a.astype(np.int16) + 120, 0, 255).astype(np.uint8)
        img = Image.fromarray(a)
        dr = ImageDraw.Draw(img)
        if "cctv" in efek: _cctv_teks(img, t)
        _label(dr, label)
        k = next((j for j, b in enumerate(batas) if t < b), None)
        if k is not None:
            _tulis_tengah(dr, potongan[k], F_SUB, 1430, isi=(255, 222, 89) if "kaget" in efek else (245, 240, 235))
        a = np.asarray(img)
        fade = min(1.0, t / 0.25, (dur - t) / 0.2)
        if fade < 1: a = (a * max(fade, 0)).astype(np.uint8)
        pipe.stdin.write(a.tobytes())


def _render_penutup(pipe, nomor_part, total_part, judul):
    n = int(AKHIR * FPS)
    for i in range(n):
        t = i / FPS
        img = Image.new("RGB", (W, H), (5, 5, 6)); dr = ImageDraw.Draw(img)
        a = min(1, t / 0.5)
        warna = tuple(int(c * a) for c in MERAH)
        putih = tuple(int(c * a) for c in (235, 228, 222))
        if nomor_part < total_part:
            y = _judul_pas(dr, "BERSAMBUNG", 720, warna) + 30
            _tulis_tengah(dr, f"Part {nomor_part + 1} segera tayang", F_SEDANG, y, isi=putih, garis=0)
            _tulis_tengah(dr, "Follow biar nggak ketinggalan", F_SEDANG, y + 90, isi=putih, garis=0)
        else:
            y = _judul_pas(dr, "TAMAT", 720, warna) + 30
            _tulis_tengah(dr, f"“{judul}”", F_SEDANG, y, isi=putih, garis=0)
            _tulis_tengah(dr, "Mau cerita apa lagi? Tulis di komen", F_SEDANG, y + 90, isi=putih, garis=0)
        a2 = _efek_array(np.asarray(img), [], t, i, None)
        pipe.stdin.write(a2.tobytes())


def _ffmpeg_tulis(path):
    return subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                             "-crf", "20", "-pix_fmt", "yuv420p", path], stdin=subprocess.PIPE)


def buat_video(adegan_list, gambar_list, audio_list, durasi_list, musik, keluar, label, nomor_part,
               total_part, judul, kerja):
    """Render video satu part. durasi_list = durasi tiap adegan (narasi + JEDA)."""
    bagian = []
    for idx, (a, g, d) in enumerate(zip(adegan_list, gambar_list, durasi_list)):
        p = os.path.join(kerja, f"adegan_{idx:02d}.mp4"); tmp = p + ".tmp.mp4"
        pipe = _ffmpeg_tulis(tmp); _render_adegan(pipe, a, g, d, label, idx)
        pipe.stdin.close(); pipe.wait()
        if pipe.returncode != 0: raise RuntimeError(f"render adegan {idx} gagal")
        os.replace(tmp, p); bagian.append(p)
    p = os.path.join(kerja, "penutup.mp4"); tmp = p + ".tmp.mp4"
    pipe = _ffmpeg_tulis(tmp); _render_penutup(pipe, nomor_part, total_part, judul)
    pipe.stdin.close(); pipe.wait(); os.replace(tmp, p); bagian.append(p)

    daftar = os.path.join(kerja, "daftar.txt")
    with open(daftar, "w") as f:
        for b in bagian: f.write(f"file '{os.path.abspath(b)}'\n")
    gabung = os.path.join(kerja, "gabung.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", daftar,
                    "-c", "copy", gabung], check=True)

    # trek narasi: tiap audio diberi jeda sampai durasi adegannya, lalu kartu penutup diam
    masukan, filt = [], []
    for k, (au, d) in enumerate(zip(audio_list, durasi_list)):
        masukan += ["-i", au]
        filt.append(f"[{k}:a]aresample=44100,aformat=channel_layouts=mono,apad,atrim=0:{d:.3f}[n{k}]")
    nn = len(audio_list)
    filt.append(f"anullsrc=r=44100:cl=mono,atrim=0:{AKHIR}[sepi]")
    filt.append("".join(f"[n{k}]" for k in range(nn)) + f"[sepi]concat=n={nn + 1}:v=0:a=1[narasi]")
    filt.append(f"[{nn}:a]aformat=channel_layouts=mono[musik]")
    filt.append("[narasi]volume=1.6[nv];[nv][musik]amix=inputs=2:duration=first:normalize=0,"
                "alimiter=limit=0.95[aout]")
    masukan += ["-i", musik]
    audio = os.path.join(kerja, "audio.m4a")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *masukan, "-filter_complex", ";".join(filt),
                    "-map", "[aout]", "-c:a", "aac", "-b:a", "160k", audio], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", gabung, "-i", audio, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "copy", "-shortest", "-movflags", "+faststart", keluar], check=True)
    return keluar
