#!/usr/bin/env python3
"""Tab "Săn Makro" trong app Cửa hàng (15.11.2026 anh chọn) – rút gọn result.json của lần quét Săn giá Makro
thành data/san.json (nhỏ, chỉ phần app cần) rồi đẩy lên kho kín Supabase:

  python3 xuat_san.py result.json [mk.json] [thu_muc_ra=san]
  python3 ../checkgia_cloud.py day san "Săn Makro <ngày giờ>" --bo sangia

mk.json (tuỳ chọn) để lấy mã ảnh Makro (cột r[17]). Không có thì app hiện biểu tượng nhóm hàng."""
import json, os, sys

res = json.load(open(sys.argv[1]))
img = {}
if len(sys.argv) > 2 and os.path.exists(sys.argv[2]):
    for r in json.load(open(sys.argv[2])):
        if len(r) > 17 and r[17]: img[str(r[0])] = r[17]
out = sys.argv[3] if len(sys.argv) > 3 else 'san'

K = ('id', 'n', 'ks', 'm', 'base', 'ratio', 'r_eff', 'end', 'top', 'sub', 'bb', 'silent', 'new', 'ns', 'st', 'wt', 'fav', 'prio',
     'fake', 'c_cheaper', 'c_src', 'c_eq', 'c_name', 'w_cheaper', 'w_src', 'w_eq')
drops = []
for d in res.get('drops', []):
    x = {k: d[k] for k in K if d.get(k) not in (None, '', False, [])}
    if img.get(str(d['id'])): x['img'] = img[str(d['id'])]
    drops.append(x)
cheap = []
for d in res.get('makro_cheap', []):
    x = {k: d[k] for k in ('id', 'n', 'ks', 'm', 'end', 'top', 'sub', 'bb', 'why', 'ratio', 'c_src', 'c_eq', 'c_name', 'new') if d.get(k) not in (None, '', False, [])}
    if img.get(str(d.get('id'))): x['img'] = img[str(d['id'])]
    cheap.append(x)
san = dict(stamp=res.get('stamp'), dates=res.get('dates'), counts=res.get('counts'), hist_dates=res.get('hist_dates'),
           drops=drops, cheap=cheap, gone=res.get('gone', []))
os.makedirs(os.path.join(out, 'data'), exist_ok=True)
p = os.path.join(out, 'data', 'san.json')
json.dump(san, open(p, 'w'), ensure_ascii=False, separators=(',', ':'))
print('ok', p, os.path.getsize(p) // 1024, 'KB ·', len(drops), 'món giảm ·', len(cheap), 'rẻ bất thường ·', len(san['gone']), 'vừa hết ·', len(img), 'ảnh')
