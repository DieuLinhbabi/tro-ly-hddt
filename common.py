"""Phần dùng chung: đọc/ghi Google Sheet qua Apps Script, tìm bài liên quan, giao diện chung."""
import hashlib
import hmac
import json
import math
import secrets
import threading
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


def _logo_nho() -> str:
    """Logo thu nhỏ dạng data URI, hiện ở đầu trang khi khách ẩn thanh menu."""
    import base64, io
    from PIL import Image
    anh = Image.open(LOGO)
    anh.thumbnail((360, 120))
    bo = io.BytesIO()
    anh.save(bo, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(bo.getvalue()).decode()


LOGO_NHO = _logo_nho()


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
    for lan in range(2):  # Google đôi lúc phản hồi chậm: thử lại 1 lần
        try:
            with urllib.request.urlopen(f"{_cfg('APPS_SCRIPT_URL')}?{qs}", timeout=45) as r:
                data = json.loads(r.read().decode("utf-8"))
            break
        except (TimeoutError, OSError):
            if lan == 1:
                raise
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


def goi_post_nen(payload: dict):
    """Gửi lên Google Sheet ở chế độ nền: người dùng không phải chờ, lỗi thì bỏ qua."""
    if not da_ket_noi_sheet():
        return
    url, token = _cfg("APPS_SCRIPT_URL"), _cfg("APPS_SCRIPT_TOKEN")
    body = json.dumps({**payload, "token": token}).encode("utf-8")

    def gui():
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=60).read()
        except Exception:
            pass

    threading.Thread(target=gui, daemon=True).start()


