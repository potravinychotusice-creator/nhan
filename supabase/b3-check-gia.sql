-- B3: Check giá trong app. Supabase → SQL Editor → New query → dán toàn bộ → Run.
-- Chạy SAU KHI đã tạo tài khoản máy quét (Authentication → Users → Add user → Create new user,
-- email potravinychotusice+may@gmail.com, mật khẩu trong file may.env, tích "Auto Confirm User").
-- Chạy lại nhiều lần cũng không sao.

-- 1. Quyền "may" = máy cửa hàng (chỉ để đẩy giá lên, không phải người)
alter table public.nhan_vien drop constraint if exists nhan_vien_quyen_check;
alter table public.nhan_vien add constraint nhan_vien_quyen_check check (quyen in ('chu','nhan_vien','may'));
insert into public.nhan_vien(id, ten, quyen)
  select id, 'Máy quét giá', 'may' from auth.users where email = 'potravinychotusice+may@gmail.com'
  on conflict (id) do update set quyen = 'may', ten = 'Máy quét giá';

create or replace function public.duoc_day_gia() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.nhan_vien where id = auth.uid() and quyen in ('chu','may'))
$$;

-- 2. Kho kín "checkgia": trang Check giá + giá nhập. Chỉ người đã đăng nhập mới tải được,
--    chỉ chủ + máy quét mới ghi được.
insert into storage.buckets (id, name, public) values ('checkgia', 'checkgia', false)
  on conflict (id) do update set public = false;

drop policy if exists "checkgia doc" on storage.objects;
create policy "checkgia doc" on storage.objects for select to authenticated using (bucket_id = 'checkgia');
drop policy if exists "checkgia ghi" on storage.objects;
create policy "checkgia ghi" on storage.objects for insert to authenticated with check (bucket_id = 'checkgia' and public.duoc_day_gia());
drop policy if exists "checkgia sua" on storage.objects;
create policy "checkgia sua" on storage.objects for update to authenticated using (bucket_id = 'checkgia' and public.duoc_day_gia());
drop policy if exists "checkgia xoa" on storage.objects;
create policy "checkgia xoa" on storage.objects for delete to authenticated using (bucket_id = 'checkgia' and public.duoc_day_gia());

-- 3. Dữ liệu chung của trang Check giá (mã đã học, báo sai, món hay xem, list leták, trạng thái quét)
create table if not exists public.tai_lieu (
  bo   text not null,              -- ean, report, views, letak_list, status…
  id   text not null,
  data jsonb not null,
  luc  timestamptz not null default now(),
  boi  uuid references auth.users(id) default auth.uid(),
  primary key (bo, id)
);
create or replace function public.dong_dau_luc() returns trigger
language plpgsql as $$ begin new.luc = now(); return new; end $$;
drop trigger if exists dong_dau_luc on public.tai_lieu;
create trigger dong_dau_luc before update on public.tai_lieu for each row execute function public.dong_dau_luc();

grant select, insert, update, delete on public.tai_lieu to authenticated;
alter table public.tai_lieu enable row level security;
drop policy if exists "tl doc" on public.tai_lieu;
create policy "tl doc" on public.tai_lieu for select to authenticated using (true);
drop policy if exists "tl ghi" on public.tai_lieu;
create policy "tl ghi" on public.tai_lieu for insert to authenticated with check (true);
drop policy if exists "tl sua" on public.tai_lieu;
create policy "tl sua" on public.tai_lieu for update to authenticated using (true) with check (true);
drop policy if exists "tl xoa" on public.tai_lieu;
create policy "tl xoa" on public.tai_lieu for delete to authenticated using (true);

-- Kiểm tra: phải ra 1 dòng "Máy quét giá | may" và 1 dòng bucket checkgia (public = false)
select ten, quyen from public.nhan_vien where quyen = 'may';
select id, public from storage.buckets where id = 'checkgia';
