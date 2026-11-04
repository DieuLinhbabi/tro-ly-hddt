"""Màn hình hỏi đáp cho người dùng (không cần đăng nhập)."""
import base64
import io
import json
import re
import time
from collections import OrderedDict

import streamlit as st
from groq import Groq

from common import BRAND, HOTLINE, LOGO, che_thong_tin, goi_post_nen, trich_doan, da_ket_noi_sheet, doc_tat_ca_bai, goi_post, nguon_anh, tim_bai

DEFAULT_MODEL = "llama-3.3-70b-versatile"
VISION_MODEL = "qwen/qwen3.8-27b"  # model Groq đọc được ảnh; đổi bằng GROQ_VISION_MODEL trong Secrets
CAU_HOI_ANH = "Màn hình trong ảnh là gì và tôi cần làm gì tiếp theo?"
PROMPT_DOC_ANH = ("Đây là ảnh chụp màn hình phần mềm hóa đơn điện tử do người dùng gửi. Hãy mô tả ngắn gọn bằng tiếng Việt: "
                  "đang ở màn hình/menu nào, các nút và ô nhập chính, và chép NGUYÊN VĂN mọi thông báo lỗi hay cảnh báo "
                  "nếu có. Nếu ảnh không phải màn hình phần mềm, nói rõ ảnh có gì. Không đoán cách xử lý.")
GOI_Y = ["Cách điều chỉnh hóa đơn?", "Hóa đơn sai thì xử lý thế nào?", "Lập mẫu 04/SS-HĐĐT", "Thêm người dùng và phân quyền"]
ICON_GOI_Y = ["✏️", "🧐", "📮", "👥"]
AVATAR_TRO_LY = "assets/mascot.png"
LOI_CHAO = ("Xin chào! Bạn cần tìm cách làm thao tác nào trên phần mềm hóa đơn điện tử? "
            "Có thể bắt đầu với một câu hỏi gợi ý bên dưới.")

