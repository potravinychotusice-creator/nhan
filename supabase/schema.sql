-- B1: khung dữ liệu chung. Chạy 1 lần trong Supabase → SQL Editor → New query → Run.
-- Chỉ người đã đăng nhập mới đọc/ghi được. Không ai tự đăng ký được (tắt sign-up trong Authentication).

-- Hồ sơ nhân viên (tên hiển thị + quyền)
create table if not exists public.nhan_vien (
  id uuid primary key references auth.users(id) on delete cascade,
  ten text,
  quyen text not null default 'nhan_vien' check (quyen in ('chu','nhan_vien')),
  tao_luc timestamptz not null default now()
);

-- Tự tạo hồ sơ khi anh thêm người dùng mới
create or replace function public.tao_nhan_vien() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.nhan_vien(id, ten) values (new.id, split_part(new.email,'@',1))
  on conflict do nothing;
  return new;
end $$;
drop trigger if exists tao_nhan_vien on auth.users;
create trigger tao_nhan_vien after insert on auth.users
  for each row execute function public.tao_nhan_vien();

-- Dữ liệu chung dạng khoá → JSON (danh mục GOKASA, giá nhập, leták, cài đặt…)
create table if not exists public.du_lieu (
  khoa text primary key,
  gia_tri jsonb not null,
  cap_nhat_luc timestamptz not null default now(),
  cap_nhat_boi uuid references auth.users(id) default auth.uid()
);

create or replace function public.dong_dau_gio() returns trigger
language plpgsql as $$ begin new.cap_nhat_luc = now(); return new; end $$;
drop trigger if exists dong_dau_gio on public.du_lieu;
create trigger dong_dau_gio before update on public.du_lieu
  for each row execute function public.dong_dau_gio();

alter table public.nhan_vien enable row level security;
alter table public.du_lieu  enable row level security;

drop policy if exists "doc nhan vien" on public.nhan_vien;
create policy "doc nhan vien" on public.nhan_vien for select to authenticated using (true);
drop policy if exists "sua ten minh" on public.nhan_vien;
create policy "sua ten minh" on public.nhan_vien for update to authenticated
  using (id = auth.uid()) with check (id = auth.uid() and quyen = (select quyen from public.nhan_vien where id = auth.uid()));

drop policy if exists "doc du lieu" on public.du_lieu;
create policy "doc du lieu" on public.du_lieu for select to authenticated using (true);
drop policy if exists "ghi du lieu" on public.du_lieu;
create policy "ghi du lieu" on public.du_lieu for insert to authenticated with check (true);
drop policy if exists "sua du lieu" on public.du_lieu;
create policy "sua du lieu" on public.du_lieu for update to authenticated using (true) with check (true);

-- Hồ sơ cho người dùng đã tạo trước khi chạy file này
insert into public.nhan_vien(id, ten)
  select id, split_part(email,'@',1) from auth.users on conflict do nothing;

-- Anh là chủ
update public.nhan_vien set quyen = 'chu'
  where id = (select id from auth.users where email = 'potravinychotusice@gmail.com');
