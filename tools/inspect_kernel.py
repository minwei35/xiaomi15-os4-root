"""Offline kernel decompression and identity inspection; no device operations."""
from pathlib import Path
import sys,struct,hashlib,re,gzip,json
R=Path(__file__).parent
sys.path.insert(0,str(R/'python-deps'))
import lz4.block,lz4.frame
packed=(R/'kernel-packed.bin').read_bytes()
if packed[:4]==b'\x02\x21\x4c\x18':
 pos=4;chunks=[]
 while pos+4<=len(packed):
  n=struct.unpack_from('<I',packed,pos)[0];pos+=4
  if not n:break
  if pos+n>len(packed):raise ValueError('LZ4 block outside input')
  chunks.append(lz4.block.decompress(packed[pos:pos+n],uncompressed_size=8*1024*1024));pos+=n
 data=b''.join(chunks)
elif packed[:4]==b'\x04\x22\x4d\x18':data=lz4.frame.decompress(packed)
elif packed[:2]==b'\x1f\x8b':data=gzip.decompress(packed)
elif packed[56:60]==b'ARMd':data=packed
else:raise ValueError('Unrecognized kernel compression '+packed[:16].hex())
assert data[56:60]==b'ARMd','Not ARM64 Image'
(R/'Image').write_bytes(data)
banners=[s.decode('ascii','replace') for s in re.findall(rb'Linux version [^\x00\n]{1,800}',data)]
report={'image_size':len(data),'image_sha256':hashlib.sha256(data).hexdigest(),'banners':banners,'packed_sha256':hashlib.sha256(packed).hexdigest()}
# Presence of symbol text is only a hint, never a proof of patch status.
report['symbol_text_hints']={s:data.find(s.encode()+b'\0') for s in ['posixtimer_exec','posix_cpu_timers_exit','begin_new_exec']}
(R/'kernel-identity.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
