"""Trang quản lý: kiến thức, góp ý, tài khoản (phân quyền Admin / Giảng viên / Thực tập)."""
import csv
import hmac
import io

import streamlit as st

import base64

from common import (BRAND, LOGO, da_ket_noi_sheet, doc_gop_y, doc_tai_khoan, doc_tat_ca_bai, esc, ghi_anh, goi_post,
                    kiem_tra_mat_khau, lam_moi_du_lieu, ma_hoa_mat_khau, nguon_anh)

# Quyền của từng vai trò
QUYEN = {
    "Admin": {"them_bai", "sua_bai", "xem_gop_y", "xu_ly_gop_y", "tai_khoan"},
    "Giảng viên": {"them_bai", "sua_bai", "xem_gop_y"},
    "Thực tập": {"them_bai", "sua_bai"},
}
MO_TA_QUYEN = {
    "Admin": "Toàn bộ quyền truy cập",
    "Giảng viên": "Xem toàn bộ đánh giá + nạp và cập nhật kiến thức",
    "Thực tập": "Nạp kiến thức + cập nhật kiến thức",
}
MENU = [("Kiến thức", {"them_bai", "sua_bai"}), ("Góp ý người dùng", {"xem_gop_y"}),
        ("Quản lý tài khoản", {"tai_khoan"})]

ss = st.session_state
ss.setdefault("user", None)  # {"username", "role"}
ss.setdefault("bai_moi_goi_y", "")


def co_quyen(q: str) -> bool:
    return bool(ss.user) and q in QUYEN.get(ss.user["role"], set())


def dang_nhap(ten: str, mk: str):
    """Trả về vai trò nếu đúng, None nếu sai. Tài khoản gốc lấy từ Secrets."""
    goc_ten = str(st.secrets.get("ADMIN_USERNAME", "admin"))
    goc_mk = str(st.secrets.get("ADMIN_PASSWORD", ""))
    if goc_mk and ten.lower() == goc_ten.lower():
        return "Admin" if hmac.compare_digest(mk.encode(), goc_mk.encode()) else None
    if not da_ket_noi_sheet():
        return None
    for tk in doc_tai_khoan():
        if tk["username"].lower() == ten.lower():
            ok = kiem_tra_mat_khau(mk, tk["password_hash"]) and tk["role"] in QUYEN
            return tk["role"] if ok else None
    return None


# ---------- Đăng nhập ----------
if not ss.user:
    _, giua, _ = st.columns([1, 1.2, 1])
    with giua:
        st.image(LOGO, width=260)
        st.markdown(f"#### {BRAND}")
        st.markdown("## Đăng nhập quản trị")
        st.caption("Dành cho người quản lý kiến thức và xem góp ý của người dùng.")
        if not st.secrets.get("ADMIN_PASSWORD"):
            st.error("Chưa khai báo ADMIN_PASSWORD trong Secrets nên chưa thể đăng nhập.")
            st.stop()
        with st.form("dang_nhap"):
            ten = st.text_input("Tên đăng nhập", placeholder="Nhập tên đăng nhập")
            mk = st.text_input("Mật khẩu", type="password", placeholder="Nhập mật khẩu")
            if st.form_submit_button("Đăng nhập", type="primary", width="stretch"):
                try:
                    vai_tro = dang_nhap(ten.strip(), mk)
                except Exception as e:
                    vai_tro = None
                    st.error(f"Không kiểm tra được tài khoản: {e}")
                if vai_tro:
                    ss.user = {"username": ten.strip(), "role": vai_tro}
                    ss.admin_tab = next(m for m, q in MENU if q & QUYEN[vai_tro])
                    st.rerun()
                else:
                    st.error("Tên đăng nhập hoặc mật khẩu chưa đúng.")
        st.markdown("Người dùng hỏi đáp không cần đăng nhập. [Về trang hỏi đáp →](/)")
    st.stop()

if ss.get("chuyen_tab"):  # đổi mục từ nút bấm
    ss.admin_tab = ss.pop("chuyen_tab")
menu_duoc_xem = [m for m, q in MENU if any(co_quyen(x) for x in q)]
if ss.get("admin_tab") not in menu_duoc_xem:
    ss.admin_tab = menu_duoc_xem[0]

