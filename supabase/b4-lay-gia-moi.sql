-- B4: Nút "Lấy giá mới" (F5) gửi từ điện thoại → máy cửa hàng nhận và chạy.
-- Supabase → SQL Editor → New query → dán toàn bộ → Run. Chạy lại nhiều lần cũng không sao.
-- Cần chạy SAU b3-check-gia.sql (đã có bảng nhan_vien với quyền 'chu' / 'nhan_vien' / 'may').
--
-- Thiết kế:
--   * Điện thoại KHÔNG ghi thẳng vào bảng. Chỉ gọi hàm yeu_cau_lam_moi('letak') → hàm tự kiểm quyền,
--     chống bấm trùng (mỗi việc chỉ 1 yêu cầu đang chờ/đang chạy), đặt hạn 15 phút.
--   * Máy cửa hàng (tài khoản quyền 'may') gọi may_nhan_viec() mỗi vài giây: lấy 1 yêu cầu đang chờ,
--     khoá bằng FOR UPDATE SKIP LOCKED → 2 tiến trình không bao giờ nhận cùng 1 yêu cầu.
--   * Chỉ có các việc cố định trong danh sách check (job in (...)). Không có chỗ nào nhận câu lệnh.
--   * may_nhip: nhịp tim của máy (30 giây/lần) → app biết máy đang chạy hay đang tắt.

-- 1. Bảng hàng đợi
create table if not exists public.refresh_requests (
  id           bigint generated always as identity primary key,
  job          text not null check (job in ('letak', 'checkgia')),
  status       text not null default 'cho' check (status in ('cho', 'dang_chay', 'xong', 'loi', 'het_han')),
  tao_luc      timestamptz not null default now(),
  tao_boi      uuid references auth.users(id) default auth.uid(),
  het_han      timestamptz not null default now() + interval '15 minutes',
  nhan_luc     timestamptz,
  nhan_boi     text,
  xong_luc     timestamptz,
  cap_nhat_luc timestamptz not null default now(),
  thong_bao    text,
  ket_qua      jsonb
);
-- Mỗi việc chỉ có tối đa 1 yêu cầu đang chờ hoặc đang chạy (chống bấm trùng ở mức cơ sở dữ liệu)
create unique index if not exists refresh_requests_mot_viec on public.refresh_requests (job) where status in ('cho', 'dang_chay');
create index if not exists refresh_requests_job_luc on public.refresh_requests (job, tao_luc desc);

-- 2. Nhịp tim máy cửa hàng
create table if not exists public.may_nhip (
  may  text primary key,
  luc  timestamptz not null default now(),
  info jsonb
);

-- 3. Quyền: mọi người đã đăng nhập (có hồ sơ nhan_vien) chỉ được ĐỌC; ghi chỉ qua hàm bên dưới
alter table public.refresh_requests enable row level security;
alter table public.may_nhip enable row level security;
revoke insert, update, delete on public.refresh_requests from anon, authenticated;
revoke insert, update, delete on public.may_nhip from anon, authenticated;
revoke all on public.refresh_requests from anon;
revoke all on public.may_nhip from anon;
grant select on public.refresh_requests to authenticated;
grant select on public.may_nhip to authenticated;

create or replace function public.la_nhan_vien() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.nhan_vien where id = auth.uid())
$$;
create or replace function public.la_may() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.nhan_vien where id = auth.uid() and quyen = 'may')
$$;

drop policy if exists "rr doc" on public.refresh_requests;
create policy "rr doc" on public.refresh_requests for select to authenticated using (public.la_nhan_vien());
drop policy if exists "nhip doc" on public.may_nhip;
create policy "nhip doc" on public.may_nhip for select to authenticated using (public.la_nhan_vien());

-- Dọn yêu cầu cũ: chờ quá hạn → het_han; đang chạy quá 45 phút (máy chết giữa chừng) → loi
create or replace function public.rr_don_dep() returns void
language sql security definer set search_path = public as $$
  update public.refresh_requests set status = 'het_han', cap_nhat_luc = now(),
         thong_bao = 'Máy cửa hàng không nhận yêu cầu trong 15 phút (máy tắt hoặc chương trình nhận lệnh không chạy).'
   where status = 'cho' and het_han < now();
  update public.refresh_requests set status = 'loi', cap_nhat_luc = now(), xong_luc = now(),
         thong_bao = 'Máy chạy quá 45 phút không báo xong – coi như lỗi. Dữ liệu cũ vẫn giữ nguyên.'
   where status = 'dang_chay' and coalesce(cap_nhat_luc, nhan_luc) < now() - interval '45 minutes';
