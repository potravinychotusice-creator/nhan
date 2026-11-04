-- B4: Nút "🔄 Lấy leták mới" – ai có link app cũng bấm được (KHÔNG cần đăng nhập), máy cửa hàng nhận và chạy.
-- Supabase → SQL Editor → New query → dán toàn bộ → Run. Chạy lại nhiều lần cũng không sao.
-- Cần chạy SAU b3-check-gia.sql (đã có bảng nhan_vien với quyền 'may' cho tài khoản máy quét).
--
-- File này KHÔNG xoá bảng/dữ liệu nào đang có, KHÔNG đổi quyền bảng cũ (nhan_vien, du_lieu, tai_lieu, kho checkgia).
-- Chỉ TẠO MỚI: 2 bảng (refresh_requests, may_nhip) + 6 hàm. Các lệnh "drop policy/function if exists" chỉ đụng
-- tới chính các policy/hàm của file này (để chạy lại được).
--
-- Quyền:
--   * Khách (anon, chưa đăng nhập) và người đã đăng nhập: CHỈ gọi được 2 hàm
--       yeu_cau_lam_moi()   – gửi yêu cầu lấy leták (việc cố định 'letak', không nhận tham số)
--       trang_thai_lam_moi() – xem trạng thái yêu cầu gần nhất + máy có đang chạy không (không lộ ai bấm)
--     Không đọc/ghi thẳng 2 bảng được.
--   * Máy cửa hàng (tài khoản quyền 'may', mật khẩu chỉ nằm trên máy): may_nhan_viec, may_bao, may_nhip_tim.
-- Chống lạm dụng (thực thi trong cơ sở dữ liệu, có khoá → nhiều người bấm cùng lúc vẫn an toàn):
--   * Toàn hệ thống chỉ 1 yêu cầu đang chờ/đang chạy; bấm tiếp → trả về yêu cầu đó.
--   * Tối đa 1 lượt MỚI mỗi 10 phút; bấm sớm hơn → trả về lượt gần nhất kèm giờ được bấm lại.
--   * Chờ quá 15 phút → hết hạn (máy bật lại không chạy việc cũ). Đang chạy quá 45 phút không báo → lỗi.

-- 1. Bảng
create table if not exists public.refresh_requests (
  id           bigint generated always as identity primary key,
  job          text not null default 'letak' check (job in ('letak')),
  status       text not null default 'cho' check (status in ('cho', 'dang_chay', 'xong', 'loi', 'het_han')),
  tao_luc      timestamptz not null default now(),
  tao_boi      uuid,                                   -- null = khách chưa đăng nhập
  het_han      timestamptz not null default now() + interval '15 minutes',
  nhan_luc     timestamptz,
  nhan_boi     text,
  xong_luc     timestamptz,
  cap_nhat_luc timestamptz not null default now(),
  thong_bao    text,
  ket_qua      jsonb
);
create unique index if not exists refresh_requests_mot_viec on public.refresh_requests ((true)) where status in ('cho', 'dang_chay');
create index if not exists refresh_requests_luc on public.refresh_requests (tao_luc desc);

create table if not exists public.may_nhip (
  may  text primary key,
  luc  timestamptz not null default now(),
  info jsonb
);

-- 2. Không ai đọc/ghi thẳng 2 bảng qua API (chỉ qua hàm)
alter table public.refresh_requests enable row level security;
alter table public.may_nhip enable row level security;
revoke all on public.refresh_requests from anon, authenticated;
revoke all on public.may_nhip from anon, authenticated;
grant select on public.refresh_requests to authenticated;     -- chỉ máy đọc được (policy dưới), để dọn việc dở khi khởi động
drop policy if exists "rr doc" on public.refresh_requests;
drop policy if exists "rr may doc" on public.refresh_requests;
drop policy if exists "nhip doc" on public.may_nhip;

create or replace function public.la_may() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.nhan_vien where id = auth.uid() and quyen = 'may')
$$;
create policy "rr may doc" on public.refresh_requests for select to authenticated using (public.la_may());

