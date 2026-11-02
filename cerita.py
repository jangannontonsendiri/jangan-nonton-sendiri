"""Menulis cerita horor orisinal 3 part memakai Gemini."""
import json, os, random, re, time
import requests

MODELS = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-flash-latest"]
GERAK = ["zoom_in", "zoom_out", "pan_up", "pan_down", "pan_left", "pan_right"]
EFEK = ["flicker", "shake", "cctv", "kaget", "kabut", "hujan"]
SFX = ["langkah", "pintu", "ketukan", "petir", "bisikan", "detak", "getar_hp", "kaca", "pukulan"]
FOKUS = ["atas", "tengah", "bawah", "kiri", "kanan"]
SUASANA = ["hujan", "angin", "sunyi", "jangkrik"]

PROMPT = """Kamu penulis cerita horor Indonesia untuk video pendek animasi.

Tulis SATU cerita horor ORISINAL bertema: "{tema}".
Aturan isi:
- Cerita harus baru dan karanganmu sendiri. Jangan menyalin atau meniru alur cerita kreator/channel mana pun.
- Latar Indonesia, sudut pandang orang pertama ("aku"), seperti orang biasa yang sedang curhat pengalaman nyata.
- HARUS terasa NATURAL dan RELATE: situasi sehari-hari yang pernah dialami banyak orang (pulang kerja lembur,
  ngekos, jaga warung, nugas tengah malam, nunggu ojol, mudik, ronda). Detail kecil yang akrab
  (bunyi kipas angin, notifikasi HP, bau melati, lampu teras kedip, suara motor lewat) membuat cerita terasa nyata.
- Bahasa obrolan santai sehari-hari (boleh "nggak", "banget", "kok", "sih"), BUKAN bahasa buku. Kalimat pendek.
  Hindari kata berlebihan seperti "amat", "luar biasa", "sangat mencekam".
- Tidak ada nama orang terkenal, tidak ada tempat nyata yang spesifik, tidak ada adegan sadis berlebihan.
- Cerita dibagi menjadi 3 part. Part 1 dan 2 WAJIB diakhiri cliffhanger yang bikin penasaran. Part 3 berisi klimaks dan akhir yang menghantui.
- Setiap part berisi 11 sampai 14 adegan PENDEK supaya video cepat berganti gambar. Narasi tiap adegan 7-15 kata. Total narasi per part 130-180 kata.
- Adegan pertama setiap part adalah hook yang langsung bikin penasaran (part 2 dan 3 boleh mulai dengan "Lanjutan..." singkat).

Untuk setiap part isi "judul_layar": judul besar yang tampil di atas video, HURUF KAPITAL, 2-4 kata,
sangat memancing rasa penasaran dan takut, sesuai isi part itu (contoh gaya: "MBAH YANG GENTAYANGAN",
"JANGAN BUKA JENDELA", "TAMU JAM DUA MALAM"). Jangan membocorkan akhir cerita.

Untuk setiap adegan isi:
- "narasi": teks yang dibacakan narator (Bahasa Indonesia).
- "gambar": deskripsi visual dalam BAHASA INGGRIS untuk generator gambar: komposisi, lokasi, pencahayaan, apa yang terlihat. Jangan tulis gaya gambar (sudah ditambahkan otomatis). Jangan ada tulisan/teks di gambar.
  PENTING: gambar harus MEMPERLIHATKAN hal seram yang sedang diceritakan di narasi itu, jangan disembunyikan.
  Kalau narasi menyebut hantu, wajah mengerikan, senyum yang terlalu lebar, kaki melayang, mata kosong,
  tunjukkan itu dengan jelas (close-up untuk momen paling seram). Buat makhluknya menyeramkan dan ganjil,
  tapi JANGAN sadis: tanpa darah berceceran, tanpa luka terbuka, tanpa potongan tubuh. Seram, bukan jijik.
- "tokoh": true jika tokoh utama terlihat di gambar.
- "gerak": salah satu dari {gerak}.
- "efek": daftar (boleh kosong) dari {efek}. "kaget" hanya untuk 1-2 momen paling menakutkan per part. "cctv" untuk adegan rekaman kamera. "hujan" bila adegan di luar ruangan saat hujan.
- "suara": daftar efek suara (boleh kosong, maks 2) dari {sfx} yang COCOK dengan yang terjadi di adegan itu
  (contoh: ada yang berjalan mendekat = "langkah", pintu dibuka = "pintu", ada yang mengetuk = "ketukan",
  ketakutan = "detak"). Pakai di banyak adegan supaya terasa nyata.
  "getar_hp" HANYA untuk notifikasi / pesan / telepon MASUK, maksimal 1 kali per part. Sekadar membuka atau
  melihat HP TIDAK diberi suara.
- Kalimat yang DIUCAPKAN tokoh lain (hantu atau orang) WAJIB ditulis di dalam tanda kutip ganda di narasi,
  contoh: Lalu suara itu berbisik, "Kenapa nggak balik badan?"
- "dialog": isi HANYA jika narasi berisi kalimat dalam tanda kutip:
  {{"siapa": "hantu" atau "orang", "kelamin": "pria" atau "wanita"}}. Kalau tidak ada, isi null.
- "fokus": bagian gambar yang paling penting untuk di-close-up, salah satu dari {fokus}.

Kembalikan HANYA JSON dengan bentuk:
{{
  "judul": "judul cerita singkat (maks 5 kata)",
  "suasana": "suara latar sepanjang cerita, salah satu dari {suasana}",
  "tokoh_utama": "deskripsi fisik tokoh utama dalam bahasa Inggris (usia, wajah, rambut, pakaian khas) yang akan dipakai di semua gambar",
  "part": [
    {{"judul_layar": "JUDUL BESAR", "caption": "caption media sosial 1-2 kalimat yang bikin penasaran", "hashtag": ["#ceritahoror", "..."], "adegan": [{{"narasi": "...", "gambar": "...", "tokoh": true, "gerak": "zoom_in", "efek": [], "suara": [], "fokus": "tengah", "dialog": null}}]}}
  ]
}}
"""


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
            a["suara"] = [x for x in a.get("suara", []) if x in SFX][:2]
            if a.get("fokus") not in FOKUS:
                a["fokus"] = "tengah"
    if c.get("suasana") not in SUASANA:
        c.pop("suasana", None)
    return c


def buat_cerita(tema):
    key = os.environ["GEMINI_API_KEY"]
    prompt = PROMPT.format(tema=tema, gerak=GERAK, efek=EFEK, sfx=SFX, fokus=FOKUS, suasana=SUASANA)
    for _ in range(3):
        try:
            return _rapikan(_panggil(prompt, key))
        except ValueError:
            continue
    raise RuntimeError("Gemini tidak menghasilkan cerita yang valid")
