from pathlib import Path
import json,csv
import win32com.client
ROOT=Path(__file__).resolve().parent
project=ROOT.parent.parent/'UNTITLED.opju'
app=win32com.client.DispatchEx('Origin.Application')
try:
    app.Visible=0
    assert app.Load(str(project),True)
    print('books',app.WorksheetPages.Count,flush=True)
    books=[]
    for i in range(app.WorksheetPages.Count):
        page=app.WorksheetPages(i)
        record={'name':page.Name,'sheets':[]}
        print('book',page.Name,'layers',page.Layers.Count,flush=True)
        for j in range(page.Layers.Count):
            sheet=page.Layers(j)
            name='['+page.Name+']'+sheet.Name
            values=app.GetWorksheet(name,0,0,-1,-1)
            print('sheet',name,'rows',len(values) if values else 0,flush=True)
            item={'name':sheet.Name,'data':values}
            record['sheets'].append(item)
            with (ROOT/(page.Name+'_'+sheet.Name+'.csv')).open('w',newline='',encoding='utf-8-sig') as f:
                csv.writer(f).writerows(values)
        books.append(record)
    (ROOT/'origin_data.json').write_text(json.dumps(books,ensure_ascii=False,indent=2),encoding='utf-8')
finally:
    app.Exit()
