# Seeded random sample of the live cohort launched >= 2026-07-01, deadline < 2026-11-03. One request per ~1.1 s. Stops after 2 throttle runs.
import pickle,random,json,time,subprocess,sys,datetime as dt,os
utc=dt.timezone.utc; T=lambda s: dt.datetime.fromisoformat(s).replace(tzinfo=utc).timestamp()
fate=pickle.load(open('work/fate.pkl','rb')); urls=pickle.load(open('work/urls.pkl','rb'))
co=sorted(i for i,f in fate.items() if i in urls and f['la']>=T('2026-07-01') and f['dl']<T('2026-11-03'))
print('cohort',len(co),flush=True)
random.seed(20261105); random.shuffle(co); co=co[:int(sys.argv[1])]
done=set()
if os.path.exists('work/resolved.jsonl'): done={json.loads(l)['id'] for l in open('work/resolved.jsonl')}
bad=0
with open('work/resolved.jsonl','a') as o:
    for i in co:
        if i in done: continue
        r=subprocess.run(['curl','-s','-m','20','-A','Mozilla/5.0','-w','\n%{http_code}',urls[i]+'/stats.json?v=1'],capture_output=True,text=True)
        body,_,code=r.stdout.rpartition('\n'); st=None
        try: st=json.loads(body)['project']
        except Exception: pass
        o.write(json.dumps(dict(id=i,code=code,state=st and st['state'],pledged=st and st['pledged'],sc=st and st['state_changed_at'],file_fin=fate[i]['fin'],first=fate[i]['first'],live_pf=fate[i]['live']['pf']))+'\n'); o.flush()
        if code in('429','403','503'):
            bad+=1
            if bad>=2: print('STOP throttled',code,flush=True); break
            time.sleep(60)
        else: bad=0
        time.sleep(1.1)
print('end',flush=True)
