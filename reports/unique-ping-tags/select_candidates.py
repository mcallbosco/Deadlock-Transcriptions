import json,pathlib,collections
sections={
'relationship, nickname, joke, or bespoke warning in a targeted ping': '''85 87 93 237 241 280 281 303 349 372 374 375 389 643 1216 1234 1288 1290 1291 1366 1367 1369 1370 1371 1381 1383 1444 1445 1448 1463 1464 1977 1989 2052 2180 2194 2218 2234 2241 2257 2656 3014 3019 3430 3431 3434 3435 3466 3518 3589 3598 3646 3896 4035 4041 4056 4112 4779 5018 5019 5040 5047 5112 5115 5219 5645 6096 6113 6114 6136 6190 6220 6308 6338 6339 6416''',
'expressive ability or response wording beyond a readiness/name substitution': '''22 23 25 26 28 108 109 112 113 114 335 337 338 417 418 419 422 423 584 587 588 766 769 770 880 1138 1141 1144 1145 1146 1147 1197 1199 1200 1203 1205 1206 1241 1243 1244 1388 1389 1392 1393 1394 1395 1431 1432 1471 1472 1475 1477 1694 1697 1698 1699 1926 1995 2000 2287 2293 2295 2328 2600 2602 2603 2662 2670 2841 3073 3079 3080 3357 3359 3360 3361 3442 3446 3447 3449 3463 3507 3600 3615 3625 3627 3632 3634 3636 3637 3639 3641 3643 3653 3661 3665 3666 3668 4118 4121 4123 4153 4156 4157 4158 4710 4712 4714 4789 4791 4795 4797 4971 4974 5022 5126 5129 5444 5446 5921 5927 5933 6060 6062 6064 6145 6152 6153 6154 6183 6189 6259 6263 6264 6266 6349 6433 6438 6455 6639 6650 6652 6654 6656''',
'coherent historical wording of an independently confirmed bespoke ping': '''6340'''
}
# Plain action descriptions and companion readiness alone do not qualify.
for reason in sections:
 sections[reason]=' '.join(x for x in sections[reason].split() if int(x) not in {22,23,112,114,338,4712,4714,4153,3357,3359,3361,6259,6263,6349})
groups=json.load(open('.scratch/ping-comparison-all.json'));byid={g['id']:g for g in groups}
rows=[];decisions=[]
for reason,ids in sections.items():
 for i in map(int,ids.split()):
  g=byid[i]
  # Ability use, readiness, cooldown, and targeted ability requests are excluded.
  if any("ability" in f or f.startswith(("ult ready", "stun ")) or f == "with swap" for f in g["families"]): continue
  assert not any(f in {'pre game','post game'} for f in g['families']), g
  decisions.append({k:g[k] for k in ['id','text','source','normalized','heroes','families','examples']}|{'reason':reason})
  for r in g['revisions']:
   rows.append({'filename':r['filename'],'revisionIndex':r['revisionIndex'],'text':r['text'],'tagId':'unique-pings','reason':reason,'comparisonGroup':i})
assert len({(r['filename'],r['revisionIndex']) for r in rows})==len(rows)
pathlib.Path('.scratch/unique-candidates.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False)+'\n')
pathlib.Path('.scratch/unique-decisions.json').write_text(json.dumps(decisions,indent=2,ensure_ascii=False)+'\n')
pathlib.Path('.scratch/unique-defs.json').write_text('[{"id":"unique-pings","label":"Unique Pings"}]\n')
for d in decisions:
 if d['reason'].startswith('expressive'): print(d['id'],d['text'])
print('Selected groups',len(decisions),'candidate revisions',len(rows))
