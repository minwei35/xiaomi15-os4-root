"""Compare recovered symbols against the miro (K80 Pro) 4.0.3.0 profile."""
from pathlib import Path
import json,re
R=Path(__file__).parent
sym={}
for line in (R/'Image.kallsyms').read_text().splitlines():
    a,n=line.split(' ',1)
    sym[n[1:]]=int(a,16)
profile={
 'image_base':0xffffffc080000000,'stext':0xffffffc080010000,
 'getpid':0xffffffc0800cda70,'gettid':0xffffffc0800cdaa0,'getppid':0xffffffc0800cdad0,
 'set_task_comm':0xffffffc0803d4ac4,'do_timer_create':0xffffffc080195cf4,
 'copy_process':0xffffffc0800ab7fc,'prepare_creds':0xffffffc0800e4040,
 'commit_creds':0xffffffc0800e45e8,'timer_link':0xffffffc080195d9c,
 'task_alloc_link':0xffffffc0800ab93c,'cred_link':0xffffffc0800e4064,
 'selinux_state':0xffffffc08237a350,'user_ns':0xffffffc08214ef90,
 'root_user':0xffffffc08214f220,'init_groups':0xffffffc082150780,
 'init_ucounts':0xffffffc082150cf0,'init_task':0xffffffc08213e2c0,
 'init_cred':0xffffffc082150788,'posix_timers_cache':0xffffffc08235c760,
 'memstart_addr':0xffffffc0816873e8,'kimage_voffset':0xffffffc0816874a0,
}
alias={'_text':'image_base','_stext':'stext','__set_task_comm':'set_task_comm'}
rows=[];bad=0
for key,expected in profile.items():
    actual=sym.get(key)
    if actual is None:
        for a,k in alias.items():
            if k==key and a in sym: actual=sym[a]
    ok=actual==expected
    if not ok: bad+=1
    rows.append({'symbol':key,'miro_expected':hex(expected),
                 'device_recovered':hex(actual) if actual else None,'match':ok})
out={'matched':len(rows)-bad,'mismatched':bad,'rows':rows}
(R/'profile-compare.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
for r in rows:
    print(('OK   ' if r['match'] else 'DIFF '),r['symbol'],r['miro_expected'],r['device_recovered'])
print('SUMMARY matched=%d mismatched=%d'%(out['matched'],out['mismatched']))
