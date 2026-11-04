"""Gambar untuk MODE VIDEO PANJANG: gambar acuan wajah per tokoh + adegan 16:9 dengan beberapa tokoh sekaligus.
Memakai ulang gambar.py (alamat API, gaya gambar, pembaca hasil). gambar.py asli TIDAK diubah.

Bila filter Cloudflare menolak gambar (HTTP 400, kode 3030 "Your output has been flagged"), urutannya:
  1) prompt asli  2) prompt asli + seed lain  3) prompt lebih halus  4) prompt lebih halus + seed lain.
Kalau masih ditolak, panjang_main.py memakai gambar adegan sebelumnya supaya video tetap jadi."""
import io, os, re, time
import requests
from PIL import Image
import gambar as G

LEBAR, TINGGI = 1344, 768
MAKS_ACUAN = 3
JEDA_ULANG = 8               # detik; dikali nomor percobaan untuk galat jaringan/server (bukan penolakan filter)
_BANYAK_ACUAN_OK = True      # jadi False bila generator menolak lebih dari satu gambar acuan
_HALUSKAN_DULU = False       # jadi True setelah ada penolakan: prompt rawan langsung dihaluskan (hemat kuota)


class Ditolak(Exception):
    """Gambar ditolak filter keamanan Cloudflare (bukan galat jaringan; mengulang prompt yang sama sia-sia)."""


# Kata yang hampir pasti memicu filter pada gambar sosok berpakaian basah/terbuka. SELALU diganti.
SELALU_HALUS = [
    (r"\bclinging to (?:her|his|their) bod(?:y|ies)\b", "hanging loosely"),
    (r"\bclinging to (?:her|his|their) skin\b", "hanging loosely"),
]
# Pelembut tambahan untuk percobaan ulang: tetap seram, tidak vulgar/grafis.
HALUS = [
    (r"\bsoaked\b", "damp"),
    (r"\bbare-chested\b", "in a plain sleeveless undershirt,"),
    (r"\bshirtless\b", "in a plain sleeveless undershirt"),
    (r"\bdeathly pale grey skin\b", "very pale skin"),
    (r"\bdeathly pale\b", "very pale"),
    (r"\bhollow dark eyes\b", "sad dark eyes"),
    (r"\bTerrifying close-up reveal of the supernatural entity\b", "Eerie close-up of the supernatural spirit"),
    (r"\bterrifying and uncanny\b", "eerie and uncanny"),
    (r"\bterrifying\b", "eerie"),
    (r"\bdemonic\b", "shadowy"),
    (r"\bmenacing\b", "ominous"),
    (r"\bgreedy\b", "intense"),
    (r"\bcruel\b", "cold"),
]
SUFIKS_HALUS = " Fully clothed and modest, spooky but non-graphic, atmospheric ghost-story illustration."


def selalu_halus(p):
    for pola, ganti in SELALU_HALUS:
        p = re.sub(pola, ganti, p, flags=re.I)
    return p


def halus(p):
    for pola, ganti in HALUS:
        p = re.sub(pola, ganti, p, flags=re.I)
    return p + SUFIKS_HALUS


def _kirim(prompt, path, width, height, acuan, seed):
    form = {"prompt": (None, prompt), "width": (None, str(width)), "height": (None, str(height)),
            "seed": (None, str(seed))}
    for i, p in enumerate(acuan):
        im = Image.open(p).convert("RGB"); im.thumbnail((500, 500))
        buf = io.BytesIO(); im.save(buf, "PNG")
        form[f"input_image_{i}"] = (f"ref{i}.png", buf.getvalue(), "image/png")
    r = requests.post(G._url(), headers={"Authorization": f"Bearer {os.environ['CLOUDFLARE_API_TOKEN']}"},
                      files=form, timeout=180)
    if r.status_code >= 400:
        if r.status_code == 400 and ("3030" in r.text or "flagged" in r.text.lower()):
            raise Ditolak(r.text[:200])
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    G._ambil_gambar(r).save(path)


