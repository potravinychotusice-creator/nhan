-- Sửa lỗi "new row violates row-level security policy for table du_lieu".
-- Supabase → SQL Editor → New query → dán toàn bộ → Run. Chạy lại nhiều lần cũng không sao.

grant select, insert, update, delete on public.du_lieu  to authenticated;
grant select, update                 on public.nhan_vien to authenticated;

alter table public.du_lieu enable row level security;

drop policy if exists "doc du lieu" on public.du_lieu;
create policy "doc du lieu" on public.du_lieu for select to authenticated using (true);
drop policy if exists "ghi du lieu" on public.du_lieu;
create policy "ghi du lieu" on public.du_lieu for insert to authenticated with check (true);
drop policy if exists "sua du lieu" on public.du_lieu;
create policy "sua du lieu" on public.du_lieu for update to authenticated using (true) with check (true);
drop policy if exists "xoa du lieu" on public.du_lieu;
create policy "xoa du lieu" on public.du_lieu for delete to authenticated using (true);

-- Kết quả phải ra 4 dòng: doc / ghi / sua / xoa du lieu
select policyname, cmd from pg_policies where tablename = 'du_lieu' order by policyname;
