import io,zipfile,urllib.request,json
from pathlib import Path
URL='https://bkt-sgp-miui-ota-update-alisgp.oss-ap-southeast-1.aliyuncs.com/OS4.0.4.0.XOCCNXM/dada-ota_full-OS4.0.4.0.XOCCNXM-user-17.0-92227559a4.zip'
class Remote(io.RawIOBase):
 def __init__(self):
  self.pos=0; self.size=8795504847
 def seekable(self): return True
 def readable(self): return True
 def tell(self): return self.pos
 def seek(self,offset,whence=0):
  self.pos=offset if whence==0 else (self.pos+offset if whence==1 else self.size+offset)
  return self.pos
 def read(self,n=-1):
  if n<0: n=self.size-self.pos
  n=min(n,self.size-self.pos)
  if not n:return b''
  if n>4*1024*1024:raise ValueError('Metadata-only reader limits request size')
  req=urllib.request.Request(URL,headers={'Range':f'bytes={self.pos}-{self.pos+n-1}'})
  with urllib.request.urlopen(req,timeout=40) as r:
   if r.status!=206:raise ValueError(f'Range ignored: {r.status}')
   data=r.read(n)
  self.pos+=len(data); return data
out=Path(__file__).parent
with zipfile.ZipFile(Remote()) as z:
 listing=[{'name':i.filename,'size':i.file_size,'compressed':i.compress_size,'method':i.compress_type,'offset':i.header_offset} for i in z.infolist()]
 (out/'ota-entries.json').write_text(json.dumps(listing,indent=2),encoding='utf-8')
 for name in ['META-INF/com/android/metadata','payload_properties.txt']:
  if name in z.namelist():
   data=z.read(name).decode()
   (out/('ota-'+name.rsplit('/',1)[-1]+'.txt')).write_text(data,encoding='utf-8')
   print(name+'\n'+data)
 print('ENTRIES',len(listing))
