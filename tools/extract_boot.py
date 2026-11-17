"""Read-only OTA boot extraction with payload operation and partition SHA256 checks."""
import urllib.request,struct,hashlib,base64,lzma,bz2,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).parent
URL='https://bkt-sgp-miui-ota-update-alisgp.oss-ap-southeast-1.aliyuncs.com/OS4.0.4.0.XOCCNXM/dada-ota_full-OS4.0.4.0.XOCCNXM-user-17.0-92227559a4.zip'
BASE=4942

def fetch(off,n):
 cache=ROOT/'range-cache';cache.mkdir(exist_ok=True)
 target=cache/f'{off}-{n}.bin';headers=cache/f'{off}-{n}.headers'
 if target.exists() and target.stat().st_size==n:return target.read_bytes()
 subprocess.run(['C:/Users/KURO/.dsh/profiles/desktop/node_modules/@dsh-ops/bash-win32-x64/ucrt64/bin/curl.exe','--fail','--location','--retry','3','--max-time','180','--referer','https://www.miui.com/','--range',f'{off}-{off+n-1}','--dump-header',str(headers),'--output',str(target),URL.replace('bkt-sgp-miui-ota-update-alisgp.oss-ap-southeast-1.aliyuncs.com','bn.d.miui.com')],check=True)
 data=target.read_bytes()
 if len(data)!=n:raise ValueError('Unexpected response size')
 h=headers.read_text().lower()
 if f'content-range: bytes {off}-' not in h:raise ValueError('Wrong range')
 return data

def varint(b,p):
 n=0;s=0
 while True:
  v=b[p];p+=1;n|=(v&127)<<s
  if v<128:return n,p
  s+=7
  if s>70:raise ValueError('Invalid protobuf')

def fields(b):
 d={};p=0
 while p<len(b):
  k,p=varint(b,p);wire=k&7
  if wire==0:v,p=varint(b,p)
  elif wire==2:
   n,p=varint(b,p);v=b[p:p+n];p+=n
  elif wire in (1,5):
   n=8 if wire==1 else 4;v=b[p:p+n];p+=n
  else:raise ValueError(f'wire {wire}')
  d.setdefault(k>>3,[]).append(v)
 return d

def one(d,k,default=None):return d.get(k,[default])[0]
head=fetch(BASE,24)
magic,version,mlen,slen=struct.unpack('>4sQQI',head)
assert magic==b'CrAU' and version==2
metadata=head+fetch(BASE+24,mlen)
expected='72ijdERdFGZAV/d1wlTawH2jcNBHu8dBp2AC3MsU2xo='
assert base64.b64encode(hashlib.sha256(metadata).digest()).decode()==expected,'Metadata hash mismatch'
(ROOT/'payload-metadata.bin').write_bytes(metadata)
m=fields(metadata[24:]);block=one(m,3,4096);blob=BASE+24+mlen+slen
report={'metadata_hash_verified':True,'partitions':[]}
for raw in m.get(13,[]):
 p=fields(raw);name=one(p,1).decode();info=fields(one(p,7));size=one(info,1);sha=one(info,2)
 report['partitions'].append({'name':name,'size':size,'sha256':sha.hex()})
 if name!='boot':continue
 image=bytearray(size)
 for idx,opraw in enumerate(p.get(8,[])):
  op=fields(opraw);kind=one(op,1);length=one(op,3,0)
  print('boot operation',idx,'type',kind,'download',length,flush=True)
  if kind in (6,7):data=b''
  else:
   data=fetch(blob+one(op,2,0),length)
   if one(op,8):assert hashlib.sha256(data).digest()==one(op,8),'Operation hash mismatch'
   if kind==8:data=lzma.decompress(data)
   elif kind==1:data=bz2.decompress(data)
   elif kind!=0:raise ValueError(f'Unsupported operation {kind}')
  cursor=0
  for ext in op.get(6,[]):
   e=fields(ext);start=one(e,1)*block;n=one(e,2)*block
   assert start+n<=size
   chunk=data[cursor:cursor+n]
   image[start:start+n]=chunk+b'\0'*(n-len(chunk));cursor+=n
  assert len(data)<=cursor
 assert hashlib.sha256(image).digest()==sha,'Partition hash mismatch'
 target=ROOT/'boot-stock.img'
 if target.exists():assert target.read_bytes()==image,'Existing output differs'
 else:target.write_bytes(image)
 print('BOOT SHA256 VERIFIED',sha.hex(),flush=True)
 assert image[:8]==b'ANDROID!'
 kernel_size=struct.unpack_from('<I',image,8)[0];header_version=struct.unpack_from('<I',image,40)[0]
 assert header_version in (3,4),header_version
 kernel=bytes(image[4096:4096+kernel_size]);(ROOT/'kernel-packed.bin').write_bytes(kernel)
 report['boot']={'header_version':header_version,'kernel_size':kernel_size,'sha256':sha.hex(),'kernel_sha256':hashlib.sha256(kernel).hexdigest(),'kernel_magic':kernel[:16].hex()}
 print('KERNEL',report['boot'],flush=True)
(ROOT/'extraction-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
