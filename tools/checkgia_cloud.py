#!/usr/bin/env python3
"""Đẩy trang Check giá + dữ liệu lên kho kín Supabase (bucket checkgia) và đọc/ghi bảng tai_lieu.

Tài khoản máy quét: ~/.config/cuahang/may.env (SB_EMAIL=..., SB_PASS=...), chmod 600. Không in mật khẩu.

  checkgia_cloud.py kiem                       # thử đăng nhập
  checkgia_cloud.py day <thu_muc> [ghi_chu] [--bo letak]  # đẩy index.html, data/*.json (Check giá; --bo letak = So giá leták vào letak/)
                                               # --bo letak: XUẤT BẢN THEO PHIÊN BẢN (letak/v/<ver>/…, manifest đổi sau cùng)
  checkgia_cloud.py doc <bo> [chi_chua_xong]   # in JSON {id: data} của 1 bộ (report, views, ean, letak_list, status)
  checkgia_cloud.py ghi <bo> <id> <json|@file> # ghi 1 tài liệu (vd status f5 '{"state":"done",...}')
"""
import gzip, hashlib, json, os, sys, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone

SB_URL = 'https://xgqblifqfgvicnxdddye.supabase.co'
SB_KEY = 'sb_publishable_fDH0P14KjDq0D_2KXjS_oA_tjy-6jlf'
BUCKET = 'checkgia'
ENV = os.path.expanduser('~/.config/cuahang/may.env')
BO = {'letak': ['index.html', 'data/ean.json', 'data/img.json', 'data/ncc_list.json']}   # bộ khác: thư mục con trong bucket
FILES = ['index.html', 'data/cat.json', 'data/deals.json', 'data/dod_img.json',
         'data/letak.json', 'data/report_replies.json', 'data/akce_unikom.json']


