"""Menulis cerita horor orisinal 3 part memakai Gemini."""
import json, os, random, re, time
import requests

MODELS = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-flash-latest"]
GERAK = ["zoom_in", "zoom_out", "pan_up", "pan_down", "pan_left", "pan_right"]
EFEK = ["flicker", "shake", "cctv", "kaget", "kabut"]

PROMPT = """Kamu penulis cerita horor Indonesia untuk video pendek animasi.

Tulis SATU cerita horor ORISINAL bertema: "{tema}".
Aturan isi:
- Cerita harus baru dan karanganmu sendiri. Jangan menyalin atau meniru alur cerita kreator/channel mana pun.
- Latar Indonesia, sudut pandang orang pertama ("aku"), bahasa santai sehari-hari, kalimat pendek dan mencekam.
- Tidak ada nama orang terkenal, tidak ada tempat nyata yang spesifik, tidak ada adegan sadis berlebihan.
- Cerita dibagi menjadi 3 part. Part 1 dan 2 WAJIB diakhiri cliffhanger yang bikin penasaran. Part 3 berisi klimaks dan akhir yang menghantui.
- Setiap part berisi 8 sampai 10 adegan. Narasi tiap adegan 12-22 kata. Total narasi per part 140-190 kata.
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
- "efek": daftar (boleh kosong) dari {efek}. "kaget" hanya untuk 1-2 momen paling menakutkan per part. "cctv" untuk adegan rekaman kamera.

Kembalikan HANYA JSON dengan bentuk:
{{
  "judul": "judul cerita singkat (maks 5 kata)",
  "tokoh_utama": "deskripsi fisik tokoh utama dalam bahasa Inggris (usia, wajah, rambut, pakaian khas) yang akan dipakai di semua gambar",
  "part": [
    {{"judul_layar": "JUDUL BESAR", "caption": "caption media sosial 1-2 kalimat yang bikin penasaran", "hashtag": ["#ceritahoror", "..."], "adegan": [{{"narasi": "...", "gambar": "...", "tokoh": true, "gerak": "zoom_in", "efek": []}}]}}
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
    return c


def buat_cerita(tema):
    key = os.environ["GEMINI_API_KEY"]
    prompt = PROMPT.format(tema=tema, gerak=GERAK, efek=EFEK)
    for _ in range(3):
        try:
            return _rapikan(_panggil(prompt, key))
        except ValueError:
            continue
    raise RuntimeError("Gemini tidak menghasilkan cerita yang valid")
