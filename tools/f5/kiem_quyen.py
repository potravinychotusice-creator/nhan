#!/usr/bin/env python3
"""Kiểm quyền hàng đợi "Lấy leták mới" trên Supabase THẬT (chạy trong Ubuntu trên máy cửa hàng).

  python3 tools/f5/kiem_quyen.py          # thử với khách (chỉ khoá publishable) + tài khoản máy (may.env)
  python3 tools/f5/kiem_quyen.py --bam    # thêm: 10 khách bấm cùng lúc + bấm lại (TẠO 1 yêu cầu thật, tự hết hạn sau 15 phút
                                          #        nếu worker chưa chạy; sau đó 10 phút không tạo lượt mới được)
In bảng: tình huống · mong đợi · thực tế · ĐẠT/KHÔNG ĐẠT. Không in mật khẩu, không in token.
"""
import concurrent.futures as cf, json, os, sys, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import checkgia_cloud as cc

KQ = []


def goi(method, path, body=None, tok=None, extra=None):
    h = {'apikey': cc.SB_KEY, 'Content-Type': 'application/json'}
    if tok: h['Authorization'] = 'Bearer ' + tok
    h.update(extra or {})
    r = urllib.request.Request(cc.SB_URL + path, data=json.dumps(body).encode() if body is not None else None, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=30) as x: return x.status, x.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()


def ghi(ten, mong, ok, thuc):
    KQ.append((ten, mong, 'ĐẠT' if ok else 'KHÔNG ĐẠT', thuc[:110].replace('\n', ' ')))


def bi_chan(st, t): return st in (401, 403, 404) or 'permission denied' in t or '42501' in t


# ---- Khách (không đăng nhập) ----
st, t = goi('POST', '/rest/v1/rpc/trang_thai_lam_moi', {}); ghi('Khách xem trạng thái', 'được', st == 200, f'{st} {t}')
for ten, m, p, b in [('Khách đọc thẳng refresh_requests', 'GET', '/rest/v1/refresh_requests?select=*', None),
                     ('Khách đọc thẳng may_nhip', 'GET', '/rest/v1/may_nhip?select=*', None),
                     ('Khách ghi thẳng refresh_requests', 'POST', '/rest/v1/refresh_requests', {'job': 'letak'}),
                     ('Khách sửa trạng thái', 'PATCH', '/rest/v1/refresh_requests?id=gt.0', {'status': 'xong'}),
                     ('Khách ghi nhịp tim (bảng)', 'POST', '/rest/v1/may_nhip', {'may': 'gia'}),
                     ('Khách gọi may_nhan_viec', 'POST', '/rest/v1/rpc/may_nhan_viec', {'p_may': 'gia'}),
                     ('Khách gọi may_bao', 'POST', '/rest/v1/rpc/may_bao', {'p_id': 1, 'p_may': 'gia', 'p_status': 'xong', 'p_thong_bao': 'x'}),
                     ('Khách gọi may_nhip_tim', 'POST', '/rest/v1/rpc/may_nhip_tim', {'p_may': 'gia'}),
                     ('Khách gọi rr_don_dep', 'POST', '/rest/v1/rpc/rr_don_dep', {}),
                     ('Khách sửa quyền nhan_vien', 'PATCH', '/rest/v1/nhan_vien?id=not.is.null', {'quyen': 'chu'})]:
    st, t = goi(m, p, b, extra={'Prefer': 'return=representation'})
    ok = bi_chan(st, t) or (m in ('PATCH', 'GET') and st == 200 and t.strip() == '[]')
    ghi(ten, 'bị chặn', ok, f'{st} {t}')

# ---- Tài khoản máy ----
tok = cc.login()
st, t = goi('POST', '/rest/v1/rpc/may_nhip_tim', {'p_may': 'kiem-quyen', 'p_info': {'kiem': True}}, tok); ghi('Máy gửi nhịp tim', 'được', st in (200, 204), f'{st} {t}')
st, t = goi('GET', '/rest/v1/refresh_requests?select=id,status&limit=1', None, tok); ghi('Máy đọc hàng đợi', 'được', st == 200, f'{st} {t}')
st, t = goi('POST', '/rest/v1/refresh_requests', {'job': 'letak'}, tok); ghi('Máy ghi thẳng bảng', 'bị chặn', bi_chan(st, t), f'{st} {t}')

# ---- Bấm thật (tuỳ chọn) ----
if '--bam' in sys.argv:
    with cf.ThreadPoolExecutor(10) as ex:
        rs = list(ex.map(lambda _: goi('POST', '/rest/v1/rpc/yeu_cau_lam_moi', {}), range(10)))
    ds = [json.loads(t) for st, t in rs if st == 200]
    ids = {d['id'] for d in ds}; moi = sum(1 for d in ds if d.get('moi'))
    ghi('10 khách bấm cùng lúc', '1 mã, ≤1 lượt mới', len(ds) == 10 and len(ids) == 1 and moi <= 1, f'{len(ds)}/10 trả lời, mã {sorted(ids)}, lượt mới {moi}')
    st, t = goi('POST', '/rest/v1/rpc/yeu_cau_lam_moi', {}); d = json.loads(t) if st == 200 else {}
    ghi('Bấm lại ngay', 'cùng mã, không mới', st == 200 and d.get('id') in ids and not d.get('moi'), f'{st} mã {d.get("id")} {d.get("status")} bấm lại sau {d.get("bam_lai_luc")}')

w = max(len(k[0]) for k in KQ)
for ten, mong, kq, thuc in KQ: print(f'{kq:10} {ten:{w}}  [{mong}]  {thuc}')
print('\nTỔNG:', sum(1 for k in KQ if k[2] == 'ĐẠT'), '/', len(KQ), 'ĐẠT')
