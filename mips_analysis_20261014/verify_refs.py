from pathlib import Path
import requests,json,concurrent.futures
DOIS=['10.1146/annurev-conmatphys-031214-014710','10.1103/PhysRevLett.110.055701','10.1016/j.crhy.2015.05.001','10.1103/PhysRevLett.96.180602','10.1103/PhysRevLett.113.038302','10.1038/ncomms4013','10.1103/PhysRevE.97.042605','10.1039/D3SM00895A']
def fetch(doi):
 r={'doi':doi}
 for server,url in [('crossref','https://api.crossref.org/works/'+doi),('openalex','https://api.openalex.org/works/https://doi.org/'+doi)]:
  try:
   q=requests.get(url,timeout=30);q.raise_for_status();d=q.json()
   if server=='crossref':
    d=d['message'];r.update(title=d.get('title'),authors=d.get('author'),journal=d.get('container-title'),published=d.get('published'),volume=d.get('volume'),pages=d.get('page'),article_number=d.get('article-number'),crossref_citations=d.get('is-referenced-by-count'))
   else:r['openalex_citations']=d.get('cited_by_count');r['openalex_id']=d.get('id')
  except Exception as e:r[server+'_error']=str(e)
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:result=list(pool.map(fetch,DOIS))
Path(__file__).with_name('references_verified.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
for r in result:print(r['doi'],r.get('title'),r.get('openalex_citations'),r.get('crossref_error'),r.get('openalex_error'))
