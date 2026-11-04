#!/usr/bin/env python3
# build_letak.py letak_page.html → so-gia-letak.html (nhúng letak_data.json)
import json,sys
t=open(sys.argv[1] if len(sys.argv)>1 else 'letak_page.html',encoding='utf-8').read()
d=open('letak_data.json',encoding='utf-8').read().replace('</','<\\/')
open('so-gia-letak.html','w',encoding='utf-8').write(t.replace('__DATA__',d))
print('ok',len(t)+len(d))
