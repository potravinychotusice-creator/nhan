# Cài "máy nhận lệnh Lấy giá mới" tự chạy khi đăng nhập Windows (đúng phiên người dùng, chạy ẩn).
# Chạy 1 lần trong PowerShell THƯỜNG (không cần Admin):
# Trong Ubuntu:  powershell.exe -ExecutionPolicy Bypass -File "$(wslpath -w ~/nhan/tools/f5/cai_dat_f5.ps1)" -Distro "$WSL_DISTRO_NAME"
# Chạy lại nhiều lần an toàn: ghi đè cùng 2 việc, cùng file VBS.
param([Parameter(Mandatory=$true)][string]$Distro)   # tên bản Ubuntu (trong Ubuntu: echo $WSL_DISTRO_NAME)
$ErrorActionPreference = 'Stop'
$ds = (wsl.exe -l -q) -replace "`0", '' | Where-Object { $_.Trim() } | ForEach-Object { $_.Trim() }
if ($ds -notcontains $Distro) { throw "Khong thay ban WSL '$Distro'. Co: $($ds -join ', ')" }
$ten = 'CuaHang - Nhan lenh Lay gia moi'
$vbs = Join-Path $env:LOCALAPPDATA 'CuaHang\f5_an.vbs'
New-Item -ItemType Directory -Force -Path (Split-Path $vbs) | Out-Null
# VBS chạy wsl ẩn (không hiện cửa sổ đen)
Set-Content -Path $vbs -Encoding ASCII -Value ('CreateObject("WScript.Shell").Run "wsl.exe -d ' + $Distro + ' -e bash -lc ~/nhan/tools/f5/f5_chay.sh", 0, False')
$act = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument ('"' + $vbs + '"')
$trg = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
# Tự chạy lại nếu lỗi: 3 lần, cách 1 phút; không dừng sau 72 giờ; chạy cả khi dùng pin
$set = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$pr  = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $ten -Action $act -Trigger $trg -Settings $set -Principal $pr -Force | Out-Null
# Mỗi 15 phút gọi lại (f5_chay.sh có khoá flock → nếu đang chạy thì thoát ngay; nếu đã chết thì dựng lại)
$trg2 = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 15)
Register-ScheduledTask -TaskName ($ten + ' (kiem tra)') -Action $act -Trigger $trg2 -Settings $set -Principal $pr -Force | Out-Null
Start-ScheduledTask -TaskName $ten
Write-Host "Da cai va da chay: $ten"
Write-Host "Nhat ky trong Ubuntu: ~/.local/share/cuahang/f5/f5.log"
