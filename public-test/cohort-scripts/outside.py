import re,html,pickle,collections,datetime as dt
utc=dt.timezone.utc; T=lambda s: dt.datetime.fromisoformat(s).replace(tzinfo=utc).timestamp()
tab={}
for ts,sn in (('20250715','2025-07-13'),('20260121','2026-01-21')):
    s=open(f'work/web/st_{ts}.html',encoding='utf8',errors='ignore').read()
    t=html.unescape(re.sub(r'<(script|style).*?</\1>','',s,flags=re.S));t=re.sub(r'<[^>]+>',' ',t);t=re.sub(r'\s+',' ',t)
    j=t.find('Unsuccessfully Funded Projects'); k=t.find(' All ',j); row=t[k:k+90]; print(sn,'UNSUCC header+All:',t[j+200:k+90])
    h=t.find('Successfully Funded Projects Category',0); 
    m=re.search(r'Successfully Funded Projects[^A]*?Category[^A]*?All ([\d,]+)',t); print(' succ row', t[t.find('Category Successfully')-5:t.find('Category Successfully')+200] if 'Category Successfully' in t else m and m.group(0)[:200])
    m=re.search(r'All ([\d,]+) \$ [\d.]+ B',t); tab[sn]=dict(launched=int(m.group(1).replace(',','')))
    lv=re.search(r'All [\d,]+ \$ [\d.]+ B \$ [\d.]+ B \$ [\d.]+ [MB] \$ [\d.]+ [MB] ([\d,]+) ([\d.]+) %',t); tab[sn]['live']=int(lv.group(1).replace(',','')); tab[sn]['rate']=lv.group(2)
    sf=re.search(r'([\d,]+) Successfully funded projects',t); tab[sn]['succ']=int(sf.group(1).replace(',',''))
print(tab)
a,b=tab['2025-07-13'],tab['2026-01-21']
dl,dlive,ds=b['launched']-a['launched'],b['live']-a['live'],b['succ']-a['succ']
ended=dl-dlive; print('site delta launched',dl,'live',dlive,'succ',ds,'ended incl canceled',ended,'funded share of all ended %.3f'%(ds/ended))
D=pickle.load(open('work/Kickstarter_2026-06-11T03_20_1.pkl','rb'))
O=pickle.load(open('work/raw.json.gz.pkl','rb'))
A,B=T('2025-07-13'),T('2026-01-21')
for nm,X in (('June file',D),('Oct file',O)):
    c=collections.Counter(r['state'] for r in X.values() if r['dl'] and A<=r['dl']<B and r['state'] in('successful','failed','canceled','suspended'))
    n=sum(c.values()); print(nm,'deadline in delta window',dict(c),'s/(s+f) %.3f'%(c['successful']/(c['successful']+c['failed'])),'s/all %.3f'%(c['successful']/n),'cover succ %.3f unsucc %.3f'%(c['successful']/ds,(n-c['successful'])/(ended-ds)))
# stock coverage
J=pickle.load(open('work/Kickstarter_2025-07-14T06_25_2.pkl','rb')); c=collections.Counter(r['state'] for r in J.values())
uns=c['failed']+c['canceled']+c['suspended']; print('stock 2025-07-14 file: succ',c['successful'],'of',a['succ'],'%.3f'%(c['successful']/a['succ']),'unsuccessful',uns,'of',a['launched']-a['live']-a['succ'],'%.3f'%(uns/(a['launched']-a['live']-a['succ'])),'live',c['live'],'of',a['live'],'%.3f'%(c['live']/a['live']))
