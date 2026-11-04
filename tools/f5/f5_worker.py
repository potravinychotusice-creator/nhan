#!/usr/bin/env python3
"""Máy cửa hàng nhận lệnh "Lấy giá mới" từ app (Supabase refresh_requests) – KHÔNG mở phiên Claude.

Chạy thường trực trong Ubuntu (WSL) bằng f5_chay.sh (tự chạy lại khi lỗi), khởi động cùng Windows bằng cai_dat_f5.ps1.
Mỗi 7 giây hỏi Supabase 1 lần (gọi hàm may_nhan_viec – cũng là nhịp tim). Có việc thì chạy ĐÚNG việc đã định sẵn:

  letak     Kupi.cz (Python, không cần trình duyệt) → so với giá nhập trong ~/checkgia → build trang → đẩy lên kho kín letak/
  checkgia  (chưa làm: giá Makro/JIP/Tamda cần đăng nhập – xem README_F5.md)

Chỉ báo "xong" SAU KHI đẩy Supabase thành công. Lỗi ở bất kỳ bước nào trước khi đẩy → cloud giữ nguyên bản cũ.
Tài khoản máy: ~/.config/cuahang/may.env (SB_EMAIL, SB_PASS) – dùng chung với checkgia_cloud.py, không in mật khẩu.
Cấu hình thêm (không bắt buộc): ~/.config/cuahang/f5.env
  GIA_DIR=~/checkgia        thư mục giá nhập (mk.json, jip.json, tamda.json, bidfood.json, unikom_cenik.json|unikom.json, inv_rows.json, dates.json)
  MAY_TEN=may-cua-hang      tên máy hiện trên app

  python3 f5_worker.py            chạy vòng lặp
  python3 f5_worker.py --mot-lan  chạy 1 việc 'letak' ngay, không qua hàng đợi (thử tay), CÓ đẩy lên cloud
  python3 f5_worker.py --kiem     thử đăng nhập + gọi hàm nhịp tim rồi thoát
"""
import datetime as dt, glob, gzip, json, os, shutil, socket, subprocess, sys, time, traceback, urllib.error, urllib.parse, urllib.request
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS); sys.path.insert(0, HERE)
import checkgia_cloud as cc  # SB_URL, SB_KEY, ENV, login(), day()
import kupi

PRAHA = ZoneInfo('Europe/Prague')
CFG = {}
_f = os.path.expanduser('~/.config/cuahang/f5.env')
if os.path.exists(_f):
    CFG = dict(l.strip().split('=', 1) for l in open(_f) if '=' in l and not l.lstrip().startswith('#'))
GIA = os.path.expanduser(CFG.get('GIA_DIR', '~/checkgia'))
MAY = CFG.get('MAY_TEN') or ('may-' + socket.gethostname())
WORK = os.path.expanduser('~/.local/share/cuahang/f5')
LOG = os.path.join(WORK, 'f5.log')
POLL = 7
VERSION = '2026-11-04'
os.makedirs(WORK, exist_ok=True)


def log(*a):
    s = dt.datetime.now(PRAHA).strftime('%Y-%m-%d %H:%M:%S') + ' ' + ' '.join(str(x) for x in a)
    print(s, flush=True)
    try:
        with open(LOG, 'a', encoding='utf-8') as f: f.write(s + '\n')
        if os.path.getsize(LOG) > 2_000_000: os.replace(LOG, LOG + '.1')
    except Exception: pass


# ---------- Supabase (REST, thư viện chuẩn) ----------
_tok = {'t': None, 'exp': 0}
def token():
    if not _tok['t'] or time.time() > _tok['exp']:
        _tok['t'] = cc.login(); _tok['exp'] = time.time() + 45 * 60  # token sống 1 giờ → đăng nhập lại sau 45 phút
    return _tok['t']


