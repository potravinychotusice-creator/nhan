// Tài khoản nhà cung cấp: chủ nhập 1 lần trên điện thoại. Mật khẩu được KHOÁ NGAY TRÊN MÁY (RSA-OAEP 3072, khoá công khai bên dưới)
// rồi mới gửi lên Supabase (bảng tai_lieu, bo = 'ncc_tk'). Chỉ máy tính cửa hàng có chìa mở (C:\Users\potra\.cuahang\ncc_private.pem).
// Không ai khác đọc được: Supabase, nhân viên, Claude.
(function (g) {
  const PUB = 'MIIBojANBgkqhkiG9w0BAQEFAAOCAY8AMIIBigKCAYEAqUOzyNz7N39DBiPGR1GreL6vFCylCUHloWv0+RI2EM0u0uebJNM3Jal1fgZKFxLSZqipzHG7MfJwLp6LU2UqLdANmo82FheYRzwwjxZpVJkl20LuFvns0rb4pZwNA7uXlAcDe3WnUEkbZFfDAO+YGHKziFFsgNbDGCGMdv9B9kpARmwtea5rP25g9I0pctVOXsWeCECYT/1pQTfpAytqXPzKv33J8fJBQps/f7RQ1IujFH9RkF4M+yA6ZbqGnkPOmDgvku9hse3Bmx5jcgTPPlL7QMCPiTzkQm1KbuZOMvgBEebVEa4548zMhgwXFn8LCpNqDrKoMVmXx6X8Kp/vYH/+YyKlwwAbvO0aVwW10b1SxNokS3YMKp/rJLnqvdhYMinYYJPZ1RfHCQNVKvHdBzX5Jak2r+wBW2Si3ECvc+JV32Hn9tNkSRBRMww5+w11dyCFkmh+avxKP01mMhHaemt5yaWYGm6ShLaNneG65coINt9bw96nlO6EwBQq3GyPAgMBAAE=';
  const NCC = [
    ['jip', 'JIP', 'https://www.jip-eshop.cz'],
    ['tamda', 'Tamda', 'https://tamdaexpress.eu'],
    ['bidfood', 'Bidfood', 'https://www.mujbidfood.cz'],
    ['makro', 'Makro', 'https://distribuce.makro.cz'],
    ['cocacola', 'Coca-Cola HBC', 'https://www.cchbcshop.com'],
    ['linsan', 'Linsan 24h', 'https://potraviny.linsan24h.cz'],
    ['lusoma', 'Lusoma', 'https://www.lusoma.cz'],
    ['bomba', 'Bomba cena', ''],
    ['alimpex', 'Alimpex', 'https://objednavky.alimpex.cz'],
    ['rapadog', 'Rapa-Dog', 'https://rapa-dog.cz']
  ];
  let khoa = null;
  async function layKhoa() {
    if (khoa) return khoa;
    const der = Uint8Array.from(atob(PUB), c => c.charCodeAt(0));
    return khoa = await crypto.subtle.importKey('spki', der, { name: 'RSA-OAEP', hash: 'SHA-256' }, false, ['encrypt']);
  }
  async function khoaLai(obj) {
    const b = await crypto.subtle.encrypt({ name: 'RSA-OAEP' }, await layKhoa(), new TextEncoder().encode(JSON.stringify(obj)));
    return btoa(String.fromCharCode(...new Uint8Array(b)));
  }
  async function danhSach(sb) {
    const { data, error } = await sb.from('tai_lieu').select('id,data,luc').eq('bo', 'ncc_tk');
    if (error) throw error;
    const o = {}; for (const r of data) o[r.id] = Object.assign({}, r.data, { luc: r.luc }); return o;
  }
  async function trangThai(sb) {
    const { data } = await sb.from('tai_lieu').select('id,data').eq('bo', 'ncc_tt');
    const o = {}; for (const r of data || []) o[r.id] = r.data; return o;
  }
  async function luu(sb, id, ten, user, pass) {
    const enc = await khoaLai({ u: user, p: pass });
    const { error } = await sb.from('tai_lieu').upsert({ bo: 'ncc_tk', id, data: { ten, enc, co: true } });
    if (error) throw error;
  }
  async function xoa(sb, id) {
    const { error } = await sb.from('tai_lieu').delete().eq('bo', 'ncc_tk').eq('id', id);
    if (error) throw error;
  }
  g.NccTk = { NCC, danhSach, trangThai, luu, xoa };
})(window);
