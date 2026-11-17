from pathlib import Path
import sys,logging,json
R=Path(__file__).parent
sys.path.insert(0,str(R/'python-deps'))
from vmlinux_to_elf.core.kallsyms import KallsymsFinder
logging.basicConfig(level=logging.INFO)
k=KallsymsFinder((R/'Image').read_bytes(),64,False,None)
with (R/'Image.kallsyms').open('w',encoding='utf-8') as f:
 for address,name in zip(k.kernel_addresses,k.symbol_names):f.write(f'{address:016x} {name}\n')
wanted=['begin_new_exec','de_thread','posix_cpu_timers_exit','posixtimer_exec','exec_mmap']
selected={name:hex(address) for address,name in zip(k.kernel_addresses,k.symbol_names) if name in wanted or name[1:] in wanted}
(R/'patch-symbol-hints.json').write_text(json.dumps(selected,indent=2),encoding='utf-8')
print('symbols',len(k.symbol_names));print(json.dumps(selected,indent=2))