SYSTEM_PROMPT = f"""Bạn là "Trợ lý Hóa đơn điện tử" của Nhanh.vn, hỗ trợ người dùng tra cứu cách sử dụng phần mềm hóa đơn điện tử.
Quy tắc:
- CHỈ trả lời dựa trên phần TÀI LIỆU được cung cấp. Không tự suy đoán thao tác không có trong tài liệu.
- Nếu người dùng định làm khác với quy định hoặc lưu ý trong TÀI LIỆU (ví dụ chuyển từ điều chỉnh sang thay thế), phải nhắc quy định đó trước rồi mới hướng dẫn cách làm đúng; không làm theo ngay yêu cầu sai.
- Được thêm lưu ý hoặc giải thích ngắn cho dễ hiểu (ví dụ kết quả sau khi làm xong), nhưng không bịa tên menu, tên nút hay thao tác không có trong tài liệu.
- Nếu TÀI LIỆU có thông tin liên quan, dù chỉ một phần, hãy trả lời theo phần đó (có thể nói rõ phần nào tài liệu chưa đề cập).
- Chỉ khi không có tài liệu nào liên quan mới trả lời: "Tài liệu hướng dẫn chưa có nội dung này. Vui lòng gọi hotline {HOTLINE} để được hỗ trợ."
- Trình bày ngắn gọn, đánh số từng bước thao tác, in đậm tên menu/nút như trong tài liệu.
- Nếu người dùng gửi kèm ảnh chụp màn hình: mở đầu bằng một câu cho biết họ đang ở màn hình nào hoặc gặp thông báo gì, rồi hướng dẫn theo TÀI LIỆU.
- Không ghi nguồn, tên bài, tên mục tài liệu hay link ở câu trả lời.
- Dòng cuối cùng của câu trả lời luôn là [[BAI:x]], với x là số thứ tự TÀI LIỆU bạn dựa vào nhiều nhất; ghi [[BAI:0]] nếu không dùng tài liệu nào. Người dùng không thấy dòng này.
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
    st.image(LOGO, width=210)
    st.markdown(f'<div class="brand">{BRAND}</div>', unsafe_allow_html=True)
    if st.button("＋  HỎI ĐÁP NHANH", width="stretch", help="Bắt đầu cuộc hội thoại mới"):
        ss.messages, ss.fb_sent = [], set()
        st.rerun()
    st.markdown('<div class="sub" style="margin:18px 0 6px;font-weight:600;letter-spacing:.08em">HƯỚNG DẪN SỬ DỤNG</div>',
                unsafe_allow_html=True)
    nhom_bai = OrderedDict()
    for b in bai_viet:
        if b["noi_dung"] and not b.get("an"):  # bài bị ẩn vẫn được trợ lý dùng để trả lời
            nhom_bai.setdefault(b["nhom"] or "Khác", []).append(b)
    for nhom, ds in nhom_bai.items():
        with st.expander(nhom):
            for b in ds:
                if st.button(b["tieu_de"], key=f"bai_{b['row']}_{b['tieu_de']}", width="stretch"):
                    ss.pending = f"Hướng dẫn: {b['tieu_de']}"
    st.markdown(f'<div class="hotline-card">Không có câu trả lời?<br>Gọi hotline <b>{HOTLINE}</b></div>',
                unsafe_allow_html=True)

# ---------- Tiêu đề ----------
st.markdown('<div class="hero"><span class="hero-badge">✨ Trợ lý 24/7 · trả lời trong vài giây</span>'
            '<div class="hero-title">Chào bạn, hôm nay bạn cần tra cứu thông tin gì?</div>'
            '<div class="hero-sub">Gõ câu hỏi, dán hoặc tải ảnh lỗi lên đây, trợ lý sẽ giúp bạn ✨</div></div>',
            unsafe_allow_html=True)

if "GROQ_API_KEY" not in st.secrets:
    st.error("Chưa khai báo GROQ_API_KEY trong Secrets.")
    st.stop()
client = Groq(api_key=st.secrets["GROQ_API_KEY"], max_retries=1, timeout=60)
model = st.secrets.get("GROQ_MODEL", DEFAULT_MODEL)
vision_model = st.secrets.get("GROQ_VISION_MODEL", VISION_MODEL)


def gui_gop_y(i: int, danh_gia: str, ghi_chu: str = ""):
    m = ss.messages[i]
    try:
        if da_ket_noi_sheet():
            bai_dung = "; ".join(m.get("bai", [])) or "không tìm thấy bài nào"
            goi_post({"action": "feedback", "danh_gia": danh_gia, "cau_hoi": m.get("question", ""),
                      "tra_loi": f"{m['content']}\n\n[Bài trợ lý đã tìm: {bai_dung}]", "ghi_chu": ghi_chu})
        ss.fb_sent.add(i)
        st.toast("Cảm ơn bạn đã góp ý!")
    except Exception as e:
        st.error(f"Chưa gửi được góp ý: {e}")


def nut_sao_chep(noi_dung: str):
    """Nút sao chép câu trả lời dạng chữ thường (bỏ ký hiệu **, #) để dán vào Zalo, email..."""
    chu = re.sub(r"\*\*|__|^#+\s*", "", noi_dung, flags=re.M).strip()
    st.iframe(f"""<style>body{{margin:0;padding:2px 0}}</style>
<button id="b" style="font:500 14px 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;color:#221E1E;
background:#FFFFFF;border:1px solid #E6E0DE;border-radius:8px;padding:6px 14px;cursor:pointer">📋 Sao chép câu trả lời</button>
<script>
const chu = {json.dumps(chu).replace("</", "<\\/").replace("<!--", "<\\!--")};
const b = document.getElementById("b");
function xong() {{ b.textContent = "✓ Đã sao chép"; setTimeout(() => b.textContent = "📋 Sao chép câu trả lời", 2000); }}
function cachCu() {{
  const t = document.createElement("textarea"); t.value = chu; document.body.appendChild(t); t.select();
  try {{ document.execCommand("copy"); xong(); }} catch (e) {{ b.textContent = "Không sao chép được"; }}
  t.remove();
}}
b.onclick = () => {{
  if (navigator.clipboard) navigator.clipboard.writeText(chu).then(xong).catch(cachCu); else cachCu();
}};
</script>""", height=44)


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


# Gói miễn phí của Groq chỉ cho khoảng 8.000 token/phút, nên gửi tài liệu vừa đủ để trả lời nhanh
GIOI_HAN_BAI = [3500, 1500, 1000]  # số ký tự tối đa của bài khớp nhất, bài thứ 2, bài thứ 3


def rut_gon(text: str, toi_da: int) -> str:
    return text if len(text) <= toi_da else text[:toi_da].rsplit("\n", 1)[0] + "\n(...)"


def tham_so_them(ten_model: str) -> dict:
    """Model gpt-oss suy nghĩ trước khi trả lời: để mức nghĩ thấp cho nhanh."""
    return {"reasoning_effort": "low"} if "gpt-oss" in ten_model else {}


def bao_loi_ai(e: Exception) -> str:
    t = str(e).lower()
    if "rate" in t or "429" in t or "413" in t or "too large" in t:
        return f"⚠️ Trợ lý đang quá tải, bạn vui lòng thử lại sau ít phút hoặc gọi hotline {HOTLINE}."
    return f"⚠️ Lỗi khi gọi AI: {e}"


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
        model=vision_model, temperature=0.2, max_tokens=800,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": f"{PROMPT_DOC_ANH}\nCâu hỏi kèm theo của người dùng: {cau_hoi}"},
            {"type": "image_url", "image_url": {"url": url}},
        ]}],
    )
    mo_ta = kq.choices[0].message.content or ""
    return re.sub(r"<think>.*?</think>", "", mo_ta, flags=re.S).strip()