def che_thong_tin(text: str) -> str:
    """Che email, số điện thoại, mã số thuế, số CCCD... trước khi lưu lịch sử hỏi."""
    text = re.sub(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", "[email]", text)
    # dãy từ 9 chữ số trở lên (có thể xen dấu cách, chấm, gạch): SĐT, MST, CCCD, số tài khoản
    return re.sub(r"\+?\d(?:[\s-]?\d){8,}", "[số đã che]", text)


def doc_lich_su_hoi() -> list[dict]:
    ds = []
    for r in _goi_get("questions"):
        c = [str(x) for x in (list(r["cells"]) + [""] * 6)[:6]]
        ds.append({"thoi_gian": c[0], "cau_hoi": c[1], "co_anh": c[2] == "Có", "bai": c[3], "ket_qua": c[4],
                   "giay": c[5]})
    return ds


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


def _du_lieu_mau() -> list[dict]:
    mau = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return [{"anh": [], "an": False, **b, "row": None} for b in mau]


@st.cache_resource(show_spinner=False)
def _ban_du_phong() -> dict:
    """Bản kiến thức đọc thành công gần nhất, dùng tạm khi Google Sheet phản hồi chậm."""
    return {}


def doc_tat_ca_bai() -> list[dict]:
    """Mọi dòng trong tab kiến thức, kể cả bài chưa có nội dung."""
    if not da_ket_noi_sheet():
        return _du_lieu_mau()
    du_phong = _ban_du_phong()
    try:
        bai = _doc_tu_sheet()
        du_phong["bai"] = bai
        return bai
    except Exception:
        if du_phong.get("bai"):
            return du_phong["bai"]  # Sheet chậm: dùng bản gần nhất, người dùng không bị gián đoạn
        raise


@st.cache_data(ttl=300, show_spinner=False)  # tự đọc lại Sheet mỗi 5 phút
def _doc_tu_sheet() -> list[dict]:
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
    _doc_tu_sheet.clear()
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


# Từ viết tắt / cách nói khác mà khách hay dùng -> thêm từ trong tài liệu để tìm đúng bài (viết không dấu)
DONG_NGHIA = {
    "hd": "hoa don", "hddt": "hoa don dien tu", "cks": "chu ky so", "cqt": "co quan thue",
    "tct": "tong cuc thue", "mst": "ma so thue", "kh": "khach hang", "sp": "san pham", "ncc": "nha cung cap",
    "hang loat": "nhieu cung luc excel", "nhieu hoa don": "hang loat cung luc", "cung luc": "hang loat nhieu",
    "copy": "sao chep", "nhan ban": "sao chep", "huy hoa don": "xoa bo hoa don", "huy": "xoa bo",
    "sua hoa don": "dieu chinh thay the hoa don",
    "tao hoa don": "tao moi lap hoa don danh sach", "lap hoa don": "tao moi hoa don danh sach",
    "xuat hoa don": "tao moi lap phat hanh hoa don", "viet hoa don": "tao moi lap hoa don",
}


def mo_rong_cau_hoi(cau_hoi: str) -> str:
    """Thêm từ đồng nghĩa vào câu hỏi trước khi tìm bài."""
    t = " " + " ".join(re.findall(r"\w+", bo_dau(cau_hoi))) + " "
    them = [v for k, v in DONG_NGHIA.items() if f" {k} " in t]
    return cau_hoi + (" " + " ".join(them) if them else "")


def trich_doan(noi_dung: str, cau_hoi: str, toi_da: int) -> str:
    """Bài dài: giữ phần mở đầu và các đoạn khớp câu hỏi nhất (không cắt cụt cuối bài)."""
    if len(noi_dung) <= toi_da:
        return noi_dung
    dong = [d for d in noi_dung.splitlines() if d.strip()]  # bỏ dòng trống
    q = set(tach_tu(mo_rong_cau_hoi(cau_hoi)))
    diem = [len(q & set(tach_tu(d))) for d in dong]
    chon = set(range(min(3, len(dong))))  # vài dòng đầu để biết bài nói về gì
    do_dai = sum(len(dong[i]) + 1 for i in chon)
    for i in sorted(range(len(dong)), key=lambda i: -diem[i]):
        if diem[i] == 0:
            break
        for j in range(max(0, i - 2), min(len(dong), i + 6)):  # lấy cả các bước ngay sau dòng khớp
            if j not in chon and do_dai + len(dong[j]) + 1 <= toi_da:
                chon.add(j)
                do_dai += len(dong[j]) + 1
        if do_dai >= toi_da:
            break
    kq, truoc = [], -1
    for i in sorted(chon):
        if truoc != -1 and i != truoc + 1:
            kq.append("(...)")
        kq.append(dong[i])
        truoc = i
    return "\n".join(kq)


def tim_bai(cau_hoi: str, k: int = 4, kem_diem: bool = False) -> list:
    bai, docs, df, avg = _chi_muc()
    q, n, kq = tach_tu(mo_rong_cau_hoi(cau_hoi)), len(docs), []
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
[data-testid="stSidebar"] [data-testid="stImage"], [data-testid="stSidebar"] [data-testid="stImageContainer"],
[data-testid="stSidebar"] [data-testid="stFullScreenFrame"] { display:flex; justify-content:center; width:100%; margin:0 auto; }
[data-testid="stSidebarHeader"] { height: 2.25rem; padding-bottom: 0; }
[data-testid="stSidebarUserContent"] { padding-top: 0.25rem; }
[data-testid="stSidebar"] .brand { text-align: center; margin-top: 6px; }
[data-testid="stChatMessage"] { scroll-margin-top: 72px; }  /* chừa chỗ cho thanh trên cùng khi tự cuộn về câu hỏi */
[data-testid="stToolbarActions"], [data-testid="stToolbarActionButton"], [data-testid="stAppDeployButton"] { display:none !important; }
/* ===== Phương án A: Mềm mại ===== */
.stApp { background: radial-gradient(#EFDCD8 1.2px, transparent 1.2px) 0 0/22px 22px, #FBF7F4; }
[data-testid="stSidebar"] { box-shadow: 6px 0 28px rgba(150,40,40,.07); border-right: none; }
[data-testid="stSidebar"] .stButton button, [data-testid="stSidebar"] [data-testid="stExpander"] details { border-radius: 16px !important; }
[data-testid="stSidebar"] [data-testid="stExpander"] { border-radius: 16px; border: 1px solid #F0E3E0; }
[data-testid="stSidebar"] .stButton button[kind="secondary"]:first-of-type { }
.hotline-card { margin-top: 22px; padding: 14px 16px; border-radius: 18px; background: #FDEEEE; font-size: 13.5px; line-height: 1.6; }
.hero { padding: 10px 0 6px; }
.hero-badge { display:inline-block; padding: 6px 14px; border-radius: 999px; background: #FFFFFF; border: 1px solid #F3D3D4;
  color: #B3191F !important; font-size: 13px; font-weight: 600; box-shadow: 0 3px 10px rgba(196,30,36,.08); }
.hero-title { font-size: 32px; font-weight: 800; color: #221E1E; margin: 14px 0 4px; letter-spacing: -.01em; }
.hero-sub { color: #7A6E6E; font-size: 15px; margin-bottom: 8px; }
[data-testid="stChatMessage"] { background: #FFFFFF; border: 1px solid #F1E5E2; border-radius: 24px; padding: 16px 20px;
  box-shadow: 0 8px 24px rgba(120,40,40,.06); border-bottom-left-radius: 8px; margin-right: 4%; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { background: #C41E24; border-color: #C41E24;
  margin-left: auto; margin-right: 0; width: fit-content; max-width: 78%; border-radius: 24px; border-bottom-right-radius: 8px; box-shadow: 0 8px 20px rgba(196,30,36,.18); }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p { color: #FFFFFF; }
[data-testid="stChatMessageAvatarUser"] { background: #FFFFFF; color: #C41E24; }
.stMain .stButton button[kind="secondary"] { border-radius: 16px; background: #FFF8F7; border: 1.5px solid #F4D6D6; color: #4A2B2B;
  padding: 10px 14px; justify-content: flex-start; transition: all .15s ease; }
.stMain .stButton button[kind="secondary"]:hover { background: #FDECEC; border-color: #E8A9AB; transform: translateY(-2px);
  box-shadow: 0 6px 14px rgba(196,30,36,.12); color: #A3161C; }
[data-testid="stChatInput"] { border-radius: 26px !important; border: 1.5px solid #F2C9CA !important; box-shadow: 0 10px 28px rgba(196,30,36,.10); background:#FFFFFF; }
[data-testid="stChatInput"] > div { border-radius: 26px !important; }
[data-testid="stChatInputSubmitButton"] { background: #C41E24 !important; border-radius: 999px !important; }
[data-testid="stChatInputSubmitButton"] svg { fill: #FFFFFF !important; color:#FFFFFF !important; }
[data-testid="stBottomBlockContainer"] { background: transparent; }

[data-testid="stChatMessageAvatarImage"] { width: 46px !important; height: 46px !important; }
[data-testid="stChatMessage"] { box-sizing: border-box; }


.stMainBlockContainer:has(.hero), .stApp:has(.hero) [data-testid="stBottomBlockContainer"] { max-width: 980px; margin-left: auto; margin-right: auto; }
.hero-logo { display: none; height: 46px; margin: 0 0 18px; }
.stApp:has([data-testid="stSidebar"][data-collapsed="true"]) .hero-logo { display: block; }
.stMain .stButton button p { white-space: normal; text-align: center; }  /* nút dài thì xuống dòng, không bị cắt chữ */
</style>
"""

def ap_dung_giao_dien():
    st.markdown(CSS, unsafe_allow_html=True)


def esc(text: str) -> str:
    """Chống chèn HTML khi hiển thị chữ do người dùng nhập."""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("\n", "<br>"))
