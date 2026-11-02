"""Menulis cerita horor orisinal 3 part memakai Gemini."""
import json, os, random, re, time
import requests

MODELS = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-flash-latest"]
GERAK = ["zoom_in", "zoom_out", "pan_up", "pan_down", "pan_left", "pan_right"]
EFEK = ["flicker", "shake", "cctv", "kaget", "kabut", "hujan"]
SFX = ["langkah", "pintu", "ketukan", "petir", "bisikan", "detak", "getar_hp", "kaca", "pukulan"]
FOKUS = ["atas", "tengah", "bawah", "kiri", "kanan"]
SUASANA = ["hujan", "angin", "sunyi", "jangkrik"]

PROMPT = """Kamu penulis naskah cerita horor Indonesia untuk video pendek animasi (TikTok/Reels/Shorts).

{sumber}

RESEP CERITA (wajib diikuti):
- Detik pertama = HOOK berupa aturan, larangan, atau keanehan yang langsung bikin penasaran. Jangan buka dengan
  suasana ("Malam itu hujan..."). Part 2 dan 3 dibuka dengan kalimat yang langsung menyambung ketegangan
  part sebelumnya (boleh diawali "Lanjutan..." yang sangat singkat).
- Tokoh utama AKTIF: dia mengambil keputusan (mengecek, menjawab, membuka, kabur) dan keputusan itu ada akibatnya.
- Taruh detail kecil di awal yang tampak sepele tapi jadi kunci twist di part 3.
- Part 1 dan 2 berakhir di kalimat reveal/cliffhanger yang konkret (sesuatu terlihat/terdengar/terungkap),
  bukan rasa takut yang samar. Part 3 = klimaks + twist yang tidak klise + kalimat penutup yang menggantung.
- Hindari klise: "ternyata cuma mimpi", "ternyata dia sudah meninggal" sebagai twist utama.
- Terasa NATURAL dan RELATE: seperti orang biasa curhat pengalamannya, situasi sehari-hari, detail akrab
  (notifikasi WA, kipas angin, motor lewat, lampu teras kedip).
- Bahasa obrolan santai (boleh "nggak", "banget", "kok", "sih"), kalimat pendek. Hindari "amat", "luar biasa".
- Tidak ada nama orang terkenal, tidak ada tempat nyata yang spesifik, tidak sadis.
- Setiap part 11-14 adegan PENDEK. Narasi tiap adegan 7-15 kata. Total narasi per part 130-180 kata.

INTERAKTIF:
- Setiap part punya SATU adegan "petunjuk": true, yaitu detail seram tersembunyi di gambar yang mudah terlewat
  pada tontonan pertama (sosok samar di latar, pantulan di cermin/kaca, mata di celah). Narasinya TIDAK
  menyebut detail itu. Tulis detail tersebut di deskripsi "gambar" adegan itu.
- Setiap part punya "pertanyaan": satu kalimat pendek untuk penonton (dijawab di komen), maks 12 kata.

Untuk setiap adegan isi:
- "narasi": teks yang dibacakan narator (Bahasa Indonesia).
- "gambar": deskripsi visual dalam BAHASA INGGRIS untuk generator gambar: komposisi, lokasi, pencahayaan, apa yang terlihat. Jangan tulis gaya gambar (sudah ditambahkan otomatis). Jangan ada tulisan/teks di gambar.
  Gambar harus MEMPERLIHATKAN hal seram yang sedang diceritakan, jangan disembunyikan (close-up untuk momen
  paling seram). Makhluknya menyeramkan dan ganjil, tapi tanpa darah, luka terbuka, atau potongan tubuh.
- "tokoh": true jika tokoh utama terlihat di gambar.
- "petunjuk": true hanya untuk adegan detail tersembunyi (satu per part).
- "gerak": salah satu dari {gerak}.
- "efek": daftar (boleh kosong) dari {efek}. "kaget" hanya untuk 1-2 momen paling menakutkan per part. "cctv" untuk adegan rekaman kamera. "hujan" bila adegan di luar ruangan saat hujan.
- "suara": daftar efek suara (boleh kosong, maks 2) dari {sfx} yang COCOK dengan kejadian di adegan itu
  (berjalan mendekat = "langkah", pintu dibuka = "pintu", mengetuk = "ketukan", ketakutan = "detak").
  "getar_hp" HANYA untuk notifikasi / pesan / telepon MASUK, maksimal 1 kali per part.
- Kalimat yang DIUCAPKAN tokoh lain WAJIB di dalam tanda kutip ganda di narasi, contoh: Ibu berbisik, "Jawab dari sini."
- "dialog": isi HANYA jika narasi berisi kalimat dalam tanda kutip:
  {{"siapa": "hantu" atau "orang", "kelamin": "pria" atau "wanita"}}. Kalau tidak ada, isi null.
- "fokus": bagian gambar yang paling penting untuk di-close-up, salah satu dari {fokus}.

Kembalikan HANYA JSON dengan bentuk:
{{
  "judul": "judul cerita (maks 5 kata)",
  "suasana": "suara latar sepanjang cerita, salah satu dari {suasana}",
  "tokoh_utama": "deskripsi fisik tokoh utama dalam bahasa Inggris (usia, wajah, rambut, pakaian khas) yang akan dipakai di semua gambar",
  "part": [
    {{"pertanyaan": "...", "caption": "caption media sosial 1-2 kalimat yang bikin penasaran tanpa spoiler", "hashtag": ["#ceritahoror", "..."], "adegan": [{{"narasi": "...", "gambar": "...", "tokoh": true, "petunjuk": false, "gerak": "zoom_in", "efek": [], "suara": [], "fokus": "tengah", "dialog": null}}]}}
  ]
}}
"""