# ---------- Thanh bên ----------
with st.sidebar:
    st.image(LOGO, width="stretch")
    st.markdown(f'<div class="brand">{BRAND}</div><div class="sub">Trang quản lý</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub" style="margin-top:10px">Xin chào <b>{esc(ss.user["username"])}</b>'
                f' · {esc(ss.user["role"])}</div>', unsafe_allow_html=True)
    st.write("")
    for muc in menu_duoc_xem:
        if st.button(muc, key=f"nav_{muc}", width="stretch",
                     type="primary" if ss.admin_tab == muc else "secondary"):
            ss.admin_tab = muc
            st.rerun()
    tab = ss.admin_tab
    st.markdown("[↗  Xem trang hỏi đáp](/)")
    st.write("")
    if st.button("Đăng xuất", width="stretch"):
        ss.user = None
        st.rerun()

if not da_ket_noi_sheet():
    st.warning("Chưa kết nối Google Sheet (thiếu APPS_SCRIPT_URL / APPS_SCRIPT_TOKEN trong Secrets). "
               "Trang quản lý cần kết nối này để đọc và lưu dữ liệu.")
    st.stop()


# ======================= KIẾN THỨC =======================
def doi_hien_nhom(n: str, rows: list, k: str):
    """Chỉ chạy khi người quản lý bấm bật/tắt: ghi cột 'Ẩn trên web' cho cả nhóm."""
    hien_web = ss[k]
    try:
        goi_post({"action": "set_hidden", "rows": rows, "value": "" if hien_web else "Ẩn"})
        lam_moi_du_lieu()
        st.toast(f"Đã {'hiện' if hien_web else 'ẩn'} nhóm {n} trên web.")
    except Exception as e:
        ss.loi_hien_nhom = str(e)


