# Nút "Lấy giá mới" (F5) từ điện thoại – không qua Claude

Luồng: điện thoại bấm 🔄 F5 trong tab Leták → hàm Supabase `yeu_cau_lam_moi('letak')` → bảng `refresh_requests`
→ máy cửa hàng (`f5_worker.py`, chạy thường trực trong Ubuntu/WSL) hỏi mỗi 7 giây bằng `may_nhan_viec`
→ quét Kupi.cz (Python) → so với giá nhập trong `~/checkgia` → build trang → đẩy kho kín `checkgia/letak/`
→ báo `xong` → app tự mở bản mới. Không mở phiên Claude, không cần Tailscale/tunnel/mở cổng.

## Cài (1 lần)
1. **Supabase** → SQL Editor → New query → dán `supabase/b4-lay-gia-moi.sql` → Run. Cuối phải ra 2 bảng + 4 hàm.
2. **Ubuntu (WSL) trên máy cửa hàng**:
   ```
   cd ~/nhan && git pull
   pip install --user pillow        # không bắt buộc: chỉ để lấy ảnh món mới
   python3 tools/f5/f5_worker.py --kiem      # thử đăng nhập tài khoản máy (may.env) + gọi hàm
   python3 tools/f5/f5_worker.py --mot-lan   # chạy thử 1 lần thật: Kupi → so giá → đẩy lên app (2–5 phút)
   powershell.exe -ExecutionPolicy Bypass -File "$(wslpath -w ~/nhan/tools/f5/cai_dat_f5.ps1)"
   ```
   Lệnh cuối tạo việc Windows "CuaHang - Nhan lenh Lay gia moi": tự chạy khi đăng nhập Windows (đúng phiên anh, ẩn),
   thêm việc kiểm tra mỗi 15 phút (đã chạy thì thôi, chết thì dựng lại). `f5_chay.sh` có khoá `flock` → chỉ 1 bản.
3. Tuỳ chọn `~/.config/cuahang/f5.env`: `GIA_DIR=~/checkgia` (nơi có mk.json, jip.json, tamda.json, bidfood.json,
   unikom_cenik.json, inv_rows.json, dates.json) · `MAY_TEN=may-cua-hang`.

Nhật ký: `~/.local/share/cuahang/f5/f5.log` (và `chay.log`).

## An toàn
- Điện thoại chỉ gọi được `yeu_cau_lam_moi` (chủ + nhân viên). Không ghi thẳng bảng được (đã thu quyền insert/update/delete).
- Chỉ nhận việc trong danh sách cố định (`letak`, `checkgia`); worker chỉ có hàm cho `letak`. Không có chỗ nào nhận lệnh shell.
- Chống bấm trùng: chỉ mục duy nhất "1 việc đang chờ/chạy mỗi loại". Hai máy/hai tiến trình không nhận trùng: `FOR UPDATE SKIP LOCKED` + `flock`.
- Yêu cầu chờ quá 15 phút → `het_han` (không chạy lệnh cũ hôm sau). Đang chạy quá 45 phút không báo → `loi`.
- Máy offline (không có nhịp tim 90 s) → app ghi "ĐANG CHỜ MÁY", không ghi đã bắt đầu.
- Chỉ báo `xong` sau khi `checkgia_cloud.day()` đẩy xong; manifest ghi cuối → app chỉ đổi khi đủ file.
  Kupi < 3000 akce hoặc so giá < 3000 dòng → báo lỗi, KHÔNG đẩy → app giữ bản cũ.
- Mật khẩu máy chỉ nằm trong `~/.config/cuahang/may.env` trên máy. Frontend chỉ có khoá publishable (vốn có).

## Chưa làm / còn phụ thuộc
- Việc `checkgia` (Makro/JIP/Tamda cần đăng nhập): chưa có. Giá nhập dùng file trong `~/checkgia` (máy tự quét buổi sáng, nếu còn chạy).
  Trình duyệt có sẵn trong app Claude giữ đăng nhập riêng → script Windows/WSL KHÔNG dùng chung được.
- Kích hoạt scheduled task Claude từ script: không có giao diện chính thức đã kiểm chứng; lần thử "chạy ngay" từ chat bị chặn chờ người dùng duyệt → không dùng.
- `data/ean.json` (tra mã vạch trang leták) không làm lại ở đây → cloud giữ bản cũ.
