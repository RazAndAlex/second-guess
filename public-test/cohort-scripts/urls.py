# Pull project URLs for live-captured ids in window; save a seeded sample of vanished + controls.
import gzip,json,pickle,random,sys,datetime as dt
utc=dt.timezone.utc; T=lambda s: dt.datetime.fromisoformat(s).replace(tzinfo=utc).timestamp()
fate=pickle.load(open('work/fate.pkl','rb'))
want={i for i,f in fate.items() if f['la']>=T('2026-06-15')}
urls={}
for p in sys.argv[1:]:
    for line in gzip.open(p,'rt',encoding='utf-8'):
        if '"state":"live"' not in line: continue
        d=json.loads(line)['data']
        if d['id'] in want: urls[d['id']]=d['urls']['web']['project']
pickle.dump(urls,open('work/urls.pkl','wb')); print(len(urls),len(want))
