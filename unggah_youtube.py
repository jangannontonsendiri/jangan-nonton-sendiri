"""Mengunggah video terbaru (hasil/terbaru.json) ke YouTube Shorts."""
import json, os, sys
import requests

AKAR = os.path.dirname(os.path.abspath(__file__))


def token_akses():
    r = requests.post("https://oauth2.googleapis.com/token", timeout=60, data={
        "client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"})
    if r.status_code != 200:
        raise RuntimeError(f"Gagal minta token YouTube: {r.text[:300]}")
    return r.json()["access_token"]


def metadata(info):
    judul = f"{info['judul']} (Part {info['part']}/3) #shorts #ceritahoror"
    if len(judul) > 100:
        judul = f"{info['judul'][:60]} Part {info['part']}/3 #shorts"
    desk = info["teks_lengkap"]
    desk += "\n\nCerita ini adalah karya fiksi. Visual dibuat dengan bantuan AI."
    tags = [h.lstrip("#") for h in info.get("hashtag", [])][:10] + ["cerita horor", "horor indonesia", "shorts"]
    return {
        "snippet": {"title": judul, "description": desk[:4900], "tags": tags,
                    "categoryId": "24", "defaultLanguage": "id", "defaultAudioLanguage": "id"},
        "status": {"privacyStatus": os.environ.get("YT_PRIVASI", "public"), "selfDeclaredMadeForKids": False,
                   "containsSyntheticMedia": True},
    }


def unggah(info):
    tok = token_akses()
    path = info["video"]; ukuran = os.path.getsize(path)
    r = requests.post("https://www.googleapis.com/upload/youtube/v3/videos",
                      params={"uploadType": "resumable", "part": "snippet,status"},
                      headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json",
                               "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(ukuran)},
                      data=json.dumps(metadata(info)), timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Gagal memulai upload: {r.status_code} {r.text[:400]}")
    with open(path, "rb") as f:
        r2 = requests.put(r.headers["Location"], data=f, timeout=900,
                          headers={"Authorization": f"Bearer {tok}", "Content-Type": "video/mp4"})
    if r2.status_code not in (200, 201):
        raise RuntimeError(f"Gagal upload: {r2.status_code} {r2.text[:400]}")
    vid = r2.json()["id"]; status = r2.json().get("status", {}).get("privacyStatus")
    print(f"YouTube: terunggah https://youtube.com/shorts/{vid} (status: {status})")
    return vid


if __name__ == "__main__":
    kosong = [k for k in ["YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"] if not os.environ.get(k, "").strip()]
    if kosong:
        print("YouTube dilewati: secret ini belum terbaca -> " + ", ".join(kosong)); sys.exit(0)
    info = json.load(open(os.path.join(AKAR, "hasil", "terbaru.json"), encoding="utf-8"))
    vid = unggah(info)
    sp = os.path.join(AKAR, "state.json"); st = json.load(open(sp, encoding="utf-8"))
    st.setdefault("terakhir", {})["youtube"] = vid
    json.dump(st, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
