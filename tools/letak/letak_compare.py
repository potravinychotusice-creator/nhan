import os
#!/usr/bin/env python3
"""SO GIÁ LETÁK SIÊU THỊ – Kupi.cz (7 chuỗi) so với giá nhập Makro / JIP / Tamda.   (anh Viktor duyệt 23.10.2026)
Vào : kupi.json (kupi.js), mk.json (Makro, kho mk_last của trang Săn giá), jip.json, tamda.json (kho của trang Săn giá)
Ra  : letak_data.json  (dữ liệu cho trang 'So giá leták'), letak_hist_rows.json (dòng 'giá đẹp' để ghi Google Sheet)

QUY TẮC
- Mọi giá s DPH. Siêu thị: giá Kupi (giá thẻ/app nếu Kupi ghi vậy → cột 'the'). Makro: giá Distribuce, không dùng giá gạch ngang.
- Quy về CÙNG KHỐI LƯỢNG / DUNG TÍCH / SỐ CÁI / SỐ DÁVKA rồi mới so (giá / 1 g, ml, ks, dávka).
- Cùng hãng (hãng = các từ viết HOA ở cuối tên Kupi, vd 'Prací gel Persil' → persil) + cùng loại (chung ≥1 từ loại hàng) + cỡ ±12 %.
- Không cùng hãng (vd Lidl hàng nhãn riêng Pilos, Milbona…): cùng loại (chung ≥2 từ loại hàng) + cỡ ±12 % → ghi 'khác hãng'.
- 'Rẻ hơn giá nhập' khi rẻ hơn nơi nhập rẻ nhất ≥ 3 %; chênh < 3 % = ngang giá.
- 'Rẻ nhất giữa siêu thị': cùng sản phẩm Kupi, so giá / đơn vị giữa các chuỗi.
- Giới hạn số ks/khách: lấy từ ghi chú Kupi; Kupi không ghi thì để 'không ghi' (cần xem leták gốc – chưa chắc chắn).
"""
import json, re, unicodedata, datetime, statistics, sys
from collections import defaultdict

def na(s): return ''.join(ch for ch in unicodedata.normalize('NFD', (s or '').lower().replace("'", '').replace('\u2019', '')) if unicodedata.category(ch) != 'Mn')   # 27.10: Lay's = Lays
U = {'g':1,'kg':1000,'ml':1,'l':1000,'cl':10,'dl':100}
num = lambda s: float(s.replace(',', '.'))
GEN = set('metro aro fine horeca rioba bez vinarstvi vinne zamecke zamecka mlekarna vino vina chef pivovar sklepy'.split())
STOPT = set('chlaz mraz cerstve cerstvy baleno bal cena krabice plech pet sklo vratna lahev jakostni gastro platky platek krajene porce sada mix multipack pack baleni velke male mini maxi extra nove new edice limited sacek doza karton vanicka vanicky lahvicka sklenice ruzne druhy vybrane druh'.split())
SYN = {'kulick':'koule','kulock':'koule'}
def ttok(n): return set(SYN.get(x[:6], x[:6]) for x in re.findall(r'[a-z]+', na(n)) if len(x) >= 3 and x not in STOPT and x not in GEN and x not in SMALL)
SMALL = set('pro bez pod nad the and with s z na od do ke se ve'.split())
# từ chung chung không phải tên hãng (Kupi viết hoa cả tên dòng hàng)
NOTBRAND = set('swiss premium classic deluxe original gold bio extra fresh family mini maxi special selection select light zero max plus super ultra natural fine royal grand love life sun party baby kids home day night'.split())

