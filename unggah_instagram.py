"""Mengunggah video terbaru ke Instagram Reels (Instagram API with Instagram Login).

Instagram mengambil video dari URL publik, jadi workflow lebih dulu menaruh video
di GitHub Release sementara (VIDEO_URL), lalu menghapusnya setelah selesai.
"""
import json, os, sys, time
import requests

AKAR = os.path.dirname(os.path.abspath(__file__))


def _api(tok):
    # token Instagram Login (IGAA...) -> graph.instagram.com ; token Facebook (EAA...) -> graph.facebook.com
    return "https://graph.facebook.com/v23.0" if tok.startswith("EAA") else "https://graph.instagram.com/v23.0"


def _cek(r, apa):
    if r.status_code != 200:
        raise RuntimeError(f"Instagram gagal {apa}: {r.status_code} {r.text[:400]}")
    return r.json()


USERNAME = os.environ.get("IG_USERNAME", "jangan.nontonsendiri").lower()


def cari_akun(tok, uid_simpan=""):
    """Token Facebook (EAA) butuh ID 'Instagram Business Account', bukan ID yang tampil di halaman Meta.
    Cari otomatis lewat beberapa jalur; kembalikan (api, id)."""
    api = _api(tok)
    if not tok.startswith("EAA"):
        return api, uid_simpan
    fb = "https://graph.facebook.com/v23.0"; ketemu = []
    def get(path, **params):
        params["access_token"] = tok
        r = requests.get(f"{fb}/{path}", params=params, timeout=60)
        return r.json() if r.status_code == 200 else {"_error": r.text[:200]}
    # 0) baca isi token: izin apa saja & akun mana yang diizinkan
    dbg = get("debug_token", input_token=tok).get("data", {})
    print("Instagram: izin di token ->", dbg.get("scopes"))
    for gs in dbg.get("granular_scopes", []):
        print(f"  {gs.get('scope')}: {gs.get('target_ids', 'semua')}")
        if gs.get("scope") in ("instagram_content_publish", "instagram_basic",
                               "instagram_business_content_publish", "instagram_business_basic"):
            for t in gs.get("target_ids", []):
                d0 = get(t, fields="id,username")
                if d0.get("username"): ketemu.append((d0["id"], d0["username"]))
    # 0b) token milik Halaman: 'me' adalah Halaman itu sendiri
    dp = get("me", fields="name,instagram_business_account{id,username}")
    if dp.get("instagram_business_account"):
        ig = dp["instagram_business_account"]; ketemu.append((ig["id"], ig.get("username", "")))
    # 1) lewat Halaman Facebook yang terhubung
    d = get("me/accounts", fields="name,instagram_business_account{id,username}")
    for pg in d.get("data", []):
        ig = pg.get("instagram_business_account")
        if ig: ketemu.append((ig["id"], ig.get("username", "")))
    # 2) lewat business portfolio
    b = get("me/businesses", fields="name")
    for bz in b.get("data", []):
        for kolom in ["owned_instagram_accounts", "instagram_business_accounts", "instagram_accounts"]:
            d2 = get(f"{bz['id']}/{kolom}", fields="id,username")
            for ig in d2.get("data", []):
                ketemu.append((ig["id"], ig.get("username", "")))
    # 3) ID yang disimpan, kalau ternyata valid
    if uid_simpan:
        d3 = get(uid_simpan, fields="id,username")
        if d3.get("username"): ketemu.append((d3["id"], d3["username"]))
    unik = list(dict.fromkeys(ketemu))
    print("Instagram: akun yang terlihat oleh token ->", [u for _, u in unik] or "TIDAK ADA")
    for i, u in unik:
        if u.lower() == USERNAME:
            return fb, i
    if len(unik) == 1:
        return fb, unik[0][0]
    raise RuntimeError(f"Akun {USERNAME} tidak ditemukan lewat token. Detail: me/accounts={d} me/businesses={b}")


def daftar_token():
    return [(n, os.environ.get(n, "").strip()) for n in ["IG_PAGE_TOKEN", "IG_ACCESS_TOKEN"]
            if os.environ.get(n, "").strip()]


