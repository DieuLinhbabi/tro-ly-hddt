"""Màn hình hỏi đáp cho người dùng (không cần đăng nhập)."""
import base64
import io
import re
from collections import OrderedDict

import streamlit as st
from groq import Groq

from common import BRAND, HOTLINE, LOGO, da_ket_noi_sheet, doc_tat_ca_bai, goi_post, nguon_anh, tim_bai

DEFAULT_MODEL = "llama-3.3-70b-versatile"
VISION_MODEL = "qwen/qwen3.8-27b"  # model Groq đọc được ảnh; đổi bằng GROQ_VISION_MODEL trong Secrets
CAU_HOI_ANH = "Màn hình trong ảnh là gì và tôi cần làm gì tiếp theo?"
PROMPT_DOC_ANH = ("Đây là ảnh chụp màn hình phần mềm hóa đơn điện tử do người dùng gửi. Hãy mô tả ngắn gọn bằng tiếng Việt: "
                  "đang ở màn hình/menu nào, các nút và ô nhập chính, và chép NGUYÊN VĂN mọi thông báo lỗi hay cảnh báo "
                  "nếu có. Nếu ảnh không phải màn hình phần mềm, nói rõ ảnh có gì. Không đoán cách xử lý.")
GOI_Y = ["Cách điều chỉnh hóa đơn?", "Xóa bỏ hóa đơn đã phát hành", "Lập mẫu 04/SS-HĐĐT", "Thêm người dùng và phân quyền"]
LOI_CHAO = ("Xin chào! Bạn cần tìm cách làm thao tác nào trên phần mềm hóa đơn điện tử? "
            "Có thể bắt đầu với một câu hỏi gợi ý bên dưới.")

SYSTEM_PROMPT = f"""Bạn là "Trợ lý Hóa đơn điện tử" của Nhanh.vn, hỗ trợ người dùng tra cứu cách sử dụng phần mềm hóa đơn điện tử.
Quy tắc:
- CHỈ trả lời dựa trên phần TÀI LIỆU được cung cấp. Không tự suy đoán thao tác không có trong tài liệu.
- Nếu tài liệu không có thông tin, trả lời: "Tài liệu hướng dẫn chưa có nội dung này. Vui lòng gọi hotline {HOTLINE} để được hỗ trợ."
- Trình bày ngắn gọn, đánh số từng bước thao tác, in đậm tên menu/nút như trong tài liệu.
- Nếu người dùng gửi kèm ảnh chụp màn hình: mở đầu bằng một câu cho biết họ đang ở màn hình nào hoặc gặp thông báo gì, rồi hướng dẫn theo TÀI LIỆU.
- Không ghi nguồn, tên bài hay link ở câu trả lời.
- Luôn trả lời bằng tiếng Việt."""

ss = st.session_state
ss.setdefault("messages", [])     # {"role", "content", "question"?}
ss.setdefault("fb_sent", set())   # chỉ số câu trả lời đã gửi góp ý
ss.setdefault("pending", None)    # câu hỏi đến từ nút gợi ý / mục lục

try:
    bai_viet = doc_tat_ca_bai()
except Exception as e:
    bai_viet = []
    st.error(f"Không đọc được dữ liệu hướng dẫn từ Google Sheet: {e}")

# ---------- Thanh bên ----------
with st.sidebar:
    st.image(LOGO, width="stretch")
    st.markdown(f'<div class="brand">{BRAND}</div>', unsafe_allow_html=True)
    if st.button("＋  HỎI ĐÁP NHANH", width="stretch", help="Bắt đầu cuộc hội thoại mới"):
        ss.messages, ss.fb_sent = [], set()
        st.rerun()
    st.markdown('<div class="sub" style="margin:18px 0 6px;font-weight:600;letter-spacing:.08em">HƯỚNG DẪN SỬ DỤNG</div>',
                unsafe_allow_html=True)
    nhom_bai = OrderedDict()
    for b in bai_viet:
        if b["noi_dung"]:
            nhom_bai.setdefault(b["nhom"] or "Khác", []).append(b)
    for nhom, ds in nhom_bai.items():
        with st.expander(nhom):
            for b in ds:
                if st.button(b["tieu_de"], key=f"bai_{b['row']}_{b['tieu_de']}", width="stretch"):
                    ss.pending = f"Hướng dẫn: {b['tieu_de']}"
    st.markdown(f'<div class="sub" style="margin-top:24px">Không có câu trả lời?<br>Gọi hotline '
                f'<b>{HOTLINE}</b></div>', unsafe_allow_html=True)

