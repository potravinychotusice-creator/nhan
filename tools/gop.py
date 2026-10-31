"""Gộp src/<khoa>.html trở lại vào nhan.html (giữ nguyên thứ tự)."""
import json, base64, pathlib
goc = pathlib.Path(__file__).resolve().parent.parent
f = goc / 'nhan.html'
s = f.read_text(encoding='utf-8')
i = s.index('var DATA=') + 9
d, n = json.JSONDecoder().raw_decode(s[i:])
for k in d:
    p = goc / 'src' / f'{k}.html'
    if p.exists():
        d[k] = base64.b64encode(p.read_text(encoding='utf-8').encode('utf-8')).decode()
f.write_text(s[:i] + json.dumps(d, ensure_ascii=False, separators=(', ', ': ')) + s[i + n:], encoding='utf-8')
print('đã gộp vào nhan.html')
