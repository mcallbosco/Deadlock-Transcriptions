import json,re,pathlib,collections
root=pathlib.Path('.')
aliases=json.loads((root/'config/deadlock/character-mappings.json').read_text())
name_map={a.lower():k for k,v in aliases.items() for a in [k,*v]}
pattern=re.compile(r'(?<!\w)('+ '|'.join(re.escape(k) for k in sorted(name_map,key=len,reverse=True))+r')(?!\w)',re.I)
def norm(t):
 t=t.lower().replace('’',"'")
 t=pattern.sub(' HERO ',t)
 t=re.sub(r"\b(i'm|im)\b",'i am',t);t=re.sub(r"\b(let's|lets)\b",'let us',t)
 return ' '.join(re.findall(r'[a-z0-9]+',t))
rows=[];groups=collections.defaultdict(list);families=collections.defaultdict(collections.Counter)
for p in sorted((root/'transcripts').rglob('*.json')):
 if '_ping_' not in p.name:continue
 d=json.loads(p.read_text());filename=d['filename'];hero=filename.split('/')[0]
 event=filename.split('_ping_',1)[1].split('.mp3')[0]
 event=pattern.sub('HERO',event.replace('_',' '));event=re.sub(r'\b(old|alt|\d+)\b','',event);event=' '.join(event.split())
 for i,r in enumerate(d['revisions']):
  t=r['text'].strip()
  if not t:continue
  row={'filename':filename,'revisionIndex':i,'text':t,'source':r['source'],'hero':hero,'family':event,'normalized':norm(t),'tags':r.get('tags',[])}
  rows.append(row);groups[norm(t)].append(row);families[event][norm(t)]+=1
out=[]
for n,rr in groups.items():
 heroes=sorted(set(r['hero'] for r in rr));fs=set(r['family'] for r in rr)
 # Shared standard phrasing is not a candidate. Single-hero wording still requires review.
 if len(heroes)>2:continue
 representative=next((r for r in rr if r['source']=='official'),rr[0])
 out.append({'id':len(out),'normalized':n,'heroes':heroes,'text':representative['text'],'source':representative['source'],'families':sorted(fs),'examples': [{'family':f,'common':families[f].most_common(4)} for f in sorted(fs)[:2]],'revisions':rr})
(root/'.scratch/ping-comparison-all.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
# Split compact review catalog into buckets: target-aware calls vs pre/post game vs other pings.
buckets=collections.defaultdict(list)
for g in out:
 f=' '.join(g['families']);bucket='social' if any(x in f for x in ['pre game','post game']) else 'targeted' if 'HERO' in f else 'other'
 buckets[bucket].append({k:v for k,v in g.items() if k!='revisions'}|{'filenames':sorted(set(r['filename'] for r in g['revisions']))[:3]})
for b,gs in buckets.items():(root/f'.scratch/ping-review-{b}.json').write_text(json.dumps(gs,ensure_ascii=False,indent=2))
print('Revisions',len(rows),'normalized groups',len(groups),'candidate groups',len(out),'buckets', {b:len(gs) for b,gs in buckets.items()})