# ---------- Tiêu đề ----------
st.markdown("## HỎI ĐÁP - NHANH")

if "GROQ_API_KEY" not in st.secrets:
    st.error("Chưa khai báo GROQ_API_KEY trong Secrets.")
    st.stop()
client = Groq(api_key=st.secrets["GROQ_API_KEY"])
model = st.secrets.get("GROQ_MODEL", DEFAULT_MODEL)
vision_model = st.secrets.get("GROQ_VISION_MODEL", VISION_MODEL)


def gui_gop_y(i: int, danh_gia: str, ghi_chu: str = ""):
    m = ss.messages[i]
    try:
        if da_ket_noi_sheet():
            goi_post({"action": "feedback", "danh_gia": danh_gia, "cau_hoi": m.get("question", ""),
                      "tra_loi": m["content"], "ghi_chu": ghi_chu})
        ss.fb_sent.add(i)
        st.toast("Cảm ơn bạn đã góp ý!")
    except Exception as e:
        st.error(f"Chưa gửi được góp ý: {e}")


def khung_gop_y(i: int):
    if i in ss.fb_sent:
        st.caption("Đã ghi nhận góp ý. Cảm ơn bạn!")
        return
    chon = st.feedback("thumbs", key=f"fb_{i}")
    if chon == 1:
        gui_gop_y(i, "Hữu ích")
        st.rerun()
    elif chon == 0:
        with st.form(f"form_fb_{i}", border=True):
            ly_do = st.text_area("Câu trả lời chưa đúng ở đâu? (không bắt buộc)", key=f"lydo_{i}",
                                 placeholder="Ví dụ: thiếu bước, sai tên nút, chưa đúng ý câu hỏi...")
            if st.form_submit_button("Gửi góp ý", type="primary"):
                gui_gop_y(i, "Chưa đúng", ly_do.strip())
                st.rerun()


def hien_anh(ds: list[dict]):
    """Ảnh minh họa của bài hướng dẫn, mỗi ảnh kèm chú thích."""
    co_anh = [(a, nguon_anh(a["src"])) for a in ds]
    co_anh = [(a, x) for a, x in co_anh if x is not None]
    if not co_anh:
        return
    st.markdown("**📷 Ảnh minh họa trên phần mềm**")
    for a, x in co_anh:
        st.image(x, caption=a["cap"] or None, width="stretch")


def chuan_bi_anh(f) -> bytes:
    """Thu nhỏ ảnh người dùng gửi (tối đa 1600px, JPEG) để gửi AI nhanh và nhẹ."""
    from PIL import Image
    im = Image.open(f)
    im = im.convert("RGB")
    im.thumbnail((1600, 1600))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def doc_anh_bang_ai(anh: bytes, cau_hoi: str) -> str:
    """Nhờ model đọc ảnh mô tả màn hình/lỗi, để trợ lý tìm đúng bài hướng dẫn."""
    url = "data:image/jpeg;base64," + base64.b64encode(anh).decode()
    kq = client.chat.completions.create(
        model=vision_model, temperature=0.2,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": f"{PROMPT_DOC_ANH}\nCâu hỏi kèm theo của người dùng: {cau_hoi}"},
            {"type": "image_url", "image_url": {"url": url}},
        ]}],
    )
    mo_ta = kq.choices[0].message.content or ""
    return re.sub(r"<think>.*?</think>", "", mo_ta, flags=re.S).strip()


# ---------- Hội thoại ----------
with st.chat_message("assistant", avatar="🧾"):
    st.markdown(LOI_CHAO)
    if not ss.messages:
        cols = st.columns(len(GOI_Y))
        for col, g in zip(cols, GOI_Y):
            if col.button(g, width="stretch"):
                ss.pending = g