SUMBER_KONSEP = """Kembangkan KONSEP berikut menjadi naskah 3 part. Pertahankan hook, alur tiap part, cliffhanger,
twist, dan penutupnya (jangan diganti), tapi kembangkan menjadi adegan-adegan yang hidup dengan detail sehari-hari.
Judul cerita: "{judul}"
Hook: {hook}
Part 1: {part1}
Part 2: {part2}
Part 3: {part3}
Detail tersembunyi: {petunjuk}
Pertanyaan untuk penonton: Part 1 = "{q1}", Part 2 = "{q2}". Part 3 buat sendiri (ajak penonton menebak/berbagi)."""

SUMBER_TEMA = """Tulis SATU cerita horor ORISINAL bertema: "{tema}". Cerita harus karanganmu sendiri,
jangan menyalin atau meniru alur cerita kreator/channel mana pun."""


def _panggil(prompt, key):
    err = None
    for model in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for coba in range(3):
            try:
                r = requests.post(url, params={"key": key}, timeout=180, json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"responseMimeType": "application/json", "temperature": 1.0},
                })
                if r.status_code == 404:
                    break
                r.raise_for_status()
                teks = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(re.sub(r"^```(json)?|```$", "", teks.strip()))
            except Exception as e:  # coba lagi
                err = e
                time.sleep(5 * (coba + 1))
    raise RuntimeError(f"Gemini gagal: {err}")


def _rapikan(c):
    if len(c.get("part", [])) < 3:
        raise ValueError("cerita kurang dari 3 part")
    c["part"] = c["part"][:3]
    for p in c["part"]:
        if len(p.get("adegan", [])) < 5:
            raise ValueError("adegan terlalu sedikit")
        for a in p["adegan"]:
            if a.get("gerak") not in GERAK:
                a["gerak"] = random.choice(GERAK)
            a["efek"] = [e for e in a.get("efek", []) if e in EFEK]
            a["tokoh"] = bool(a.get("tokoh"))
            a["petunjuk"] = bool(a.get("petunjuk"))
            a["suara"] = [x for x in a.get("suara", []) if x in SFX][:2]
            if a.get("fokus") not in FOKUS:
                a["fokus"] = "tengah"
    if c.get("suasana") not in SUASANA:
        c.pop("suasana", None)
    return c


def buat_cerita(tema=None, konsep=None):
    key = os.environ["GEMINI_API_KEY"]
    if konsep:
        q = (konsep.get("pertanyaan") or ["", ""]) + ["", ""]
        sumber = SUMBER_KONSEP.format(q1=q[0], q2=q[1], **{k: konsep.get(k, "") for k in
                                      ["judul", "hook", "part1", "part2", "part3", "petunjuk"]})
    else:
        sumber = SUMBER_TEMA.format(tema=tema)
    prompt = PROMPT.format(sumber=sumber, gerak=GERAK, efek=EFEK, sfx=SFX, fokus=FOKUS, suasana=SUASANA)
    for _ in range(3):
        try:
            c = _rapikan(_panggil(prompt, key))
            if konsep:
                c["judul"] = konsep["judul"]
                for p, q in zip(c["part"], konsep.get("pertanyaan", [])):
                    p["pertanyaan"] = q
            return c
        except ValueError:
            continue
    raise RuntimeError("Gemini tidak menghasilkan cerita yang valid")
