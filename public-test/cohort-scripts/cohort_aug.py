import pickle,collections,datetime as dt,statistics as st
utc=dt.timezone.utc; T=lambda s: dt.datetime.fromisoformat(s).replace(tzinfo=utc).timestamp()
L=lambda n: pickle.load(open(f'work/{n}.pkl','rb'))
fate=pickle.load(open('work/fate.pkl','rb'))
J,A,S=L('Kickstarter_2026-07-24T08_26_1'),L('Kickstarter_2026-08-12T08_12_0'),L('Kickstarter_2026-09-10T03_20_4')
# completeness of the 08-12 file: other files' records that must have been live on 08-12
c=collections.Counter()
for nm,D in (('jul',J),('sep',S),('oct',L('raw.json.gz'))):
    for i,r in D.items():
        if r['la'] and r['la']<T('2026-08-10') and r['dl']>T('2026-08-14') and r['state'] not in('submitted','started'):
            c[nm,'n']+=1; a=A.get(i); c[nm,'live_in_aug']+=bool(a and a['state']=='live'); c[nm,'absent']+=a is None
print('08-12 completeness',dict(c))
ids=[i for i,r in A.items() if r['state']=='live' and T('2026-07-14')<=r['la']<T('2026-08-10') and (r['dl']-r['la'])/86400>=29.5]
print('AUG cohort',len(ids),'file-resolved',sum(1 for i in ids if fate[i]['fin']),'first',collections.Counter(fate[i]['first'] for i in ids))
age=[(T(fate[i]['first'])-A[i]['la'])/86400 for i in ids]; print('age first capture median %.1f p90 %.1f max %.1f'%(st.median(age),sorted(age)[int(.9*len(age))],max(age)))
print('latest deadline',dt.datetime.fromtimestamp(max(A[i]['dl'] for i in ids),utc))
ed=collections.Counter()
for i in ids:
    f=fate[i]
    if f['first']!='2026-08-12' : ed['n']+=1; ed['name']+=A[i]['name']!=f['live']['name']; ed['blurb']+=A[i]['blurb']!=f['live']['blurb']
print('edits 07-24 to 08-12 (19 days)',dict(ed))
pickle.dump(sorted(ids),open('work/aug_ids.pkl','wb'))