def req(method, path, body=None, headers=None, token=None, timeout=300):
    h = {'apikey': SB_KEY}
    if token: h['Authorization'] = 'Bearer ' + token
    h.update(headers or {})
    if isinstance(body, (dict, list)):
        body = json.dumps(body, ensure_ascii=False).encode(); h.setdefault('Content-Type', 'application/json')
    r = urllib.request.Request(SB_URL + path, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as x:
            t = x.read(); return json.loads(t) if t and 'json' in x.headers.get('Content-Type', '') else t
    except urllib.error.HTTPError as e:
        raise SystemExit(f'Lỗi {e.code} {method} {path.split("?")[0]}: {e.read().decode(errors="replace")[:400]}')


def login():
    if not os.path.exists(ENV): raise SystemExit(f'Chưa có {ENV} (tài khoản máy quét)')
    env = dict(l.strip().split('=', 1) for l in open(ENV) if '=' in l and not l.startswith('#'))
    if not env.get('SB_PASS'): raise SystemExit(f'{ENV} chưa có SB_PASS')
    j = req('POST', '/auth/v1/token?grant_type=password', {'email': env['SB_EMAIL'], 'password': env['SB_PASS']})
    return j['access_token']


def upload(tok, name, raw, ctype):
    req('POST', f'/storage/v1/object/{BUCKET}/{urllib.parse.quote(name)}', raw,
        {'Content-Type': ctype, 'x-upsert': 'true', 'Cache-Control': 'no-cache'}, tok)


def day(folder, note='', bo=''):
    tok = login(); pre = bo + '/' if bo else ''; ds = BO.get(bo, FILES)
    old = {}
    try:
        m = req('GET', f'/storage/v1/object/authenticated/{BUCKET}/{pre}manifest.json', token=tok, headers={'Cache-Control': 'no-cache'})
        old = (m if isinstance(m, dict) else json.loads(m or b'{}')).get('files', {})
    except SystemExit: pass
    files, sent = {}, 0
    for f in ds:
        p = os.path.join(folder, f)
        if not os.path.exists(p):
            if f in old: files[f] = old[f]  # giữ bản cũ trên cloud
            continue
        raw = open(p, 'rb').read(); sha = hashlib.sha256(raw).hexdigest()[:16]
        files[f] = {'sha': sha, 'size': len(raw)}
        if old.get(f, {}).get('sha') == sha: continue
        upload(tok, pre + f + '.gz', gzip.compress(raw, 9), 'application/gzip'); sent += 1
        print(f'  ↑ {f} {len(raw)//1024} KB')
    man = {'files': files, 'luc': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'note': note}
    upload(tok, pre + 'manifest.json', json.dumps(man, ensure_ascii=False).encode(), 'application/json')
    print(f'ok: {sent} file mới, {len(files)} file trên cloud, lúc {man["luc"]}')


def _get(tok, path):
    return req('GET', f'/storage/v1/object/authenticated/{BUCKET}/{urllib.parse.quote(path)}', token=tok, headers={'Cache-Control': 'no-cache'})


def day_ver(folder, note='', bo='letak', loi_sau=None):
    """Xuất bản theo phiên bản (4.11.2026): mọi file vào <bo>/v/<ver>/…; tải lại từng file kiểm sha; đủ hết mới ghi
    <bo>/manifest.json = {ver, files, luc, note}. App đọc mọi file theo manifest.ver → hỏng giữa chừng thì manifest vẫn
    trỏ phiên bản cũ (trọn vẹn). File không có trong thư mục (vd ean.json) thì CHÉP từ phiên bản cũ sang phiên bản mới.
    loi_sau=N (hoặc biến môi trường F5_LOI_SAU=N): cố ý làm lỗi sau N file – chỉ để kiểm thử."""
    if loi_sau is None and os.environ.get('F5_LOI_SAU'): loi_sau = int(os.environ['F5_LOI_SAU'])
    tok = login(); pre = bo + '/'
    try:
        m = _get(tok, pre + 'manifest.json'); old = m if isinstance(m, dict) else json.loads(m or b'{}')
    except SystemExit: old = {}
    ofiles, over = old.get('files', {}), old.get('ver')
    ver = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    vp = f'{pre}v/{ver}/'; files, n = {}, 0
    for f in BO.get(bo, FILES):
        p = os.path.join(folder, f)
        if os.path.exists(p):
            raw = open(p, 'rb').read(); files[f] = {'sha': hashlib.sha256(raw).hexdigest()[:16], 'size': len(raw)}
            upload(tok, vp + f + '.gz', gzip.compress(raw, 9), 'application/gzip')
        elif f in ofiles:
            src = (f'{pre}v/{over}/' if over else pre) + f + '.gz'
            req('POST', '/storage/v1/object/copy', {'bucketId': BUCKET, 'sourceKey': src, 'destinationKey': vp + f + '.gz'}, token=tok)
            files[f] = ofiles[f]
        else: continue
        n += 1; print(f'  ↑ {f} → v/{ver}')
        if loi_sau is not None and n >= loi_sau: raise SystemExit(f'(thử lỗi) dừng sau {n} file – phiên bản {ver} dở, manifest chưa đổi')
    for f, i in files.items():   # đọc lại từng file của phiên bản mới
        raw = gzip.decompress(_get(tok, vp + f + '.gz'))
        if hashlib.sha256(raw).hexdigest()[:16] != i['sha']: raise SystemExit(f'Đọc lại {f} ở v/{ver} không khớp – không đổi manifest')
    man = {'ver': ver, 'files': files, 'luc': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'note': note, 'truoc': over}
    upload(tok, pre + 'manifest.json', json.dumps(man, ensure_ascii=False).encode(), 'application/json')
    print(f'ok: phiên bản {ver}, {len(files)} file, lúc {man["luc"]}')
    try:   # dọn: giữ phiên bản hiện hành + 2 bản trước
        ls = req('POST', f'/storage/v1/object/list/{BUCKET}', {'prefix': pre + 'v/', 'limit': 100, 'sortBy': {'column': 'name', 'order': 'desc'}}, token=tok)
        vs = sorted({x['name'] for x in ls if x.get('name')}, reverse=True)
        for v in vs[3:]:
            ds = req('POST', f'/storage/v1/object/list/{BUCKET}', {'prefix': f'{pre}v/{v}/', 'limit': 100}, token=tok)
            ks = [f'{pre}v/{v}/' + x['name'] for x in ds if x.get('name')] + [f'{pre}v/{v}/data/' + x['name'] for x in (req('POST', f'/storage/v1/object/list/{BUCKET}', {'prefix': f'{pre}v/{v}/data/', 'limit': 100}, token=tok) or []) if x.get('name')]
            if ks: req('DELETE', f'/storage/v1/object/{BUCKET}', {'prefixes': ks}, token=tok)
    except SystemExit as e: print('  (dọn phiên bản cũ lỗi, bỏ qua)', e)
    return man


def doc(bo, chua_xong=False):
    tok = login()
    rows = req('GET', f'/rest/v1/tai_lieu?select=id,data,luc&bo=eq.{urllib.parse.quote(bo)}', token=tok)
    out = {r['id']: dict(r['data'], _luc=r['luc']) if isinstance(r['data'], dict) else r['data'] for r in rows}
    if chua_xong: out = {k: v for k, v in out.items() if not (isinstance(v, dict) and v.get('done'))}
    print(json.dumps(out, ensure_ascii=False, indent=1))


def ghi(bo, id_, val):
    tok = login()
    data = json.load(open(val[1:])) if val.startswith('@') else json.loads(val)
    req('POST', '/rest/v1/tai_lieu?on_conflict=bo,id', {'bo': bo, 'id': id_, 'data': data},
        {'Prefer': 'resolution=merge-duplicates,return=minimal'}, tok)
    print('ok')


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit()
    if a[0] == 'kiem': login(); print('ok: đăng nhập được')
    elif a[0] == 'day':
        bo = a[a.index('--bo') + 1] if '--bo' in a else ''
        (day_ver if bo == 'letak' else day)(a[1], ' '.join(x for x in a[2:] if x not in ('--bo', bo)), bo)
    elif a[0] == 'doc': doc(a[1], len(a) > 2)
    elif a[0] == 'ghi': ghi(a[1], a[2], a[3])
    else: print(__doc__)
