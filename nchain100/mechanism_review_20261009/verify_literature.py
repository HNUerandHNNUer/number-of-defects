from pathlib import Path
import requests,json,concurrent.futures
OUT=Path(__file__).resolve().parent
DOIS=['10.1126/science.1254784','10.1103/PhysRevE.97.042605','10.1038/s41598-017-05612-6','10.1038/ncomms13483','10.1039/C8SM02202J','10.1038/s41467-025-62694-x','10.1103/PhysRevLett.110.228101','10.1103/PhysRevX.5.031003','10.1038/s41467-018-05666-8','10.1063/1.436761','10.1063/1.457480','10.1103/PhysRevE.102.012607']
def fetch(doi):
    record={'doi':doi,'retrieved':'2026-10-09'}
    try:
        r=requests.get('https://api.crossref.org/works/'+doi,timeout=30);r.raise_for_status(); m=r.json()['message']
        record['crossref']={k:m.get(k) for k in ['title','author','container-title','volume','issue','page','article-number','published','published-print','published-online','is-referenced-by-count','URL']}
    except Exception as e: record['crossref_error']=str(e)
    try:
        r=requests.get('https://api.openalex.org/works/https://doi.org/'+doi,timeout=25);r.raise_for_status();m=r.json()
        record['openalex']={k:m.get(k) for k in ['id','title','publication_year','cited_by_count','ids','primary_location']}
    except Exception as e:record['openalex_error']=str(e)
    return record
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex: records=list(ex.map(fetch,DOIS))
(OUT/'verified_literature.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
for r in records:
    c=r.get('crossref',{});o=r.get('openalex',{})
    print(r['doi'],c.get('title'),c.get('container-title'),c.get('published'),c.get('volume'),c.get('page'),c.get('article-number'),'Crossref citations',c.get('is-referenced-by-count'),'OpenAlex',o.get('cited_by_count'),r.get('crossref_error',''),flush=True)
