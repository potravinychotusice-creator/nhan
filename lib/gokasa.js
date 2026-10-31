// Danh mục hàng GOKASA: đọc CSV → lưu Supabase (chia nhiều phần) → giữ bản trên máy để dùng offline.
(function (g) {
  const KHOA = 'gokasa';          // du_lieu: 'gokasa' = thông tin, 'gokasa/0', 'gokasa/1'… = dữ liệu
  const PHAN = 4000;              // số mã mỗi phần
  const KHO = 'cuahang-du-lieu';  // Cache API trên điện thoại
  let dang = null;                // lần tải đang chạy / vừa xong

  const bo = s => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();

  function giaiMa(buf) {
    try { return new TextDecoder('utf-8', { fatal: true }).decode(buf).replace(/^﻿/, '') }
    catch (e) { return new TextDecoder('windows-1250').decode(buf) }
  }

  function tachDong(txt) {
    const dau = txt.slice(0, txt.indexOf('\n') + 1 || txt.length);
    const dem = c => dau.split(c).length - 1;
    const sep = ['\t', ';', ','].sort((a, b) => dem(b) - dem(a))[0];
    const rows = []; let row = [], o = '', q = false;
    for (let i = 0; i < txt.length; i++) {
      const c = txt[i];
      if (q) { if (c === '"') { if (txt[i + 1] === '"') { o += '"'; i++ } else q = false } else o += c; continue }
      if (c === '"' && o === '') q = true;
      else if (c === sep) { row.push(o); o = '' }
      else if (c === '\n') { row.push(o.replace(/\r$/, '')); rows.push(row); row = []; o = '' }
      else o += c;
    }
    if (o || row.length) { row.push(o.replace(/\r$/, '')); rows.push(row) }
    return rows.filter(r => r.some(x => x.trim()));
  }

  // Nhận cột theo tên (tiếng Anh / Séc). Giá nhập (inprice, nákup) không bao giờ là giá bán.
  function nhanCot(h) {
    const H = h.map(bo), tim = (ok, bo_qua) => H.findIndex(x => ok.some(k => x.includes(k)) && !(bo_qua || []).some(k => x.includes(k)));
    return {
      ean: tim(['ean', 'carov', 'barcode', 'kod']),
      ten: tim(['name', 'nazev', 'popis', 'zbozi']),
      gia: tim(['sellprice', 'sell', 'prodej', 'price', 'cena'], ['inprice', 'in price', 'in_price', 'nakup', 'nakupni', 'purchase', 'dph', 'vat', 'tax', 'marze']),
      nhom: tim(['group', 'skupin', 'kategor']),
      dv: tim(['unit', 'jednot', 'mj'])
    };
  }

  const so = s => { const n = parseFloat(String(s).replace(/\s/g, '').replace(',', '.')); return isFinite(n) ? n : null };
  function gramaz(ten) {
    const m = /(\d+(?:[.,]\d+)?)\s*(kg|g|ml|l)\b/i.exec(ten);
    return m ? m[1].replace('.', ',') + ' ' + m[2].toLowerCase() : '';
  }

  // Trả về { ds: {ean: {n,p,w,g,u}}, cot, bo_qua, mau }
  function docCsv(buf) {
    const rows = tachDong(giaiMa(buf));
    if (rows.length < 2) throw new Error('File trống');
    const cot = nhanCot(rows[0]);
    if (cot.ean < 0 || cot.ten < 0) throw new Error('Không thấy cột EAN hoặc tên hàng. Dòng đầu file: ' + rows[0].join(' | '));
    if (cot.gia < 0) throw new Error('File này KHÔNG có cột giá bán (dòng đầu: ' + rows[0].join(' | ') + '). Anh xuất danh mục hàng có giá bán.');
    const ds = {}; let bo_qua = 0;
    for (const r of rows.slice(1)) {
      const ma = String(r[cot.ean] || '').replace(/\D/g, '');
      const ten = String(r[cot.ten] || '').trim();
      if (ma.length < 6 || !ten) { bo_qua++; continue }
      const x = { n: ten };
      const p = so(r[cot.gia]); if (p != null) x.p = p;
      const w = gramaz(ten); if (w) x.w = w;
      if (cot.nhom >= 0 && r[cot.nhom]) x.g = r[cot.nhom].trim();
      if (cot.dv >= 0) { const u = bo(r[cot.dv]); if (u === 'kg') x.u = 'kg' }
      ds[ma] = x;
    }
    const mau = Object.entries(ds).slice(0, 3);
    return { ds, cot: Object.fromEntries(Object.entries(cot).map(([k, i]) => [k, i >= 0 ? rows[0][i] : '—'])), bo_qua, mau };
  }

  async function luuMay(info, ds) {
    try { const c = await caches.open(KHO); await c.put('/_gokasa', new Response(JSON.stringify({ info, ds }))) } catch (e) {}
  }
  async function docMay() {
    try { const c = await caches.open(KHO); const r = await c.match('/_gokasa'); return r ? await r.json() : null } catch (e) { return null }
  }

  async function taiLen(sb, ds, tenFile) {
    const ma = Object.keys(ds), phan = [];
    for (let i = 0; i < ma.length; i += PHAN) phan.push(Object.fromEntries(ma.slice(i, i + PHAN).map(k => [k, ds[k]])));
    const rows = phan.map((p, i) => ({ khoa: KHOA + '/' + i, gia_tri: p }));
    for (const r of rows) { const { error } = await sb.from('du_lieu').upsert(r); if (error) throw error }
    // xoá phần thừa của bản cũ (nếu bản cũ dài hơn)
    const { data: cu } = await sb.from('du_lieu').select('khoa').like('khoa', KHOA + '/%');
    const thua = (cu || []).map(r => r.khoa).filter(k => +k.split('/')[1] >= rows.length);
    if (thua.length) await sb.from('du_lieu').delete().in('khoa', thua);
    const info = { so_ma: ma.length, so_phan: rows.length, ten_file: tenFile };
    const { data, error } = await sb.from('du_lieu').upsert({ khoa: KHOA, gia_tri: info }).select('cap_nhat_luc').single();
    if (error) throw error;
    info.luc = data.cap_nhat_luc;
    await luuMay(info, ds);
    dang = Promise.resolve(ds);
    return info;
  }

  // Lấy danh mục: dùng bản trên máy nếu cloud chưa có bản mới hơn; mất mạng thì dùng bản trên máy.
  function layGokasa(sb) {
    if (dang) return dang;
    dang = (async () => {
      const may = await docMay();
      let info = null;
      try {
        const { data, error } = await sb.from('du_lieu').select('gia_tri,cap_nhat_luc').eq('khoa', KHOA).maybeSingle();
        if (error) throw error;
        if (data) info = Object.assign({}, data.gia_tri, { luc: data.cap_nhat_luc });
      } catch (e) { return may ? may.ds : null }
      if (!info) return may ? may.ds : null;
      if (may && may.info && may.info.luc === info.luc) return may.ds;
      const { data, error } = await sb.from('du_lieu').select('gia_tri').like('khoa', KHOA + '/%');
      if (error) return may ? may.ds : null;
      const ds = Object.assign({}, ...data.map(r => r.gia_tri));
      await luuMay(info, ds);
      return ds;
    })();
    dang.catch(() => {}).finally(() => { setTimeout(() => { dang = null }, 60000) });
    return dang;
  }

  async function thongTin(sb) {
    try {
      const { data } = await sb.from('du_lieu').select('gia_tri,cap_nhat_luc').eq('khoa', KHOA).maybeSingle();
      if (data) return Object.assign({}, data.gia_tri, { luc: data.cap_nhat_luc });
    } catch (e) {}
    const may = await docMay(); return may ? may.info : null;
  }

  g.Gokasa = { docCsv, taiLen, layGokasa, thongTin, _tachDong: tachDong, _nhanCot: nhanCot };
})(typeof window !== 'undefined' ? window : globalThis);