def trang_kien_thuc():
    h1, h2 = st.columns([3, 2])
    h1.markdown("## Kiến thức")
    h1.caption("Các bài hướng dẫn trợ lý dùng để trả lời. Dữ liệu lưu trên Google Sheet.")
    b1, b2 = h2.columns(2)
    if b1.button("⟳  Đồng bộ từ Sheet", width="stretch"):
        lam_moi_du_lieu()
        st.rerun()
    if co_quyen("them_bai") and b2.button("＋  Thêm bài", type="primary", width="stretch"):
        ss.dang_sua = "moi"

    try:
        bai = doc_tat_ca_bai()
    except Exception as e:
        st.error(f"Không đọc được Google Sheet: {e}")
        return

    da_co = sum(1 for b in bai if b["noi_dung"])
    m = st.columns(4)
    m[0].metric("Tổng số bài", len(bai))
    m[1].metric("Đã có nội dung", da_co)
    m[2].metric("Chưa có nội dung", len(bai) - da_co)
    m[3].metric("Số nhóm", len({b["nhom"] for b in bai if b["nhom"]}))

    ds_nhom = list(dict.fromkeys(b["nhom"] for b in bai if b["nhom"]))
    nhom_an = {n for n in ds_nhom if all(x["an"] for x in bai if x["nhom"] == n)}

    if co_quyen("sua_bai"):
        with st.expander(f"👁  Hiển thị nhóm trên web · đang ẩn {len(nhom_an)}/{len(ds_nhom)} nhóm"):
            st.caption("Tắt để ẩn cả nhóm khỏi mục lục bên trái trang hỏi đáp. "
                       "Bài bị ẩn vẫn được trợ lý dùng để trả lời.")
            cot = st.columns(3)
            for i, n in enumerate(ds_nhom):
                rows = [x["row"] for x in bai if x["nhom"] == n]
                k = f"hien_nhom_{n}"
                ss[k] = n not in nhom_an  # luôn lấy theo dữ liệu mới nhất trên Sheet
                cot[i % 3].toggle(f"{n} ({len(rows)} bài)", key=k, on_change=doi_hien_nhom, args=(n, rows, k))
            if ss.get("loi_hien_nhom"):
                st.error(f"Chưa đổi được: {ss.pop('loi_hien_nhom')}")

    trai, phai = st.columns([3, 2], gap="large")

    with trai:
        f1, f2, f3 = st.columns([2, 1.3, 1.3])
        tu_khoa = f1.text_input("Tìm bài", placeholder="Nhập tên bài...")
        loc_nhom = f2.selectbox("Nhóm", ["Tất cả nhóm"] + ds_nhom)
        loc_tt = f3.selectbox("Trạng thái", ["Tất cả", "Chưa có nội dung", "Đã có nội dung"])
        hien = [b for b in bai
                if (not tu_khoa or tu_khoa.lower() in b["tieu_de"].lower())
                and (loc_nhom == "Tất cả nhóm" or b["nhom"] == loc_nhom)
                and (loc_tt == "Tất cả" or (loc_tt == "Đã có nội dung") == bool(b["noi_dung"]))]
        bang = [{"Nhóm": b["nhom"], "Tên bài": b["tieu_de"],
                 "Trạng thái": "✅ Đã có nội dung" if b["noi_dung"] else "⚠️ Chưa có nội dung",
                 "Trên web": "🙈 Ẩn" if b["an"] else "Hiện"} for b in hien]
        chon = st.dataframe(bang, width="stretch", hide_index=True, height=520,
                            on_select="rerun", selection_mode="single-row", key="bang_bai")
        st.caption(f"Hiển thị {len(hien)} / {len(bai)} bài · Bấm vào một dòng để sửa")
        sel = chon.selection.rows[0] if chon.selection.rows else None
        if sel != ss.get("dong_da_chon"):  # chỉ đổi bài đang sửa khi bấm dòng khác
            ss.dong_da_chon = sel
            if sel is not None and sel < len(hien):
                ss.dang_sua = hien[sel]["row"]

    with phai:
        dang_sua = ss.get("dang_sua")
        if dang_sua == "moi" and not co_quyen("them_bai"):
            dang_sua = ss.dang_sua = None
        if dang_sua is None:
            st.info("Chọn một bài trong bảng để sửa" + (", hoặc bấm **Thêm bài**." if co_quyen("them_bai") else "."))
            return
        b = next((x for x in bai if x["row"] == dang_sua), None) if dang_sua != "moi" else None
        if dang_sua != "moi" and b is None:
            st.warning("Không tìm thấy bài này nữa, hãy đồng bộ lại.")
            return
        st.markdown("### " + ("Thêm bài mới" if b is None else "Sửa bài"))
        if b is not None:
            st.markdown('<span class="tag-good">Đã có nội dung</span>' if b["noi_dung"]
                        else '<span class="tag-bad">Chưa có nội dung</span>', unsafe_allow_html=True)
        with st.form(f"form_bai_{dang_sua}"):
            lua_chon_nhom = ds_nhom + (["(Nhóm mới)"] if co_quyen("them_bai") else [])
            nhom_mac_dinh = lua_chon_nhom.index(b["nhom"]) if b and b["nhom"] in ds_nhom else 0
            nhom = st.selectbox("Nhóm", lua_chon_nhom, index=nhom_mac_dinh)
            nhom_moi = st.text_input("Tên nhóm mới (nếu chọn Nhóm mới)") if co_quyen("them_bai") else ""
            ten = st.text_input("Tên bài", value=b["tieu_de"] if b else ss.bai_moi_goi_y)
            link = st.text_input("Link bài gốc", value=b["link"] if b else "")
            an_bai = st.checkbox("Ẩn bài này khỏi mục lục trên web (trợ lý vẫn dùng để trả lời)",
                                 value=b["an"] if b else False)
            noi_dung = st.text_area("Nội dung hướng dẫn", value=b["noi_dung"] if b else "", height=300,
                                    placeholder="Dán nội dung bài hướng dẫn vào đây. Nên ghi từng bước, "
                                                "giữ đúng tên menu và nút bấm.")

            st.markdown("**Ảnh minh họa**")
            anh_cu = b.get("anh", []) if b else []
            giu_anh = []
            for i, a in enumerate(anh_cu):
                c1, c2 = st.columns([1, 2])
                x = nguon_anh(a["src"])
                if x is not None:
                    c1.image(x, width="stretch")
                else:
                    c1.caption(f"Không tìm thấy ảnh {a['src']}")
                cap = c2.text_input(f"Chú thích ảnh {i + 1}", value=a["cap"], key=f"cap_{dang_sua}_{i}")
                if c2.checkbox("Giữ ảnh này", value=True, key=f"giu_{dang_sua}_{i}"):
                    giu_anh.append({"src": a["src"], "cap": cap.strip()})
            anh_moi = st.file_uploader("Thêm ảnh (PNG, JPG). Ảnh hiển thị theo thứ tự tải lên.",
                                       type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True,
                                       key=f"up_{dang_sua}")
            cap_moi = st.text_area("Chú thích cho ảnh mới (mỗi dòng một ảnh, theo thứ tự)", height=80,
                                   key=f"capmoi_{dang_sua}")
            luu = st.form_submit_button("Lưu vào Sheet", type="primary", width="stretch")
        if st.button("Hủy", width="stretch"):
            ss.dang_sua = None
            st.rerun()
        if luu:
            ten_nhom = nhom_moi.strip() if nhom == "(Nhóm mới)" else nhom
            if not ten.strip() or not ten_nhom:
                st.error("Cần có Tên bài và Nhóm.")
                return
            try:
                ds_anh = list(giu_anh)
                ds_cap = cap_moi.splitlines()
                for i, f in enumerate(anh_moi or []):
                    if f.size > 5 * 1024 * 1024:
                        raise RuntimeError(f"Ảnh {f.name} lớn hơn 5MB")
                    kq = goi_post({"action": "upload_image", "name": f.name, "mime": f.type or "image/png",
                                   "data": base64.b64encode(f.getvalue()).decode()})
                    ds_anh.append({"src": f"drive:{kq['id']}", "cap": ds_cap[i].strip() if i < len(ds_cap) else ""})
                goi_post({"action": "save_article", "row": b["row"] if b else None, "nhom": ten_nhom,
                          "ten": ten.strip(), "link": link.strip(), "noi_dung": noi_dung.strip(),
                          "anh": ghi_anh(ds_anh),
                          # bài mới thêm vào nhóm đang ẩn thì cũng ẩn theo nhóm
                          "an": "Ẩn" if an_bai or (b is None and ten_nhom in nhom_an) else ""})
            except Exception as e:
                st.error(f"Chưa lưu được: {e}")
                return
            lam_moi_du_lieu()
            ss.dang_sua, ss.bai_moi_goi_y = None, ""
            st.toast("Đã lưu vào Google Sheet. Trợ lý dùng nội dung mới ngay.")
            st.rerun()


