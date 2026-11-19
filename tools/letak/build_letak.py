#!/usr/bin/env python3
# build_letak.py letak_page.html → so-gia-letak.html (nhúng letak_data.json)
import json,sys
t=open(sys.argv[1] if len(sys.argv)>1 else 'letak_page.html',encoding='utf-8').read()
d=open('letak_data.json',encoding='utf-8').read().replace('</','<\\/')
# 19.11: ảnh to Kupi (thumbs 170×340) cho thẻ kiểu e-shop – chỉ giữ đuôi link, theo slug sản phẩm
P='https://img.kupi.cz/kupi/thumbs/';U={}
try:
    sl={(r[22] or '').split('/')[-1] for r in json.loads(open('letak_data.json',encoding='utf-8').read())['D'] if len(r)>22 and r[22]}
    for r in json.load(open('kupi.json',encoding='utf-8')):
        s=(r.get('prod') or '').split('/')[-1];u=r.get('img') or ''
        if s in sl and u.startswith(P):U.setdefault(s,u[len(P):])
except Exception as e:print('  ảnh to: bỏ qua',e)
open('so-gia-letak.html','w',encoding='utf-8').write(t.replace('__DATA__',d).replace('__IMGU__',json.dumps(U,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')))
print('ok',len(t)+len(d))
