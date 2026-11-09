import pickle, collections, datetime as dt, re, random
utc=dt.timezone.utc
T=lambda s: dt.datetime.fromisoformat(s).replace(tzinfo=utc).timestamp()
snap={'2026-05-12':'Kickstarter_2026-05-12T07_26_5','2026-06-11':'Kickstarter_2026-06-11T03_20_1','2026-07-24':'Kickstarter_2026-07-24T08_26_1','2026-08-12':'Kickstarter_2026-08-12T08_12_0','2026-09-10':'Kickstarter_2026-09-10T03_20_4','2026-10-12':'raw.json.gz'}
F={k:pickle.load(open(f'work/{v}.pkl','rb')) for k,v in snap.items()}
K=sorted(F); ts={k:T(k) for k in K}
# A: P(file holds an id | outcome). Reference: ended projects seen in ANY file, launched 2024-01..2026-03 (all ended before first file's... ) 
A,B=T('2024-01-01'),T('2026-03-01')
u={}
for k in K:
    for i,r in F[k].items():
        if r['la'] and A<=r['la']<B and r['state'] in('successful','failed'): u[i]=r['state']
tot=collections.Counter(u.values()); print('A union',dict(tot),'share %.3f'%(tot['successful']/sum(tot.values())))
for k in K:
    h=collections.Counter(u[i] for i in u if i in F[k])
    print(' ',k,'holds succ %.3f fail %.3f'%(h['successful']/tot['successful'],h['failed']/tot['failed']),'share in file %.3f'%(h['successful']/sum(h.values())))
# B: live capture vs outcome: ended projects whose campaign spanned snapshot S at least 3 days, was it captured live at S?
print('B capture at S of projects spanning S (outcome known from any later file)')
final={}
for k in K:
    for i,r in F[k].items():
        if r['state'] in('successful','failed'): final[i]=r
for k in K[:-1]:
    S=ts[k]; c=collections.defaultdict(lambda:[0,0])
    for i,r in final.items():
        if r['la'] and r['dl'] and r['la']<S-3*86400 and r['dl']>S+3*86400:
            c[r['state']][1]+=1
            if F[k].get(i,{}).get('state')=='live': c[r['state']][0]+=1
    print(' ',k,{s:(v[0],v[1],round(v[0]/max(1,v[1]),3)) for s,v in c.items()})
# C: vanished vs resolved: traction at last live capture
fate=pickle.load(open('work/fate.pkl','rb'))
LAST=ts['2026-10-12']
def frac(r,S): return (S-r['la'])/max(1,r['dl']-r['la'])
print('C pct funded at first live capture, cohort first seen 05-12 to 08-12, deadline before 10-10')
grp=collections.defaultdict(list)
for i,f in fate.items():
    if f['first'] in K[:4] and f['dl']<LAST-2*86400:
        lab=f['fin'][0] if f['fin'] else 'vanished'
        grp[lab].append((f['live'].get('pf') or 0, frac(f['live'],ts[f['first']])))
import statistics as st
for l,v in grp.items():
    p=[x[0] for x in v]; print(' ',l,len(v),'median pf %.1f'%st.median(p),'share<10 %.3f'%(sum(x<10 for x in p)/len(p)),'share>=100 %.3f'%(sum(x>=100 for x in p)/len(p)),'median frac elapsed %.2f'%st.median(x[1] for x in v))
# D: expected funded share among vanished, from resolved with same pf bin and elapsed bin
def bins(p,fr): return (min(int(p//20),6) if p<120 else 7, min(int(fr*4),3))
cnt=collections.defaultdict(lambda:[0,0])
for l,v in grp.items():
    if l in('successful','failed'):
        for p,fr in v: cnt[bins(p,fr)][l=='successful']+=1
exp=0;n=0
for p,fr in grp['vanished']:
    a=cnt[bins(p,fr)]
    if sum(a): exp+=a[1]/sum(a); n+=1
print('D expected funded rate among vanished, matched on traction bin: %.3f (n=%d)'%(exp/n,n))
# E: name/blurb change first live->later record; traction words
ch=collections.Counter(); w=re.compile(r'\b(funded|stretch goal|goal reached|unlocked|overfunded|thank you)\b',re.I); wl=0;wf=0;tot2=0
for i,f in fate.items():
    r=f['live']
    if f['fin']:
        e=F[f['fin'][1]][i]; ch['n']+=1; ch['name']+=e['name']!=r['name']; ch['blurb']+=e['blurb']!=r['blurb']; ch['goal']+=e['goal']!=r['goal']; ch['cat']+=e['cat']!=r['cat']
        wf+=bool(w.search((e['name'] or '')+' '+(e['blurb'] or '')))
    wl+=bool(w.search((r['name'] or '')+' '+(r['blurb'] or ''))); tot2+=1
print('E first live vs final record',dict(ch),'; traction words: live %d/%d, final %d/%d'%(wl,tot2,wf,ch['n']))
print('E2 pop: state at capture', collections.Counter(f['live']['state'] for f in fate.values()))
print('F categories in oct file: names',len({r['cat'] for r in F['2026-10-12'].values()}),'parents',len({r['parent'] for r in F['2026-10-12'].values()}),sorted(map(str,{r['parent'] for r in F['2026-10-12'].values()})))
lines=91931
print('G duplicates: oct unique',len(F['2026-10-12']))
