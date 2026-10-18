/**
 * Kết nối giữa Google Sheet và "Trợ lý Hóa đơn điện tử".
 * Dán toàn bộ file này vào Tiện ích mở rộng > Apps Script của file Sheet dữ liệu.
 *
 * Tab đầu tiên  : kiến thức (Nhóm | Tên bài | Link | Nội dung | Ảnh minh họa)
 * Tab "GopY"    : góp ý người dùng (tự tạo khi có góp ý đầu tiên)
 * Tab "TaiKhoan": tài khoản trang quản lý (tự tạo; mật khẩu chỉ lưu dạng đã mã hóa)
 *
 * Bảo mật: đặt Script property tên TOKEN (một chuỗi bí mật bất kỳ),
 * và khai báo cùng chuỗi đó là APPS_SCRIPT_TOKEN trong Secrets của Streamlit.
 */

var GOPY_SHEET = 'GopY';
var GOPY_HEADER = ['Thời gian', 'Đánh giá', 'Câu hỏi', 'Trả lời', 'Ghi chú', 'Trạng thái'];
var TK_SHEET = 'TaiKhoan';
var ANH_FOLDER = 'Ảnh Trợ lý Hóa đơn điện tử';
var TK_HEADER = ['Tên đăng nhập', 'Mật khẩu (đã mã hóa)', 'Quyền', 'Ngày tạo', 'Người tạo'];

function doGet(e) {
  var p = e.parameter || {};
  if (!checkToken_(p.token)) return json_({ ok: false, error: 'Sai token' });
  if (p.action === 'articles') return json_({ ok: true, rows: readRows_(kienThucSheet_()) });
  if (p.action === 'feedback') return json_({ ok: true, rows: readRows_(gopYSheet_()) });
  if (p.action === 'accounts') return json_({ ok: true, rows: readRows_(taiKhoanSheet_()) });
  return json_({ ok: false, error: 'Không rõ action' });
}

function doPost(e) {
  var d;
  try {
    d = JSON.parse(e.postData.contents);
  } catch (err) {
    return json_({ ok: false, error: 'Dữ liệu gửi lên không hợp lệ' });
  }
  if (!checkToken_(d.token)) return json_({ ok: false, error: 'Sai token' });

  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    if (d.action === 'feedback') {
      gopYSheet_().appendRow([
        new Date(), safe_(d.danh_gia), safe_(d.cau_hoi), safe_(d.tra_loi), safe_(d.ghi_chu), 'Chưa xử lý'
      ]);
      return json_({ ok: true });
    }
    if (d.action === 'save_article') {
      var sh = kienThucSheet_();
      var values = [safe_(d.nhom), safe_(d.ten), safe_(d.link), safe_(d.noi_dung), safe_(d.anh)];
      var row = parseInt(d.row, 10);
      if (row >= 2 && row <= sh.getLastRow()) {
        sh.getRange(row, 1, 1, 5).setValues([values]);
      } else {
        sh.appendRow(values);
      }
      return json_({ ok: true });
    }
    if (d.action === 'upload_image') {
      var mime = String(d.mime || '');
      if (!/^image\/(png|jpeg|webp|gif)$/.test(mime)) return json_({ ok: false, error: 'Chỉ nhận ảnh PNG, JPG, WEBP, GIF' });
      var blob = Utilities.newBlob(Utilities.base64Decode(d.data), mime, String(d.name || 'anh'));
      var file = anhFolder_().createFile(blob);
      file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
      return json_({ ok: true, id: file.getId() });
    }
    if (d.action === 'mark_done') {
      var g = gopYSheet_();
      var r = parseInt(d.row, 10);
      if (r >= 2 && r <= g.getLastRow()) g.getRange(r, 6).setValue('Đã xử lý');
      return json_({ ok: true });
    }
    if (d.action === 'add_account') {
      var tk = taiKhoanSheet_();
      var ten = String(d.username || '').trim();
      if (!ten) return json_({ ok: false, error: 'Thiếu tên đăng nhập' });
      var ds = tk.getDataRange().getDisplayValues();
      for (var i = 1; i < ds.length; i++) {
        if (String(ds[i][0]).trim().toLowerCase() === ten.toLowerCase()) {
          return json_({ ok: false, error: 'Tên đăng nhập đã tồn tại' });
        }
      }
      tk.appendRow([safe_(ten), safe_(d.password_hash), safe_(d.role), new Date(), safe_(d.created_by)]);
      return json_({ ok: true });
    }
    if (d.action === 'delete_account') {
      var t = taiKhoanSheet_();
      var dr = parseInt(d.row, 10);
      if (dr >= 2 && dr <= t.getLastRow() &&
          String(t.getRange(dr, 1).getDisplayValue()).trim() === String(d.username || '').trim()) {
        t.deleteRow(dr);
        return json_({ ok: true });
      }
      return json_({ ok: false, error: 'Không tìm thấy tài khoản, hãy tải lại trang' });
    }
    return json_({ ok: false, error: 'Không rõ action' });
  } finally {
    lock.releaseLock();
  }
}

function checkToken_(token) {
  var expected = PropertiesService.getScriptProperties().getProperty('TOKEN');
  return !!expected && token === expected;
}

function kienThucSheet_() {
  return SpreadsheetApp.getActive().getSheets()[0];
}

function gopYSheet_() {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(GOPY_SHEET);
  if (!sh) {
    sh = ss.insertSheet(GOPY_SHEET);
    sh.appendRow(GOPY_HEADER);
    sh.setFrozenRows(1);
  }
  return sh;
}

function taiKhoanSheet_() {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(TK_SHEET);
  if (!sh) {
    sh = ss.insertSheet(TK_SHEET);
    sh.appendRow(TK_HEADER);
    sh.setFrozenRows(1);
  }
  return sh;
}

function anhFolder_() {
  var it = DriveApp.getFoldersByName(ANH_FOLDER);
  return it.hasNext() ? it.next() : DriveApp.createFolder(ANH_FOLDER);
}

function readRows_(sh) {
  var values = sh.getDataRange().getDisplayValues();
  var out = [];
  for (var i = 1; i < values.length; i++) {
    out.push({ row: i + 1, cells: values[i] });
  }
  return out;
}

// Chặn chữ do người dùng nhập bị Sheet hiểu thành công thức (=, +, -, @)
function safe_(v) {
  var s = (v === undefined || v === null) ? '' : String(v);
  return /^[=+\-@]/.test(s) ? "'" + s : s;
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
