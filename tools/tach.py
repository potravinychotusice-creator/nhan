"""Tách các công cụ con (base64 trong nhan.html) ra src/<khoa>.html để sửa."""
import json, base64, pathlib
goc = pathlib.Path(__file__).resolve().parent.parent
s = (goc / 'nhan.html').read_text(encoding='utf-8')
i = s.index('var DATA=') + 9
d, _ = json.JSONDecoder().raw_decode(s[i:])
for k, v in d.items():
    (goc / 'src' / f'{k}.html').write_text(base64.b64decode(v).decode('utf-8'), encoding='utf-8')
print('đã tách', len(d), 'công cụ vào src/')
