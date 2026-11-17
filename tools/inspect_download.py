from pathlib import Path
import re,base64
for filename in ['firmware-load.html']:
 s=Path(__file__).with_name(filename).read_text(encoding='utf-8')
 for value in re.findall(r'data-href=[\"\']([^\"\']+)',s):
  try:
   decoded=base64.b64decode(value).decode()
   if any(t in decoded for t in ['zip','tgz','download','miui']): print(decoded)
  except Exception: pass
p=Path(__file__).with_name('khleak-release-1.2.0')
for word in re.findall(rb'[ -~]{8,}',p.read_bytes()):
 if any(t in word for t in [b'BUILD=',b'abogki551',b'hazardfix',b'guard v']): print(word.decode())
