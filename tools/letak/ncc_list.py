#!/usr/bin/env python3
"""Danh sách chung "Nhập rẻ hơn siêu thị" (anh Viktor yêu cầu 23.10.2026).
Mọi lần so leták: món mà Makro / JIP / Tamda / Bidfood rẻ hơn giá akce siêu thị (cùng hãng, ≥3 %) được GỘP vào 1 danh sách
chung, giữ mãi các lần sau. Mỗi nơi nhập có hàng chờ riêng: trang nào chưa đăng nhập thì món nằm "chờ"; lần sau trang đó
đăng nhập được thì thêm hết món "chờ" vào danh sách trên chính trang đó (Makro seznam, JIP wish-list) rồi đánh dấu "đã thêm".

  python3 ncc_list.py merge <YYYY-MM-DD>          ncc_list.json (cũ, có thể chưa có) + letak_ncc_new.json → ncc_list.json, in số món chờ
  python3 ncc_list.py pending <Makro|JIP>         in JSON mảng mã cần thêm (Makro: bettyBundleId, JIP: variantId)
  python3 ncc_list.py done <Makro|JIP> <ngày> <file mã đã thêm .json>   đánh dấu "đã thêm"
Tamda, Bidfood: chưa có cách tạo danh sách trên web → chỉ giữ trong ncc_list.json (hiện trên trang So giá leták).
"""
import json, sys, os
F = 'ncc_list.json'
def load():
    if os.path.exists(F):
        try: return json.load(open(F))
        except Exception: pass
    return {'items': {}}
def save(d): json.dump(d, open(F, 'w'), ensure_ascii=False, separators=(',', ':'))
LISTABLE = {'Makro', 'JIP'}
cmd = sys.argv[1]
d = load(); it = d['items']
if cmd == 'merge':
    day = sys.argv[2]; new = json.load(open('letak_ncc_new.json')); added = 0
    for e in new:
        k = e['key']; o = it.get(k)
        if not o:
            o = it[k] = dict(src=e['src'], id=e['id'], n=e['n'], first=day, seen=[], st=('chờ' if e['src'] in LISTABLE and e['id'] else 'chỉ trên trang'))
            added += 1
        o.update(n=e['n'], p=e['p'], eq=e['eq'], sm=e['sm'], last=day)
        if day not in o['seen']: o['seen'].append(day)
    save(d)
    from collections import Counter
    print('mới', added, '| tổng', len(it), '| chờ:', dict(Counter(o['src'] for o in it.values() if o['st'] == 'chờ')))
elif cmd == 'pending':
    src = sys.argv[2]
    print(json.dumps([o['id'] for o in it.values() if o['src'] == src and o['st'] == 'chờ']))
elif cmd == 'done':
    src, day, ids = sys.argv[2], sys.argv[3], set(map(str, json.load(open(sys.argv[4]))))
    n = 0
    for o in it.values():
        if o['src'] == src and o['st'] == 'chờ' and str(o['id']) in ids: o['st'] = 'đã thêm'; o['added'] = day; n += 1
    save(d); print('đánh dấu đã thêm', n)
