"""Trợ lý Hóa đơn điện tử - Nhanh.vn

Chạy trên máy: streamlit run app.py
- Trang hỏi đáp: mở thẳng, không cần đăng nhập.
- Trang quản lý: thêm /quan-ly vào cuối địa chỉ trang, đăng nhập bằng ADMIN_PASSWORD.
Secrets cần khai báo: xem file HUONG_DAN_CAI_DAT.md
"""
import streamlit as st

from common import ICON, ap_dung_giao_dien

st.set_page_config(page_title="Trợ lý Hóa đơn điện tử", page_icon=ICON, layout="wide")
ap_dung_giao_dien()

trang = st.navigation(
    [
        st.Page("hoi_dap.py", title="Hỏi đáp", default=True),
        st.Page("quan_ly.py", title="Quản lý", url_path="quan-ly"),
    ],
    position="hidden",  # không hiện menu trang; admin vào bằng địa chỉ /quan-ly
)
trang.run()
