from pathlib import Path
import json,re,hashlib
import pandas as pd
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
refs=json.loads((OUT/'references_verified.json').read_text(encoding='utf-8'));lines=[]
fallback={2:'042605',4:'20130365',6:'2579',9:'031003'}
for i,r in enumerate(refs,1):
 authors='; '.join(' '.join([a.get('given',''),a.get('family','')]).strip() for a in r['authors']);year=r['published']['date-parts'][0][0];pages=r.get('pages') or fallback.get(i,'')
 lines.append(f"**R{i}.** {authors}. **{r['title'][0]}**. *{r['journal'][0]}* **{r.get('volume','')}**, {pages} ({year}). [DOI](https://doi.org/{r['doi']}). OpenAlex引用数：{r.get('openalex_citations','未取得')}。")
p=OUT/'report_zh.md';s=p.read_text(encoding='utf-8');s=s.split('<!-- VERIFIED_REFERENCES -->')[0];p.write_text(s+'<!-- VERIFIED_REFERENCES -->\n\n'+'\n\n'.join(lines)+'\n',encoding='utf-8')
prov=[]
for branch,folder in [('direct',ROOT/'nchain10/F_2_cpu2'),('gpu2',ROOT/'nchain10/gpu2/F_2')]:
 text=(folder/'log.lammps').read_text(errors='replace');prov.append(dict(branch=branch,path=str(folder),polymer_sha256=hashlib.sha256((folder/'polymer.data').read_bytes()).hexdigest(),expanded_fixes=[x for x in text.splitlines() if x.startswith('fix') and 'bd/sphere' in x and '$' not in x],lammps_header=text.splitlines()[0]))
(OUT/'F2_branch_provenance.json').write_text(json.dumps(prov,indent=2),encoding='utf-8')
coverage=pd.read_csv(OUT/'count_coverage.csv');inventory=json.loads((OUT/'video_inventory.json').read_text());meta=dict(count_trajectories=len(coverage),count_records=int(coverage.frames.sum()),spatial_trajectories=155,spatial_frames=9007,full_current_small_sphere_frames=6006,same_force_comparison_frames=1002,video_files=len(inventory),spread_video_frames=sum(sum(q['read'] for q in r['samples']) for r in inventory),contiguous_video_frames=80)
(OUT/'analysis_inventory.json').write_text(json.dumps(meta,indent=2));print(meta)
# Recompute a small-sample scale sensitivity diagnostic explicitly, rather than hiding it.
a=pd.read_csv(OUT/'smoothing_frames.csv');b=pd.read_csv(ROOT/'mips_analysis_20261014/all_sampled_frames.csv');c=a.merge(b[['n','F','step','cv3']],on=['n','F','step']);rows=[]
for (n,F,h),d in c.groupby(['n','F','h']):rows.append(dict(n=n,F=F,h=h,frames=len(d),corr_count_cv=d[['Nplus','cv3']].corr().iloc[0,1]))
pd.DataFrame(rows).to_csv(OUT/'smoothing_correlation.csv',index=False)