# ======================= GÓP Ý =======================
def trang_gop_y():
    h1, h2 = st.columns([3, 2])
    h1.markdown("## Góp ý người dùng")
    h1.caption("Đánh giá người dùng gửi khi bấm 👍 hoặc 👎 dưới câu trả lời.")
    try:
        ds = doc_gop_y()
    except Exception as e:
        st.error(f"Không đọc được góp ý từ Google Sheet: {e}")
        return

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Thời gian", "Đánh giá", "Câu hỏi", "Trả lời", "Ghi chú", "Trạng thái"])
    for g in ds:
        w.writerow([g["thoi_gian"], g["danh_gia"], g["cau_hoi"], g["tra_loi"], g["ghi_chu"], g["trang_thai"]])
    b1, b2 = h2.columns(2)
    if b1.button("⟳  Làm mới", width="stretch"):
        st.rerun()
    b2.download_button("⤓  Tải về Excel", buf.getvalue().encode("utf-8-sig"), "gop_y.csv", "text/csv",
                       width="stretch")

    m = st.columns(4)
    m[0].metric("Tổng góp ý", len(ds))
    m[1].metric("Hữu ích", sum(g["danh_gia"] == "Hữu ích" for g in ds))
    m[2].metric("Chưa đúng", sum(g["danh_gia"] == "Chưa đúng" for g in ds))
    m[3].metric("Chưa xử lý", sum(g["trang_thai"] != "Đã xử lý" for g in ds))

    loc = st.radio("Lọc", ["Tất cả", "Chưa đúng", "Hữu ích", "Chưa xử lý"], horizontal=True,
                   label_visibility="collapsed")
    if loc == "Chưa xử lý":
        ds = [g for g in ds if g["trang_thai"] != "Đã xử lý"]
    elif loc != "Tất cả":
        ds = [g for g in ds if g["danh_gia"] == loc]
    if not ds:
        st.info("Chưa có góp ý nào ở mục này.")
        return

    for g in ds[:100]:
        tag = "tag-bad" if g["danh_gia"] == "Chưa đúng" else "tag-good"
        ghi_chu = (f'<div class="label">Ghi chú của người dùng</div><div>{esc(g["ghi_chu"])}</div>'
                   if g["ghi_chu"] else "")
        st.markdown(
            f'<div class="card"><div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px">'
            f'<div><span class="{tag}">{esc(g["danh_gia"])}</span> <span class="tag">{esc(g["trang_thai"])}</span></div>'
            f'<div class="hint">{esc(g["thoi_gian"])}</div></div>'
            f'<div class="label">Câu hỏi</div><div style="font-weight:600">{esc(g["cau_hoi"])}</div>'
            f'<div class="label">Trợ lý đã trả lời</div>'
            f'<div style="background:#F6F4F3;border-radius:8px;padding:10px 12px;color:#3D3838">{esc(g["tra_loi"].replace("**", ""))}</div>'
            f'{ghi_chu}</div>', unsafe_allow_html=True)
        c1, c2, _ = st.columns([1, 1, 3])
        if co_quyen("them_bai") and c1.button("✎ Bổ sung kiến thức", key=f"bs_{g['row']}", width="stretch"):
            ss.chuyen_tab, ss.dang_sua, ss.bai_moi_goi_y = "Kiến thức", "moi", g["cau_hoi"]
            st.rerun()
        if co_quyen("xu_ly_gop_y") and g["trang_thai"] != "Đã xử lý" and c2.button("Đánh dấu đã xử lý", key=f"xl_{g['row']}",
                                                         width="stretch"):
            try:
                goi_post({"action": "mark_done", "row": g["row"]})
                st.rerun()
            except Exception as e:
                st.error(f"Chưa cập nhật được: {e}")
    if len(ds) > 100:
        st.caption(f"Đang hiện 100 / {len(ds)} góp ý mới nhất. Tải về Excel để xem toàn bộ.")


