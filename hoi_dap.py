"""Màn hình hỏi đáp cho người dùng (không cần đăng nhập)."""
from collections import OrderedDict

import streamlit as st
from groq import Groq

from common import BRAND, HOTLINE, da_ket_noi_sheet, doc_tat_ca_bai, goi_post, nguon_anh, tim_bai

DEFAULT_MODEL = "llama-3.3-70b-versatile"
GOI_Y = ["Cách điều chỉnh hóa đơn?", "Xóa bỏ hóa đơn đã phát hành", "Lập mẫu 04/SS-HĐĐT", "Thêm người dùng và phân quyền"]
LOI_CHAO = ("Xin chào! Bạn cần tìm cách làm thao tác nào trên phần mềm hóa đơn điện tử? "
            "Có thể bắt đầu với một câu hỏi gợi ý bên dưới.")

SYSTEM_PROMPT = f"""Bạn là "Trợ lý Hóa đơn điện tử" của Nhanh.vn, hỗ trợ người dùng tra cứu cách sử dụng phần mềm hóa đơn điện tử.
Quy tắc:
- CHỈ trả lời dựa trên phần TÀI LIỆU được cung cấp. Không tự suy đoán thao tác không có trong tài liệu.
- Nếu tài liệu không có thông tin, trả lời: "Tài liệu hướng dẫn chưa có nội dung này. Vui lòng gọi hotline {HOTLINE} để được hỗ trợ."
- Trình bày ngắn gọn, đánh số từng bước thao tác, in đậm tên menu/nút như trong tài liệu.
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
                f'<b style="color:#fff">{HOTLINE}</b></div>', unsafe_allow_html=True)

# ---------- Tiêu đề ----------
c1, c2 = st.columns([3, 1])
c1.markdown("## HỎI ĐÁP - NHANH")
c2.markdown('<div style="text-align:right;padding-top:14px"><span class="badge">✓ Chỉ trả lời theo tài liệu</span></div>',
            unsafe_allow_html=True)

if "GROQ_API_KEY" not in st.secrets:
    st.error("Chưa khai báo GROQ_API_KEY trong Secrets.")
    st.stop()
client = Groq(api_key=st.secrets["GROQ_API_KEY"])
model = st.secrets.get("GROQ_MODEL", DEFAULT_MODEL)


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
        st.markdown(m["content"])
        if m["role"] == "assistant":
            hien_anh(m.get("anh", []))
            khung_gop_y(i)

cau_hoi = st.chat_input("Nhập câu hỏi về hóa đơn điện tử...") or ss.pending
ss.pending = None
st.markdown('<div class="hint">AI có thể nhầm. Với thao tác quan trọng, hãy kiểm tra lại hoặc gọi hotline '
            f'{HOTLINE}.</div>', unsafe_allow_html=True)

if cau_hoi:
    ss.messages.append({"role": "user", "content": cau_hoi})
    with st.chat_message("user"):
        st.markdown(cau_hoi)

    ket_qua = tim_bai(cau_hoi, kem_diem=True)
    tai_lieu = [b for _, b in ket_qua]
    ngu_canh = "\n\n---\n\n".join(f"[{b['nhom']} > {b['tieu_de']}]\n{b['noi_dung']}" for b in tai_lieu) \
        or "(Không tìm thấy bài liên quan)"
    lich_su = [{"role": m["role"], "content": m["content"]} for m in ss.messages[-7:-1]]
    messages = ([{"role": "system", "content": SYSTEM_PROMPT}] + lich_su
                + [{"role": "user", "content": f"TÀI LIỆU:\n{ngu_canh}\n\nCÂU HỎI: {cau_hoi}"}])

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
    ss.messages.append({"role": "assistant", "content": tra_loi, "question": cau_hoi, "anh": anh})
    st.rerun()
