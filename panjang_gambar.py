"""Gambar untuk MODE VIDEO PANJANG: gambar acuan wajah per tokoh + adegan 16:9 dengan beberapa tokoh sekaligus.
Memakai ulang gambar.py (alamat API, gaya gambar, pembaca hasil). gambar.py asli TIDAK diubah."""
import io, os, time
import requests
from PIL import Image
import gambar as G

LEBAR, TINGGI = 1344, 768
MAKS_ACUAN = 3
_BANYAK_ACUAN_OK = True      # jadi False bila generator menolak lebih dari satu gambar acuan


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
            except Exception as e:
                err = e; time.sleep(8 * (coba + 1))
    raise RuntimeError(f"Cloudflare gagal membuat gambar: {err}")


def potret_tokoh(deskripsi, path, seed):
    """Gambar acuan wajah satu tokoh (dipakai ulang di semua adegan yang memuat tokoh itu)."""
    p = f"{G.GAYA}. Character portrait, waist-up, facing camera, plain dark background. {deskripsi}"
    return buat_gambar(p, path, width=512, height=512, seed=seed)


def adegan_lebar(a, daftar_tokoh, path, seed):
    """daftar_tokoh = [(deskripsi, path_acuan), ...] untuk tokoh yang tampil di adegan ini."""
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
    return buat_gambar(p, path, acuan=acuan, seed=seed)
