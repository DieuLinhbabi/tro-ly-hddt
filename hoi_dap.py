"""Màn hình hỏi đáp cho người dùng (không cần đăng nhập)."""
import base64
import io
import json
import re
import time
from collections import OrderedDict

import streamlit as st
from groq import Groq

from common import LOGO_NHO, BRAND, HOTLINE, LOGO, che_thong_tin, goi_post_nen, trich_doan, da_ket_noi_sheet, doc_tat_ca_bai, goi_post, nguon_anh, tim_bai

DEFAULT_MODEL = "llama-3.3-70b-versatile"
VISION_MODEL = "qwen/qwen3.8-27b"  # model Groq đọc được ảnh; đổi bằng GROQ_VISION_MODEL trong Secrets
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"  # AI dự phòng; đổi bằng GEMINI_MODEL trong Secrets
CAU_HOI_ANH = "Màn hình trong ảnh là gì và tôi cần làm gì tiếp theo?"
PROMPT_DOC_ANH = ("Đây là ảnh chụp màn hình phần mềm hóa đơn điện tử do người dùng gửi. Hãy mô tả ngắn gọn bằng tiếng Việt: "
                  "đang ở màn hình/menu nào, các nút và ô nhập chính, và chép NGUYÊN VĂN mọi thông báo lỗi hay cảnh báo "
                  "nếu có. Nếu ảnh là danh sách/bảng hóa đơn hoặc tờ khai thì chép NGUYÊN VĂN chữ ở cột Trạng thái "
                  "và các mã lỗi nhìn thấy. Nếu ảnh không phải màn hình phần mềm, nói rõ ảnh có gì. Không đoán cách xử lý.")
GOI_Y = ["Cách điều chỉnh hóa đơn?", "Hóa đơn sai thì xử lý thế nào?", "Lập mẫu 04/SS-HĐĐT", "Thêm người dùng và phân quyền"]
ICON_GOI_Y = ["✏️", "🧐", "📮", "👥"]
AVATAR_TRO_LY = "assets/mascot.png"
LOI_CHAO = ("Xin chào! Bạn cần tìm cách làm thao tác nào trên phần mềm hóa đơn điện tử? "
            "Có thể bắt đầu với một câu hỏi gợi ý bên dưới.")

