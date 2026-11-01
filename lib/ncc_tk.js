// Tình trạng lấy giá nhà cung cấp (máy cửa hàng ghi tai_lieu bo='ncc_tt' {co, luc, loi}).
// Mật khẩu KHÔNG nằm trong app: anh nhập trên máy tính cửa hàng (biểu tượng "Mật khẩu NCC", Windows khoá, không lên mạng).
(function (g) {
  const NCC = [['jip', 'JIP'], ['tamda', 'Tamda'], ['bidfood', 'Bidfood'], ['makro', 'Makro'], ['cocacola', 'Coca-Cola HBC'],
    ['linsan', 'Linsan 24h'], ['lusoma', 'Lusoma'], ['bomba', 'Bomba cena'], ['alimpex', 'Alimpex'], ['rapadog', 'Rapa-Dog']];
  async function trangThai(sb) {
    const { data, error } = await sb.from('tai_lieu').select('id,data').eq('bo', 'ncc_tt');
    if (error) throw error;
    const o = {}; for (const r of data || []) o[r.id] = r.data; return o;
  }
  g.NccTk = { NCC, trangThai };
})(window);