$$;

-- 4. Điện thoại gửi yêu cầu (chủ + nhân viên). Trả về yêu cầu đang có nếu đã bấm rồi.
create or replace function public.yeu_cau_lam_moi(p_job text)
returns public.refresh_requests
language plpgsql security definer set search_path = public as $$
declare r public.refresh_requests;
begin
  if not exists (select 1 from public.nhan_vien where id = auth.uid() and quyen in ('chu', 'nhan_vien')) then
    raise exception 'Tài khoản này không được gửi yêu cầu lấy giá' using errcode = '42501';
  end if;
  if p_job not in ('letak', 'checkgia') then
    raise exception 'Việc không hợp lệ: %', p_job using errcode = '22023';
  end if;
  perform public.rr_don_dep();
  select * into r from public.refresh_requests where job = p_job and status in ('cho', 'dang_chay') limit 1;
  if found then return r; end if;
  begin
    insert into public.refresh_requests (job) values (p_job) returning * into r;
  exception when unique_violation then  -- 2 người bấm cùng lúc
    select * into r from public.refresh_requests where job = p_job and status in ('cho', 'dang_chay') limit 1;
  end;
  return r;
end $$;

-- 5. Máy nhận 1 việc (chỉ tài khoản quyền 'may'). Không có việc → trả về null.
create or replace function public.may_nhan_viec(p_may text, p_jobs text[] default array['letak'])
returns public.refresh_requests
language plpgsql security definer set search_path = public as $$
declare r public.refresh_requests;
begin
  if not public.la_may() then raise exception 'Chỉ máy quét giá được nhận việc' using errcode = '42501'; end if;
  insert into public.may_nhip (may, luc) values (p_may, now())
    on conflict (may) do update set luc = now();
  perform public.rr_don_dep();
  select * into r from public.refresh_requests
   where status = 'cho' and het_han >= now() and job = any (p_jobs)
   order by tao_luc limit 1
   for update skip locked;
  if not found then return null; end if;
  update public.refresh_requests
     set status = 'dang_chay', nhan_luc = now(), nhan_boi = p_may, cap_nhat_luc = now(),
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
  insert into public.may_nhip (may, luc) values (p_may, now()) on conflict (may) do update set luc = now();
  return r;
end $$;

-- 7. Nhịp tim (máy gọi 30 giây/lần, kèm thông tin nhỏ: phiên bản, việc đang chạy)
create or replace function public.may_nhip_tim(p_may text, p_info jsonb default null)
returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.la_may() then raise exception 'Chỉ máy quét giá' using errcode = '42501'; end if;
  insert into public.may_nhip (may, luc, info) values (p_may, now(), p_info)
    on conflict (may) do update set luc = now(), info = coalesce(excluded.info, public.may_nhip.info);
end $$;

revoke all on function public.yeu_cau_lam_moi(text) from public, anon;
revoke all on function public.may_nhan_viec(text, text[]) from public, anon;
revoke all on function public.may_bao(bigint, text, text, text, jsonb) from public, anon;
revoke all on function public.may_nhip_tim(text, jsonb) from public, anon;
revoke all on function public.rr_don_dep() from public, anon, authenticated;
grant execute on function public.yeu_cau_lam_moi(text) to authenticated;
grant execute on function public.may_nhan_viec(text, text[]) to authenticated;
grant execute on function public.may_bao(bigint, text, text, text, jsonb) to authenticated;
grant execute on function public.may_nhip_tim(text, jsonb) to authenticated;

-- Kiểm tra: phải ra 2 bảng và 4 hàm
select table_name from information_schema.tables where table_schema = 'public' and table_name in ('refresh_requests', 'may_nhip');
select routine_name from information_schema.routines where routine_schema = 'public'
   and routine_name in ('yeu_cau_lam_moi', 'may_nhan_viec', 'may_bao', 'may_nhip_tim');
