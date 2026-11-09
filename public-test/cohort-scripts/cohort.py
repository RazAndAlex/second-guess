import pickle, glob, os, collections, datetime as dt
utc=dt.timezone.utc
T=lambda s: dt.datetime.fromisoformat(s).replace(tzinfo=utc).timestamp()
snap={'2026-05-12':'Kickstarter_2026-05-12T07_26_5','2026-06-11':'Kickstarter_2026-06-11T03_20_1','2026-07-24':'Kickstarter_2026-07-24T08_26_1','2026-08-12':'Kickstarter_2026-08-12T08_12_0','2026-09-10':'Kickstarter_2026-09-10T03_20_4','2026-10-12':'raw.json.gz'}
F={k:pickle.load(open(f'work/{v}.pkl','rb')) for k,v in snap.items()}
K=sorted(F); ts={k:T(k) for k in K}
print('--- per snapshot: unique, live, ended launched in last 365d')
for k in K:
    D=F[k]; st=collections.Counter(r['state'] for r in D.values())
    print(k,len(D),'live',st['live'],'succ',st['successful'],'fail',st['failed'],'cancel',st['canceled'],'funded share %.3f'%(st['successful']/(st['successful']+st['failed'])))
print('--- funded share by launch quarter, per snapshot (ended only)')
qs=collections.defaultdict(dict)
for k in K:
    c=collections.defaultdict(collections.Counter)
    for r in F[k].values():
        if r['la'] and r['state'] in('successful','failed'):
            m=dt.datetime.fromtimestamp(r['la'],utc); c[f'{m.year}Q{(m.month-1)//3+1}'][r['state']]+=1
    for q,v in c.items(): qs[q][k]=v
for q in sorted(qs):
    if q>='2024Q1' or q in('2015Q1','2015Q3','2019Q1','2021Q1','2023Q1'):
        print(q,' '.join(f"{k[5:]}:{v['successful']}/{v['failed']}={v['successful']/(v['successful']+v['failed']):.2f}" for k,v in sorted(qs[q].items())))
print('--- live cohorts: first live capture in snapshot k; fate by last file')
LAST='2026-10-12'
fate={}
for i,k in enumerate(K):
    for id_,r in F[k].items():
        if r['state']=='live' and id_ not in fate:
            fate[id_]=dict(first=k,la=r['la'],dl=r['dl'],live=r)
for id_,f in fate.items():
    fin=None; seen=[]
    for k in K:
        if ts[k]<=ts[f['first']]: continue
        r=F[k].get(id_)
        if r:
            seen.append((k,r['state']))
            if r['state'] in('successful','failed','canceled','suspended'): fin=(r['state'],k)
    f['fin']=fin; f['seen']=seen
pickle.dump(fate,open('work/fate.pkl','wb'))
for k in K:
    co=[f for f in fate.values() if f['first']==k]
    done=[f for f in co if f['dl'] and f['dl']<ts[LAST]-86400]
    c=collections.Counter((f['fin'][0] if f['fin'] else 'VANISHED_or_still_live') for f in done)
    s,fl=c['successful'],c['failed']
    print(k,'cohort',len(co),'deadline before last snap',len(done),dict(c),'funded share %.3f'%(s/max(1,s+fl)),'upper-if-vanished-failed vs lower: lower %.3f'%(s/max(1,len(done))))
print('--- by launch date windows: live cohort vs last-file')
for a,b in (('2026-04-01','2026-06-01'),('2026-06-01','2026-08-13'),('2026-07-01','2026-08-13'),('2026-07-01','2026-09-10')):
    A,B=T(a),T(b)
    co=[f for f in fate.values() if f['la'] and A<=f['la']<B and f['dl']<ts[LAST]-86400]
    c=collections.Counter((f['fin'][0] if f['fin'] else 'VANISHED') for f in co)
    s,fl=c['successful'],c['failed']
    r10=collections.Counter(r['state'] for r in F[LAST].values() if r['la'] and A<=r['la']<B)
    # union of ended in all files
    u={}
    for k in K:
        for id_,r in F[k].items():
            if r['la'] and A<=r['la']<B and r['state'] in('successful','failed','canceled','suspended'): u[id_]=r['state']
    uc=collections.Counter(u.values())
    print(a,b,'cohort',len(co),dict(c),'funded/(f+s) %.3f'%(s/max(1,s+fl)),'| oct file',dict(r10),'share %.3f'%(r10['successful']/max(1,r10['successful']+r10['failed'])),'| union ended',dict(uc),'share %.3f'%(uc['successful']/max(1,uc['successful']+uc['failed'])))