def rpc(name, args):
    body = json.dumps(args, ensure_ascii=False).encode()
    for lan in range(2):
        r = urllib.request.Request(cc.SB_URL + '/rest/v1/rpc/' + name, data=body, method='POST', headers={
            'apikey': cc.SB_KEY, 'Authorization': 'Bearer ' + token(), 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(r, timeout=30) as x:
                t = x.read(); return json.loads(t) if t else None
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors='replace')[:300]
            if e.code == 401 and lan == 0: _tok['t'] = None; continue
            raise RuntimeError(f'Supabase {name}: {e.code} {msg}')


def tai_cloud(path):
    """Tải 1 file trong kho kín checkgia (để lấy bản trước khi máy chưa có bản riêng)."""
    r = urllib.request.Request(cc.SB_URL + f'/storage/v1/object/authenticated/{cc.BUCKET}/' + urllib.parse.quote(path),
                               headers={'apikey': cc.SB_KEY, 'Authorization': 'Bearer ' + token()})
    with urllib.request.urlopen(r, timeout=120) as x: raw = x.read()
    return gzip.decompress(raw) if path.endswith('.gz') else raw


def bao(job, status, msg, kq=None):
    log(f'[{job["id"]}] {status}: {msg}')
    if job.get('thu_tay'): return
    try: rpc('may_bao', {'p_id': job['id'], 'p_may': MAY, 'p_status': status, 'p_thong_bao': msg, 'p_ket_qua': kq})
    except Exception as e: log('  không báo được trạng thái:', e)


def chay(cmd, cwd, env=None, timeout=900):
    p = subprocess.run(cmd, cwd=cwd, env=dict(os.environ, **(env or {})), capture_output=True, text=True, timeout=timeout)
    out = (p.stdout or '')[-1500:] + (p.stderr or '')[-1500:]
    if p.returncode != 0: raise RuntimeError(f'{" ".join(cmd[:3])} lỗi {p.returncode}: {out.strip()[-400:]}')
    return out


# ---------- Việc 'letak' ----------
def anh(rows, cu):
    """Ảnh 48 px webp cho món chưa có ảnh (cần Pillow; không có thì bỏ qua, giữ ảnh cũ)."""
    try:
        from PIL import Image
        import io, base64
    except Exception:
        log('  Pillow chưa cài → không lấy ảnh mới (pip install pillow)'); return cu
    can = {}
    for r in rows:
        s = (r.get('prod') or '').split('/')[-1]
        if s and r.get('img') and s not in cu and s not in can: can[s] = r['img']
    def mot(item):
        s, u = item
        try:
            rq = urllib.request.Request(u, headers={'User-Agent': kupi.UA})
            with urllib.request.urlopen(rq, timeout=20) as x: im = Image.open(io.BytesIO(x.read())).convert('RGBA')
            im.thumbnail((48, 48)); b = io.BytesIO(); im.save(b, 'WEBP', quality=60)
            return s, 'data:image/webp;base64,' + base64.b64encode(b.getvalue()).decode()
        except Exception: return s, None
    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(8) as ex:
        for s, v in ex.map(mot, can.items()):
            if v: cu[s] = v
    log(f'  ảnh: thêm {sum(1 for s in can if s in cu)}/{len(can)}')
    return cu


def viec_letak(job):
    hom_nay = dt.datetime.now(PRAHA).date().isoformat()
    D = os.path.join(WORK, 'letak'); MOI = os.path.join(WORK, 'letak_moi')
    os.makedirs(D, exist_ok=True)
    shutil.rmtree(MOI, ignore_errors=True); os.makedirs(os.path.join(MOI, 'data'))

    # Bản trước (để giữ ngày bắt đầu akce, ảnh, danh sách NCC). Lần đầu: lấy từ cloud.
    prev = os.path.join(D, 'letak_latest.json')
    if not os.path.exists(prev) or not os.path.exists(os.path.join(D, 'img.json')):
        bao(job, 'dang_chay', 'Lần đầu: tải bản leták trước từ cloud…')
        h = tai_cloud('letak/index.html.gz').decode('utf-8')
        i = h.index('const DATA=') + len('const DATA='); j = h.index('\n', i)
        open(prev, 'w', encoding='utf-8').write(h[i:j].rstrip().rstrip(';').replace('<\\/', '</'))
        for f in ('img.json', 'ncc_list.json', 'ean.json'):
            try: open(os.path.join(D, f), 'wb').write(tai_cloud('letak/data/' + f + '.gz'))
            except Exception as e: log('  chưa có', f, e)

    # 1. Kupi
    bao(job, 'dang_chay', 'Đang lấy leták 7 siêu thị từ Kupi.cz…')
    t0 = time.time()
    rows, err = kupi.scrape(log=lambda m: log('  ' + m))
    if len(rows) < 3000:
        raise RuntimeError(f'Kupi chỉ ra {len(rows)} akce (cần ≥ 3000) – có thể Kupi đổi trang hoặc mất mạng. Lỗi: {"; ".join(err[:3])}')
    json.dump(rows, open(os.path.join(MOI, 'kupi.json'), 'w'), ensure_ascii=False)
    gio_kupi = dt.datetime.now(PRAHA).strftime('%Y-%m-%d %H:%M')
    log(f'  Kupi {len(rows)} akce trong {int(time.time() - t0)} s, lỗi {len(err)}')

    # 2. Giá nhập (của máy, tự quét mỗi sáng) → chép vào thư mục làm
    bao(job, 'dang_chay', f'Kupi {len(rows)} akce. Đang so với giá nhập…')
    thieu = []
    for f, g in (('mk.json', 'mk.json'), ('jip.json', 'jip.json'), ('tamda.json', 'tamda.json'), ('bidfood.json', 'bidfood.json'),
                 ('unikom.json', 'unikom.json'), ('unikom_cenik.json', 'unikom.json'), ('inv_rows.json', 'inv_rows.json'), ('dates.json', 'dates.json')):
        p = os.path.join(GIA, f)
        if os.path.exists(p): shutil.copy(p, os.path.join(MOI, g))
    for g in ('mk.json', 'jip.json', 'tamda.json'):
        if not os.path.exists(os.path.join(MOI, g)): thieu.append(g)
    if 'mk.json' in thieu: raise RuntimeError(f'Không có giá Makro ({GIA}/mk.json) – không so được.')
    mk_ngay = dt.datetime.fromtimestamp(os.path.getmtime(os.path.join(MOI, 'mk.json')), PRAHA).date().isoformat()
    for f in ('letak_compare.py', 'build_letak.py', 'letak_page.html', 'ncc_list.py'):
        shutil.copy(os.path.join(TOOLS, 'letak', f), MOI)
    if os.path.exists(os.path.join(D, 'ncc_list.json')): shutil.copy(os.path.join(D, 'ncc_list.json'), MOI)

    # 3. So giá + build
    chay([sys.executable, 'letak_compare.py', hom_nay, mk_ngay], MOI, {'PREV_LETAK': prev, 'STAMP': gio_kupi})
    L = json.load(open(os.path.join(MOI, 'letak_data.json')))
    n, nd1 = len(L['D']), sum(1 for r in L['D'] if not r[10])
    if n < 3000: raise RuntimeError(f'So giá chỉ ra {n} dòng (cần ≥ 3000) – không đẩy.')
    if nd1: log(f'  cảnh báo: {nd1} dòng thiếu ngày hết hạn')
    try: chay([sys.executable, 'ncc_list.py', 'merge', hom_nay], MOI)
    except Exception as e: log('  ncc_list lỗi (bỏ qua):', e)
    chay([sys.executable, 'build_letak.py', 'letak_page.html'], MOI)

    # 4. Ảnh + gói đẩy
    img = {}
    try: img = json.load(open(os.path.join(D, 'img.json')))
    except Exception: pass
    img = anh(rows, img)
    slugs = {(r[22] or '').split('/')[-1] for r in L['D'] if len(r) > 22 and r[22]}
    img = {s: v for s, v in img.items() if s in slugs}
    PUB = os.path.join(MOI, 'pub'); os.makedirs(os.path.join(PUB, 'data'))
    shutil.copy(os.path.join(MOI, 'so-gia-letak.html'), os.path.join(PUB, 'index.html'))
    json.dump(img, open(os.path.join(PUB, 'data', 'img.json'), 'w'), separators=(',', ':'))
    if os.path.exists(os.path.join(MOI, 'ncc_list.json')): shutil.copy(os.path.join(MOI, 'ncc_list.json'), os.path.join(PUB, 'data'))
    # data/ean.json: không làm lại ở đây → cloud giữ bản cũ (day() tự giữ file không có)

    # 5. Đẩy Supabase (manifest ghi CUỐI CÙNG → app chỉ đổi sang bản mới khi mọi file đã lên)
    m = L['meta']
    note = f'Leták {hom_nay} {gio_kupi[-5:]} (máy, bấm F5): {m.get("n_buy")} món rẻ hơn giá nhập'
    bao(job, 'dang_chay', 'Đang đẩy lên app…')
    try: cc.day(PUB, note, 'letak')
    except SystemExit as e: raise RuntimeError(f'Đẩy Supabase lỗi: {e}')

    # 6. Thành công → giữ làm bản trước cho lần sau
    shutil.copy(os.path.join(MOI, 'letak_data.json'), prev)
    shutil.copy(os.path.join(PUB, 'data', 'img.json'), os.path.join(D, 'img.json'))
    if os.path.exists(os.path.join(MOI, 'ncc_list.json')): shutil.copy(os.path.join(MOI, 'ncc_list.json'), D)
    shutil.copy(os.path.join(MOI, 'kupi.json'), os.path.join(D, 'kupi_last.json'))
    sd = m.get('sup_dates') or {}
    kq = {'akce': len(rows), 'dong': n, 'r_hon_nhap': m.get('n_buy'), 'sap_co': m.get('n_fut'), 'gio_kupi': gio_kupi,
          'makro': mk_ngay, 'jip': sd.get('jip'), 'tamda': sd.get('tamda'), 'thieu': thieu, 'kupi_loi': len(err)}
    cu = [f'{k} {v[8:10]}.{v[5:7]}.' for k, v in (('JIP', sd.get('jip')), ('Tamda', sd.get('tamda'))) if v]
    return kq, (f'Xong: leták {gio_kupi[8:10]}.{gio_kupi[5:7]}. {gio_kupi[-5:]} · {len(rows)} akce · {m.get("n_buy")} món rẻ hơn giá nhập · '
                f'giá Makro {mk_ngay[8:10]}.{mk_ngay[5:7]}.' + (' · ' + ', '.join(cu) if cu else '') + (' · thiếu ' + ', '.join(thieu) if thieu else ''))


VIEC = {'letak': viec_letak}   # chỉ các việc cố định này; tên việc lạ → không chạy


def lam(job):
    f = VIEC.get(job['job'])
    if not f: bao(job, 'loi', f'Máy chưa biết làm việc "{job["job"]}".'); return
    try:
        kq, msg = f(job)
        bao(job, 'xong', msg, kq)
    except Exception as e:
        log(traceback.format_exc())
        bao(job, 'loi', f'Lỗi: {e}. App vẫn giữ dữ liệu cũ.'[:480])


def vong_lap():
    log(f'Bắt đầu nhận lệnh – máy "{MAY}", hỏi mỗi {POLL} s, giá nhập ở {GIA}')
    nhip = 0; loi_lien = 0
    while True:
        try:
            if time.time() - nhip > 60:
                rpc('may_nhip_tim', {'p_may': MAY, 'p_info': {'v': VERSION, 'viec': list(VIEC)}}); nhip = time.time()
            job = rpc('may_nhan_viec', {'p_may': MAY, 'p_jobs': list(VIEC)})
            loi_lien = 0
            if job and job.get('id'):
                log(f'Nhận yêu cầu {job["id"]} ({job["job"]})'); lam(job); nhip = 0
        except Exception as e:
            loi_lien += 1
            log('Lỗi khi hỏi Supabase:', e)
            if loi_lien > 3: time.sleep(min(300, 15 * loi_lien))  # mất mạng → giãn dần, tự hồi phục
        time.sleep(POLL)


if __name__ == '__main__':
    if '--kiem' in sys.argv:
        rpc('may_nhip_tim', {'p_may': MAY, 'p_info': {'v': VERSION, 'kiem': True}}); print('ok – đăng nhập và gọi hàm được, máy:', MAY)
    elif '--mot-lan' in sys.argv:
        job = {'id': 0, 'job': 'letak', 'thu_tay': True}
        kq, msg = viec_letak(job); print(msg); print(json.dumps(kq, ensure_ascii=False))
    else:
        vong_lap()