SYSTEM_PROMPT = f"""Bạn là "Trợ lý Hóa đơn điện tử" của Nhanh.vn, hỗ trợ người dùng tra cứu cách sử dụng phần mềm hóa đơn điện tử.
Quy tắc:
- CHỈ trả lời dựa trên phần TÀI LIỆU được cung cấp. Không tự suy đoán thao tác không có trong tài liệu.
- Nếu người dùng định làm khác với quy định hoặc lưu ý trong TÀI LIỆU (ví dụ chuyển từ điều chỉnh sang thay thế), phải nhắc quy định đó trước rồi mới hướng dẫn cách làm đúng; không làm theo ngay yêu cầu sai.
- Được thêm lưu ý hoặc giải thích ngắn cho dễ hiểu (ví dụ kết quả sau khi làm xong), nhưng không bịa tên menu, tên nút hay thao tác không có trong tài liệu, không nhắc trang web hay hệ thống khác không có trong tài liệu.
- Chỉ dùng hướng dẫn của đúng chức năng người dùng hỏi; không lấy hướng dẫn của chức năng khác để trả lời thay (ví dụ hỏi thêm logo vào mẫu hóa đơn thì không trả lời bằng cách chèn logo trong nội dung email). Nếu tài liệu không có chức năng đó thì nói rõ là chưa có hướng dẫn.
- Khi TÀI LIỆU có nguyên tắc riêng cho đúng trường hợp của người dùng (ví dụ hóa đơn điều chỉnh/thay thế lại bị sai thì phải giữ nguyên hình thức cũ), nguyên tắc riêng đó được ưu tiên hơn hướng dẫn chung.
- Nếu TÀI LIỆU có thông tin liên quan, dù chỉ một phần, hãy trả lời theo phần đó (có thể nói rõ phần nào tài liệu chưa đề cập).
- Nếu người dùng chỉ chào hỏi, làm quen, cảm ơn, khen hoặc nói chuyện xã giao (ví dụ: hi, chào em, em là ai, cảm ơn nhé): đáp lại thân thiện, tự nhiên trong 1-2 câu như nhân viên CSKH (có thể giới thiệu mình là trợ lý hóa đơn điện tử của Nhanh.vn), rồi mời họ đặt câu hỏi hoặc gửi ảnh lỗi; KHÔNG trả lời câu "Tài liệu hướng dẫn chưa có nội dung này" và ghi [[BAI:0]].
- Chỉ khi không có tài liệu nào liên quan mới trả lời: "Tài liệu hướng dẫn chưa có nội dung này. Vui lòng gọi hotline {HOTLINE} để được hỗ trợ."
- Trình bày ngắn gọn, đánh số từng bước thao tác, in đậm tên menu/nút như trong tài liệu. Không dùng thẻ HTML (như <br>); không kẻ bảng khi một ô cần nhiều dòng, hãy dùng danh sách gạch đầu dòng.
- Trả lời như nhân viên CSKH: ngắn gọn, đúng trọng tâm, chỉ nêu cách làm cho đúng trường hợp của người dùng; KHÔNG liệt kê tất cả các trường hợp.
- BẮT BUỘC: với mọi câu hỏi về hóa đơn bị sai/cần sửa (kể cả hóa đơn điều chỉnh, hóa đơn thay thế vừa lập bị sai), nếu người dùng chưa nói rõ hóa đơn còn Nháp (chưa ký) hay đã ký phát hành/đã có mã CQT, thì PHẢI hỏi lại trạng thái trước theo cách bên dưới; không được gộp hướng dẫn cho nhiều trạng thái trong cùng một câu trả lời. Các từ như 'vừa lập', 'vừa tạo', 'vừa xuất' chưa cho biết hóa đơn đã ký hay chưa. NGOẠI LỆ: nếu câu hỏi hoặc NỘI DUNG ẢNH đã cho thấy trạng thái (ví dụ cột Trạng thái ghi 'Không đủ đk cấp mã/tiếp nhận', 'không hợp lệ', 'từ chối cấp mã', 'đã cấp mã', 'Nháp') thì KHÔNG hỏi lại trạng thái mà hướng dẫn luôn theo trạng thái đó. Câu hỏi có MÃ LỖI hoặc thông báo lỗi (ví dụ 'MLoi: 2002 - MTa: ...', 'lỗi 1012') thì KHÔNG hỏi trạng thái hóa đơn: đọc kỹ cả nội dung sau mã lỗi, tìm bài trong TÀI LIỆU khớp cả mã lẫn nội dung (lỗi tờ khai thì hướng dẫn theo tờ khai) và trả lời luôn; TÀI LIỆU không có thì nói rõ và mời gọi hotline. Người dùng nói 'đã phát hành', 'phát hành sai', 'xuất sai hóa đơn đã phát hành', 'đã gửi thuế' nghĩa là hóa đơn ĐÃ ký, ĐÃ gửi cơ quan thuế và ĐÃ được cấp mã: KHÔNG hỏi trạng thái, hướng dẫn luôn cách xử lý hóa đơn đã được cấp mã (không được hủy; tùy loại sai: Mẫu 04/SS-HĐĐT, điều chỉnh hoặc thay thế), và chỉ thêm 1 câu ngắn: nếu hóa đơn thực ra bị từ chối cấp mã hoặc còn Nháp thì cách xử lý khác. NGOẠI LỆ: người dùng hỏi CÁCH LÀM hóa đơn điều chỉnh/thay thế (kể cả làm hàng loạt, bằng file Excel) thì KHÔNG hỏi trạng thái mà hướng dẫn luôn, vì điều chỉnh/thay thế chỉ dùng cho hóa đơn đã phát hành; nếu có bài làm bằng Excel/hàng loạt thì dùng đúng bài đó.
- Nếu người dùng muốn tạo/lập/xuất/làm một hóa đơn mà chưa nói rõ loại hóa đơn, thì hỏi lại loại trước, kèm [[CHON: Hóa đơn bán ra mới | Hóa đơn điều chỉnh | Hóa đơn thay thế]]; sau khi người dùng chọn thì hướng dẫn đúng loại đó (hóa đơn bán ra mới: tạo trong Danh sách hóa đơn; điều chỉnh/thay thế: dùng chức năng Điều chỉnh hóa đơn/Thay thế hóa đơn).
- Nếu cách làm phụ thuộc vào thông tin người dùng CHƯA nói (ví dụ hóa đơn sai nhưng chưa nói hóa đơn đang ở trạng thái nào: Nháp/chưa ký phát hành, bị từ chối cấp mã, hay đã được cấp mã), thì CHƯA hướng dẫn mà hỏi lại 1 câu thật ngắn để khai thác thông tin. Ngay sau câu hỏi, thêm 1 dòng [[CHON: lựa chọn 1 | lựa chọn 2 | lựa chọn 3]] gồm 2-4 lựa chọn, mỗi lựa chọn tối đa 5 từ ; câu hỏi và các lựa chọn phải đúng chủ đề người dùng đang hỏi (ví dụ đang nói về lỗi tờ khai thì KHÔNG hỏi trạng thái hóa đơn). Mỗi vấn đề hỏi lại TỐI ĐA 2 lần và chỉ hỏi những thông tin quyết định cách làm (loại hóa đơn, trạng thái hóa đơn); không hỏi chi tiết lỗi sai ở đâu mà nêu ngắn gọn cách xử lý cho từng nhóm lỗi. Khi người dùng đã trả lời đủ thì phải hướng dẫn luôn. Khi hỏi lại, LUÔN có dòng [[CHON: ...]] và thêm 1 câu ngắn chỉ chỗ xem thông tin đó nếu TÀI LIỆU có (ví dụ: trạng thái hóa đơn xem ở **Hóa đơn bán ra → Danh sách hóa đơn**, cột **Trạng thái**).
- CHỈ hỏi lại khi TÀI LIỆU thật sự chia cách xử lý theo thông tin đó (ví dụ trạng thái hóa đơn, loại hóa đơn, hộ kinh doanh hay doanh nghiệp). KHÔNG tự nghĩ ra câu hỏi về điều TÀI LIỆU không nhắc tới (ví dụ 'đã cập nhật phần mềm chưa', 'đang dùng phiên bản nào', 'đã cài bản mới chưa'); phần mềm hóa đơn chạy trên web nên khách không phải tự cài hay cập nhật. Nếu người dùng đã nêu rõ mã lỗi thì trả lời luôn theo bài của mã lỗi đó; nếu TÀI LIỆU không có đúng nội dung lỗi đó thì nói rõ và mời gọi hotline, không đoán nguyên nhân.
- KHÔNG hỏi lại thông tin người dùng đã trả lời ở các lượt trước, và không hỏi để xác nhận điều người dùng vừa nói rõ (ví dụ 'đúng không?'). Câu nối tiếp ngắn (ví dụ 'tạo hàng loạt được không', 'còn cái kia thì sao') phải hiểu theo chủ đề đang nói trong cuộc trò chuyện.
- Khi người dùng bổ sung thông tin về mình hoặc trường hợp của mình (ví dụ 'tôi là công ty', 'tôi dùng chữ ký số USB'), KHÔNG hỏi lại mà trả lời lại cho đúng trường hợp đó dựa trên TÀI LIỆU; nếu TÀI LIỆU chỉ nói về trường hợp khác (ví dụ chỉ nói về hộ kinh doanh dùng CCCD) thì nói rõ tài liệu chưa có hướng dẫn riêng cho trường hợp của họ và mời gọi hotline.
- Nếu TÀI LIỆU không có hướng dẫn cho đúng yêu cầu (ví dụ làm hàng loạt), nói rõ tài liệu chưa hướng dẫn chi tiết phần đó, nêu phần liên quan nhất có trong tài liệu (ví dụ chức năng Nhập excel ở Danh sách hóa đơn) và mời gọi hotline; không thay bằng hướng dẫn của việc khác (ví dụ hướng dẫn tạo một hóa đơn).
- Nếu người dùng nói chưa biết cách xem thông tin bạn vừa hỏi (ví dụ 'xem trạng thái ở đâu', 'không biết xem'), thì hướng dẫn ngay cách xem theo TÀI LIỆU rồi kèm lại [[CHON: ...]]; tuyệt đối không lặp lại cùng câu hỏi và không chuyển sang chủ đề khác. Luôn bám theo vấn đề ban đầu của người dùng trong cuộc hội thoại.
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
st.markdown(f'<div class="hero"><img class="hero-logo" src="{LOGO_NHO}">'
            '<span class="hero-badge">✨ Trợ lý 24/7 · trả lời trong vài giây</span>'
            '<div class="hero-title">Chào bạn, hôm nay bạn cần tra cứu thông tin gì?</div>'
            '<div class="hero-sub">Gõ câu hỏi, dán hoặc tải ảnh lỗi lên đây, trợ lý sẽ giúp bạn ✨</div></div>',
            unsafe_allow_html=True)

if "GROQ_API_KEY" not in st.secrets:
    st.error("Chưa khai báo GROQ_API_KEY trong Secrets.")
    st.stop()
# Có Gemini dự phòng thì Groq không chờ thử lại khi quá tải (chờ có thể tới 20-30 giây), mà chuyển ngay sang Gemini
co_du_phong = bool(st.secrets.get("GEMINI_API_KEY"))
client = Groq(api_key=st.secrets["GROQ_API_KEY"], max_retries=0 if co_du_phong else 1,
              timeout=25 if co_du_phong else 60)
model = st.secrets.get("GROQ_MODEL", DEFAULT_MODEL)
vision_model = st.secrets.get("GROQ_VISION_MODEL", VISION_MODEL)

# AI dự phòng: chỉ dùng Gemini khi Groq báo quá tải hoặc lỗi. Không khai báo GEMINI_API_KEY thì bỏ qua.
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
gemini_client = None
if st.secrets.get("GEMINI_API_KEY"):
    from openai import OpenAI
    gemini_client = OpenAI(api_key=st.secrets["GEMINI_API_KEY"], base_url=GEMINI_URL, max_retries=0, timeout=60)
gemini_model = st.secrets.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
ai_da_dung = ["Groq"]  # AI đã trả lời câu hiện tại, để ghi vào thống kê


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


def goi_ai(**kw):
    """Gọi Groq trước; nếu Groq quá tải hoặc lỗi thì tự chuyển sang Gemini (nếu đã khai báo khóa)."""
    ten_model = kw.pop("model")
    try:
        kq = client.chat.completions.create(model=ten_model, **kw, **tham_so_them(ten_model))
        ai_da_dung[0] = "Groq"
        return kq
    except Exception:
        if gemini_client is None:
            raise
        try:
            # Gemini tính cả phần "suy nghĩ" vào giới hạn chữ, nên nới thêm để câu trả lời không bị cụt
            kq = gemini_client.chat.completions.create(model=gemini_model, reasoning_effort="low",
                                                       **{**kw, "max_tokens": kw.get("max_tokens", 1500) + 1000})
            ai_da_dung[0] = "Gemini"
            return kq
        except Exception:
            # Gemini cũng lỗi: quay lại Groq, lần này cho phép chờ và thử lại
            kq = client.with_options(max_retries=2, timeout=60).chat.completions.create(
                model=ten_model, **kw, **tham_so_them(ten_model))
            ai_da_dung[0] = "Groq"
            return kq


def doc_anh_bang_ai(anh: bytes, cau_hoi: str) -> str:
    """Nhờ model đọc ảnh mô tả màn hình/lỗi, để trợ lý tìm đúng bài hướng dẫn."""
    url = "data:image/jpeg;base64," + base64.b64encode(anh).decode()
    kq = goi_ai(
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
            if m.get("chon"):
                if i == len(ss.messages) - 1:  # chỉ cho bấm ở câu hỏi lại mới nhất
                    cot = st.columns(2)  # tối đa 2 nút một hàng để chữ không bị cắt
                    for j, lua_chon in enumerate(m["chon"]):
                        if cot[j % 2].button(lua_chon, key=f"chon_{i}_{j}", width="stretch"):
                            ss.pending = lua_chon
            else:
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

    # Câu hỏi nối tiếp ("cái này", "xem ở đâu") cần thêm các câu hỏi trước để tìm đúng bài theo vấn đề ban đầu
    cau_truoc = "\n".join([m["content"] for m in ss.messages[:-1] if m["role"] == "user"][-3:])
    ket_qua = tim_bai(f"{cau_hoi}\n{cau_hoi}\n{mo_ta_anh}\n{cau_truoc}", k=len(GIOI_HAN_BAI), kem_diem=True)
    tai_lieu = [b for _, b in ket_qua]
    ngu_canh = "\n\n---\n\n".join(f"[TÀI LIỆU {i}: {b['nhom']} > {b['tieu_de']}]\n{trich_doan(b['noi_dung'], f"{cau_hoi} {mo_ta_anh}", GIOI_HAN_BAI[i - 1])}"
                                   for i, b in enumerate(tai_lieu, 1)) \
        or "(Không tìm thấy bài liên quan)"
    # Đếm số lần trợ lý vừa hỏi lại liên tiếp: tối đa 2 lần rồi phải hướng dẫn luôn, tránh hỏi vòng vo
    so_lan_hoi_lai = 0
    for m in reversed([m for m in ss.messages[:-1] if m["role"] == "assistant"]):
        la_cau_hoi = m.get("chon") or (len(m["content"]) < 300 and m["content"].rstrip().endswith("?"))
        if not la_cau_hoi:
            break
        so_lan_hoi_lai += 1
    lich_su = [{"role": m["role"], "content": rut_gon(m["content"], 600)} for m in ss.messages[-5:-1]]
    messages = ([{"role": "system", "content": SYSTEM_PROMPT}] + lich_su
                + [{"role": "user", "content": f"TÀI LIỆU:\n{ngu_canh}\n\n"
                                              + (f"NGƯỜI DÙNG GỬI KÈM ẢNH CHỤP MÀN HÌNH, NỘI DUNG ẢNH:\n{mo_ta_anh}\n\n"
                                                 if mo_ta_anh else "")
                                              + (f"LƯU Ý: Bạn đã hỏi lại người dùng {so_lan_hoi_lai} lần liên tiếp. KHÔNG được hỏi thêm, KHÔNG ghi [[CHON]]; hãy hướng dẫn luôn dựa trên các thông tin người dùng đã trả lời.\n\n"
                                                 if so_lan_hoi_lai >= 2 else "")
                                              + f"CÂU HỎI: {cau_hoi}"}])

    with st.chat_message("assistant", avatar=AVATAR_TRO_LY):
        try:
            with st.spinner("Trợ lý đang soạn câu trả lời..."):
                stream = goi_ai(model=model, messages=messages, temperature=0, stream=True, max_tokens=1500)
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
    if ket_qua_hoi == "Đã trả lời" and m_bai and int(m_bai.group(1)) == 0:
        ket_qua_hoi = "Trò chuyện"  # chào hỏi, cảm ơn... không dùng tài liệu
    # Câu hỏi lại kèm lựa chọn: dòng [[CHON: a | b | c]] -> hiện thành nút bấm
    m_chon = re.search(r"\[\[\s*CHON\s*:(.*?)\]\]", tra_loi_goc[0], re.S)
    chon = [x.strip() for x in m_chon.group(1).split("|") if x.strip()][:4] if m_chon else []
    if so_lan_hoi_lai >= 2:
        chon = []  # đã hỏi đủ 2 lần: không hiện thêm nút chọn
    if chon:
        anh = []  # câu hỏi lại thì chưa cần ảnh minh họa
        ket_qua_hoi = "Hỏi lại thông tin"
    tra_loi = re.sub(r"<br\s*/?>", " ", tra_loi)
    bai_dung = (tai_lieu[int(m_bai.group(1)) - 1]["tieu_de"]
                if m_bai and 1 <= int(m_bai.group(1)) <= len(tai_lieu) else "")
    if ai_da_dung[0] == "Gemini":  # đánh dấu câu do AI dự phòng trả lời, để so sánh chất lượng
        bai_dung = f"{bai_dung} · (Gemini trả lời)" if bai_dung else "(Gemini trả lời)"
    goi_post_nen({"action": "log_question", "cau_hoi": che_thong_tin(cau_hoi), "co_anh": bool(anh_gui),
                  "bai": bai_dung, "ket_qua": ket_qua_hoi, "giay": round(time.time() - bat_dau, 1)})
    ss.cuon_den = len(ss.messages) - 1  # vị trí câu hỏi vừa gửi
    ss.messages.append({"role": "assistant", "content": tra_loi, "question": cau_hoi + (" [kèm ảnh]" if anh_gui else ""),
                        "anh": anh, "bai": [b["tieu_de"] for b in tai_lieu], "chon": chon})
    st.rerun()
