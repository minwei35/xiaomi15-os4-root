"""Offline audit of exec timer-cleanup order; does not construct or run an exploit."""
from pathlib import Path
import sys,json
R=Path(__file__).parent;sys.path.insert(0,str(R/'python-deps'))
from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
image=(R/'Image').read_bytes();base=0xffffffc080000000
symbols=[]
for line in (R/'Image.kallsyms').read_text().splitlines():
 address,name=line.split(' ',1);symbols.append((int(address,16),name[1:]))
lookup={a:n for a,n in symbols};byname={n:a for a,n in symbols}
a=byname['begin_new_exec'];end=min(v for v,n in symbols if v>a)
cs=Cs(CS_ARCH_ARM64,CS_MODE_ARM);cs.detail=True
lines=[];calls=[]
for ins in cs.disasm(image[a-base:end-base],a):
 text=f'{ins.address:016x}: {ins.mnemonic:8s} {ins.op_str}'
 if ins.mnemonic in ('bl','b') and ins.op_str.startswith('#'):
  dest=int(ins.op_str[1:],16);name=lookup.get(dest,'unknown');text+=' ; '+name
  calls.append({'address':hex(ins.address),'target':name})
 lines.append(text)
(R/'begin_new_exec.disasm.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
(R/'exec-call-order.json').write_text(json.dumps(calls,indent=2),encoding='utf-8')
print(json.dumps(calls,indent=2))
