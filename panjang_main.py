"""Jangan Nonton Sendiri — MODE VIDEO PANJANG (YouTube, mendatar 1920x1080, sekitar 12-13 menit).

Terpisah dari main.py: tidak membaca/menulis state.json, tidak membuat folder cerita/, tidak mengunggah ke mana pun.
Cerita diberikan sebagai file JSON (lihat panjang/README.md):
    python panjang_main.py cerita_panjang/nama-cerita.json
MOCK=1 untuk uji tanpa internet (gambar & suara palsu): MOCK=1 python panjang_main.py
"""
import json, os, re, shutil, sys, zlib

import gambar as gambar_modul          # dipakai ulang: pembuat gambar (Cloudflare) + gaya gambar
import suara                           # dipakai ulang: narator, suara tokoh, musik, efek suara
import panjang_suara, panjang_video

AKAR = os.path.dirname(os.path.abspath(__file__))
HASIL = os.path.join(AKAR, "hasil_panjang")
KERJA_DIR = os.path.join(AKAR, "kerja_panjang")
CONTOH = os.path.join(AKAR, "panjang", "contoh.json")
MOCK = os.environ.get("MOCK") == "1"
GERAK = ["zoom_in", "zoom_out", "pan_up", "pan_down", "pan_left", "pan_right"]
EFEK = ["flicker", "shake", "cctv", "kabut", "kaget", "hujan"]
FOKUS = ["atas", "tengah", "bawah", "kiri", "kanan"]
LEBAR, TINGGI = 1344, 768     # ukuran gambar 16:9 yang diminta ke generator gambar


def slug(teks):
    return re.sub(r"[^a-z0-9]+", "-", teks.lower()).strip("-")[:40] or "cerita"


def muat_cerita(path):
    with open(path, encoding="utf-8") as f:
        c = json.load(f)
    adegan = c.get("adegan")
    if not adegan and c.get("part"):          # cerita 3-part lama juga boleh: semua part disambung
        adegan = [a for p in c["part"] for a in p["adegan"]]
    if not adegan:
        raise ValueError("file cerita tidak punya daftar 'adegan'")
    for a in adegan:
        if not a.get("narasi") or not a.get("gambar"):
            raise ValueError("setiap adegan wajib punya 'narasi' dan 'gambar'")
        if a.get("gerak") not in GERAK: a["gerak"] = GERAK[len(a["narasi"]) % len(GERAK)]
        a["efek"] = [e for e in a.get("efek", []) if e in EFEK]
        a["tokoh"] = bool(a.get("tokoh")); a["petunjuk"] = bool(a.get("petunjuk"))
        if "suara" in a: a["suara"] = [x for x in a["suara"] if x in suara.SFX][:2]
        else: a["suara"] = suara.tebak_sfx(a["narasi"])
        if a.get("fokus") not in FOKUS: a["fokus"] = "tengah"
        teks = (a["narasi"] + " " + a["gambar"]).lower()
        if re.search(r"hujan|gerimis|\brain", teks) and "hujan" not in a["efek"]:
            a["efek"].append("hujan")
    c["adegan"] = adegan
    c.setdefault("judul", "Cerita Horor")
    c.setdefault("tokoh_utama", "Indonesian person, short black hair, plain dark clothes")
    return c


def tebak_dialog(a):
    """Siapa yang bicara di kalimat bertanda kutip bila penulis tidak mengisi 'dialog'."""
    if isinstance(a.get("dialog"), dict):
        return a["dialog"]
    teks = a["narasi"].lower()
    seram = "kaget" in a.get("efek", []) or re.search(r"bisik|ghaib|gaib|suara itu|dingin|serak|melengking|sosok|hantu", teks)
    return {"siapa": "hantu" if seram else "orang", "kelamin": "pria" if re.search(r"pria|bapak|laki|mas |pak ", teks) else "wanita"}


def gambar_palsu(path, teks, ukuran=(LEBAR, TINGGI)):
    from PIL import Image, ImageDraw
    w, h = ukuran
    im = Image.new("RGB", (w, h), (18, 40, 44)); dr = ImageDraw.Draw(im)
    for k in range(0, w, 64): dr.line([(k, 0), (k + 300, h)], fill=(30, 60, 64), width=3)
    dr.rectangle([w * 0.38, h * 0.2, w * 0.62, h * 0.85], outline=(240, 180, 90), width=8)
    dr.text((40, 40), teks[:80], fill=(255, 255, 255))
    im.save(path)


def suara_palsu(path, kata):
    import subprocess
    d = max(2.5, kata * 0.45)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=180:duration={d}",
                    "-c:a", "libmp3lame", path], check=True)


def gambar_adegan_lebar(a, tokoh_utama, ref_tokoh, path, seed):
    """Sama seperti gambar.gambar_adegan, tetapi komposisi mendatar 16:9."""
    p = f"{gambar_modul.GAYA}. Wide cinematic 16:9 landscape shot. {a['gambar']}"
    if "kaget" in a.get("efek", []):
        p += (" Terrifying close-up reveal of the supernatural entity, clearly visible, unsettling and uncanny,"
              " deep shadows, stylized horror, no blood, no gore.")
    if a.get("petunjuk"):
        p += (" Include the described hidden creepy detail subtly in the background or a reflection,"
              " small and easy to miss at first glance but clearly there when you look closely.")
    ref = None
    if a.get("tokoh"):
        p += f" The main character: {tokoh_utama}. Keep the same face, hair and clothing as the person in image 0."
        ref = ref_tokoh
    return gambar_modul.buat_gambar(p, path, width=LEBAR, height=TINGGI, referensi=ref, seed=seed)


