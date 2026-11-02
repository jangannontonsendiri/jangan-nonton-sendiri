"""Jangan Nonton Sendiri — membuat satu part video cerita horor setiap kali dijalankan.

Alur: (cerita baru bila perlu) -> gambar -> suara -> video -> simpan di folder hasil/.
MOCK=1 untuk uji tanpa internet (gambar & suara palsu).
"""
import json, os, random, re, shutil, sys
from datetime import datetime, timezone, timedelta

import suara, video

AKAR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(AKAR, "state.json")
TEMA = os.path.join(AKAR, "tema.json")
CERITA_DIR = os.path.join(AKAR, "cerita")
HASIL = os.path.join(AKAR, "hasil")
MOCK = os.environ.get("MOCK") == "1"
WIB = timezone(timedelta(hours=7))


def baca(path, bawaan):
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError:
        return bawaan


def tulis(path, data):
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)


def slug(teks):
    return re.sub(r"[^a-z0-9]+", "-", teks.lower()).strip("-")[:40] or "cerita"


def pilih_tema(state):
    semua = baca(TEMA, [])
    sisa = [t for t in semua if t not in state.get("tema_terpakai", [])]
    if not sisa:
        state["tema_terpakai"] = []; sisa = semua
    return random.choice(sisa)


def cerita_mock():
    return baca(os.path.join(AKAR, "contoh", "cerita_contoh.json"), None)


def siapkan_cerita(state):
    if state.get("cerita") and state.get("part_berikut", 1) <= 3:
        return baca(os.path.join(CERITA_DIR, state["cerita"], "cerita.json"), None)
    if MOCK:
        c = cerita_mock(); tema = "contoh"
    else:
        import cerita
        tema = os.environ.get("TEMA") or pilih_tema(state)
        print(f"Menulis cerita baru, tema: {tema}")
        c = cerita.buat_cerita(tema)
    cid = datetime.now(WIB).strftime("%Y%m%d-%H%M") + "-" + slug(c["judul"])
    os.makedirs(os.path.join(CERITA_DIR, cid), exist_ok=True)
    c["tema"] = tema
    tulis(os.path.join(CERITA_DIR, cid, "cerita.json"), c)
    state.update({"cerita": cid, "part_berikut": 1})
    state.setdefault("tema_terpakai", []).append(tema)
    return c


def gambar_palsu(path, teks):
    from PIL import Image, ImageDraw
    if os.environ.get("MOCK_GAMBAR"):
        Image.open(os.environ["MOCK_GAMBAR"]).convert("RGB").resize((768, 1344)).save(path); return
    im = Image.new("RGB", (768, 1344), (18, 40, 44)); dr = ImageDraw.Draw(im)
    for k in range(0, 1344, 64): dr.line([(0, k), (768, k + 300)], fill=(30, 60, 64), width=3)
    dr.rectangle([234, 300, 534, 1000], outline=(240, 180, 90), width=8)
    dr.text((40, 40), teks[:60], fill=(255, 255, 255))
    im.save(path)


def suara_palsu(path, kata):
    import subprocess
    d = max(2.5, kata * 0.38)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=180:duration={d}",
                    "-c:a", "libmp3lame", path], check=True)


def tebak_dialog(a):
    """Siapa yang bicara di kalimat bertanda kutip (cerita lama belum punya kolom 'dialog')."""
    if isinstance(a.get("dialog"), dict):
        return a["dialog"]
    teks = a["narasi"].lower()
    seram = "kaget" in a.get("efek", []) or re.search(r"bisik|ghaib|gaib|suara itu|dingin|serak|melengking|sosok|hantu", teks)
    return {"siapa": "hantu" if seram else "orang", "kelamin": "pria" if re.search(r"pria|bapak|laki|mas |pak ", teks) else "wanita"}