-- 3. Dọn: chờ quá hạn → het_han; đang chạy quá 45 phút không báo → loi
create or replace function public.rr_don_dep() returns void
language sql security definer set search_path = public as $$
  update public.refresh_requests set status = 'het_han', cap_nhat_luc = now(),
         thong_bao = 'Máy cửa hàng không nhận yêu cầu trong 15 phút (máy tắt hoặc chương trình nhận lệnh không chạy).'
   where status = 'cho' and het_han < now();
  update public.refresh_requests set status = 'loi', cap_nhat_luc = now(), xong_luc = now(),
         thong_bao = 'Máy chạy quá 45 phút không báo xong – coi như lỗi. Dữ liệu cũ vẫn giữ nguyên.'
   where status = 'dang_chay' and coalesce(cap_nhat_luc, nhan_luc) < now() - interval '45 minutes';
$$;

-- Kết quả trả cho app (không có tao_boi / nhan_boi / ket_qua chi tiết)
drop function if exists public.yeu_cau_lam_moi(text);
drop function if exists public.yeu_cau_lam_moi();
drop function if exists public.trang_thai_lam_moi();
drop type if exists public.lam_moi_tt;
create type public.lam_moi_tt as (
  id bigint, status text, tao_luc timestamptz, het_han timestamptz, nhan_luc timestamptz, xong_luc timestamptz,
  cap_nhat_luc timestamptz, thong_bao text, may_luc timestamptz, bam_lai_luc timestamptz, moi boolean
);

create or replace function public.trang_thai_lam_moi()
returns public.lam_moi_tt
language plpgsql stable security definer set search_path = public as $$
declare r public.refresh_requests; t public.lam_moi_tt; m timestamptz;
begin
  select max(luc) into m from public.may_nhip;
  select * into r from public.refresh_requests order by tao_luc desc limit 1;
  -- hàm chỉ đọc (không dọn được) → trả trạng thái HIỆU LỰC: chờ quá hạn = het_han, chạy quá 45 phút = loi
  if r.status = 'cho' and r.het_han < now() then
    r.status := 'het_han'; r.thong_bao := 'Máy cửa hàng không nhận yêu cầu trong 15 phút (máy tắt hoặc chương trình nhận lệnh không chạy).';
  elsif r.status = 'dang_chay' and coalesce(r.cap_nhat_luc, r.nhan_luc) < now() - interval '45 minutes' then
    r.status := 'loi'; r.thong_bao := 'Máy chạy quá 45 phút không báo xong – coi như lỗi. Dữ liệu cũ vẫn giữ nguyên.';
  end if;
  t := (r.id, r.status, r.tao_luc, r.het_han, r.nhan_luc, r.xong_luc, r.cap_nhat_luc, r.thong_bao, m,
        case when r.id is null then null else r.tao_luc + interval '10 minutes' end, false);
  return t;
end $$;

-- 4. Gửi yêu cầu (khách hoặc người đăng nhập). Việc cố định 'letak'.
create or replace function public.yeu_cau_lam_moi()
returns public.lam_moi_tt
language plpgsql security definer set search_path = public as $$
declare r public.refresh_requests; t public.lam_moi_tt;
begin
  perform pg_advisory_xact_lock(hashtext('refresh_requests.yeu_cau'));   -- nhiều người bấm cùng lúc → xếp hàng
  perform public.rr_don_dep();
  -- đang có yêu cầu chờ/chạy → trả về yêu cầu đó
  if exists (select 1 from public.refresh_requests where status in ('cho', 'dang_chay')) then
    return public.trang_thai_lam_moi();
  end if;
  -- lượt gần nhất tạo chưa đủ 10 phút → không tạo mới
  if exists (select 1 from public.refresh_requests where tao_luc > now() - interval '10 minutes') then
    return public.trang_thai_lam_moi();
  end if;
  insert into public.refresh_requests (job, tao_boi) values ('letak', auth.uid()) returning * into r;
  t := public.trang_thai_lam_moi(); t.moi := true;
  return t;
end $$;