tra_loi_goc = [""]  # câu trả lời nguyên bản, còn dòng [[BAI:x]]


def an_ma_bai(dong_chu):
    """Hiện câu trả lời từng chữ nhưng giữ lại phần [[BAI:x]] ở cuối, không cho người dùng thấy."""
    tra_loi_goc[0] = ""
    cho = ""
    for manh in dong_chu:
        tra_loi_goc[0] += manh
        cho += manh
        i = cho.find("[[")
        if i == -1:
            j = cho.rfind("[")  # có thể là nửa đầu của "[["
            if j != -1 and j == len(cho) - 1:
                yield cho[:j]
                cho = cho[j:]
            else:
                yield cho
                cho = ""
        else:
            if cho[:i]:
                yield cho[:i]
            cho = cho[i:]  # từ "[[" trở đi giữ lại, không hiện
    if "[[" not in cho:
        yield cho


# Tự tải lại trang khi mất kết nối với máy chủ (để lâu không dùng, máy ngủ, app vừa cập nhật...)
# để khách không gặp màn hình "đơ" bấm không được. Chỉ tải lại khi máy chủ đã sẵn sàng.
TU_KET_NOI_LAI = """<script>
const w = window.parent;
if (!w.__tuKetNoiLai) {
  w.__tuKetNoiLai = true;
  const s = w.document.createElement("script");
  s.textContent = `
    (function () {
      let mat = 0, dangThu = false;
      setInterval(async function () {
        const loi = document.querySelector('[data-testid="stConnectionStatus"]');
        mat = loi ? mat + 5 : 0;
        if (mat < 20 || dangThu) return;
        dangThu = true;
        try {
          const r = await fetch("_stcore/health", {cache: "no-store"});
          if (r.ok) { location.reload(); return; }
        } catch (e) {}
        dangThu = false;
      }, 5000);
    })();`;
  w.document.head.appendChild(s);
}
</script>"""
st.iframe(TU_KET_NOI_LAI, height=1)


# ---------- Hội thoại ----------
with st.chat_message("assistant", avatar=AVATAR_TRO_LY):
    st.markdown(LOI_CHAO)
    if not ss.messages:
        cols = st.columns(2)
        for i, (g, ic) in enumerate(zip(GOI_Y, ICON_GOI_Y)):
            if cols[i % 2].button(f"{ic}  {g}", width="stretch", key=f"goiy_{i}"):
                ss.pending = g

for i, m in enumerate(ss.messages):
    with st.chat_message(m["role"], avatar=AVATAR_TRO_LY if m["role"] == "assistant" else None):
        if m.get("img"):
            st.image(m["img"], width=320)
        st.markdown(m["content"])
        if m["role"] == "assistant":
            hien_anh(m.get("anh", []))
            if not m["content"].startswith("⚠️"):
                nut_sao_chep(m["content"])
            khung_gop_y(i)