def main():
    state = baca(STATE, {})
    c = siapkan_cerita(state)
    cid, nomor = state["cerita"], state["part_berikut"]
    part = c["part"][nomor - 1]
    folder = os.path.join(CERITA_DIR, cid)
    kerja = os.path.join(AKAR, "kerja", f"{cid}-p{nomor}")
    os.makedirs(kerja, exist_ok=True); os.makedirs(HASIL, exist_ok=True)
    print(f"Membuat: {c['judul']} — Part {nomor}/3 ({len(part['adegan'])} adegan)")

    # 1. tokoh utama (sekali per cerita, disimpan supaya part berikutnya wajahnya sama)
    ref = os.path.join(folder, "tokoh.png")
    if not os.path.exists(ref):
        if MOCK: gambar_palsu(ref, "tokoh")
        else:
            import gambar; gambar.gambar_tokoh(c["tokoh_utama"], ref)

    # 2. gambar, 3. suara
    gambar_list, audio_list, dur_list = [], [], []
    import zlib
    benih = zlib.crc32(cid.encode()) % 100000
    for i, a in enumerate(part["adegan"]):
        g = os.path.join(kerja, f"g{i:02d}.png"); au = os.path.join(kerja, f"n{i:02d}.mp3")
        if MOCK:
            gambar_palsu(g, a["gambar"]); suara_palsu(au, len(a["narasi"].split()))
        else:
            import gambar
            gambar.gambar_adegan(a, c["tokoh_utama"], ref, g, seed=benih + nomor * 100 + i)
            suara.narasi(a["narasi"], au, tebak_dialog(a))
        gambar_list.append(g); audio_list.append(au)
        dur_list.append(suara.durasi(au) + video.JEDA)
        print(f"  adegan {i + 1}: gambar & suara siap ({dur_list[-1]:.1f} dtk)")

    # 4. efek suara + musik latar + video
    t, kaget, kejadian = 0.0, [], []
    for a, d in zip(part["adegan"], dur_list):
        if "suara" in a:   # dipilih penulis cerita
            a["suara"] = [x for x in a["suara"] if x in suara.SFX]
        else:              # cerita lama tanpa pilihan suara: tebak dari narasi
            a["suara"] = suara.tebak_sfx(a["narasi"])
        teks = (a["narasi"] + " " + a.get("gambar", "")).lower()
        if re.search(r"hujan|gerimis|\brain", teks) and "hujan" not in a.get("efek", []):
            a.setdefault("efek", []).append("hujan")
        if "kaget" in a.get("efek", []): kaget.append(t)
        for j, jenis in enumerate(a["suara"]):
            kejadian.append((t + 0.25 + j * 1.2, jenis))
        t += d
    # suara HP cukup sekali per part
    hp = [k for k, (_, j) in enumerate(kejadian) if j == "getar_hp"]
    for k in reversed(hp[1:]): kejadian.pop(k)
    musik = os.path.join(kerja, "musik.wav")
    suasana = c.get("suasana") or suara.tebak_suasana(c)
    suara.musik_latar(musik, t + video.AKHIR, kaget, kejadian, suasana)
    print(f"  efek suara: {[k for _, k in kejadian]} | suasana: {suasana}")
    nama = f"{cid}-part{nomor}"
    keluar = os.path.join(HASIL, nama + ".mp4")
    video.buat_video(part["adegan"], gambar_list, audio_list, dur_list, musik, keluar,
                     part.get("judul_layar") or c["judul"].upper(), nomor, 3, c["judul"], kerja)

    tag = " ".join(part.get("hashtag", [])[:6]) or "#ceritahoror #horor #ceritaseram"
    caption = f"{c['judul']} — Part {nomor}/3\n\n{part.get('caption', '')}\n\n{tag}"
    with open(os.path.join(HASIL, nama + ".txt"), "w", encoding="utf-8") as f: f.write(caption)
    print(f"SELESAI: {keluar} ({t + video.AKHIR:.1f} detik)")

    state["part_berikut"] = nomor + 1
    if nomor >= 3: state["cerita"] = None
    state["terakhir"] = {"video": nama, "waktu": datetime.now(WIB).isoformat(timespec="minutes")}
    tulis(STATE, state)
    if not os.environ.get("SIMPAN_KERJA"): shutil.rmtree(kerja, ignore_errors=True)


if __name__ == "__main__":
    main()