def unggah(info, video_url):
    err = None
    for nama, tok in daftar_token():
        try:
            return _unggah(info, video_url, tok, nama)
        except Exception as e:
            err = e; print(f"Instagram: {nama} gagal -> {str(e)[:200]}")
    raise RuntimeError(f"Semua token Instagram gagal: {err}")


def _unggah(info, video_url, tok, nama):
    API, uid = cari_akun(tok, os.environ.get("IG_USER_ID", "").strip())
    print(f"Instagram: memakai {nama} di {API.split('/')[2]}, akun id ...{uid[-4:]}")
    caption = info["teks_lengkap"][:2150]
    c = _cek(requests.post(f"{API}/{uid}/media", timeout=120, data={
        "media_type": "REELS", "video_url": video_url, "caption": caption,
        "share_to_feed": "true", "access_token": tok}), "membuat container")
    cid = c["id"]; print(f"Instagram: container {cid} dibuat, menunggu video diproses...")
    for _ in range(60):                       # maks ~10 menit
        time.sleep(10)
        s = _cek(requests.get(f"{API}/{cid}", timeout=60, params={
            "fields": "status_code,status", "access_token": tok}), "cek status")
        st = s.get("status_code")
        if st == "FINISHED": break
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram menolak video: {s}")
    else:
        raise RuntimeError("Instagram terlalu lama memproses video")
    p = _cek(requests.post(f"{API}/{uid}/media_publish", timeout=120, data={
        "creation_id": cid, "access_token": tok}), "publish")
    print(f"Instagram: terposting (media id {p['id']})")
    return p["id"]


TES_GAMBAR = "https://raw.githubusercontent.com/jangannontonsendiri/jangan-nonton-sendiri/main/contoh/tes.jpg"


def cek(nama, tok):
    print(f"\n=== {nama} ===")
    api, uid = cari_akun(tok, os.environ.get("IG_USER_ID", "").strip())
    r = requests.get(f"{api}/{uid}", params={"fields": "username", "access_token": tok}, timeout=60)
    print("akun:", r.json().get("username", r.text[:150]))
    d = requests.get(f"{api}/debug_token", params={"input_token": tok, "access_token": tok}, timeout=60).json()
    exp = d.get("data", {}).get("expires_at")
    print("kedaluwarsa:", "TIDAK PERNAH" if exp == 0 else (time.strftime("%d-%m-%Y", time.gmtime(exp)) if exp else "tidak diketahui"))
    # uji izin posting: buat container gambar TANPA dipublikasikan (hilang sendiri dalam 24 jam)
    c = requests.post(f"{api}/{uid}/media", timeout=120, data={
        "image_url": TES_GAMBAR, "caption": "tes", "access_token": tok})
    ok = c.status_code == 200
    print("izin posting:", "OK" if ok else f"GAGAL {c.text[:200]}")
    return ok


if __name__ == "__main__" and os.environ.get("CEK_SAJA"):
    hasil = {}
    for nama, tok in daftar_token():
        try: hasil[nama] = cek(nama, tok)
        except Exception as e: print(f"{nama}: GAGAL {str(e)[:200]}"); hasil[nama] = False
    print("\nRINGKASAN:", {k: ("BERHASIL" if v else "GAGAL") for k, v in hasil.items()})
    sys.exit(0 if any(hasil.values()) else 1)

if __name__ == "__main__":
    kosong = [k for k in ["VIDEO_URL"] if not os.environ.get(k, "").strip()]
    if not daftar_token(): kosong.append("IG_ACCESS_TOKEN / IG_PAGE_TOKEN")
    if kosong:
        print("Instagram dilewati: belum terbaca -> " + ", ".join(kosong)); sys.exit(0)
    info = json.load(open(os.path.join(AKAR, "hasil", "terbaru.json"), encoding="utf-8"))
    mid = unggah(info, os.environ["VIDEO_URL"].strip())
    sp = os.path.join(AKAR, "state.json"); st = json.load(open(sp, encoding="utf-8"))
    st.setdefault("terakhir", {})["instagram"] = mid
    json.dump(st, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