# Sau khi có câu trả lời: đưa màn hình về đúng câu hỏi vừa hỏi để đọc từ đầu, không bị cuộn xuống cuối
if ss.get("cuon_den") is not None:
    vi_tri = ss.pop("cuon_den") + 1  # +1 vì có lời chào ở đầu
    st.iframe(f"""<script>
    const doc = window.parent.document;
    function den(lan) {{
      const tin = doc.querySelectorAll('[data-testid="stChatMessage"]');
      if (tin[{vi_tri}]) tin[{vi_tri}].scrollIntoView({{block: "start"}});
      if (lan > 0) setTimeout(() => den(lan - 1), 250);
    }}
    setTimeout(() => den(4), 150);
    </script>""", height=1)

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

    bat_dau = time.time()
    mo_ta_anh = ""
    if anh_gui:
        with st.spinner("Đang xem ảnh..."):
            try:
                mo_ta_anh = doc_anh_bang_ai(anh_gui, cau_hoi)
            except Exception as e:
                st.warning(f"Chưa đọc được ảnh ({e}). Trợ lý sẽ trả lời theo câu hỏi chữ.")

    # Câu hỏi nối tiếp ("cái này", "còn sao chép thì sao") cần thêm câu hỏi trước để tìm đúng bài
    cau_truoc = next((m["content"] for m in reversed(ss.messages[:-1]) if m["role"] == "user"), "")
    ket_qua = tim_bai(f"{cau_hoi}\n{cau_hoi}\n{mo_ta_anh}\n{cau_truoc}", k=len(GIOI_HAN_BAI), kem_diem=True)
    tai_lieu = [b for _, b in ket_qua]
    ngu_canh = "\n\n---\n\n".join(f"[TÀI LIỆU {i}: {b['nhom']} > {b['tieu_de']}]\n{trich_doan(b['noi_dung'], f"{cau_hoi} {mo_ta_anh}", GIOI_HAN_BAI[i - 1])}"
                                   for i, b in enumerate(tai_lieu, 1)) \
        or "(Không tìm thấy bài liên quan)"
    lich_su = [{"role": m["role"], "content": rut_gon(m["content"], 600)} for m in ss.messages[-5:-1]]
    messages = ([{"role": "system", "content": SYSTEM_PROMPT}] + lich_su
                + [{"role": "user", "content": f"TÀI LIỆU:\n{ngu_canh}\n\n"
                                              + (f"NGƯỜI DÙNG GỬI KÈM ẢNH CHỤP MÀN HÌNH, NỘI DUNG ẢNH:\n{mo_ta_anh}\n\n"
                                                 if mo_ta_anh else "")
                                              + f"CÂU HỎI: {cau_hoi}"}])

    with st.chat_message("assistant", avatar=AVATAR_TRO_LY):
        try:
            with st.spinner("Trợ lý đang soạn câu trả lời..."):
                stream = client.chat.completions.create(model=model, messages=messages, temperature=0, stream=True,
                                                        max_tokens=1500, **tham_so_them(model))
            tra_loi = st.write_stream(an_ma_bai(chunk.choices[0].delta.content or "" for chunk in stream)).strip()
        except Exception as e:
            tra_loi = bao_loi_ai(e)
            st.error(tra_loi)
    # Ảnh minh họa: lấy theo bài mà trợ lý cho biết đã dựa vào (dòng [[BAI:x]] cuối câu trả lời)
    m_bai = re.search(r"\[\[\s*BAI\s*:\s*(\d+)\s*\]\]", tra_loi_goc[0])
    anh = []
    if not tra_loi.startswith("⚠️") and "chưa có nội dung" not in tra_loi.lower():
        if m_bai:
            so = int(m_bai.group(1))
            if 1 <= so <= len(tai_lieu):
                anh = tai_lieu[so - 1].get("anh", [])
        elif ket_qua:  # trợ lý không ghi số bài: chỉ hiện ảnh khi bài đầu vượt trội rõ ràng
            diem_2 = ket_qua[1][0] if len(ket_qua) > 1 else 0
            if ket_qua[0][0] >= 1.3 * diem_2:
                anh = ket_qua[0][1].get("anh", [])
    # Ghi lại lượt hỏi để thống kê (chạy nền, đã che thông tin liên hệ)
    if tra_loi.startswith("⚠️"):
        ket_qua_hoi = "Lỗi AI"
    elif "chưa có nội dung" in tra_loi.lower():
        ket_qua_hoi = "Chưa có nội dung"
    else:
        ket_qua_hoi = "Đã trả lời"
    bai_dung = (tai_lieu[int(m_bai.group(1)) - 1]["tieu_de"]
                if m_bai and 1 <= int(m_bai.group(1)) <= len(tai_lieu) else "")
    goi_post_nen({"action": "log_question", "cau_hoi": che_thong_tin(cau_hoi), "co_anh": bool(anh_gui),
                  "bai": bai_dung, "ket_qua": ket_qua_hoi, "giay": round(time.time() - bat_dau, 1)})
    ss.cuon_den = len(ss.messages) - 1  # vị trí câu hỏi vừa gửi
    ss.messages.append({"role": "assistant", "content": tra_loi, "question": cau_hoi + (" [kèm ảnh]" if anh_gui else ""),
                        "anh": anh, "bai": [b["tieu_de"] for b in tai_lieu]})
    st.rerun()
