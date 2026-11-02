# Jangan Nonton Sendiri

Sistem otomatis pembuat video cerita horor animasi 2D (vertikal 1080×1920) untuk TikTok, Instagram Reels, dan YouTube Shorts.

Setiap kali dijalankan, sistem membuat **satu part** video. Satu cerita = 3 part bersambung.

## Alur
1. **Cerita** — Gemini mengembangkan konsep di `konsep.json` (dipakai berurutan) menjadi naskah 3 part. Kalau konsep habis, memakai tema acak dari `tema.json`.
2. **Gambar** — Cloudflare Workers AI membuat gambar gaya komik horor (tokoh utama dijaga tetap sama lewat `cerita/<id>/tokoh.png`).
3. **Suara** — narator Edge TTS (`id-ID-ArdiNeural`) + musik latar mencekam buatan sendiri.
4. **Video** — gerakan kamera (zoom/geser), efek (lampu berkedip, guncangan, CCTV, kabut, kaget), subtitle, kartu "BERSAMBUNG"/"TAMAT".

## Menjalankan
GitHub → tab **Actions** → **Buat video horor** → **Run workflow**. Video bisa diunduh di bagian **Artifacts** setelah selesai.

## Secrets yang dibutuhkan
- `GEMINI_API_KEY`
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

## Uji tanpa internet
`MOCK=1 python main.py` — memakai cerita contoh, gambar dan suara palsu.
