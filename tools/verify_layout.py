"""Verify struct offsets used by the profile against real device disassembly."""
from pathlib import Path
import sys,re,json
R=Path(__file__).parent;sys.path.insert(0,str(R/'python-deps'))
from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
image=(R/'Image').read_bytes();base=0xffffffc080000000
sym={}
for line in (R/'Image.kallsyms').read_text().splitlines():
    a,n=line.split(' ',1);sym.setdefault(n[1:],int(a,16))
addrs=sorted(sym.values())
def body(name):
    a=sym[name];end=min(v for v in addrs if v>a)
    return image[a-base:end-base],a
def offsets(name,limit=400):
    data,a=body(name);cs=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    found=[]
    for ins in cs.disasm(data,0):
        m=ins.op_str
        for pat in (r'#0x([0-9a-f]+)\]',):
            for h in re.findall(pat,m):
                found.append(int(h,16))
        if len(found)>limit:break
    return found
report={}
# cred_layout: prepare_creds copies cred_jar then zeroes ctty? check cred_security store offset
pc=offsets('prepare_creds')
report['prepare_creds_offsets_present']={hex(o):(o in pc) for o in [0x00,0x08,0x28,0x30,0x38,0x40,0x48,0x50,0x80,0x88,0x90,0x98,0xa0]}
stc=offsets('__set_task_comm')
report['set_task_comm_has_0x830']=0x830 in stc
report['set_task_comm_sample']=[hex(o) for o in sorted(set(stc))[:40]]
cp=offsets('copy_process',2000)
report['copy_process_has_cred_pair']={'0x818':0x818 in cp,'0x820':0x820 in cp,'0x61c':0x61c in cp,'0x880':0x880 in cp}
(R/'layout-verify.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