# ======================= TÀI KHOẢN =======================
def trang_tai_khoan():
    st.markdown("## Quản lý tài khoản")
    st.caption("Tạo tài khoản cho người quản lý kiến thức. Mật khẩu được mã hóa trước khi lưu vào Google Sheet.")
    goc = str(st.secrets.get("ADMIN_USERNAME", "admin"))
    try:
        ds = doc_tai_khoan()
    except Exception as e:
        st.error(f"Không đọc được danh sách tài khoản: {e}")
        return

    trai, phai = st.columns([2, 3], gap="large")
    with trai:
        st.markdown("### Thêm tài khoản")
        with st.form("them_tk", clear_on_submit=True):
            ten = st.text_input("Tên đăng nhập", placeholder="Ví dụ: linh.nguyen")
            mk = st.text_input("Mật khẩu", type="password", placeholder="Ít nhất 6 ký tự")
            vai_tro = st.selectbox("Quyền", list(QUYEN), index=2,
                                   format_func=lambda r: f"{r} – {MO_TA_QUYEN[r]}")
            tao = st.form_submit_button("Tạo tài khoản", type="primary", width="stretch")
        if tao:
            ten = ten.strip()
            if not ten or len(mk) < 6:
                st.error("Cần có tên đăng nhập và mật khẩu từ 6 ký tự.")
            elif " " in ten:
                st.error("Tên đăng nhập không được có dấu cách.")
            elif ten.lower() == goc.lower() or any(t["username"].lower() == ten.lower() for t in ds):
                st.error("Tên đăng nhập đã tồn tại.")
            else:
                try:
                    goi_post({"action": "add_account", "username": ten, "password_hash": ma_hoa_mat_khau(mk),
                              "role": vai_tro, "created_by": ss.user["username"]})
                    st.toast(f"Đã tạo tài khoản {ten} ({vai_tro}).")
                    st.rerun()
                except Exception as e:
                    st.error(f"Chưa tạo được: {e}")
        st.markdown("**Các quyền**")
        for r, mo_ta in MO_TA_QUYEN.items():
            st.markdown(f"- **{r}**: {mo_ta}")

    with phai:
        st.markdown(f"### Danh sách tài khoản ({len(ds) + 1})")
        st.markdown(
            f'<div class="card" style="display:flex;justify-content:space-between;align-items:center;gap:8px">'
            f'<div><b>{esc(goc)}</b> <span class="tag-good">Admin</span><div class="hint">Tài khoản gốc · '
            f'không xóa được</div></div></div>', unsafe_allow_html=True)
        for t in ds:
            c1, c2 = st.columns([5, 1])
            tag = {"Admin": "tag-good", "Giảng viên": "tag", "Thực tập": "tag-bad"}.get(t["role"], "tag")
            c1.markdown(
                f'<div class="card"><b>{esc(t["username"])}</b> <span class="{tag}">{esc(t["role"])}</span>'
                f'<div class="hint">Tạo ngày {esc(t["ngay_tao"])} · bởi {esc(t["nguoi_tao"])}</div></div>',
                unsafe_allow_html=True)
            if t["username"].lower() == ss.user["username"].lower():
                c2.caption("Đang dùng")
            elif c2.button("Xóa", key=f"xoa_{t['row']}", width="stretch"):
                ss.xac_nhan_xoa = t
        x = ss.get("xac_nhan_xoa")
        if x:
            st.warning(f"Xóa tài khoản **{x['username']}**? Người này sẽ không đăng nhập được nữa.")
            k1, k2, _ = st.columns([1, 1, 3])
            if k1.button("Xóa luôn", type="primary", width="stretch"):
                try:
                    goi_post({"action": "delete_account", "row": x["row"], "username": x["username"]})
                    st.toast(f"Đã xóa {x['username']}.")
                except Exception as e:
                    st.error(f"Chưa xóa được: {e}")
                ss.xac_nhan_xoa = None
                st.rerun()
            if k2.button("Hủy", key="huy_xoa", width="stretch"):
                ss.xac_nhan_xoa = None
                st.rerun()


if tab == "Kiến thức":
    trang_kien_thuc()
elif tab == "Góp ý người dùng":
    trang_gop_y()
else:
    trang_tai_khoan()