def main():
    path = (sys.argv[1] if len(sys.argv) > 1 else "") or os.environ.get("FILE_CERITA", "")
    if not path:
        if not MOCK: sys.exit("Beri file cerita: python panjang_main.py cerita_panjang/nama.json (atau MOCK=1 untuk uji)")
        path = CONTOH
    c = muat_cerita(path if os.path.isabs(path) else os.path.join(AKAR, path))
    adegan = c["adegan"]
    cid = slug(c["judul"])
    kerja = os.path.join(KERJA_DIR, cid)
    shutil.rmtree(kerja, ignore_errors=True)
    os.makedirs(kerja); os.makedirs(HASIL, exist_ok=True)
    print(f"Membuat video panjang: {c['judul']} ({len(adegan)} adegan){' [MOCK]' if MOCK else ''}")

    # 1. tokoh utama: pakai gambar tokoh yang sudah ada (tokoh_ref) supaya wajahnya sama, atau buat baru
    ref = os.path.join(kerja, "tokoh.png")
    acuan = c.get("tokoh_ref")
    if acuan and os.path.exists(os.path.join(AKAR, acuan)):
        shutil.copy(os.path.join(AKAR, acuan), ref)
    elif MOCK:
        gambar_palsu(ref, "tokoh", (512, 512))
    else:
        gambar_modul.gambar_tokoh(c["tokoh_utama"], ref)

    # 2. gambar + 3. suara tiap adegan
    benih = zlib.crc32(cid.encode()) % 100000
    gambar_list, audio_list, dur_list = [], [], []
    for i, a in enumerate(adegan):
        g = os.path.join(kerja, f"g{i:03d}.png"); au = os.path.join(kerja, f"n{i:03d}.mp3")
        if MOCK:
            gambar_palsu(g, a["gambar"]); suara_palsu(au, len(a["narasi"].split()))
        else:
            gambar_adegan_lebar(a, c["tokoh_utama"], ref, g, seed=benih + i)
            panjang_suara.narasi(a["narasi"], au, tebak_dialog(a))
        gambar_list.append(g); audio_list.append(au)
        dur_list.append(suara.durasi(au) + panjang_video.JEDA)
        if (i + 1) % 5 == 0 or i == len(adegan) - 1:
            print(f"  adegan {i + 1}/{len(adegan)}: gambar & suara siap", flush=True)

    total = panjang_video.AWAL + sum(dur_list) + panjang_video.AKHIR
    menit = total / 60
    print(f"Perkiraan durasi video: {int(menit)} menit {int(total % 60)} detik")
    if not MOCK and not 10 <= menit <= 15:
        print("PERINGATAN: durasi di luar target 12-13 menit. Tambah/kurangi adegan atau panjang narasi.")

    # 4. efek suara + musik latar (geser waktunya karena ada kartu pembuka)
    t, kaget, kejadian = panjang_video.AWAL, [], []
    for a, d in zip(adegan, dur_list):
        if "kaget" in a["efek"]: kaget.append(t)
        for j, jenis in enumerate(a["suara"]):
            kejadian.append((t + 0.25 + j * 1.2, jenis))
        t += d
    hp = [k for k, (_, j) in enumerate(kejadian) if j == "getar_hp"]       # suara HP secukupnya
    for k in reversed(hp[2:]): kejadian.pop(k)
    musik = os.path.join(kerja, "musik.wav")
    suasana = c.get("suasana") if c.get("suasana") in suara.SUASANA else suara.tebak_suasana({"part": [{"adegan": adegan}]})
    suara.musik_latar(musik, total + 1, kaget, kejadian, suasana)
    print(f"  efek suara: {len(kejadian)} kejadian | suasana: {suasana}")
    audio = os.path.join(kerja, "audio.m4a")
    panjang_suara.campur(audio_list, dur_list, panjang_video.AWAL, panjang_video.AKHIR, musik, audio)

    # 5. video
    nama = f"{cid}-panjang"
    keluar = os.path.join(HASIL, nama + ".mp4")
    panjang_video.buat_video(adegan, gambar_list, dur_list, audio, keluar, c["judul"], kerja)

    tag = " ".join(c.get("hashtag", [])[:8]) or "#ceritahoror #horor #ceritaseram #jangannontonsendiri"
    deskripsi = c.get("deskripsi") or f"{c['judul']} — cerita horor animasi pengantar tidur dari Jangan Nonton Sendiri."
    with open(os.path.join(HASIL, nama + ".txt"), "w", encoding="utf-8") as f:
        f.write(f"{c['judul']}\n\n{deskripsi}\n\n{tag}\n")
    print(f"SELESAI: {keluar} ({total:.0f} detik)")
    if not os.environ.get("SIMPAN_KERJA"): shutil.rmtree(kerja, ignore_errors=True)


if __name__ == "__main__":
    main()
