import json,collections,pickle,math,datetime as dt
utc=dt.timezone.utc
R=[json.loads(l) for l in open('work/resolved.jsonl')]
ids=set(pickle.load(open('work/aug_ids.pkl','rb')))
fate=pickle.load(open('work/fate.pkl','rb'))
def ci(s,n):
    p=s/n; z=1.96; d=1+z*z/n; c=(p+z*z/(2*n))/d; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d; return round(c-h,3),round(c+h,3)
print('ALL direct fetches',len(R),collections.Counter(r['code'] for r in R),'null state',sum(r['state'] is None for r in R))
ag=collections.Counter((r['file_fin'][0],r['state']) for r in R if r['file_fin']); print('file vs direct',dict(ag))
C=[r for r in R if r['id'] in ids]; c=collections.Counter(r['state'] for r in C); print('AUG cohort sample',len(C),dict(c))
s,f=c['successful'],c['failed']; e=s+f+c['canceled']+c['suspended']
print(' funded/(f+s) %.3f CI %s ; funded/all ended %.3f CI %s'%(s/(s+f),ci(s,s+f),s/e,ci(s,e)))
print(' Brier of constant at this share: %.3f'%((s/(s+f))*(f/(s+f))))
v=[r for r in C if not r['file_fin']]; vc=collections.Counter(r['state'] for r in v); print(' vanished from all files',len(v),dict(vc))
ff=[r for r in C if r['file_fin']]; fc=collections.Counter(r['state'] for r in ff); print(' resolved in files',len(ff),dict(fc),'share %.3f'%(fc['successful']/(fc['successful']+fc['failed'])))
oct_=pickle.load(open('work/raw.json.gz.pkl','rb')); oc=collections.Counter(oct_[r['id']]['state'] for r in C if r['id'] in oct_); print(' same ids in Oct file',dict(oc),'share %.3f'%(oc['successful']/(oc['successful']+oc['failed'])))
zp=[float(r['pledged'] or 0) for r in C if r['state']=='failed']; print(' failed with 0 pledged %.3f (site unsuccessful at 0%%: 15.5%%)'%(sum(x==0 for x in zp)/max(1,len(zp))))
V=[json.loads(l) for l in open('work/val25.jsonl')]; vc=collections.Counter(r['state'] for r in V); print('2025-07-14 live sample',len(V),dict(vc),collections.Counter(r['code'] for r in V))
s,f=vc['successful'],vc['failed']; e=s+f+vc['canceled']+vc['suspended']; print(' funded/all ended %.3f CI %s; funded/(f+s) %.3f'%(s/e,ci(s,e),s/(s+f)),'; site 56.3%')
