#!/usr/bin/env bash
# Chạy f5_worker.py thường trực: chỉ 1 bản (flock), chết thì 10 giây sau tự chạy lại.
# Windows gọi lúc đăng nhập qua cai_dat_f5.ps1:  wsl.exe -e bash -lc ~/nhan/tools/f5/f5_chay.sh
cd "$(dirname "$0")" || exit 1
mkdir -p ~/.local/share/cuahang/f5
exec 9>~/.local/share/cuahang/f5/f5.lock
flock -n 9 || { echo "f5_worker đang chạy rồi"; exit 0; }
while true; do
  python3 f5_worker.py >> ~/.local/share/cuahang/f5/chay.log 2>&1
  echo "$(date '+%F %T') f5_worker dừng (mã $?) – chạy lại sau 10 s" >> ~/.local/share/cuahang/f5/chay.log
  sleep 10
done
