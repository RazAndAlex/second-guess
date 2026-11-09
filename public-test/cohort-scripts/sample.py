import json,collections,pickle,datetime as dt,statistics as st,sys
utc=dt.timezone.utc; T=lambda s: dt.datetime.fromisoformat(s).replace(tzinfo=utc).timestamp()
R=[json.loads(l) for l in open('work/resolved.jsonl')]
fate=pickle.load(open('work/fate.pkl','rb'))
print('n',len(R),collections.Counter(r['code'] for r in R))
c=collections.Counter(r['state'] for r in R); print(dict(c))
s,f=c['successful'],c['failed']; n=sum(c.values())
print('funded/(f+s) %.3f  funded/all-ended %.3f'%(s/(s+f),s/max(1,n-c['live'])))
ag=collections.Counter()
for r in R:
    if r['file_fin']: ag[(r['file_fin'][0],r['state'])]+=1
print('file vs direct',dict(ag))
v=[r for r in R if not r['file_fin']]; vc=collections.Counter(r['state'] for r in v); print('vanished from files',len(v),dict(vc),'funded/(f+s) %.3f'%(vc['successful']/max(1,vc['successful']+vc['failed'])))
for lab,lo,hi in (('launch07-01..09-01','2026-07-01','2026-09-01'),('launch07-01..08-13','2026-07-01','2026-08-13')):
    rr=[r for r in R if T(lo)<=fate[r['id']]['la']<T(hi)]; cc=collections.Counter(r['state'] for r in rr); print(lab,len(rr),dict(cc),'f/(f+s) %.3f'%(cc['successful']/max(1,cc['successful']+cc['failed'])))
# 30d+ duration
for lab,fn in (('dur<30',lambda d:d<29.5),('dur>=30',lambda d:d>=29.5)):
    rr=[r for r in R if fn((fate[r['id']]['dl']-fate[r['id']]['la'])/86400) and T('2026-07-01')<=fate[r['id']]['la']<T('2026-09-01')]; cc=collections.Counter(r['state'] for r in rr); print(lab,len(rr),dict(cc),'f/(f+s) %.3f'%(cc['successful']/max(1,cc['successful']+cc['failed'])))
for k in ('2026-07-24','2026-08-12','2026-09-10','2026-10-12'):
    rr=[r for r in R if r['first']==k]; cc=collections.Counter(r['state'] for r in rr); print('first',k,len(rr),dict(cc),'f/(f+s) %.3f'%(cc['successful']/max(1,cc['successful']+cc['failed'])))
z=[(r['live_pf'] or 0) for r in R if r['state'] in('failed',)]; print('failed: share with 0 live pf %.3f'%(sum(x==0 for x in z)/max(1,len(z))))
zp=[float(r['pledged'] or 0) for r in R if r['state']=='failed']; print('failed: pledged==0 %.3f  (site: 59318/383829=15.5%% of unsuccessful are 0%%)'%(sum(x==0 for x in zp)/max(1,len(zp))))
