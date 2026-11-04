"""Jangan Nonton Sendiri — MODE VIDEO PANJANG (YouTube, mendatar 1920x1080, sekitar 12-13 menit).

Terpisah dari main.py: tidak membaca/menulis state.json, tidak membuat folder cerita/, tidak mengunggah ke mana pun.
Cerita diberikan sebagai file JSON (lihat panjang/README.md):
    python panjang_main.py cerita_panjang/nama-cerita.json
MOCK=1 untuk uji tanpa internet (gambar & suara palsu): MOCK=1 python panjang_main.py
"""
import json, os, re, shutil, sys, zlib

import suara                           # dipakai ulang: narator, suara tokoh, musik, efek suara
import panjang_gambar, panjang_suara, panjang_video   # versi video panjang; memakai gambar.py & suara.py di dalamnya

AKAR = os.path.dirname(os.path.abspath(__file__))
HASIL = os.path.join(AKAR, "hasil_panjang")
KERJA_DIR = os.path.join(AKAR, "kerja_panjang")
SIMPAN_DIR = os.path.join(AKAR, "simpanan_panjang")   # gambar yang sudah jadi; diunggah sebagai Artifacts walau proses gagal
CONTOH = os.path.join(AKAR, "panjang", "contoh.json")
MOCK = os.environ.get("MOCK") == "1"
GERAK = ["zoom_in", "zoom_out", "pan_up", "pan_down", "pan_left", "pan_right"]
EFEK = ["flicker", "shake", "cctv", "kabut", "kaget", "hujan"]
FOKUS = ["atas", "tengah", "bawah", "kiri", "kanan"]
LEBAR, TINGGI = panjang_gambar.LEBAR, panjang_gambar.TINGGI


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
        a["petunjuk"] = bool(a.get("petunjuk"))
        if "suara" in a: a["suara"] = [x for x in a["suara"] if x in suara.SFX][:2]
        else: a["suara"] = suara.tebak_sfx(a["narasi"])
        if a.get("fokus") not in FOKUS: a["fokus"] = "tengah"
        teks = (a["narasi"] + " " + a["gambar"]).lower()
        if re.search(r"hujan|gerimis|\brain", teks) and "hujan" not in a["efek"]:
            a["efek"].append("hujan")
    c["adegan"] = adegan
    c.setdefault("judul", "Cerita Horor")
    c.setdefault("tokoh_utama", "Indonesian person, short black hair, plain dark clothes")
    # daftar tokoh: [{"id","nama","deskripsi","suara","ref"(opsional)}]; tanpa daftar = satu tokoh "utama"
    daftar = c.get("tokoh")
    if isinstance(daftar, list) and daftar and isinstance(daftar[0], dict):
        tokoh = {t["id"]: t for t in daftar}
    else:
        tokoh = {"utama": {"id": "utama", "nama": "tokoh utama", "deskripsi": c["tokoh_utama"], "ref": c.get("tokoh_ref")}}
    for t in tokoh.values():
        if t.get("suara") and t["suara"] not in panjang_suara.JENIS:
            raise ValueError(f"suara tokoh '{t['id']}' tidak dikenal: {t['suara']} (pilihan: {list(panjang_suara.JENIS)})")
    for a in adegan:
        v = a.get("tokoh")
        ids = [next(iter(tokoh))] if v is True else [x for x in v] if isinstance(v, list) else []
        for x in ids:
            if x not in tokoh: raise ValueError(f"adegan memakai tokoh '{x}' yang tidak ada di daftar tokoh")
        a["tokoh"] = ids[:panjang_gambar.MAKS_ACUAN]
    c["_tokoh"] = tokoh
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


_PERCOBAAN_PALSU = {}


def _kirim_palsu(prompt, path, width, height, acuan, seed):
    """Pengganti panggilan Cloudflare untuk MOCK. Simulasi (nomor adegan mulai 1):
    MOCK_DITOLAK="3:1,5:99" -> adegan 3 ditolak filter 1x lalu lolos, adegan 5 selalu ditolak
    MOCK_GAGAL_DI="4"       -> adegan 4 gagal karena galat jaringan (proses berhenti, gambar lain tetap tersimpan)"""
    nama = os.path.basename(path)
    m = re.match(r"g(\d+)\.png", nama)
    nomor = int(m.group(1)) + 1 if m else None
    _PERCOBAAN_PALSU[nama] = _PERCOBAAN_PALSU.get(nama, 0) + 1
    if nomor is not None and str(nomor) == os.environ.get("MOCK_GAGAL_DI", ""):
        raise RuntimeError("simulasi: jaringan putus")
    tolak = dict(x.split(":") for x in os.environ.get("MOCK_DITOLAK", "").split(",") if ":" in x)
    if nomor is not None and _PERCOBAAN_PALSU[nama] <= int(tolak.get(str(nomor), 0)):
        raise panjang_gambar.Ditolak("simulasi: Your output has been flagged")
    gambar_palsu(path, (nama + " " + prompt[-60:]) if nomor is not None else nama, (width, height))


