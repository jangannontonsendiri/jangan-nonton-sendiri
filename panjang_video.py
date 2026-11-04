"""MODE VIDEO PANJANG: menggabungkan gambar + gerakan ringan + subtitle + suara menjadi video
mendatar 1920x1080 (16:9). Terpisah dari video.py (yang khusus vertikal 1080x1920); video.py tidak diubah."""
import math, os, random, subprocess
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1920, 1080, 24
JEDA = 1.2          # jeda tenang setelah narasi tiap adegan (detik)
AWAL = 4.0          # kartu pembuka
AKHIR = 6.0         # kartu penutup
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
MERAH = (224, 49, 43)
ORANYE = (255, 149, 64)
KANDIDAT_CADANGAN = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", r"C:\Windows\Fonts\arialbd.ttf"]


def _font(nama, ukuran):
    for p in [os.path.join(FONT_DIR, nama)] + KANDIDAT_CADANGAN:
        try:
            return ImageFont.truetype(p, ukuran)
        except OSError:
            continue
    return ImageFont.load_default()


_PERSIAPAN = {}


def _siap():
    """Lapisan bantu (vinyet, bintik, scanline) dibuat sekali per proses."""
    if _PERSIAPAN:
        return _PERSIAPAN
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    _PERSIAPAN["vignet"] = np.clip(1.12 - 0.55 * d ** 1.7, 0.2, 1.0)[..., None].astype(np.float32)
    rng = np.random.default_rng(11)
    _PERSIAPAN["bintik"] = [rng.normal(0, 3.0, (H // 2, W // 2)).astype(np.float32) for _ in range(4)]
    _PERSIAPAN["scan"] = np.where((yy % 4) < 2, 0.9, 1.0)[..., None].astype(np.float32)
    # hujan
    r = np.random.default_rng(21); lap = np.zeros((H * 2, W), np.float32)
    for _ in range(1400):
        x = r.integers(0, W); y = r.integers(0, H * 2); L = r.integers(30, 80); a = r.uniform(0.25, 0.8)
        for k in range(L):
            y2, x2 = y + k, x + k // 6
            if y2 < H * 2 and x2 < W: lap[y2, x2] = max(lap[y2, x2], a)
    _PERSIAPAN["hujan"] = lap
    # kabut
    r = np.random.default_rng(31)
    kecil = Image.fromarray((r.random((10, 48)) * 255).astype(np.uint8)).resize((W * 2, H), Image.BICUBIC)
    _PERSIAPAN["kabut"] = np.clip((np.asarray(kecil, np.float32) / 255 - 0.35) * 1.6, 0, 1)
    return _PERSIAPAN


# ---------- kamera (gerakan ringan) ----------
def _siapkan(path):
    """Gambar dibesarkan 15% supaya ada ruang untuk zoom/geser."""
    im = Image.open(path).convert("RGB")
    sw, sh = int(W * 1.15), int(H * 1.15)
    r = max(sw / im.width, sh / im.height)
    im = im.resize((int(im.width * r + 1), int(im.height * r + 1)), Image.LANCZOS)
    x0, y0 = (im.width - sw) // 2, (im.height - sh) // 2
    return im.crop((x0, y0, x0 + sw, y0 + sh))


def _ease(x):
    return x * x * (3 - 2 * x)


FOKUS = {"atas": (0.5, 0.36), "tengah": (0.5, 0.5), "bawah": (0.5, 0.64),
         "kiri": (0.34, 0.5), "kanan": (0.66, 0.5)}


def _potong(big, cx, cy, cw, ch):
    bw, bh = big.size
    cw, ch = min(cw, bw), min(ch, bh)
    x0 = min(max(cx - cw / 2, 0), bw - cw); y0 = min(max(cy - ch / 2, 0), bh - ch)
    return big.transform((W, H), Image.EXTENT, (x0, y0, x0 + cw, y0 + ch), Image.BILINEAR)


def _kamera(big, gerak, p, t, shot, fokus="tengah"):
    """shot 1 = gambar lebar dengan gerak pelan; shot 2 = mendekat ke titik fokus."""
    bw, bh = big.size
    e = _ease(p)
    gx = 5 * math.sin(t * 1.1) + 2 * math.sin(t * 2.7 + 0.5)       # goyangan kamera dipegang tangan, halus
    gy = 6 * math.sin(t * 0.8 + 1.0) + 2 * math.sin(t * 2.1)
    if shot == 2:
        fx, fy = FOKUS.get(fokus, FOKUS["tengah"])
        s = 1.25 + 0.1 * e
        return _potong(big, bw * fx + gx + 14 * (e - 0.5), bh * fy + gy, W * 1.15 / s, H * 1.15 / s)
    if gerak == "zoom_in":
        s = 1.0 + 0.12 * e; cx, cy = bw / 2, bh / 2
    elif gerak == "zoom_out":
        s = 1.12 - 0.12 * e; cx, cy = bw / 2, bh / 2
    else:
        s = 1.0
        mx, my = (bw - W) / 2 - 10, (bh - H) / 2 - 10
        cx, cy = bw / 2, bh / 2
        if gerak == "pan_up": cy = bh / 2 + my * (1 - 2 * e)
        if gerak == "pan_down": cy = bh / 2 - my * (1 - 2 * e)
        if gerak == "pan_left": cx = bw / 2 + mx * (1 - 2 * e)
        if gerak == "pan_right": cx = bw / 2 - mx * (1 - 2 * e)
    dasar = 1.15 if gerak.startswith("zoom") else 1.0
    return _potong(big, cx + gx, cy + gy, W * dasar / s, H * dasar / s)


# ---------- efek ----------
def _distorsi(a, kuat, t):
    """Gelombang + pecah warna untuk momen hantu muncul."""
    baris = np.arange(H)
    geser = (kuat * np.sin(baris / 23.0 + t * 40)).astype(int)
    idx = (np.arange(W)[None, :] - geser[:, None]) % W
    b = np.take_along_axis(a, idx[..., None].repeat(3, 2), 1)
    k = max(1, int(kuat * 0.8))
    b[..., 0] = np.roll(b[..., 0], k, 1); b[..., 2] = np.roll(b[..., 2], -k, 1)
    return b


def _efek_array(a, efek, t, i):
    p = _siap()
    a = a.astype(np.float32)
    if "cctv" in efek:
        g = a.mean(axis=2, keepdims=True)
        a = np.concatenate([g * 0.78, g * 0.98, g * 0.92], axis=2) * p["scan"]
    if "flicker" in efek:
        if random.Random(int(t * 9) + i).random() < 0.18: a *= 0.4
    if "kabut" in efek:
        x0 = int((t * 30) % W)
        m = p["kabut"][:, x0:x0 + W][..., None] * 0.38
        a = a * (1 - m) + np.array([150, 175, 175], np.float32) * m
    if "hujan" in efek:
        y0 = int((t * 1400) % H)
        m = p["hujan"][y0:y0 + H][..., None] * 0.4
        a = a * (1 - m) + 200 * m
    a *= p["vignet"]
    a += p["bintik"][(i // 6) % 4].repeat(2, 0).repeat(2, 1)[..., None]
    return np.clip(a, 0, 255).astype(np.uint8)


# ---------- teks ----------
def _bungkus(teks, font, maks_lebar):
    dr = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    baris, cur = [], ""
    for k in teks.split():
        t = (cur + " " + k).strip()
        if dr.textlength(t, font=font) <= maks_lebar: cur = t
        else: baris.append(cur); cur = k
    baris.append(cur); return baris


def _potong_subtitle(teks, maks=9):
    kata = teks.split(); hasil = []
    while kata:
        hasil.append(" ".join(kata[:maks])); kata = kata[maks:]
    if len(hasil) > 1 and len(hasil[-1].split()) <= 2:
        ekor = hasil.pop(); hasil[-1] += " " + ekor
    return hasil


def _tulis_tengah(dr, teks, font, y, isi=(245, 240, 235), garis=6, jarak=64, lebar=1560):
    for i, b in enumerate(_bungkus(teks, font, lebar)):
        x = (W - dr.textlength(b, font=font)) / 2
        dr.text((x, y + i * jarak), b, font=font, fill=isi, stroke_width=garis, stroke_fill=(0, 0, 0))


_CACHE_LENCANA = {}


def _lencana(judul):
    """Kotak kecil di pojok kiri atas berisi judul cerita."""
    if judul in _CACHE_LENCANA:
        return _CACHE_LENCANA[judul]
    x0, y0, lebar = 48, 40, 640
    f_kat = _font("Montserrat-ExtraBold.ttf", 22); f_jdl = _font("Montserrat-ExtraBold.ttf", 34)
    dr0 = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    baris = _bungkus(judul.upper().strip(), f_jdl, lebar - 64)[:2]
    tinggi = 58 + 44 * len(baris) + 14
    lap = Image.new("RGBA", (W, y0 + tinggi + 10), (0, 0, 0, 0)); dr = ImageDraw.Draw(lap)
    dr.rounded_rectangle([x0, y0, x0 + lebar, y0 + tinggi], 14, fill=(18, 18, 26, 215))
    dr.rounded_rectangle([x0, y0, x0 + 8, y0 + tinggi], 4, fill=ORANYE + (255,))
    dr.ellipse([x0 + 28, y0 + 20, x0 + 40, y0 + 32], fill=ORANYE + (255,))
    dr.text((x0 + 50, y0 + 14), "CERITA HOROR", font=f_kat, fill=ORANYE + (255,))
    for k, b in enumerate(baris):
        dr.text((x0 + 28, y0 + 50 + 44 * k), b, font=f_jdl, fill=(245, 243, 248, 255))
    _CACHE_LENCANA[judul] = (lap, y0 + tinggi)
    return _CACHE_LENCANA[judul]


def _cctv_teks(img, t, y0):
    f = _font("DejaVuSansMono-Bold.ttf", 32)
    dr = ImageDraw.Draw(img)
    detik = 48 * 60 + 10 + int(t)
    dr.text((60, y0), f"2026-11-02  23:{detik // 60 % 60:02d}:{detik % 60:02d}", font=f, fill=(220, 240, 230))
    if int(t * 2) % 2 == 0:
        dr.ellipse([W - 190, y0 + 4, W - 164, y0 + 30], fill=MERAH)
    dr.text((W - 145, y0), "REC", font=f, fill=(220, 240, 230))
    dr.text((60, y0 + 44), "CAM 03", font=f, fill=(220, 240, 230))


# ---------- render ----------
def _ffmpeg_tulis(path):
    return subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                             "-crf", "26", "-maxrate", "3500k", "-bufsize", "7M", "-g", str(FPS * 2),
                             "-pix_fmt", "yuv420p", path], stdin=subprocess.PIPE)


def _render_adegan(pipe, adegan, gambar, dur, judul, idx):
    big = _siapkan(gambar)
    efek = adegan.get("efek", [])
    f_sub = _font("Montserrat-ExtraBold.ttf", 50)
    potongan = _potong_subtitle(adegan["narasi"])
    bobot = [len(p) for p in potongan]; total_b = sum(bobot)
    narr = dur - JEDA
    batas, acc = [], 0
    for b in bobot:
        acc += b; batas.append(narr * acc / total_b)
    n = int(round(dur * FPS))
    gerak = adegan.get("gerak", "zoom_in")
    potong = dur * 0.55 if dur >= 8 else None          # adegan panjang: lebar lalu mendekat
    kaget = "kaget" in efek
    petir = "petir" in adegan.get("suara", [])
    lap, bawah_judul = _lencana(judul)
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
        a = _efek_array(np.asarray(img), efek, t, i + idx * 1000)
        if kaget and t < 0.7:
            a = _distorsi(a, 14 * (1 - t / 0.7), t)
        guncang = 0
        if "shake" in efek: guncang = 4
        if kaget and t < 0.6: guncang = 16
        if guncang:
            a = np.roll(np.roll(a, random.randint(-guncang, guncang), 0), random.randint(-guncang, guncang), 1)
        if (kaget and t < 0.12) or (petir and (0.3 < t < 0.38 or 0.5 < t < 0.56)):
            a = np.clip(a.astype(np.int16) + 90, 0, 255).astype(np.uint8)   # kilatan lebih lembut dari video pendek
        fade = min(1.0, t / 0.5, (dur - t) / 0.5)                           # pindah adegan pelan, tenang
        if fade < 1: a = (a * max(fade, 0)).astype(np.uint8)
        img = Image.fromarray(a)
        img.paste(lap, (0, 0), lap)
        dr = ImageDraw.Draw(img)
        if "cctv" in efek: _cctv_teks(img, t, int(bawah_judul) + 20)
        k = next((j for j, b in enumerate(batas) if t < b), None)
        if k is not None:
            _tulis_tengah(dr, potongan[k], f_sub, H - 200,
                          isi=(255, 222, 89) if kaget else (245, 240, 235))
        pipe.stdin.write(np.asarray(img).tobytes())


def _render_buka(pipe, judul):
    f_besar = _font("Anton-Regular.ttf", 120); f_kecil = _font("Montserrat-ExtraBold.ttf", 40)
    for i in range(int(AWAL * FPS)):
        t = i / FPS
        a = min(1, t / 1.2, (AWAL - t) / 0.8)
        img = Image.new("RGB", (W, H), (5, 5, 6)); dr = ImageDraw.Draw(img)
        oranye = tuple(int(c * a) for c in ORANYE); putih = tuple(int(c * a) for c in (240, 235, 230))
        _tulis_tengah(dr, "JANGAN NONTON SENDIRI", f_kecil, 330, isi=oranye, garis=0, jarak=56)
        _tulis_tengah(dr, judul.upper(), f_besar, 430, isi=putih, garis=0, jarak=140, lebar=1700)
        _tulis_tengah(dr, "Cerita pengantar malam. Dengarkan dengan tenang.", f_kecil, 800, isi=putih, garis=0, jarak=56)
        pipe.stdin.write(_efek_array(np.asarray(img), [], t, i).tobytes())


def _render_tutup(pipe, judul):
    f_besar = _font("Anton-Regular.ttf", 150); f_kecil = _font("Montserrat-ExtraBold.ttf", 44)
    for i in range(int(AKHIR * FPS)):
        t = i / FPS
        a = min(1, t / 0.8, (AKHIR - t) / 1.0)
        img = Image.new("RGB", (W, H), (5, 5, 6)); dr = ImageDraw.Draw(img)
        merah = tuple(int(c * a) for c in MERAH); putih = tuple(int(c * a) for c in (235, 228, 222))
        _tulis_tengah(dr, "TAMAT", f_besar, 300, isi=merah, garis=0, jarak=170)
        _tulis_tengah(dr, f"“{judul}”", f_kecil, 520, isi=putih, garis=0, jarak=60)
        _tulis_tengah(dr, "Subscribe dan tulis di komentar: bagian mana yang paling bikin merinding?",
                      f_kecil, 680, isi=putih, garis=0, jarak=60)
        pipe.stdin.write(_efek_array(np.asarray(img), [], t, i).tobytes())


def _kerjakan(args):
    """Merender satu bagian (jalan di proses terpisah supaya semua inti CPU terpakai)."""
    jenis, idx, adegan, gambar, dur, judul, tujuan = args
    tmp = tujuan + ".tmp.mp4"
    pipe = _ffmpeg_tulis(tmp)
    if jenis == "buka": _render_buka(pipe, judul)
    elif jenis == "tutup": _render_tutup(pipe, judul)
    else: _render_adegan(pipe, adegan, gambar, dur, judul, idx)
    pipe.stdin.close(); pipe.wait()
    if pipe.returncode != 0: raise RuntimeError(f"render {jenis} {idx} gagal")
    os.replace(tmp, tujuan)
    return tujuan


def buat_video(adegan_list, gambar_list, durasi_list, audio, keluar, judul, kerja, proses=None):
    """Render video panjang. durasi_list = durasi tiap adegan (narasi + JEDA). audio = hasil panjang_suara.campur."""
    tugas = [("buka", 0, None, None, AWAL, judul, os.path.join(kerja, "a_buka.mp4"))]
    for idx, (a, g, d) in enumerate(zip(adegan_list, gambar_list, durasi_list)):
        tugas.append(("adegan", idx, a, g, d, judul, os.path.join(kerja, f"b_adegan_{idx:03d}.mp4")))
    tugas.append(("tutup", 0, None, None, AKHIR, judul, os.path.join(kerja, "c_tutup.mp4")))
    proses = proses or max(1, min(4, os.cpu_count() or 1))
    if proses == 1:
        bagian = [_kerjakan(t) for t in tugas]
    else:
        with Pool(proses) as kolam:
            bagian = []
            for k, p in enumerate(kolam.imap(_kerjakan, tugas), 1):
                bagian.append(p)
                if k % 5 == 0 or k == len(tugas): print(f"  render video: {k}/{len(tugas)} bagian", flush=True)
    daftar = os.path.join(kerja, "daftar.txt")
    with open(daftar, "w") as f:
        for b in bagian: f.write(f"file '{os.path.abspath(b)}'\n")
    gabung = os.path.join(kerja, "gabung.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", daftar,
                    "-c", "copy", gabung], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", gabung, "-i", audio, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "copy", "-shortest", "-movflags", "+faststart", keluar], check=True)
    return keluar