def buat_gambar(prompt, path, acuan=(), width=LEBAR, height=TINGGI, seed=7):
    global _BANYAK_ACUAN_OK
    acuan = [a for a in acuan if a and os.path.exists(a)][:MAKS_ACUAN]
    urutan = [acuan]
    if len(acuan) > 1:
        urutan = [acuan, acuan[:1]] if _BANYAK_ACUAN_OK else [acuan[:1]]
    err = None
    for k, daftar in enumerate(urutan):
        for coba in range(3):
            try:
                _kirim(prompt, path, width, height, daftar, seed)
                if k == 1:
                    _BANYAK_ACUAN_OK = False
                    print("  CATATAN: generator tidak menerima banyak gambar acuan; sisanya hanya lewat deskripsi tokoh", flush=True)
                return path
            except Ditolak:
                raise                      # ditolak filter: jangan diulang dengan prompt/seed yang sama
            except Exception as e:
                err = e; time.sleep(JEDA_ULANG * (coba + 1))
    raise RuntimeError(f"Cloudflare gagal membuat gambar: {err}")


def _dengan_ulang(nama, p, path, acuan, width, height, seed):
    """Coba beberapa variasi bila ditolak filter. Mengembalikan tingkat yang berhasil: 'asli' | 'seed' | 'halus'."""
    global _HALUSKAN_DULU
    p = selalu_halus(p)
    hp = halus(p)
    percobaan = [("asli", p, seed), ("seed", p, seed + 101), ("halus", hp, seed + 202), ("halus", hp, seed + 303)]
    if _HALUSKAN_DULU and hp != p + SUFIKS_HALUS:        # prompt ini memuat kata rawan: langsung versi halus
        percobaan = percobaan[2:]
    ditolak = 0
    for tingkat, teks, benih in percobaan:
        try:
            buat_gambar(teks, path, acuan=acuan, width=width, height=height, seed=benih)
            if ditolak:
                print(f"  {nama}: lolos setelah {ditolak} penolakan (tingkat: {tingkat})", flush=True)
            return tingkat
        except Ditolak:
            ditolak += 1
            _HALUSKAN_DULU = True
            print(f"  {nama}: ditolak filter Cloudflare (percobaan {ditolak}/{len(percobaan)}, tingkat: {tingkat})", flush=True)
    raise Ditolak(f"{nama}: ditolak filter pada semua percobaan")


def potret_tokoh(deskripsi, path, seed):
    """Gambar acuan wajah satu tokoh (dipakai ulang di semua adegan yang memuat tokoh itu)."""
    p = f"{G.GAYA}. Character portrait, waist-up, facing camera, plain dark background. {deskripsi}"
    return _dengan_ulang(os.path.basename(path), p, path, (), 512, 512, seed)


def adegan_lebar(a, daftar_tokoh, path, seed):
    """daftar_tokoh = [(deskripsi, path_acuan), ...] untuk tokoh yang tampil di adegan ini.
    Mengembalikan tingkat keberhasilan ('asli'/'seed'/'halus'); melempar Ditolak bila semua percobaan ditolak."""
    p = f"{G.GAYA}. Wide cinematic 16:9 landscape shot. {a['gambar']}"
    if "kaget" in a.get("efek", []):
        p += (" Terrifying close-up reveal of the supernatural entity, clearly visible, unsettling and uncanny,"
              " deep shadows, stylized horror, no blood, no gore.")
    if a.get("petunjuk"):
        p += (" Include the described hidden creepy detail subtly in the background or a reflection,"
              " small and easy to miss at first glance but clearly there when you look closely.")
    acuan = []
    for i, (deskripsi, ref) in enumerate(daftar_tokoh[:MAKS_ACUAN]):
        # deskripsi SELALU ditulis identik, gambar acuan menjaga wajah bila generator mendukung
        p += f" Character {i + 1}: {deskripsi}."
        if ref and _BANYAK_ACUAN_OK or (ref and i == 0):
            acuan.append(ref)
            p += f" Keep the same face, hair and clothing as the person in image {len(acuan) - 1}."
    return _dengan_ulang(os.path.basename(path), p, path, acuan, LEBAR, TINGGI, seed)
