# Mode video panjang (YouTube, 16:9)

Terpisah dari sistem video pendek. Dijalankan manual lewat workflow **Buat video panjang**
(tab Actions → Run workflow). Hasilnya hanya disimpan di Artifacts, tidak diunggah otomatis.

Cerita ditaruh sebagai file JSON di folder `cerita_panjang/`, lalu nama filenya diisi di kolom
`file_cerita` saat menjalankan workflow. Bentuknya sama dengan `contoh.json` di folder ini:

- `judul`, `suasana` (hujan/angin/sunyi/jangkrik), `tokoh_utama` (deskripsi Inggris), `deskripsi`, `hashtag`
- `tokoh_ref` (opsional): gambar tokoh yang sudah ada, mis. `cerita/<id>/tokoh.png`, agar wajah tokoh sama
- `adegan`: daftar adegan, tiap adegan berisi `narasi`, `gambar` (Inggris), `tokoh`, `petunjuk`, `gerak`,
  `efek`, `suara`, `fokus`, `dialog` — sama seperti video pendek.
  Kalimat tokoh lain ditulis dalam tanda kutip ganda supaya dibacakan dengan suara berbeda.

Beberapa tokoh dengan wajah tetap dan suara berbeda:

- `narator`: `"perempuan"` atau `"laki"` (bawaan `"laki"`).
- `tokoh`: daftar `{"id", "nama", "deskripsi" (Inggris, dipakai identik di semua adegan), "suara", "ref" (opsional)}`.
  Tiap tokoh dibuatkan satu gambar acuan wajah. Tokoh yang sama dengan penampilan berbeda (mis. hantu) dibuat sebagai tokoh terpisah.
  `suara` salah satu dari: `pria`, `perempuan`, `perempuan_jawa`, `hantu_pria`, `hantu_perempuan`, `hantu_perempuan_jawa`.
  `..._jawa` bawaannya memakai suara Indonesia terpilih (suara Jawa jv-ID dinilai kurang bagus; `SUARA_JAWA=1` untuk mencoba lagi).
- di tiap adegan: `"tokoh": ["id1", "id2"]` (maks 3) dan, bila ada kalimat dalam tanda kutip, `"dialog": {"tokoh": "id"}`.

Gambar ditolak filter Cloudflare (kode 3030) dan melanjutkan setelah gagal:

- Gambar yang ditolak dicoba ulang: seed lain, lalu kata-kata prompt yang lebih halus. Kalau tetap ditolak, adegan itu memakai gambar adegan sebelumnya supaya video tetap jadi (ada peringatan di log).
- Semua gambar yang sudah jadi disimpan sebagai Artifacts bernama `gambar-panjang` walau proses gagal.
- Untuk melanjutkan tanpa membuat ulang: jalankan workflow lagi dan isi `pakai_gambar_dari_run` dengan nomor run sebelumnya
  (angka di akhir alamat run). Gambar yang sudah jadi dipakai ulang (tanpa kuota), adegan yang tadinya diganti dicoba lagi.
- Uji simulasi tanpa internet: `MOCK=1 MOCK_DITOLAK="3:1,5:99" python panjang_main.py` (adegan 3 ditolak sekali, adegan 5 selalu ditolak)
  atau `MOCK_GAGAL_DI=4` (adegan 4 gagal karena jaringan).

Target durasi 12–13 menit: sekitar 60–75 adegan dengan narasi 18–28 kata per adegan.

Uji tanpa internet: `MOCK=1 python panjang_main.py` (atau centang `mock` di workflow).
