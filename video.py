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
GRAIN = [_rng.normal(0, 3.5, (H // 2, W // 2)).astype(np.float32) for _ in range(4)]
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


FOKUS = {"atas": (0.5, 0.33), "tengah": (0.5, 0.47), "bawah": (0.5, 0.64),
         "kiri": (0.36, 0.45), "kanan": (0.64, 0.45)}


def _potong(big, cx, cy, cw, ch):
    bw, bh = big.size
    cw, ch = min(cw, bw), min(ch, bh)
    x0 = min(max(cx - cw / 2, 0), bw - cw); y0 = min(max(cy - ch / 2, 0), bh - ch)
    # EXTENT = potongan sub-piksel, gerakan pelan tetap halus (tidak patah-patah)
    return big.transform((W, H), Image.EXTENT, (x0, y0, x0 + cw, y0 + ch), Image.BILINEAR)


def _kamera(big, gerak, p, t, shot, fokus="tengah"):
    """shot 1 = gambar lebar dengan gerak pilihan; shot 2 = close-up ke titik fokus."""
    bw, bh = big.size
    e = _ease(p)
    # goyangan kamera dipegang tangan, supaya gambar terasa hidup
    gx = 7 * math.sin(t * 1.3) + 3 * math.sin(t * 2.9 + 0.5)
    gy = 9 * math.sin(t * 0.9 + 1.0) + 3 * math.sin(t * 2.3)
    if shot == 2:
        fx, fy = FOKUS.get(fokus, FOKUS["tengah"])
        s = 1.42 + 0.12 * e
        return _potong(big, bw * fx + gx + 20 * (e - 0.5), bh * fy + gy, W * 1.16 / s, H * 1.16 / s)
    if gerak == "zoom_in":
        s = 1.0 + 0.2 * e; cx, cy = bw / 2, bh / 2
    elif gerak == "zoom_out":
        s = 1.2 - 0.2 * e; cx, cy = bw / 2, bh / 2
    else:
        s = 1.0
        mx, my = (bw - W) / 2 - 12, (bh - H) / 2 - 12
        cx, cy = bw / 2, bh / 2
        if gerak == "pan_up": cy = bh / 2 + my * (1 - 2 * e)
        if gerak == "pan_down": cy = bh / 2 - my * (1 - 2 * e)
        if gerak == "pan_left": cx = bw / 2 + mx * (1 - 2 * e)
        if gerak == "pan_right": cx = bw / 2 - mx * (1 - 2 * e)
    dasar = 1.16 if gerak.startswith("zoom") else 1.0
    return _potong(big, cx + gx, cy + gy, W * dasar / s, H * dasar / s)


# ---------- lapisan bergerak: hujan & kabut ----------
def _lapisan_hujan():
    r = np.random.default_rng(21); lap = np.zeros((H * 2, W), np.float32)
    for _ in range(900):
        x = r.integers(0, W); y = r.integers(0, H * 2); L = r.integers(40, 110); a = r.uniform(0.25, 0.8)
        for k in range(L):
            yy, xx = y + k, x + k // 6
            if yy < H * 2 and xx < W: lap[yy, xx] = max(lap[yy, xx], a)
    return lap


def _lapisan_kabut():
    r = np.random.default_rng(31)
    kecil = Image.fromarray((r.random((12, 40)) * 255).astype(np.uint8)).resize((W * 2, H), Image.BICUBIC)
    a = np.asarray(kecil, np.float32) / 255
    return np.clip((a - 0.35) * 1.6, 0, 1)


_HUJAN = _KABUT = None


def _hujan(a, t):
    global _HUJAN
    if _HUJAN is None: _HUJAN = _lapisan_hujan()
    y0 = int((t * 1900) % H)
    m = _HUJAN[y0:y0 + H][..., None] * 0.45
    return a * (1 - m) + 200 * m


def _kabut(a, t):
    global _KABUT
    if _KABUT is None: _KABUT = _lapisan_kabut()
    x0 = int((t * 35) % W)
    m = _KABUT[:, x0:x0 + W][..., None] * 0.38
    return a * (1 - m) + np.array([150, 175, 175], np.float32) * m


def _distorsi(a, kuat, t):
    """Gelombang + pecah warna untuk momen hantu muncul."""
    baris = np.arange(H)
    geser = (kuat * np.sin(baris / 23.0 + t * 40)).astype(int)
    idx = (np.arange(W)[None, :] - geser[:, None]) % W
    b = np.take_along_axis(a, idx[..., None].repeat(3, 2), 1)
    k = max(1, int(kuat * 0.8))
    b[..., 0] = np.roll(b[..., 0], k, 1); b[..., 2] = np.roll(b[..., 2], -k, 1)
    return b


def _potong_subtitle(teks, maks=6):
    kata = teks.split(); hasil = []
    while kata:
        hasil.append(" ".join(kata[:maks])); kata = kata[maks:]
    if len(hasil) > 1 and len(hasil[-1].split()) <= 2:
        ekor = hasil.pop()
        hasil[-1] += " " + ekor
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


_CACHE_LENCANA = {}
ORANYE = (255, 149, 64)


def _lencana(judul, nomor):
    """Kotak kecil di pojok kiri atas: kategori, PART n, dan judul cerita (sama untuk ketiga part)."""
    kunci = (judul, nomor)
    if kunci in _CACHE_LENCANA:
        return _CACHE_LENCANA[kunci]
    x0, y0, lebar, tinggi = 36, 150, 640, 190
    lap = Image.new("RGBA", (W, y0 + tinggi + 10), (0, 0, 0, 0)); dr = ImageDraw.Draw(lap)
    dr.rounded_rectangle([x0, y0, x0 + lebar, y0 + tinggi], 18, fill=(18, 18, 26, 215))
    dr.rounded_rectangle([x0, y0, x0 + 9, y0 + tinggi], 4, fill=ORANYE + (255,))
    f_kat = _font("Montserrat-ExtraBold.ttf", 28); f_part = _font("Montserrat-ExtraBold.ttf", 68)
    f_jdl = _font("Montserrat-ExtraBold.ttf", 28)
    dr.ellipse([x0 + 34, y0 + 30, x0 + 50, y0 + 46], fill=ORANYE + (255,))
    dr.text((x0 + 62, y0 + 22), "CERITA HOROR", font=f_kat, fill=ORANYE + (255,))
    dr.text((x0 + 32, y0 + 58), f"PART {nomor}", font=f_part, fill=(250, 248, 244, 255))
    teks = judul.upper().strip(); maks = lebar - 64
    if dr.textlength(teks, font=f_jdl) > maks:
        while teks and dr.textlength(teks + "...", font=f_jdl) > maks: teks = teks[:-1]
        teks = teks.rstrip() + "..."
    dr.text((x0 + 32, y0 + 140), teks, font=f_jdl, fill=(215, 212, 222, 255))
    _CACHE_LENCANA[kunci] = (lap, y0 + tinggi)
    return _CACHE_LENCANA[kunci]
    lap = Image.new("RGBA", (W, 520), (0, 0, 0, 0)); dr = ImageDraw.Draw(lap)
    teks = teks.upper().strip()
    ukuran = 132
    while True:
        f = _font("Anton-Regular.ttf", ukuran)
        baris = _bungkus(teks, f, 960)
        if len(baris) <= 2 or ukuran <= 70: break
        ukuran -= 8
    y = 150
    for b in baris[:2]:
        x = (W - dr.textlength(b, font=f)) / 2
        dr.text((x, y), b, font=f, fill=(248, 244, 238), stroke_width=11, stroke_fill=(0, 0, 0))
        y += int(ukuran * 1.08)
    dr.rectangle([W / 2 - 90, y + 14, W / 2 + 90, y + 24], fill=MERAH + (255,))
    _CACHE_JUDUL[teks] = (lap, y + 40)
    return _CACHE_JUDUL[teks]


def _efek_array(a, efek, t, i, rnd):
    a = a.astype(np.float32)
    if "cctv" in efek:
        g = a.mean(axis=2, keepdims=True)
        a = np.concatenate([g * 0.78, g * 0.98, g * 0.92], axis=2) * SCAN
    if "flicker" in efek:
        r = random.Random(int(t * 11) + i)
        if r.random() < 0.2: a *= 0.38
    if "kabut" in efek:
        a = _kabut(a, t)
    if "hujan" in efek:
        a = _hujan(a, t)
    a *= VIGNET
    a += GRAIN[(i // 6) % 4].repeat(2, 0).repeat(2, 1)[..., None]  # bintik halus, ganti tiap 6 frame
    return np.clip(a, 0, 255).astype(np.uint8)


def _cctv_teks(img, t, y0=520):
    dr = ImageDraw.Draw(img)
    detik = 48 * 60 + 10 + int(t)
    jam = f"2026-11-02  23:{detik // 60 % 60:02d}:{detik % 60:02d}"
    dr.text((60, y0), jam, font=F_CCTV, fill=(220, 240, 230))
    if int(t * 2) % 2 == 0:
        dr.ellipse([W - 190, y0 + 5, W - 160, y0 + 35], fill=MERAH)
    dr.text((W - 145, y0), "REC", font=F_CCTV, fill=(220, 240, 230))
    dr.text((60, y0 + 55), "CAM 03", font=F_CCTV, fill=(220, 240, 230))


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
    gerak = adegan.get("gerak", "zoom_in")
    # adegan cukup panjang dipotong jadi 2 shot: lebar lalu close-up (momen kaget: close-up dulu)
    potong = dur * 0.55 if dur >= 3.2 else None
    kaget = "kaget" in efek
    petir = "petir" in adegan.get("suara", [])
    for i in range(n):
        t = i / FPS
        if potong is None:
            img = _kamera(big, gerak, t / dur, t, 1)
        elif kaget:
            shot = 2 if t < potong * 0.7 else 1
            awal, akhir = (0, potong * 0.7) if shot == 2 else (potong * 0.7, dur)
            img = _kamera(big, gerak, (t - awal) / (akhir - awal), t, shot, adegan.get("fokus", "atas"))
        else:
            shot = 1 if t < potong else 2
            awal, akhir = (0, potong) if shot == 1 else (potong, dur)
            img = _kamera(big, gerak, (t - awal) / (akhir - awal), t, shot, adegan.get("fokus", "tengah"))
        a = _efek_array(np.asarray(img), efek, t, i + idx * 1000, None)
        if kaget and t < 0.7:
            a = _distorsi(a, 18 * (1 - t / 0.7), t)
        guncang = 0
        if "shake" in efek: guncang = 6
        if kaget and t < 0.6: guncang = 22
        if guncang:
            a = np.roll(np.roll(a, random.randint(-guncang, guncang), 0), random.randint(-guncang, guncang), 1)
        if (kaget and t < 0.12) or (petir and (0.3 < t < 0.38 or 0.5 < t < 0.56)):
            a = np.clip(a.astype(np.int16) + 120, 0, 255).astype(np.uint8)
        fade = min(1.0, t / 0.25, (dur - t) / 0.2)   # gambar saja yang memudar, judul tetap
        if fade < 1: a = (a * max(fade, 0)).astype(np.uint8)
        img = Image.fromarray(a)
        lap, bawah_judul = _lencana(*label)
        img.paste(lap, (0, 0), lap)
        dr = ImageDraw.Draw(img)
        if "cctv" in efek: _cctv_teks(img, t, int(bawah_judul) + 20)
        k = next((j for j, b in enumerate(batas) if t < b), None)
        if k is not None:
            _tulis_tengah(dr, potongan[k], F_SUB, 1430, isi=(255, 222, 89) if "kaget" in efek else (245, 240, 235))
        pipe.stdin.write(np.asarray(img).tobytes())


def _render_penutup(pipe, nomor_part, total_part, judul):
    n = int(AKHIR * FPS)
    for i in range(n):
        t = i / FPS
        img = Image.new("RGB", (W, H), (5, 5, 6)); dr = ImageDraw.Draw(img)
        a = min(1, t / 0.5)
        warna = tuple(int(c * a) for c in MERAH)
        putih = tuple(int(c * a) for c in (235, 228, 222))
        _tulis_tengah(dr, f"PART {nomor_part}/{total_part}", F_SEDANG, 620, isi=putih, garis=0)
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
                             "-crf", "24", "-maxrate", "4500k", "-bufsize", "9M", "-g", "60", "-pix_fmt", "yuv420p", path], stdin=subprocess.PIPE)


def buat_video(adegan_list, gambar_list, audio_list, durasi_list, musik, keluar, label, nomor_part,
               total_part, judul, kerja):
    """Render video satu part. durasi_list = durasi tiap adegan (narasi + JEDA)."""
    bagian = []
    for idx, (a, g, d) in enumerate(zip(adegan_list, gambar_list, durasi_list)):
        p = os.path.join(kerja, f"adegan_{idx:02d}.mp4"); tmp = p + ".tmp.mp4"
        pipe = _ffmpeg_tulis(tmp); _render_adegan(pipe, a, g, d, (label, nomor_part), idx)
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
    filt.append(f"[{nn}:a]aformat=channel_layouts=mono,volume=0.8[musik]")
    filt.append(f"[{nn + 1}:a]aformat=channel_layouts=mono[sfx]")
    # musik latar otomatis mengecil saat narator bicara (ducking), efek suara tetap terdengar
    filt.append("[narasi]volume=1.5,asplit=2[nv][kunci];"
                "[musik][kunci]sidechaincompress=threshold=0.05:ratio=4:attack=40:release=900[mk];"
                "[nv][mk][sfx]amix=inputs=3:duration=first:normalize=0,alimiter=limit=0.95[aout]")
    masukan += ["-i", musik, "-i", musik.replace(".wav", "_sfx.wav")]
    audio = os.path.join(kerja, "audio.m4a")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *masukan, "-filter_complex", ";".join(filt),
                    "-map", "[aout]", "-c:a", "aac", "-b:a", "160k", audio], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", gabung, "-i", audio, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "copy", "-shortest", "-movflags", "+faststart", keluar], check=True)
    return keluar
