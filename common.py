"""Phần dùng chung: đọc/ghi Google Sheet qua Apps Script, tìm bài liên quan, giao diện chung."""
import hashlib
import hmac
import json
import math
import secrets
import re
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

import streamlit as st

DATA_FILE = Path(__file__).parent / "data" / "huong_dan.json"
HOTLINE = "1900.2812"
BRAND = "NHANH INVOICE - TRỢ LÝ"
LOGO = str(Path(__file__).parent / "assets" / "logo.png")
ICON = str(Path(__file__).parent / "assets" / "icon.png")


# ---------- Kết nối Google Sheet (qua Apps Script) ----------
def _cfg(key: str):
    try:
        return st.secrets.get(key)
    except Exception:
        return None


def da_ket_noi_sheet() -> bool:
    return bool(_cfg("APPS_SCRIPT_URL") and _cfg("APPS_SCRIPT_TOKEN"))


def _goi_get(action: str) -> list[dict]:
    qs = urllib.parse.urlencode({"action": action, "token": _cfg("APPS_SCRIPT_TOKEN")})
    with urllib.request.urlopen(f"{_cfg('APPS_SCRIPT_URL')}?{qs}", timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    if not data.get("ok"):
        raise RuntimeError(data.get("error", "Lỗi không rõ từ Google Sheet"))
    return data["rows"]


def goi_post(payload: dict) -> dict:
    body = json.dumps({**payload, "token": _cfg("APPS_SCRIPT_TOKEN")}).encode("utf-8")
    req = urllib.request.Request(
        _cfg("APPS_SCRIPT_URL"), data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    if not data.get("ok"):
        raise RuntimeError(data.get("error", "Lỗi không rõ từ Google Sheet"))
    return data


# ---------- Ảnh minh họa ----------
IMG_DIR = Path(__file__).parent / "images"


def doc_anh(o: str) -> list[dict]:
    """Ô 'Ảnh': mỗi dòng 'tên ảnh | chú thích'. Tên ảnh là file trong thư mục images/ hoặc drive:<id>."""
    ds = []
    for dong in (o or "").splitlines():
        if not dong.strip():
            continue
        src, _, cap = dong.partition("|")
        ds.append({"src": src.strip(), "cap": cap.strip()})
    return ds


def ghi_anh(ds: list[dict]) -> str:
    return "\n".join(f"{a['src']} | {a['cap']}".rstrip(" |") for a in ds)


@st.cache_data(ttl=3600, show_spinner=False)
def _tai_anh_drive(file_id: str) -> bytes:
    url = f"https://drive.google.com/thumbnail?id={urllib.parse.quote(file_id)}&sz=w1600"
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read()


def nguon_anh(src: str):
    """Trả về thứ st.image hiển thị được, hoặc None nếu không tìm thấy."""
    if src.startswith("drive:"):
        try:
            return _tai_anh_drive(src[6:])
        except Exception:
            return None
    f = IMG_DIR / Path(src).name  # chỉ lấy tên file, không cho đi ra ngoài thư mục ảnh
    return str(f) if f.is_file() else None


def la_an(o: str) -> bool:
    """Cột F 'Ẩn trên web': ghi Ẩn (hoặc x) thì bài không hiện ở mục lục, trợ lý vẫn dùng để trả lời."""
    return bo_dau(str(o).strip()) in {"an", "x", "true", "1", "co"}


@st.cache_data(ttl=300, show_spinner=False)  # tự đọc lại Sheet mỗi 5 phút
def doc_tat_ca_bai() -> list[dict]:
    """Mọi dòng trong tab kiến thức, kể cả bài chưa có nội dung."""
    if not da_ket_noi_sheet():
        mau = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return [{"anh": [], "an": False, **b, "row": None} for b in mau]
    bai_viet, nhom = [], ""
    for r in _goi_get("articles"):
        c = (list(r["cells"]) + ["", "", "", "", "", ""])[:6]
        c = [str(x).strip() for x in c]
        nhom = c[0] or nhom  # ô Nhóm trống = cùng nhóm với dòng trên
        if not (c[1] or c[3]):
            continue  # dòng trống hẳn
        bai_viet.append({"row": r["row"], "nhom": nhom, "tieu_de": c[1], "link": c[2], "noi_dung": c[3],
                         "anh": doc_anh(c[4]), "an": la_an(c[5])})
    return bai_viet


def doc_gop_y() -> list[dict]:
    ds = []
    for r in _goi_get("feedback"):
        c = [str(x) for x in (list(r["cells"]) + [""] * 6)[:6]]
        ds.append({"row": r["row"], "thoi_gian": c[0], "danh_gia": c[1], "cau_hoi": c[2],
                   "tra_loi": c[3], "ghi_chu": c[4], "trang_thai": c[5] or "Chưa xử lý"})
    ds.reverse()  # mới nhất lên đầu
    return ds


def doc_tai_khoan() -> list[dict]:
    ds = []
    for r in _goi_get("accounts"):
        c = [str(x) for x in (list(r["cells"]) + [""] * 5)[:5]]
        if c[0].strip():
            ds.append({"row": r["row"], "username": c[0].strip(), "password_hash": c[1], "role": c[2],
                       "ngay_tao": c[3], "nguoi_tao": c[4]})
    return ds


# ---------- Mật khẩu: chỉ lưu dạng đã mã hóa ----------
def ma_hoa_mat_khau(mat_khau: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", mat_khau.encode(), salt.encode(), 200_000).hex()
    return f"pbkdf2${salt}${h}"


def kiem_tra_mat_khau(mat_khau: str, da_ma_hoa: str) -> bool:
    try:
        _, salt, h = da_ma_hoa.split("$")
    except ValueError:
        return False
    thu = hashlib.pbkdf2_hmac("sha256", mat_khau.encode(), salt.encode(), 200_000).hex()
    return hmac.compare_digest(thu, h)


def lam_moi_du_lieu():
    doc_tat_ca_bai.clear()
    _chi_muc.clear()


# ---------- Tìm bài liên quan (không cần dịch vụ trả phí) ----------
def bo_dau(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower()).replace("đ", "d")
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def tach_tu(text: str) -> list[str]:
    words = re.findall(r"\w+", bo_dau(text))
    # thêm cặp từ vì tiếng Việt nhiều từ ghép: "hoa don", "dieu chinh"...
    return words + [f"{a}_{b}" for a, b in zip(words, words[1:])]


@st.cache_data(ttl=300, show_spinner=False)
def _chi_muc():
    bai = [b for b in doc_tat_ca_bai() if b["noi_dung"]]
    docs = [tach_tu(f"{b['tieu_de']} {b['tieu_de']} {b['nhom']} {b['noi_dung']}") for b in bai]
    df = Counter(t for d in docs for t in set(d))
    avg = sum(len(d) for d in docs) / max(len(docs), 1)
    return bai, docs, df, avg


def tim_bai(cau_hoi: str, k: int = 4, kem_diem: bool = False) -> list:
    bai, docs, df, avg = _chi_muc()
    q, n, kq = tach_tu(cau_hoi), len(docs), []
    for i, d in enumerate(docs):
        tf, diem = Counter(d), 0.0
        for t in q:
            if t in tf:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                diem += idf * tf[t] * 2.2 / (tf[t] + 1.2 * (0.25 + 0.75 * len(d) / avg))
        if diem > 0:
            kq.append((diem, bai[i]))
    kq.sort(key=lambda x: x[0], reverse=True)
    return kq[:k] if kem_diem else [b for _, b in kq[:k]]


# ---------- Giao diện chung (màu theo bản thiết kế) ----------
CSS = """
<style>
.stApp { background: #F8F6F5; }
[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #ECE7E5; box-shadow: inset 4px 0 0 #C41E24; }
[data-testid="stSidebar"] * { color: #2B2626 !important; }
[data-testid="stSidebar"] .stButton button { background: #FFFFFF; border: 1px solid #E6E0DE; justify-content: flex-start; }
[data-testid="stSidebar"] .stButton button:hover { background: #FCEBEC; border-color: #F2C3C5; }
[data-testid="stSidebar"] .stButton button[kind="primary"] { background: #C41E24 !important; border-color: #C41E24 !important; font-weight: 600; }
[data-testid="stSidebar"] .stButton button[kind="primary"] * { color: #FFFFFF !important; }
[data-testid="stSidebar"] [data-testid="stExpander"] { border-color: #E6E0DE; background: #FFFFFF; }
.sub { font-size: 13px; color: #7A7070 !important; }
.brand { font-weight: 700; font-size: 15px; margin-bottom: 4px; letter-spacing: .02em; }
.badge { display:inline-flex; align-items:center; gap:6px; padding:6px 14px; border-radius:999px;
         background:#FCEBEC; color:#A3161C; font-size:13px; font-weight:600; }
.hint { font-size: 12.5px; color: #6B6565; }
.card { background:#FFFFFF; border:1px solid #E9E4E2; border-radius:12px; padding:16px 18px; margin-bottom:12px; }
.tag-bad { background:#FCEBEC; color:#A3161C; padding:3px 10px; border-radius:999px; font-size:12.5px; font-weight:600; }
.tag-good { background:#E6F3EB; color:#1F6B47; padding:3px 10px; border-radius:999px; font-size:12.5px; font-weight:600; }
.tag { background:#F2EFEE; color:#4A4444; padding:3px 10px; border-radius:999px; font-size:12.5px; font-weight:600; }
.label { font-size:12.5px; font-weight:600; color:#6B6565; margin-top:8px; }
[data-testid="stMetric"] { background:#FFFFFF; border:1px solid #E9E4E2; border-radius:12px; padding:12px 16px; }
.stButton button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"] { background:#C41E24 !important; border-color:#C41E24 !important; color:#FFFFFF !important; }
.stButton button[kind="primary"]:hover, [data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"]:hover { background:#A3161C !important; border-color:#A3161C !important; }
.stApp h1, .stApp h2, .stApp h3, .stApp h4 { -webkit-text-stroke: 0.9px currentColor; letter-spacing: .01em; }  /* Comfortaa vốn mảnh: làm tiêu đề đậm hơn */
[data-testid="stToolbarActions"], [data-testid="stToolbarActionButton"], [data-testid="stAppDeployButton"] { display:none !important; }
</style>
"""

def ap_dung_giao_dien():
    st.markdown(CSS, unsafe_allow_html=True)


def esc(text: str) -> str:
    """Chống chèn HTML khi hiển thị chữ do người dùng nhập."""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("\n", "<br>"))