for i, m in enumerate(ss.messages):
    with st.chat_message(m["role"], avatar="🧾" if m["role"] == "assistant" else None):
        if m.get("img"):
            st.image(m["img"], width=320)
        st.markdown(m["content"])
        if m["role"] == "assistant":
            hien_anh(m.get("anh", []))
            khung_gop_y(i)

nhap = st.chat_input("Nhập câu hỏi, hoặc bấm dấu + để gửi kèm ảnh chụp màn hình...", accept_file=True,
                     file_type=["png", "jpg", "jpeg", "webp"])
anh_gui = None
if nhap:
    cau_hoi = (nhap.text or "").strip()
    if nhap.files:
        try:
            anh_gui = chuan_bi_anh(nhap.files[0])
        except Exception:
            st.toast("Không đọc được ảnh, hãy thử ảnh PNG hoặc JPG khác.")
        cau_hoi = cau_hoi or (CAU_HOI_ANH if anh_gui else "")
else:
    cau_hoi = ss.pending
ss.pending = None
st.markdown('<div class="hint">AI có thể nhầm. Với thao tác quan trọng, hãy kiểm tra lại hoặc gọi hotline '
            f'{HOTLINE}.</div>', unsafe_allow_html=True)

if cau_hoi:
    ss.messages.append({"role": "user", "content": cau_hoi, "img": anh_gui})
    with st.chat_message("user"):
        if anh_gui:
            st.image(anh_gui, width=320)
        st.markdown(cau_hoi)

    mo_ta_anh = ""
    if anh_gui:
        with st.spinner("Đang xem ảnh..."):
            try:
                mo_ta_anh = doc_anh_bang_ai(anh_gui, cau_hoi)
            except Exception as e:
                st.warning(f"Chưa đọc được ảnh ({e}). Trợ lý sẽ trả lời theo câu hỏi chữ.")

    ket_qua = tim_bai(f"{cau_hoi}\n{mo_ta_anh}", kem_diem=True)
    tai_lieu = [b for _, b in ket_qua]
    ngu_canh = "\n\n---\n\n".join(f"[{b['nhom']} > {b['tieu_de']}]\n{b['noi_dung']}" for b in tai_lieu) \
        or "(Không tìm thấy bài liên quan)"
    lich_su = [{"role": m["role"], "content": m["content"]} for m in ss.messages[-7:-1]]
    messages = ([{"role": "system", "content": SYSTEM_PROMPT}] + lich_su
                + [{"role": "user", "content": f"TÀI LIỆU:\n{ngu_canh}\n\n"
                                              + (f"NGƯỜI DÙNG GỬI KÈM ẢNH CHỤP MÀN HÌNH, NỘI DUNG ẢNH:\n{mo_ta_anh}\n\n"
                                                 if mo_ta_anh else "")
                                              + f"CÂU HỎI: {cau_hoi}"}])

    with st.chat_message("assistant", avatar="🧾"):
        try:
            stream = client.chat.completions.create(model=model, messages=messages, temperature=0.2, stream=True)
            tra_loi = st.write_stream(chunk.choices[0].delta.content or "" for chunk in stream)
        except Exception as e:
            tra_loi = f"⚠️ Lỗi khi gọi AI: {e}"
            st.error(tra_loi)
    # Ảnh của bài khớp nhất, chỉ khi bài đó vượt trội rõ ràng và trợ lý có trả lời được
    anh = []
    if ket_qua and "chưa có nội dung" not in tra_loi.lower() and not tra_loi.startswith("⚠️"):
        diem_1 = ket_qua[0][0]
        diem_2 = ket_qua[1][0] if len(ket_qua) > 1 else 0
        if diem_1 >= 1.3 * diem_2:
            anh = ket_qua[0][1].get("anh", [])
    ss.messages.append({"role": "assistant", "content": tra_loi, "question": cau_hoi + (" [kèm ảnh]" if anh_gui else ""), "anh": anh})
    st.rerun()
