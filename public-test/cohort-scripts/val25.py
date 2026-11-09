# Method check against the outside figure: ids live on 2025-07-14, resolved today by stats.json. Same period as the stats delta.
import gzip,json,random,subprocess,time,sys
ids={}
for line in gzip.open('data/Kickstarter_2025-07-14T06_25_27_218Z.json.gz','rt',encoding='utf-8'):
    if '"state":"live"' not in line: continue
    d=json.loads(line)['data']
    if d['state']=='live': ids[d['id']]=d['urls']['web']['project']
k=sorted(ids); random.seed(202507); random.shuffle(k); print(len(k),flush=True); bad=0
with open('work/val25.jsonl','a') as o:
    for i in k[:int(sys.argv[1])]:
        r=subprocess.run(['curl','-s','-m','20','-A','Mozilla/5.0','-w','\n%{http_code}',ids[i]+'/stats.json?v=1'],capture_output=True,text=True)
        body,_,code=r.stdout.rpartition('\n'); st=None
        try: st=json.loads(body)['project']['state']
        except Exception: pass
        o.write(json.dumps(dict(id=i,code=code,state=st))+'\n'); o.flush()
        if code in('429','403','503'):
            bad+=1
            if bad>=2: print('STOP',code,flush=True); break
            time.sleep(60)
        else: bad=0
        time.sleep(1.1)
print('end',flush=True)