DAV = r'(?:d[aá]vk[ay]?|d[aá]vek|pran[ií]|pd|wl|wash|praci[ch]* d[aá]v)'
def piece(n, ks=None):
    """-> (đơn vị 'u' (g/ml) | 'ks' | 'dav', cỡ 1 cái, số cái)"""
    s = (n or '').lower().replace(',', '.').replace('×', 'x').replace('(', ' ').replace(')', ' ')
    m = re.search(r'(\d+)\s*' + DAV + r'\b', s)
    if m: return 'dav', 1, int(m[1])
    m = re.search(r'((?:\d+\s*x\s*)+)(\d+(?:\.\d+)?)\s*(kg|g|ml|cl|dl|l)\b', s)
    if m:
        mul = [int(x) for x in re.findall(r'\d+', m[1])]; q = num(m[2]) * U[m[3]]
    else:
        m = re.search(r'(\d+(?:\.\d+)?)\s*(kg|g|ml|cl|dl|l)\b', s)
        if m:
            q = num(m[1]) * U[m[2]]; mul = []
            rest = s.replace(m[0], '')
            bag = re.search(r'(?:bag|big pack|pack|box)\s*(\d+)\b|(\d+)\s*(?:sáčk|sacku|sáčků|sachet|tyčin|kapsl)', rest)
            k = re.search(r'(?:@|\b)(\d+)\s*(?:ks|x)\b', rest)
            if bag and 1 < int(bag[1] or bag[2]) <= 100: n_ = int(bag[1] or bag[2]); q = q / n_; mul = [n_]
            elif k and 1 < int(k[1]) <= 48: mul = [int(k[1])]
        else:
            m = re.search(r'((?:\d+\s*x\s*)*)(\d+)\s*(?:ks|rol[ií]|role|kus[yů]?|ubrous|kaps|tablet|tbl)\w*', s)
            if not m: return None, None, None
            mul = [int(x) for x in re.findall(r'\d+', m[1])] + [int(m[2])]
            tot = 1
            for x in mul: tot *= x
            c = tot // ks if ks and ks > 1 and tot % ks == 0 else tot
            return 'ks', 1, max(c, 1)
    tot = 1
    for x in mul: tot *= x
    c = (tot // ks if tot % ks == 0 else 1) if ks and ks > 1 else tot
    return 'u', q, max(c, 1)
VAR = ['nealko','light','zero','bez cukru','bezlakt','protein','bio','12°','11°','10°','12 ','10 ','vsop','xo','reserve','12 let','18 let']
def vset(n):
    a = ' ' + na(n).replace('°', '° ') + ' '
    return frozenset(v for v in ['nealko','zero','bez cukru','bezlakt','protein','vsop',' xo ','12 let','18 let'] if v in a)
BAD = re.compile(r'\bcca\b|váž|\bKEG\b|\bsud\b|d[áa]rkov|sklenic|\+\s*\d|kazet', re.I)
def L(f, d=None):
    try: return json.load(open(f))
    except Exception: return d

# ---------- nhà cung cấp ----------
MK = L('mk.json', []); MK = MK.get('rows', []) if isinstance(MK, dict) else MK
JP = L('jip.json', []); TA = L('tamda.json', [])
TA = [r if len(r) >= 6 else ['', r[0], r[1], None, r[1], r[1]] for r in TA]
sup = []
for r in MK:
    if BAD.search(r[1]) or not r[3] or (len(r) > 15 and r[15] == 0): continue
    u, q, c = piece(r[1], r[2])
    # 29.10: tên có "N x cỡ" (vd 'Coca-Cola 4 x 330 ml') thì tin tên – r[11] Makro là tổng cả gói (1320 ml) làm 1 lon bị coi như 1,32 l
    if u == 'u' and len(r) > 12 and r[11] and r[12] in ('GRAM','ML','KILOGRAM','LITER','KG','L') and not re.search(r'\d\s*[x×]\s*\d', r[1]):
        qq = r[11] * (1000 if r[12] in ('KILOGRAM','LITER','KG','L') else 1)
        if not q or not (0.5 <= qq / q <= 2): q = qq; c = c or 1
    sup.append(dict(src='Makro', n=r[1], p=r[3], u=u, q=q, c=c, bn=na(r[10]) if len(r) > 10 and r[10] else '', id=r[0], bb=r[8] if len(r) > 8 else '', akce=bool(r[4] and r[4] < '2099')))
seen = set()
for r in JP:
    if r[0] in seen or BAD.search(r[0]) or not r[1]: continue
    seen.add(r[0]); u, q, c = piece(r[0]); sup.append(dict(src='JIP', n=r[0], p=r[1], u=u, q=q, c=c, akce=bool(r[2]), id=r[4] if len(r) > 4 else None))
for r in TA:
    if BAD.search(r[1]) or not r[2]: continue   # 25.10: giá 1 ks = r[2] (p1); r[5] = giá khi mua từ r[6] ks – không dùng (trước đây dùng r[5] là SAI)
    u, q, c = piece(r[1]); sup.append(dict(src='Tamda', n=r[1], p=r[2], u=u, q=q, c=c, akce=False))
# Bidfood (Nowaco, mujbidfood.cz – thêm 23.10.2026): bidfood.json từ bidfood.js. Giá s DPH = pv (cả balení).
# Hàng bán theo kg/l (dle váhy, cca…): dùng giá / kg|l (up bez DPH × hệ số DPH của chính món đó).
for r in (L('bidfood.json', []) or []):
    if not r.get('pv') or not r.get('p'): continue
    vat = r['pv'] / r['p']; su = (r.get('su') or '').lower(); nm = (r['n'] + ' ' + (r.get('pk') or '')).strip()
    akce = bool(r.get('off'))
    if su in ('kg', 'l') and r.get('up'):
        sup.append(dict(src='Bidfood', n=nm, p=round(r['up'] * vat, 2), u='u', q=1000, c=1, akce=akce, id=r['id']))
    else:
        if re.search(r'\bcca\b|váh', nm, re.I): continue
        u, q, c = piece(nm); sup.append(dict(src='Bidfood', n=nm, p=r['pv'], u=u, q=q, c=c, akce=akce, id=r['id']))
# Unikom (CeposOS ceník, đọc màn hình – thêm 24.10.2026): unikom.json = [mã, tên, EAN, giá bez DPH, giá s DPH, mã akce]
for r in (L('unikom.json', []) or []):
    if not r[1] or not r[4] or BAD.search(r[1]): continue
    u, q, c = piece(r[1]); sup.append(dict(src='Unikom', n=r[1], p=r[4], u=u, q=q, c=c, akce=bool(r[5]), id=r[0]))
def build_idx(L_):
    bi = defaultdict(list); ti = defaultdict(list)
    for it in L_:
        if not it['u'] or not it['q']: continue
        it['pu'] = it['p'] / (it['q'] * it['c'])
        w = [x for x in re.findall(r'[a-z0-9]+', na(it['n'])) if len(x) >= 3 and not x.isdigit()]
        keys = set(w[:2])
        if it.get('bn'): keys |= {x for x in re.findall(r'[a-z0-9]+', it['bn']) if len(x) >= 3}
        it['keys'] = keys; it['tk'] = ttok(it['n'])
        for k in keys: bi[k].append(it)
        for t in it['tk']: ti[t].append(it)
    return bi, ti
bidx, tidx = build_idx(sup)

def size_ok(a, o):
    if a['u'] != o['u']: return False
    if a['u'] == 'u' and 0.88 <= o['q'] / a['q'] <= 1.14: return True
    if a['u'] == 'u' and not (0.5 <= o['q'] / a['q'] <= 2): return False   # 29.10: 1 chai 1,5 l ≠ 4 lon 330 ml (tổng gần bằng nhưng khác hàng)
    return 0.88 <= (o['q'] * o['c']) / (a['q'] * a['c']) <= 1.14

# ---------- Kupi ----------
CHAIN = {'kaufland':'Kaufland','lidl':'Lidl','penny-market':'Penny','albert':'Albert','billa':'Billa','tesco':'Tesco','globus':'Globus'}
KU = L('kupi.json', [])
TODAY = datetime.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else datetime.date.today()
def dates(v):
    # 26.10: Kupi ghi tương đối 'dnes končí' / 'zítra končí' / 'pozítří končí' → tính từ ngày quét (trước đây ra '?')
    rel = re.search(r'\b(dnes|zítra|pozítří)\s+končí', v or '', re.I)
    if rel: return None, TODAY + datetime.timedelta(days={'dnes': 0, 'zítra': 1, 'pozítří': 2}[rel.group(1).lower()])
    rel = re.search(r'končí\s+za\s+(\d+)\s+d', v or '', re.I)
    if rel: return None, TODAY + datetime.timedelta(days=int(rel.group(1)))
    ds = re.findall(r'(\d{1,2})\.\s*(\d{1,2})\.(?:\s*(\d{4}))?', v or '')
    out = []
    for d, m, y in ds:
        yy = int(y) if y else TODAY.year
        dt = datetime.date(yy, int(m), int(d))
        if not y and (dt - TODAY).days < -200: dt = dt.replace(year=yy + 1)
        out.append(dt)
    if not out: return None, None
    if len(out) == 1:
        return (None, out[0]) if re.search(r'\bdo\b', v) else (out[0], out[0])
    return out[0], out[-1]
LIM = re.compile(r'(?:max(?:imáln[eě])?\.?\s*(\d+)\s*(?:ks|kus|bal|balen|x)?)|(?:(\d+)\s*(?:ks|kusy|kusů|bal\.?)\s*(?:na|/)\s*(?:osobu|zákazn|nákup|účtenk|den))|(?:limit\w*\s*(\d+))|(?:omezen\w*[^,;]*)', re.I)
COND = re.compile(r'pouze při (?:zakoupení|nákupu)[^,;]*|při nákupu \d+[^,;]*|\d+\s*\+\s*\d+[^,;]*|do vyprodání zásob|pouze ve vybraných prodejnách|neplatí[^,;]*|platí pouze[^,;]*', re.I)
def brand_words(name):
    ws = name.split()
    return [na(w) for i, w in enumerate(ws) if i > 0 and w[:1].isupper() and len(re.sub(r'\W', '', w)) >= 2]
def type_words(name):
    ws = name.split(); out = [w for i, w in enumerate(ws) if i == 0 or not w[:1].isupper()]
    return ttok(' '.join(out))

rows = []
for r in KU:
    ss = r.get('ss'); chain = CHAIN.get(ss)
    if not chain or not r.get('price'): continue
    if not na(r.get('shop', '')).replace(' ', '').startswith(na(chain)[:4]): continue   # dòng của chuỗi khác lẫn vào
    d0, d1 = dates(r.get('valid'))
    if d1 and d1 < TODAY: continue
    amt = r.get('amt') or r.get('pamt') or ''
    u, q, c = piece(amt)
    if not u: u, q, c = piece(r.get('note', ''))
    if not u: u, q, c = piece(r['name'])
    note = r.get('note', ''); club = r.get('club', '')
    lm = LIM.search(note + ' ' + club)
    lim = lm[0].strip() if lm else ''
    cond = '; '.join(sorted(set(m[0].strip() for m in COND.finditer(note))))
    a = dict(chain=chain, g=r['g'], cat=r['cat'], n=r['name'], prod=r.get('prod', ''), amt=amt, p=r['price'], pct=r.get('pct'),
             unit=r.get('unit', ''), the=club, d0=d0.isoformat() if d0 else '', d1=d1.isoformat() if d1 else '',
             fut=bool(r.get('fut')) or bool(d0 and d0 > TODAY), note=note, lim=lim, cond=cond, did=r['did'], lk=r.get('letak', ''),
             u=u, q=q, c=c)
    if u and q: a['pu'] = a['p'] / (q * c)
    rows.append(a)


# 26.10 anh: “phân biệt 3,5 và 1,5, smetana cũng thế – phải so theo phần trăm”. Áp cho MỌI món có % (mléko, smetana, jogurt, sýr, tvaroh, máslo, rượu…):
# 2 bên đều ghi % → phải trùng (±0,3). Một bên không ghi % → so theo loại: mléko plnotučné/polotučné/odtučněné, smetana ke šlehání/na vaření/zakysaná.
def pcts(n):
    return [float(x.replace(',', '.')) for x in re.findall(r'(\d+(?:[.,]\d+)?)\s*%', n or '')]
def fatcls(n):
    t = na(n); P = pcts(n)
    if re.search(r'\bmle(ko|ka|cne)?\b|\bmilk\b', t) and not re.search(r'kefir|kondenz|zahust|cokol|kakao|napoj|jogurt|syr|susen', t):
        if re.search(r'plnotuc', t): return 'm3'
        if re.search(r'polotuc', t): return 'm1'
        if re.search(r'odtuc|odstred', t): return 'm0'
        if P: v = P[0]; return 'm0' if v <= 0.7 else 'm1' if v < 2.5 else 'm3'
    if re.search(r'smetan|\bsmet\b', t):
        if re.search(r'zakys', t): return 'sz'
        if re.search(r'sleh', t): return 'ss'
        if re.search(r'varen|do omac|na vareni', t): return 'sv'
        if P: return 'ss' if P[0] >= 25 else 'sv'
    return ''
def pct_ok(a, b):
    A, B = pcts(a), pcts(b)
    if A and B and not any(abs(x - y) <= 0.3 for x in A for y in B): return False
    ca, cb = fatcls(a), fatcls(b)
    if ca and cb and ca != cb: return False                  # zakysaná 12 % ≠ smetana na vaření 12 %
    if ca[:1] == 'm' and cb[:1] == 'm':                      # mléko čerstvé ≠ trvanlivé
        fa = 'c' if 'cerstv' in na(a) else 't' if 'trvanl' in na(a) or 'uht' in na(a) else ''
        fb = 'c' if 'cerstv' in na(b) else 't' if 'trvanl' in na(b) or 'uht' in na(b) else ''
        if fa and fb and fa != fb: return False
    return True
# 29.10 anh: tách leták MỚI / CŨ. Kupi chỉ ghi ngày bắt đầu khi akce chưa chạy ("čt 29. 10. – út 3. 11."); khi đã chạy chỉ còn "platí do …".
# → lấy lại ngày bắt đầu (d0) từ lần quét trước (letak_latest.json / PREV_LETAK) theo mã akce (did); món mới thấy lần đầu hôm nay mà không có d0 thì d0 = hôm nay.
try:
    _pf = os.environ.get('PREV_LETAK') or 'data/letak_latest.json'
    _P = json.load(open(_pf)); _PD = {r[23]: r[9] for r in _P.get('D', []) if len(r) > 23 and r[9]}
    _seen = {r[23] for r in _P.get('D', []) if len(r) > 23}
    _first = _P.get('meta', {}).get('today', '')
except Exception:
    _PD, _seen, _first = {}, set(), ''
for _a in rows:
    if not _a['d0'] and _PD.get(_a['did']): _a['d0'] = _PD[_a['did']]
    elif not _a['d0'] and _seen and _a['did'] not in _seen and not _a['fut']: _a['d0'] = TODAY.isoformat()
print('d0 lấy lại từ lần trước:', sum(1 for _a in rows if _a['d0']), '/', len(rows))
# 29.10 anh: nhầm bia CHAI với bia LON. Kupi ghi bao bì trong ghi chú ("plech", "+3 Kč záloha na láhev", "pet láhev") – trước đây chỉ đọc tên.
# Quy tắc chung (mọi đồ uống): hai bên đều biết bao bì mà khác nhau (lon / chai thuỷ tinh / PET) → KHÔNG ghép. Unikom viết "P 0,5l" = plech.
def pkg(t):
    t = ' ' + na(t) + ' '
    if re.search(r'\bpet\b', t): return 'pet'
    if re.search(r'plech|\bcan\b|\blon\b|\bp\s*0[,.]\d', t): return 'lon'
    if re.search(r'sklo|sklen|lahev|lahv|vratn|\bvr\b|zaloh', t): return 'chai'
    return ''
for _a in rows: _a['pk'] = pkg(_a['n'] + ' ' + _a['note'])
for _o in sup: _o['pk'] = pkg(_o['n'])
def pk_ok(a, o): return not (a['pk'] and o['pk'] and a['pk'] != o['pk'])
# 29.10: bia 10° ≠ 11° ≠ 12° (Kozel Medium 11° bị ghép với Kozel 10). JIP viết "Kozel 10 Světlé…" không có dấu °.
def deg(t):
    t = na(t); D_ = re.findall(r'(\d{1,2})\s*°', t)
    if not D_ and re.search(r'pivo|lezak|vycepni|\bpils', t): D_ = re.findall(r'\b(9|10|11|12|13|14)\b(?!\s*(?:x|ks|%|ml|l\b|g\b|cl))', t)
    return set(D_)
# 29.10: thịt/cá khác loại không ghép (Meining vepřové ≠ Meining kuřecí)
MEAT = [('veprov', 'veprove'), ('kurec', 'kure', 'kureci', 'kurat'), ('krut',), ('hovez',), ('telec',), ('jehnec',), ('kachn',), ('losos',), ('tunak',), ('sled',), ('makrel',)]
def meat(t):
    w = re.findall(r'[a-z]+', na(t)); return {i for i, g in enumerate(MEAT) if any(x.startswith(g[0]) or x in g for x in w)}
def kind_ok(a, o):
    da, do_ = deg(a['n']), deg(o['n'])
    if da and do_ and not (da & do_): return False
    ma, mo = meat(a['n']), meat(o['n'])
    if ma and mo and not (ma & mo): return False
    return True
def eqp(a, o): return round(o['pu'] * a['q'] * a['c'], 2)
# 29.10 anh: Limonáda Pepsi 2,25 l không ra giá Makro/JIP/Tamda vì tên NCC không có chữ 'limonáda'. Từ vựng loại hàng = các từ loại trong tên Kupi.
TYPEV = set()
_BRV = set()
for _a in rows: TYPEV |= type_words(_a['n']); _BRV |= ttok(' '.join(brand_words(_a['n'])))
TYPEV -= _BRV          # 'cola' là một phần tên hãng (Coca Cola) → không coi là từ loại hàng (Pepsi Cola Makro/JIP bị loại)
# 30.10 anh: Kaufland "Jogurt Pierot Olma" không ra Unikom "Jog.Pierot borůvka 8% 150g" (11,34 – rẻ hơn JIP). 3 lỗi chung:
# (1) chỉ tìm theo từ hãng CUỐI ('olma') → tìm theo MỌI từ hãng; (2) hãng 2 từ bắt buộc trùng 2 → chấp nhận trùng 1 từ nếu từ đó HIẾM (≤80 món NCC, vd 'pierot');
# (3) tên viết tắt (Jog. = Jogurt) → so loại hàng theo tiền tố ≥3 chữ.
DFW = defaultdict(int)
for _o in sup:
    for _w in set(re.findall(r'[a-z0-9]+', na(_o['n']))): DFW[_w] += 1
def _f1ok(a, o):   # nới luật: từ ĐẦU tên NCC (thường là hãng) phải có trong tên leták (kể cả viết tắt Jog. = Jogurt) – Pedigree Denta Stix ≠ Purina Denta Life
    f = (re.findall(r'[a-z0-9]+', na(o['n'])) or [''])[0]; ak = re.findall(r'[a-z0-9]+', na(a['n']))
    return bool(f) and any(x == f or (len(f) >= 3 and x.startswith(f)) for x in ak)
def tw_ov(tw, tk): return bool(tw & tk) or any((x.startswith(y) or y.startswith(x)) for x in tw for y in tk if min(len(x), len(y)) >= 3)
def match(a, bidx, tidx, cross=True):
    bwl = [w for w in brand_words(a['n']) if w not in GEN]; tw = type_words(a['n'])
    if not bwl and len(a['n'].split()) == 1: bwl = [na(a['n'])]; tw = set()      # 29.10: tên chỉ 1 từ = tên hãng ('Kofola')
    core = [w for w in bwl if w not in NOTBRAND] or bwl
    same = []
    if core:
        cand = {}
        for w in core:
            for o in bidx.get(w, []): cand[id(o)] = o
        for o in cand.values():
            on = set(re.findall(r'[a-z0-9]+', na(o['n'])))
            hit = [w for w in core if w in on]
            if len(hit) < min(2, len(core)) and not (len(core) == 2 and hit == [core[0]] and DFW.get(core[0], 0) <= 80 and len(core[0]) >= 4 and _f1ok(a, o)): continue   # chỉ nới khi từ trùng là DÒNG HÀNG (từ đầu, vd Pierot), không phải tên hãng mẹ (Chio ≠ PomBär)      # hãng ≥2 từ phải trùng 2 (Darling Purina ≠ Purina Friskies), trừ khi trùng 1 từ hiếm (Pierot)
            if not size_ok(a, o) or vset(a['n']) != vset(o['n']) or not pct_ok(a['n'], o['n']) or not pk_ok(a, o) or not kind_ok(a, o): continue
            if tw and o['tk'] and not tw_ov(tw, o['tk']) and (o['tk'] & TYPEV): continue   # khác loại hàng (vd sýr ≠ čokoláda); 29.10: NCC không ghi loại ('Pepsi Cola 2,25l PET' ≠ 'Limonáda') → vẫn ghép
            if 0.4 <= o['pu'] / a['pu'] <= 2.5: same.append(o)
    x = []
    if cross and not same and len(tw) >= 2:   # khác hãng: cùng loại hàng (≥2 từ, ≥60 % từ trùng) + cùng cỡ
        cnt = defaultdict(int); objs = {}
        for t in tw:
            L_ = tidx.get(t, [])
            if len(L_) > 4000: continue
            for o in L_: cnt[id(o)] += 1; objs[id(o)] = o
        for i, n_ in cnt.items():
            o = objs[i]
            if n_ < 2 or not size_ok(a, o) or vset(a['n']) != vset(o['n']) or not pct_ok(a['n'], o['n']) or not pk_ok(a, o) or not kind_ok(a, o): continue
            if n_ / len(tw | o['tk']) < 0.6: continue
            if 0.5 <= o['pu'] / a['pu'] <= 2: x.append(o)
    return same, x
for a in rows:
    a['best'] = None
    if 'pu' not in a: continue
    same, x = match(a, bidx, tidx)
    S = same or x
    if not S: continue
    per = {}
    for o in S:
        if o['src'] not in per or o['pu'] < per[o['src']]['pu']: per[o['src']] = o
    a['sup'] = {s: [eqp(a, o), o['n'], 1 if o['akce'] else 0] for s, o in per.items()}
    b = min(per.values(), key=lambda o: o['pu'])
    a['best'] = dict(src=b['src'], n=b['n'], eq=eqp(a, b), x=0 if same else 1)
    a['bobj'] = b
    a['diff'] = round((a['p'] - a['best']['eq']) / a['best']['eq'] * 100, 1)

# ---- HÀNG ĐANG NHẬP (faktura/DL trong Gmail → inv_rows.json, cùng file với trang Check giá) – anh 29.10 ----
# Món leták CÙNG HÃNG với món anh đã nhập → ghi giá anh đã trả (quy về cùng cỡ). Siêu thị rẻ hơn ≥ 3 % → gợi ý lấy hàng ở siêu thị.
# Giá: JIP/Bidfood faktura bez DPH × DPH (vat_of, như dat_o_dau.py); Makro faktura không có giá → giá Makro hiện tại theo mã.
VAT21 = re.compile(r'\bvod[ay]\b|water|napoj|nápoj|cola|limonad|džus|dzus|nektar|tonic|energ|monster|red ?bull|semtex|big shock|burn\b|ice ?tea|ledov|mattoni|rajec|aquila|bonaqua|natura\b|magnesia|kofola|pepsi|fanta|sprite|mirinda|7up|cappy|fuze|schweppes|kinley|powerade|birell|kub[ií]k|smoothie|toma\b|poděbrad|podebrad|ondrášov|ondrasov|dobrá voda|dobra voda|romerquel|römerquel|smartwater|drwitt|dr\.? witt|arizona|\bokf\b|mogu|'
                   r'pivo|ležák|lezak|víno|vino\b|rum\b|vodka|\bgin\b|likér|liker|whisk|fernet|becher|sekt|prosecco|\d+(?:[.,]\d)?\s*%\s*(?:vol|alk)|tabák|tabak|cigaret|iqos|terea|'
                   r'persil|ariel|jar\b|savo|domestos|prací|praci|sprch|šampon|sampon|zubn|toaletn|ubrous|mýdl|mydl|deodor|kondom', re.I)
def vat_of(n):
    t = n or ''
    if re.search(r'káv[ay]|kava\b|čaj\b|caj\b', t, re.I) and not re.search(r'ledov|ice ?tea|nápoj|napoj|drink|latte|cappuccino', t, re.I): return 1.12
    return 1.21 if VAT21.search(t) else 1.12
_mkp = {str(r[0]): r for r in MK}
_BF = {str(r['id']): r for r in (L('bidfood.json', []) or [])}
_ag = {}
for d_, s_, code, name, qty, pu_, _, fn in (L('inv_rows.json', []) or []):
    k = (s_, code or name); e = _ag.setdefault(k, dict(sup=s_, code=code, n=name, times=0, last='', pu=None))
    e['times'] += 1; dk = d_[-4:] + d_[3:5] + d_[:2]
    if dk >= e['last']: e['last'] = dk; e['d'] = d_; e['pu'] = pu_ if pu_ is not None else e['pu']
invl = []
for e in _ag.values():
    nm, p_ = e['n'], None
    if e['sup'] == 'Makro':
        r = _mkp.get(str(e['code']))
        if r: nm, p_ = r[1], r[3]
        u, q, c = piece(nm, r[2] if r else None)
    else:
        if not e['pu']: continue
        bf = _BF.get(str(e['code'])) if e['sup'] == 'Bidfood' else None
        vat = (bf['pv'] / bf['p']) if bf and bf.get('p') else vat_of(nm)
        p_ = round(e['pu'] * vat, 2); u, q, c = piece(nm)
        if bf and bf.get('inpk'): c = 1
    if not p_ or not u or not q or BAD.search(nm): continue
    invl.append(dict(src=e['sup'], n=nm, p=p_, u=u, q=q, c=c or 1, akce=False, d=e['d'], t=e['times']))
for _o in invl: _o['pk'] = pkg(_o['n'])
ibx, itx = build_idx(invl)
for a in rows:
    if 'pu' not in a: continue
    same, _ = match(a, ibx, itx, cross=False)
    if same:
        o = min(same, key=lambda o: o['pu'])
        a['inv'] = [o['src'], o['n'], eqp(a, o), o['d'], o['t']]
print('món leták trùng hàng đang nhập:', sum(1 for a in rows if a.get('inv')), '| siêu thị rẻ hơn hàng đang nhập:', sum(1 for a in rows if a.get('inv') and a['p'] <= a['inv'][2] * 0.97))

# rẻ nhất giữa các siêu thị: cùng sản phẩm Kupi + cùng đơn vị
grp = defaultdict(list)
for a in rows:
    if 'pu' in a: grp[(a['prod'], a['u'], a.get('pk', ''))].append(a)   # 29.10: lon ≠ chai giữa các siêu thị
for k, L_ in grp.items():
    chains = {a['chain'] for a in L_}
    m = min(a['pu'] for a in L_)
    for a in L_:
        a['nch'] = len(chains)
        a['cheapest'] = len(chains) > 1 and a['pu'] <= m * 1.005
        others = [b for b in L_ if b['chain'] != a['chain']]
        if others:
            ob = min(others, key=lambda b: b['pu']); a['oth'] = [ob['chain'], round(ob['pu'] * a['q'] * a['c'], 2)]

def st(a):
    if not a.get('best'): return 'none'
    if a['diff'] <= -55: return 'chk'      # rẻ hơn > 55 %: nghi ghép sai hàng / sai quy cách → anh kiểm tra lại, không tính là 'giá đẹp'
    return 'buy' if a['diff'] <= -3 else 'even' if a['diff'] < 3 else 'sup'
out = []
for a in rows:
    out.append([a['chain'], a['g'], a['cat'], a['n'], a['amt'], a['p'], a.get('pct'), a['unit'], a['the'], a['d0'], a['d1'], 1 if a['fut'] else 0,
                a['lim'], a['cond'], a['note'], a['lk'], st(a), a.get('diff'), a.get('best'), a.get('sup'), 1 if a.get('cheapest') else 0, a.get('oth'), a['prod'], a['did'], a.get('inv')])
from collections import Counter
cn = Counter((a['chain'], st(a)) for a in rows)
# 26.10: stamp theo giờ Praha (phiên tự động chạy giờ UTC); STAMP=... để giữ giờ lấy giá khi chạy lại
meta = dict(stamp=os.environ.get('STAMP') or datetime.datetime.now(__import__('zoneinfo').ZoneInfo('Europe/Prague')).strftime('%Y-%m-%d %H:%M'), today=TODAY.isoformat(),
            sup_dates=L('dates.json', {}) or {}, mk_date=sys.argv[2] if len(sys.argv) > 2 else '',
            n=len(rows), n_buy=sum(1 for a in rows if st(a) == 'buy'), n_fut=sum(1 for a in rows if a['fut']),
            n_lim=sum(1 for a in rows if a['lim']))
json.dump(dict(meta=meta, D=out), open('letak_data.json', 'w'), ensure_ascii=False, separators=(',', ':'))
hist = [[TODAY.isoformat(), a['chain'], 'Potraviny' if a['g'] == 'P' else 'Drogerie/Domácí', a['n'], a['amt'], a['p'], a['the'], a['d0'], a['d1'],
         a['lim'] or 'không ghi', a['best']['src'] if a.get('best') else '', a['best']['eq'] if a.get('best') else '', a.get('diff', ''),
         'rẻ hơn giá nhập' if st(a) == 'buy' else '', 'rẻ nhất siêu thị' if a.get('cheapest') else '', 'https://www.kupi.cz' + a['lk'] if a['lk'] else '']
        for a in rows if st(a) == 'buy' or a.get('cheapest')]
json.dump(hist, open('letak_hist_rows.json', 'w'), ensure_ascii=False)
print('dòng', len(rows), '| rẻ hơn giá nhập', meta['n_buy'], '| leták sắp tới', meta['n_fut'], '| có ghi giới hạn', meta['n_lim'])
for ch in CHAIN.values():
    print(ch, {k[1]: v for k, v in cn.items() if k[0] == ch})

# ---- DANH SÁCH "NHẬP RẺ HƠN SIÊU THỊ" (anh yêu cầu 23.10.2026) ----
# Món mà nơi nhập (Makro/JIP/Tamda/Bidfood) rẻ hơn giá akce siêu thị ≥ 3 % → ghi ra letak_ncc_new.json để ncc_merge.py gộp vào danh sách chung.
nn = {}
for a in rows:
    if st(a) != 'sup' or not a.get('bobj'): continue
    o = a['bobj']
    if a['best'].get('x'): continue            # chỉ lấy cùng hãng (khác hãng dễ ghép nhầm)
    key = o['src'] + ':' + str(o.get('bb') or o.get('id') or o['n'])
    e = nn.get(key)
    sm = [a['chain'], a['p'], a['n'], a['amt'], a['d1'], round(-a['diff'], 1)]
    if not e or sm[5] > e['sm'][5]:
        nn[key] = dict(key=key, src=o['src'], id=str(o.get('bb') or o.get('id') or ''), n=o['n'], p=o['p'], eq=a['best']['eq'], sm=sm)
json.dump(list(nn.values()), open('letak_ncc_new.json', 'w'), ensure_ascii=False)
print('nhập rẻ hơn siêu thị (cùng hãng):', len(nn), dict(Counter(v['src'] for v in nn.values())))
