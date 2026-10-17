# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd,json,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).parent;p=root/'progress_20261017_1800'
a=pd.concat([pd.read_csv(root/('progress_20261017_'+x)/'fixed_frames.csv') for x in ['1535','1700','1800']],ignore_index=True).drop_duplicates(['name','step','h'],keep='last')
a=a[(a.step<=100000000)&(a.step%10000000==0)].copy();a['n']=a.name.str.extract(r'n(\d+)').astype(int);a['F']=a.name.str.extract(r'_F([\d.]+)').astype(float);a['seed']=a.name.str.extract(r'_r(\d+)').astype(int)
assert (a.Nplus-a.Nminus==4).all() and a.composite.eq(0).all()
a.to_csv(p/'matched_frames.csv',index=False)
s=a[a.step>=50000000].groupby(['n','F','seed','h'])[['Nminus','P4','pair_density']].mean().reset_index();s.to_csv(p/'seed_means.csv',index=False)
g=s.groupby(['n','F','h']).agg(Nminus=('Nminus','mean'),SD=('Nminus','std'),P4=('P4','mean'),rho=('pair_density','mean'),seeds=('seed','count'));g.to_csv(p/'summary.csv');print(g)
fig,axes=plt.subplots(2,2,figsize=(10,7))
for i,n in enumerate([200,350]):
 for j,h in enumerate([1.5,3]):
  for F,z in a[(a.n==n)&(a.h==h)].groupby('F'):
   u=z.groupby('step').Nminus.mean();axes[i,j].plot(u.index/1e8,u,label='F=%g'%F)
  axes[i,j].set(xlabel='Steps / 1e8',ylabel='N minus',title='n=%d, h=%g'%(n,h));axes[i,j].legend()
fig.tight_layout();fig.savefig(p/'matched_evolution.png',dpi=250)
a[a.P4.eq(1)].to_csv(p/'four_defect_geometry.csv',index=False)
(p/'validation.json').write_text(json.dumps(dict(rows=len(a),topological_check=True,common_stride=10000000,window=[50000000,100000000],seeds_per_condition=2),indent=2))
(p/'report_zh.md').write_text('# 两尺寸首亿步双种子匹配分析\n\n统一抽样间隔1000万步，窗口5000万至1亿步；每组两个种子，但同尺寸共用初始几何。均值和SD先在每个种子内取时间均值再统计，非独立帧标准误。\n\n'+g.to_string()+'\n\n净荷检查通过，无复合荷。四缺陷条件帧及配对角保存于four_defect_geometry.csv，稀少条件帧不用于确定稳定配对态。与此前单种子初步结论比较，须优先看F=.1/.3的种子间分散程度，不把单轨迹排序当稳定最优活性；跨尺寸同窗口仍有初始缺陷密度差异，不能推断纯曲率因果。未推断产生湮灭率或稳态。\n',encoding='utf-8')