-- 5. Máy nhận 1 việc (chỉ tài khoản quyền 'may'). Không có việc → trả về hàng rỗng.
drop function if exists public.may_nhan_viec(text, text[]);
create or replace function public.may_nhan_viec(p_may text)
returns public.refresh_requests
language plpgsql security definer set search_path = public as $$
declare r public.refresh_requests;
begin
  if not public.la_may() then raise exception 'Chỉ máy quét giá được nhận việc' using errcode = '42501'; end if;
  insert into public.may_nhip (may, luc) values (left(p_may, 60), now()) on conflict (may) do update set luc = now();
  perform public.rr_don_dep();
  select * into r from public.refresh_requests
   where status = 'cho' and het_han >= now()
   order by tao_luc limit 1
   for update skip locked;
  if not found then return null; end if;
  update public.refresh_requests
     set status = 'dang_chay', nhan_luc = now(), nhan_boi = left(p_may, 60), cap_nhat_luc = now(),
         thong_bao = 'Máy cửa hàng đã nhận, đang chạy…'
   where id = r.id returning * into r;
  return r;
end $$;

-- 6. Máy báo tiến độ / kết quả. Chỉ đổi được yêu cầu đang chạy do chính máy đó nhận.
create or replace function public.may_bao(p_id bigint, p_may text, p_status text, p_thong_bao text, p_ket_qua jsonb default null)
returns public.refresh_requests
language plpgsql security definer set search_path = public as $$
declare r public.refresh_requests;
begin
  if not public.la_may() then raise exception 'Chỉ máy quét giá được báo kết quả' using errcode = '42501'; end if;
  if p_status not in ('dang_chay', 'xong', 'loi') then raise exception 'Trạng thái không hợp lệ: %', p_status; end if;
  update public.refresh_requests
     set status = p_status, thong_bao = left(p_thong_bao, 500), cap_nhat_luc = now(),
         ket_qua = coalesce(p_ket_qua, ket_qua),
         xong_luc = case when p_status in ('xong', 'loi') then now() else xong_luc end
   where id = p_id and status = 'dang_chay' and nhan_boi = p_may
   returning * into r;
  if not found then raise exception 'Yêu cầu % không còn ở trạng thái đang chạy của máy %', p_id, p_may; end if;
  insert into public.may_nhip (may, luc) values (left(p_may, 60), now()) on conflict (may) do update set luc = now();
  return r;
end $$;

-- 7. Nhịp tim máy
create or replace function public.may_nhip_tim(p_may text, p_info jsonb default null)
returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.la_may() then raise exception 'Chỉ máy quét giá' using errcode = '42501'; end if;
  insert into public.may_nhip (may, luc, info) values (left(p_may, 60), now(), p_info)
    on conflict (may) do update set luc = now(), info = coalesce(excluded.info, public.may_nhip.info);
end $$;

-- 8. Quyền gọi hàm: mặc định Postgres cho PUBLIC gọi mọi hàm → thu lại hết rồi cấp đúng chỗ
revoke all on function public.la_may() from public, anon;
revoke all on function public.rr_don_dep() from public, anon, authenticated;
revoke all on function public.trang_thai_lam_moi() from public;
revoke all on function public.yeu_cau_lam_moi() from public;
revoke all on function public.may_nhan_viec(text) from public, anon;
revoke all on function public.may_bao(bigint, text, text, text, jsonb) from public, anon;
revoke all on function public.may_nhip_tim(text, jsonb) from public, anon;
grant execute on function public.la_may() to authenticated;
grant execute on function public.trang_thai_lam_moi() to anon, authenticated;
grant execute on function public.yeu_cau_lam_moi() to anon, authenticated;
grant execute on function public.may_nhan_viec(text) to authenticated;
grant execute on function public.may_bao(bigint, text, text, text, jsonb) to authenticated;
grant execute on function public.may_nhip_tim(text, jsonb) to authenticated;
grant usage on type public.lam_moi_tt to anon, authenticated;

-- Kiểm tra: 2 bảng, 6 hàm, và tài khoản máy quét có quyền 'may'
select table_name from information_schema.tables where table_schema = 'public' and table_name in ('refresh_requests', 'may_nhip');
select routine_name from information_schema.routines where routine_schema = 'public'
   and routine_name in ('yeu_cau_lam_moi', 'trang_thai_lam_moi', 'may_nhan_viec', 'may_bao', 'may_nhip_tim', 'la_may');
select ten, quyen from public.nhan_vien where quyen = 'may';
