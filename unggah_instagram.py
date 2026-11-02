"""Mengunggah video terbaru ke Instagram Reels (Instagram API with Instagram Login).

Instagram mengambil video dari URL publik, jadi workflow lebih dulu menaruh video
di GitHub Release sementara (VIDEO_URL), lalu menghapusnya setelah selesai.
"""
import json, os, sys, time
import requests

AKAR = os.path.dirname(os.path.abspath(__file__))
API = "https://graph.instagram.com/v23.0"


def _cek(r, apa):
    if r.status_code != 200:
        raise RuntimeError(f"Instagram gagal {apa}: {r.status_code} {r.text[:400]}")
    return r.json()


def unggah(info, video_url):
    tok = os.environ["IG_ACCESS_TOKEN"].strip(); uid = os.environ["IG_USER_ID"].strip()
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


if __name__ == "__main__":
    kosong = [k for k in ["IG_ACCESS_TOKEN", "IG_USER_ID", "VIDEO_URL"] if not os.environ.get(k, "").strip()]
    if kosong:
        print("Instagram dilewati: belum terbaca -> " + ", ".join(kosong)); sys.exit(0)
    info = json.load(open(os.path.join(AKAR, "hasil", "terbaru.json"), encoding="utf-8"))
    mid = unggah(info, os.environ["VIDEO_URL"].strip())
    sp = os.path.join(AKAR, "state.json"); st = json.load(open(sp, encoding="utf-8"))
    st.setdefault("terakhir", {})["instagram"] = mid
    json.dump(st, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
