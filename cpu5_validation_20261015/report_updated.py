# -*- coding: utf-8 -*-
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent/'partial_analysis_20261015'
r=pd.read_csv(P/'run_summary.csv');df=pd.read_csv(P/'frames.csv');sc=pd.read_csv(P/'scales.csv');audit=json.loads((P/'audit.json').read_text())
matched=r[(r.window=='matched30_60')&(r.nchain>10)].copy();late=r[r.window=='late50'].copy()
def group(d,by):
 return d.groupby(by).agg(seeds=('name','count'),Nplus=('Nplus','mean'),Nplus_sd=('Nplus','std'),P=('P','mean'),P_sd=('P','std'),S=('S','mean'),C=('C','mean'),four=('four','mean'),pair_density=('pair_density','mean')).reset_index()
g=group(matched,['nchain','F']);g.to_csv(P/'matched_group_summary.csv',index=False)
b=group(late[late.nchain==10],['branch']);b.to_csv(P/'branch_group_summary.csv',index=False)
per_scale=sc[sc.step.between(30000000,60000000)].groupby(['name','nchain','F','h']).Nplus.mean().reset_index();scale=per_scale.groupby(['nchain','F','h']).Nplus.mean().reset_index();scale.to_csv(P/'matched_scale_summary.csv',index=False)
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(1,2,figsize=(10,4))
for name,z in df[df.nchain==10].groupby('name'):
 branch=z.branch.iloc[0];rep=z.replicate.iloc[0];color='#c74242' if branch=='counter' else '#168d9c'
 for ax,key in zip(axes,['P','S']):ax.plot(z.step/1e8,z[key],color=color,alpha=.6,lw=.8,label=branch if rep==1 else None)
for ax,label in zip(axes,['Local polarity P','Local nematic order S']):ax.set_xlabel('Continuation steps / 1e8');ax.set_ylabel(label);ax.grid(alpha=.2)
axes[0].legend();fig.suptitle('Same CPU implementation: 3 noise seeds per prepared n=10, F=2 state');fig.tight_layout(rect=(0,0,1,.92));fig.savefig(P/'01_branch_persistence.png',dpi=170);plt.close(fig)
fig,axes=plt.subplots(1,3,figsize=(12.5,4))
for F,color in [(2,'#2866b3'),(5,'#db7c2d')]:
 for n,rows in matched[matched.F==F].groupby('nchain'):
  for ax,key in zip(axes,['Nplus','S','C']):
   ax.scatter(n+(rows.replicate-2)*1.1+(-1 if F==2 else 1),rows[key],color=color,s=28)
 for ax,key in zip(axes,['Nplus','S','C']):
  gg=g[g.F==F];ax.plot(gg.nchain,gg[key],color=color,label='F=%d'%F)
for ax,y in zip(axes,['Positive defects N+','Local nematic order S','Global tangent circulation C']):
 ax.set_xticks([30,50,100]);ax.set_xlabel('Chain count');ax.set_ylabel(y);ax.grid(alpha=.2)
axes[0].legend();fig.suptitle('Matched production window: 30-60 million steps; 3 seeds per condition\nn=100 is interim; F=5 replicas 1/2 have FENE warnings',fontsize=11);fig.tight_layout(rect=(0,0,1,.89));fig.savefig(P/'04_updated_matched_sizes.png',dpi=170);plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(10,4))
for ax,F in zip(axes,[2,5]):
 for n,rows in scale[(scale.F==F)&(scale.nchain>10)].groupby('nchain'):ax.plot(rows.h,rows.Nplus,'o-',label='n=%d'%n)
 ax.set_title('F=%d'%F);ax.set_xlabel('Smoothing length h');ax.set_ylabel('Mean N+, same sampled times');ax.legend();ax.grid(alpha=.2)
fig.suptitle('Spatial-scale sensitivity: matched 30-60 million-step window');fig.tight_layout(rect=(0,0,1,.92));fig.savefig(P/'05_updated_scales.png',dpi=170);plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(10,4))
for F,color in [(2,'#2866b3'),(5,'#db7c2d')]:
 for rep,gg in df[(df.nchain==100)&(df.F==F)].groupby('replicate'):
  for ax,key in zip(axes,['Nplus','P']):ax.plot(gg.step/1e6,gg[key].rolling(9,center=True,min_periods=1).mean(),color=color,alpha=.75,lw=1,ls=['-','--',':'][rep-1],label='F%d r%d'%(F,rep))
