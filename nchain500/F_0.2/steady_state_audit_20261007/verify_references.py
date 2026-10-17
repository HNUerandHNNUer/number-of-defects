from pathlib import Path
import json, urllib.request, urllib.parse, concurrent.futures
OUT=Path(__file__).resolve().parent
DOIS=['10.1126/science.1254784','10.1103/PhysRevE.97.042605','10.1039/C8SM02202J','10.1063/1.457480','10.1021/acs.jctc.5b00784','10.1038/nphys4276']
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'LiteratureVerification/1.0'})
    with urllib.request.urlopen(req,timeout=25) as f: return json.load(f)
def work(doi):
    r={'doi':doi,'retrieval_date':'2026-10-07'}
    try:
        m=get('https://api.crossref.org/works/'+urllib.parse.quote(doi,safe=''))['message']
        r['crossref']={k:m.get(k) for k in ['title','author','container-title','published','published-print','published-online','volume','issue','page','article-number','is-referenced-by-count','URL']}
    except Exception as e: r['crossref_error']=str(e)
    try:
        m=get('https://api.openalex.org/works/https://doi.org/'+doi)
        r['openalex']={k:m.get(k) for k in ['id','title','publication_year','cited_by_count']}
    except Exception as e: r['openalex_error']=str(e)
    return r
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: refs=list(pool.map(work,DOIS))
(OUT/'verified_references.json').write_text(json.dumps(refs,ensure_ascii=False,indent=2),encoding='utf-8')
for r in refs:
    c=r.get('crossref',{})
    print(r['doi'],c.get('title'),c.get('published'),c.get('volume'),c.get('page'),r.get('openalex'),r.get('openalex_error'),r.get('crossref_error'))
