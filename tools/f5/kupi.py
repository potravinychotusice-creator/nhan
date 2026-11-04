#!/usr/bin/env python3
"""Lấy toàn bộ akce 7 siêu thị trên Kupi.cz BẰNG PYTHON (không cần trình duyệt, không cần đăng nhập).
Bản Python của kupi.js (claude/so-gia-letak): cùng URL /slevy/<nhóm>/<chuỗi>?page=N, cùng cách đọc HTML, cùng dạng dòng.

  python3 kupi.py kupi.json            # → kupi.json (mảng dòng, giống window.KU)
  python3 kupi.py --test page.html     # chỉ đọc 1 trang HTML đã lưu (kiểm tra bộ đọc)

Chỉ dùng thư viện chuẩn. Kupi tự nhận vị trí theo IP (máy ở cửa hàng → Čáslav).
"""
import concurrent.futures as cf, html.parser, json, re, sys, time, urllib.request

SHOPS = ['kaufland', 'lidl', 'penny-market', 'albert', 'billa', 'tesco', 'globus']
CATS = {'alkohol': 'P', 'konzervy': 'P', 'lahudky': 'P', 'maso-drubez-a-ryby': 'P', 'mlecne-vyrobky-a-vejce': 'P',
        'mrazene-a-instantni-potraviny': 'P', 'nealko-napoje': 'P', 'ovoce-a-zelenina': 'P', 'pecivo': 'P',
        'sladkosti-a-slane-snacky': 'P', 'vareni-a-peceni': 'P', 'zdrava-vyziva': 'P', 'kojenecka-vyziva': 'P',
        'drogerie': 'D', 'krasa': 'D', 'domacnost': 'D', 'pleny-a-vlhcene-ubrousky': 'D', 'detska-kosmetika': 'D', 'mazlicci': 'D'}
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}


class N:  # nút DOM tối giản
    __slots__ = ('tag', 'a', 'kids', 'up')
    def __init__(s, tag, a, up): s.tag, s.a, s.kids, s.up = tag, a, [], up
    def cls(s): return (s.a.get('class') or '').split()
    def text(s):
        out = []
        def w(n):
            for k in n.kids:
                if isinstance(k, str): out.append(k)
                else: w(k)
        w(s); return ' '.join(''.join(out).split())
    def all(s, pred):
        r = []
        def w(n):
            for k in n.kids:
                if isinstance(k, N):
                    if pred(k): r.append(k)
                    w(k)
        w(s); return r
    def one(s, pred):
        x = s.all(pred); return x[0] if x else None


class B(html.parser.HTMLParser):
    def __init__(s):
        super().__init__(convert_charrefs=True); s.root = N('#', {}, None); s.cur = s.root
    def handle_starttag(s, tag, attrs):
        n = N(tag, dict((k, v or '') for k, v in attrs), s.cur); s.cur.kids.append(n)
        if tag not in VOID: s.cur = n
    def handle_startendtag(s, tag, attrs):
        s.cur.kids.append(N(tag, dict((k, v or '') for k, v in attrs), s.cur))
    def handle_endtag(s, tag):
        n = s.cur
        while n is not s.root and n.tag != tag: n = n.up
        if n is not s.root: s.cur = n.up
    def handle_data(s, d): s.cur.kids.append(d)


C = lambda c: (lambda n: c in n.cls())
def tx(n): return n.text() if n else ''
def num(s):
    m = re.search(r'-?\d+(\.\d+)?', (s or '').replace(' ', '').replace('\xa0', '').replace(',', '.', 1))
    return float(m.group(0)) if m else None


def parse(html, cat, ss, seen, rows):
    b = B(); b.feed(html); n = nw = 0
    for gp in b.root.all(C('group_discounts')):
        w = gp.one(C('product--wrap'))
        if not w: continue
        n += 1
        h2 = w.one(lambda x: x.tag == 'h2')
        name = tx(h2.one(lambda x: x.tag == 'strong')) if h2 else ''
        a = h2.one(lambda x: x.tag == 'a') if h2 else None
        prod = a.a.get('href', '') if a else ''
        pamt = tx(h2.one(C('nowrap'))) if h2 else ''
        pi = w.one(C('product_image')); im = pi.one(lambda x: x.tag == 'img') if pi else None
        img = (im.a.get('data-src') or im.a.get('src') or '') if im else ''
        for r in gp.all(C('discount_row')):
            did = r.a.get('data-discount')
            if did in seen: continue
            seen.add(did); nw += 1
            pb = r.one(C('discounts_price')); lk = r.one(C('btn_link_leaflet'))
            rows.append(dict(img=img, g=CATS[cat], cat=cat, shop=tx(r.one(C('discounts_shop_name'))), ss=ss, name=name, prod=prod, pamt=pamt,
                             amt=re.sub(r'^/\s*', '', tx(r.one(C('discount_amount')))), price=num(tx(r.one(C('discount_price_value')))),
                             pct=num(tx(r.one(C('discount_percentage')))), unit=tx(r.one(C('price_per_unit'))), club=tx(r.one(C('discounts_club'))),
                             valid=tx(r.one(C('discounts_validity'))), fut=bool(pb and any('future' in c for c in pb.cls())), note=tx(r.one(C('discount_note'))),
                             did=did, letak=lk.a.get('href', '') if lk else ''))
    return n, nw


def get(url, tries=3):
    for i in range(tries):
        try:
            rq = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'cs-CZ,cs;q=0.9'})
            with urllib.request.urlopen(rq, timeout=40) as x: return x.status, x.read().decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            if e.code in (404, 410): return e.code, ''
            err = e
        except Exception as e: err = e
        time.sleep(2 + 3 * i)
    raise err


def scrape(log=print):
    seen, rows, err = set(), [], []
    jobs = [(c, s) for c in CATS for s in SHOPS]
    def one(job):
        c, s = job; out = []
        for pg in range(1, 61):
            try:
                st, h = get(f'https://www.kupi.cz/slevy/{c}/{s}' + (f'?page={pg}' if pg > 1 else ''))
            except Exception as e:
                err.append(f'{c}/{s}:{e}'); break
            if st != 200:
                if pg == 1: err.append(f'{c}/{s}:{st}')
                break
            out.append(h)
            if 'discount_row' not in h: break
            # dừng như kupi.js: trang không có dòng mới → hết. Kiểm tra sơ bộ ở đây, kiểm chính xác khi ghép.
            if pg > 1 and h.count('data-discount=') == 0: break
        return c, s, out
    done = 0
    with cf.ThreadPoolExecutor(4) as ex:  # 4 luồng (kupi.js dùng 6), lịch sự với Kupi
        for c, s, pages in ex.map(one, jobs):
            for h in pages:
                n, nw = parse(h, c, s, seen, rows)
                if n == 0 or nw == 0: break
            done += 1
            if done % 19 == 0: log(f'Kupi {done}/{len(jobs)} · {len(rows)} akce')
    return rows, err


if __name__ == '__main__':
    if sys.argv[1] == '--test':
        rows = []; print(parse(open(sys.argv[2], encoding='utf-8').read(), 'alkohol', 'kaufland', set(), rows))
        print(json.dumps(rows[:4], ensure_ascii=False, indent=1)); sys.exit()
    rows, err = scrape()
    json.dump(rows, open(sys.argv[1], 'w'), ensure_ascii=False)
    print('ok', len(rows), 'akce, lỗi', len(err), err[:3])