for ax,key in zip(axes,['Positive defects N+','Local polarity P']):ax.set_xlabel('Production steps / million');ax.set_ylabel(key);ax.grid(alpha=.2)
axes[0].legend(ncol=2,fontsize=8);fig.suptitle('n=100 interim trajectories: centered 9-frame means (visual smoothing only)');fig.tight_layout(rect=(0,0,1,.92));fig.savefig(P/'06_n100_interim.png',dpi=170);plt.close(fig)
def table(d,keys):
 out='| '+' | '.join(keys)+' |\n|'+'|'.join(['---']*len(keys))+'|\n'
 for _,row in d.iterrows():out+='| '+' | '.join('%.3f'%row[k] if isinstance(row[k],(float,np.floating)) else str(row[k]) for k in keys)+' |\n'
 return out
text='''# CPU5 更新验证：18条完整轨迹与6条共同时间窗快照

本报告替代第一轮16组报告。2026-10-15约21:40提取：nchain10/30/50共18组完整1亿生产步；nchain100六组当时已推进约6677万—9845万生产步，本次仅冻结其共同前6000万步。提取之后任务仍继续运行，报告统计不随实时日志自动漂移。未修改模拟。〔来源：audit.json、coverage_updated.csv。〕

**最可靠的结果仍是：同一CPU后端下，两种小球面运动分支在各3个新噪声种子中持续分离。新增nchain50第三种子及nchain100快照进一步支持：强活性促进缺陷增殖，但整体环流不应预设为随尺寸单调下降。** 下文分别报告完整轨迹与统一时间窗，不把尚未结束的nchain100称为稳态。〔来源：run_summary.csv、matched_group_summary.csv。〕

## 1. 小球面：相似缺陷纹理，不同极性组织

全部新增1亿步轨迹的后半程，独立种子均值如下。sd为三个种子均值的样本标准差，不是把相关时间帧当独立样本的误差。

'''+table(b,['branch','seeds','P','P_sd','S','Nplus','Nplus_sd','four','C'])+'''
反向初态的逐链切向分类在全部采样构型中均为6对4，同向初态为10对0；未观察到持续分支切换。四缺陷条件下，两类对内夹角都约40°。这支持有限观察时间内的初态记忆和持久运动分支，不能单凭两种已选初态证明严格多稳态或无限驻留时间。〔来源：branch_*_metrics.csv，采样间隔20万步。〕

材料实际位移也支持差异：1万步位移窗口内，反向链平均数约3.967与0.066；短时间噪声导致少量瞬时反号。整体旋转解释比例分别约10.3%与48.0%。这些数值不能直接和旧报告10万步位移窗口的18.8%/96.2%比较；两分支之间比较采用相同1万步窗口。〔来源：frames.csv中lag_steps=10000。〕

![两分支的持续差异](01_branch_persistence.png)

研究重点可以放在“缺陷纹理与极性运动的对应关系、初态记忆以及分支随尺寸变化的稳定性”。球面极性丝状体已有复杂运动图案，不能将同向/反向流动本身宣称首创。〔参考：Chiao-Peng Hsu, Alfredo Sciortino, Yu Alice de la Trobe, Andreas R. Bausch. *Activity-induced polar patterns of filaments gliding on a sphere*. Nature Communications 13,2579 (2022). [DOI](https://doi.org/10.1038/s41467-022-30128-7)。〕

## 2. 加入nchain100：统一3000万—6000万生产步

每个条件均为3个种子、每种子61个等间隔构型。nchain100的F5种子1/2有FENE警告，下表含它们，仅作带数值风险标记的阶段性统计。nchain30/50的完整后半程结果另见run_summary.csv。

'''+table(g,['nchain','F','seeds','Nplus','Nplus_sd','P','S','C','four','pair_density'])+'''
![相同时间窗的尺寸比较](04_updated_matched_sizes.png)

F=5时正缺陷数随30→50→100链明显增加，而F=2下增长弱得多。局部S仍较高，因此缺陷增多不等于体系完全失去向列序。环流C则依赖种子和活性，不支持把“所有条件下C随半径单调下降”作为预设结论；nchain50/F2已有高环流与低环流种子并存。〔来源：matched_group_summary.csv、逐种子run_summary.csv。〕

## 3. 缺陷的空间尺度

以下三个尺度均使用每组3000万、3500万、…、6000万步的同7个构型。h是高斯平滑长度，h=0为原始链切向场；它们定义了不同解析尺度，不能把滤掉的所有缺陷直接称为误检。

'''+table(scale[scale.nchain>10].pivot_table(index=['nchain','F'],columns='h',values='Nplus').reset_index().rename(columns={0.0:'h0',1.5:'h1.5',3.0:'h3'}),['nchain','F','h0','h1.5','h3'])+'''
![统一时间窗的尺度对照](05_updated_scales.png)

短尺度缺陷数对活性和尺寸的响应较强，粗尺度响应需另行报告；需要结合核轨迹的持续性，才能讨论“缺陷增殖阈值”或长寿命介观缺陷。受限活性向列中，缺陷增殖与流动失序也可能发生在不同尺度或参数处。〔参考：Achini Opathalage, Michael M. Norton, Michael P. N. Juniper, Blake Langeslay, S. Ali Aghvami, Seth Fraden, Zvonimir Dogic. *Self-organized dynamics and the transition to turbulence of confined active nematics*. PNAS 116,4788–4797 (2019). [DOI](https://doi.org/10.1073/pnas.1816733116)。〕

## 4. FENE警告：修正此前过于宽松的判断

**键长小于1.5不代表未发生数值处理。** 服务器bond_fene.cpp的代码为：rlogarg=1-r²/R0²；若rlogarg<0.1则警告并将rlogarg设为0.1后计算力。R0=1.5对应阈值1.5√0.9≈1.4230。此前用“小于1.5”解释为无影响并不充分。nchain100/F5种子1有14条、种子2有1条警告，种子3在快照时无此警告。它们没有被当作已通过数值可靠性验证的最终样本。〔来源：服务器/home/user/soft/lammps-22Jul2025/src/MOLECULE/bond_fene.cpp第80—98行与audit.json。〕

仅看无警告的F5种子3，相同窗口平均N+也明显高于F2，故“强活性下缺陷较多”并非完全由两个警告样本制造；但单个干净种子不能给出可靠误差，也不能证明另两条截断没有影响。最终结论需检查警告附近构型，并考虑短步长收敛对照。本次未新增或修改模拟参数。〔来源：下面的逐种子表。〕

'''+table(matched[matched.nchain==100],['F','replicate','Nplus','P','S','C'])+'''
![nchain100尚在演化](06_n100_interim.png)

## 5. 验证边界与后续

本轮共重算6144个主构型，均通过总拓扑荷+2检查；这证明离散场拓扑一致，不认证每个缺陷核的物理寿命。两种小球面分支的持久性是当前最稳健的结果；nchain100还需等待完整观察窗，再核对后半程是否继续漂移。缺陷产生、湮灭与寿命尚未从密集窗口完成收敛验证，当前不能用ΔN代替事件率。〔来源：validation.json。〕

输出：frames.csv、run_summary.csv、matched_group_summary.csv、matched_scale_summary.csv、branch_group_summary.csv、audit.json、coverage_updated.csv。脚本位于上一级extract_completed.py、extract_interim.py、analyze_partial.py、report_updated.py。此前report_zh.md只代表16组的早期结果，本报告优先。
'''
(P/'report_updated_zh.md').write_text(text,encoding='utf-8')
pd.DataFrame([dict(name=j['name'],nchain=j['nchain'],F=j['F'],replicate=j['replicate'],last_step=j['last_step'],status='interim' if j['nchain']==100 else 'complete',snapshot_time=j['snapshot_time']) for j in audit]).to_csv(P/'coverage_updated.csv',index=False)
print(g.to_string(index=False));print(scale[scale.nchain>10].to_string(index=False))
