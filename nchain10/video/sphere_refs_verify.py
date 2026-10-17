from pathlib import Path
import json, urllib.request, urllib.parse, concurrent.futures
DOIS=['10.1126/science.1254784','10.1103/PhysRevE.97.042605','10.1088/1367-2630/aa89aa','10.1039/D0SM00166J','10.1038/ncomms13483','10.1103/PhysRevX.5.031003','10.1038/s41467-022-30128-7','10.1103/PhysRevE.91.022306']
def fetch(doi):
    result={'doi':doi}
    for name,url in [('crossref','https://api.crossref.org/works/'+urllib.parse.quote(doi,safe='')),('openalex','https://api.openalex.org/works/https://doi.org/'+doi)]:
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'LocalSphereLiteratureAudit/1.0'})
            data=json.load(urllib.request.urlopen(req,timeout=25))
            if name=='crossref':
                m=data['message'];result[name]={'title':m.get('title'),'authors':m.get('author'),'journal':m.get('container-title'),'year':m.get('published'),'volume':m.get('volume'),'issue':m.get('issue'),'pages':m.get('page'),'article_number':m.get('article-number'),'crossref_citations':m.get('is-referenced-by-count')}
            else:result[name]={'id':data['id'],'title':data['display_name'],'cited_by_count':data['cited_by_count'],'publication_date':data['publication_date'],'authors':[a['author']['display_name'] for a in data['authorships']]}
        except Exception as e:result[name]={'error':str(e)}
    return result
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:results=list(ex.map(fetch,DOIS))
out=Path(__file__).resolve().parent/'sphere_analysis';out.mkdir(exist_ok=True)
(out/'verified_references.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
for r in results:print(json.dumps(r,ensure_ascii=True))
