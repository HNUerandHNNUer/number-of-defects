from pathlib import Path
import requests,json,concurrent.futures
dois=['10.1126/science.1254784','10.1103/PhysRevE.97.042605','10.1039/D0SM00166J','10.1098/rsta.2013.0365','10.1073/pnas.1816733116','10.1038/s41467-022-30128-7','10.1039/D3SM00895A','10.1039/C8SM00282G','10.1103/PhysRevX.5.031003']
def get(doi):
 r={'doi':doi}
 for service,url in [('crossref','https://api.crossref.org/works/'+doi),('openalex','https://api.openalex.org/works/https://doi.org/'+doi)]:
  try:
   resp=requests.get(url,timeout=25);resp.raise_for_status();d=resp.json()
   if service=='crossref':
    d=d['message'];r.update(title=d.get('title'),authors=d.get('author'),journal=d.get('container-title'),published=d.get('published'),volume=d.get('volume'),pages=d.get('page'),crossref_citations=d.get('is-referenced-by-count'))
   else:r['openalex_citations']=d.get('cited_by_count');r['openalex_id']=d.get('id')
  except Exception as e:r[service+'_error']=str(e)
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(get,dois))
Path(__file__).with_name('references_verified.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
for r in rows:print(r['doi'],r.get('title'),r.get('openalex_citations'),r.get('crossref_error'),flush=True)