def suara_palsu(path, kata):
    import subprocess
    d = max(2.5, kata * 0.45)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=180:duration={d}",
                    "-c:a", "libmp3lame", path], check=True)


def jenis_dialog(a, tokoh):
    """Pilih suara untuk kalimat dalam tanda kutip: dari tokoh yang berbicara, atau tebakan seperti video pendek."""
    d = a.get("dialog")
    if isinstance(d, dict):
        if d.get("tokoh") in tokoh and tokoh[d["tokoh"]].get("suara"):
            return tokoh[d["tokoh"]]["suara"]
        if d.get("suara") in panjang_suara.JENIS:
            return d["suara"]
    return "narator"          # tokoh sampingan / tidak jelas: dibacakan dengan suara narator biasa


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
    # gambar disimpan terpisah dari folder kerja (yang dihapus): tetap ada bila proses gagal, dan dipakai ulang bila diulang
    simpan = os.path.join(SIMPAN_DIR, cid + ("-mock" if MOCK else ""))
    os.makedirs(simpan, exist_ok=True)
    status_path = os.path.join(simpan, "status.json")
    try:
        with open(status_path, encoding="utf-8") as f: status = json.load(f)
    except (FileNotFoundError, ValueError):
        status = {}
    def catat(nama, nilai):
        status[nama] = nilai
        with open(status_path, "w", encoding="utf-8") as f: json.dump(status, f, ensure_ascii=False, indent=1)
    if MOCK:
        panjang_gambar._kirim = _kirim_palsu; panjang_gambar.JEDA_ULANG = 0
    print(f"Membuat video panjang: {c['judul']} ({len(adegan)} adegan){' [MOCK]' if MOCK else ''}")

    # 1. gambar acuan wajah tiap tokoh (supaya wajah sama di semua adegan); boleh pakai gambar yang sudah ada ('ref')
    benih = zlib.crc32(cid.encode()) % 100000
    tokoh = c["_tokoh"]
    refs = {}
    for n, (tid, t) in enumerate(tokoh.items()):
        ref = os.path.join(simpan, f"tokoh_{tid}.png")
        if os.path.exists(ref):
            pass                                              # sudah ada dari percobaan sebelumnya
        elif t.get("ref") and os.path.exists(os.path.join(AKAR, t["ref"])):
            shutil.copy(os.path.join(AKAR, t["ref"]), ref)
        else:
            try:
                panjang_gambar.potret_tokoh(t["deskripsi"], ref, seed=benih + 7000 + n)
            except panjang_gambar.Ditolak:
                print(f"  PERINGATAN: gambar acuan '{tid}' ditolak filter; adegannya memakai deskripsi saja", flush=True)
                ref = None
        refs[tid] = ref
    print(f"  gambar acuan {len(refs)} tokoh siap: {', '.join(tokoh)}", flush=True)

    # 2. gambar + 3. suara tiap adegan
    gambar_list, audio_list, dur_list = [], [], []
    dipakai_ulang, pengganti = 0, []
    for i, a in enumerate(adegan):
        nama_g = f"g{i:03d}.png"
        g = os.path.join(simpan, nama_g); au = os.path.join(kerja, f"n{i:03d}.mp3")
        if os.path.exists(g) and status.get(nama_g) != "pengganti":
            dipakai_ulang += 1                                # sudah jadi sebelumnya: tidak memakai kuota lagi
        else:
            try:
                tingkat = panjang_gambar.adegan_lebar(a, [(tokoh[x]["deskripsi"], refs[x]) for x in a["tokoh"]], g, seed=benih + i)
                catat(nama_g, tingkat)
            except panjang_gambar.Ditolak:
                # semua percobaan ditolak: pakai gambar adegan sebelumnya supaya video tetap jadi
                sebelum = gambar_list[-1] if gambar_list else None
                if sebelum: shutil.copy(sebelum, g)
                else: gambar_palsu(g, "adegan " + str(i + 1), (LEBAR, TINGGI))
                catat(nama_g, "pengganti"); pengganti.append(i + 1)
                print(f"  PERINGATAN: adegan {i + 1} ditolak filter, memakai gambar adegan sebelumnya", flush=True)
        if MOCK: suara_palsu(au, len(a["narasi"].split()))
        else: panjang_suara.narasi(a["narasi"], au, jenis_dialog(a, tokoh), narator=c.get("narator", "laki"))
        gambar_list.append(g); audio_list.append(au)
        dur_list.append(suara.durasi(au) + panjang_video.JEDA)
        if (i + 1) % 5 == 0 or i == len(adegan) - 1:
            print(f"  adegan {i + 1}/{len(adegan)}: gambar & suara siap", flush=True)
    if dipakai_ulang: print(f"  {dipakai_ulang} gambar dipakai ulang dari simpanan (tidak memakai kuota Cloudflare)")
    if pengganti:
        print(f"PERINGATAN: {len(pengganti)} adegan memakai gambar pengganti (ditolak filter): {pengganti}. "
              f"Jalankan ulang dengan simpanan gambar ini untuk mencoba adegan tersebut lagi.")

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
