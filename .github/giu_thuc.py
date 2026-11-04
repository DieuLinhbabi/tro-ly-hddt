"""Mở trang trợ lý bằng trình duyệt thật để Streamlit không cho app ngủ; nếu app đã ngủ thì bấm nút đánh thức."""
import sys
from playwright.sync_api import sync_playwright

URL = "https://trolynhanhinvoice.streamlit.app/"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto(URL, timeout=90_000)
    pg.wait_for_timeout(15_000)
    nut = pg.get_by_role("button", name="Yes, get this app back up")
    if nut.count():
        print("App đang ngủ, bấm đánh thức...")
        nut.first.click()
        pg.wait_for_timeout(90_000)
    # Nội dung app nằm trong khung (iframe) của Streamlit Cloud
    thay = any("tra cứu" in f.content() for f in pg.frames if f != pg.main_frame) or "tra cứu" in pg.content()
    print("App đang chạy." if thay else "Chưa thấy nội dung app, lần sau sẽ thử lại.")
    b.close()
    sys.exit(0)
