"""Membuat gambar gaya komik horor memakai Cloudflare Workers AI (kuota gratis harian)."""
import base64, io, os, time
import requests
from PIL import Image

MODEL = "@cf/black-forest-labs/flux-2-klein-4b"
GAYA = ("dark 2D horror graphic-novel illustration, bold black ink outlines, detailed crosshatching, "
        "gritty textures, cold teal and blue-green color palette with small warm orange lamp light, "
        "cinematic lighting, eerie atmosphere, horror webtoon style, no text, no letters, no watermark")


def _url():
    return f"https://api.cloudflare.com/client/v4/accounts/{os.environ['CLOUDFLARE_ACCOUNT_ID']}/ai/run/{MODEL}"


def _ambil_gambar(resp):
    ct = resp.headers.get("content-type", "")
    if "application/json" in ct:
        data = resp.json()
        if not data.get("success", True):
            raise RuntimeError(str(data.get("errors")))
        img = (data.get("result") or {}).get("image") or data.get("image")
        return Image.open(io.BytesIO(base64.b64decode(img))).convert("RGB")
    return Image.open(io.BytesIO(resp.content)).convert("RGB")


def buat_gambar(prompt, path, width=768, height=1344, referensi=None, seed=None):
    form = {"prompt": (None, prompt), "width": (None, str(width)), "height": (None, str(height))}
    if seed is not None:
        form["seed"] = (None, str(seed))
    if referensi and os.path.exists(referensi):
        ref = Image.open(referensi).convert("RGB")
        ref.thumbnail((500, 500))
        buf = io.BytesIO(); ref.save(buf, "PNG")
        form["input_image_0"] = ("ref.png", buf.getvalue(), "image/png")
    err = None
    for coba in range(4):
        try:
            r = requests.post(_url(), headers={"Authorization": f"Bearer {os.environ['CLOUDFLARE_API_TOKEN']}"},
                              files=form, timeout=180)
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
            _ambil_gambar(r).save(path)
            return path
        except Exception as e:
            err = e
            time.sleep(8 * (coba + 1))
    raise RuntimeError(f"Cloudflare gagal membuat gambar: {err}")


def gambar_tokoh(deskripsi, path):
    p = f"{GAYA}. Character portrait, waist-up, facing camera, plain dark background. {deskripsi}"
    return buat_gambar(p, path, width=512, height=512, seed=7)


def gambar_adegan(adegan, tokoh_utama, ref_tokoh, path, seed):
    p = f"{GAYA}. Vertical cinematic shot. {adegan['gambar']}"
    if "kaget" in adegan.get("efek", []):
        p += (" Terrifying close-up reveal of the supernatural entity, clearly visible, unsettling and uncanny,"
              " deep shadows, stylized horror, no blood, no gore.")
    ref = None
    if adegan.get("tokoh"):
        p += f" The main character: {tokoh_utama}. Keep the same face, hair and clothing as the person in image 0."
        ref = ref_tokoh
    return buat_gambar(p, path, referensi=ref, seed=seed)
