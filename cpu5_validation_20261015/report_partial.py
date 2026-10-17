# -*- coding: utf-8 -*-
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent/'partial_analysis_20261015'
df=pd.read_csv(P/'frames.csv');r=pd.read_csv(P/'run_summary.csv');late=r[r.window=='late50'];sc=pd.read_csv(P/'scales.csv');audit=json.loads((P/'audit.json').read_text())
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
colors={'counter':'#c74242','co':'#168d9c'}
fig,axes=plt.subplots(2,2,figsize=(11,7))
for name,g in df[df.nchain==10].groupby('name'):
 b=g.branch.iloc[0];rep=g.replicate.iloc[0];color=colors[b]
 axes[0,0].plot(g.step/1e8,g.P,color=color,alpha=.65,lw=.7,label=b if rep==1 else None)
 axes[0,1].plot(g.step/1e8,g.S,color=color,alpha=.6,lw=.7)
 axes[1,0].plot(g.step/1e8,g.opposite_tangent,color=color,alpha=.6,lw=.8)
 rr=late[late.name==name].iloc[0];x=(0 if b=='counter' else 1)+(rep-2)*.08
 axes[1,1].scatter(x,rr.rotation_fraction*100,color=color,s=50)
axes[0,0].legend();axes[0,0].set_ylabel('Local polarity P');axes[0,1].set_ylabel('Local nematic order S');axes[1,0].set_ylabel('Opposite tangent chains / 10')
for ax in axes.flat:
 ax.grid(alpha=.2)
for ax in [axes[0,0],axes[0,1],axes[1,0]]:ax.set_xlabel('Continuation steps / 1e8')
axes[1,1].set_xticks([0,1]);axes[1,1].set_xticklabels(['counter-prepared','co-prepared']);axes[1,1].set_ylabel('Rotation-explained displacement (%)');axes[1,1].set_title('Lag = 10,000 steps; late-half seed means')
fig.suptitle('Same CPU implementation: 3 noise seeds per prepared n=10, F=2 state');fig.tight_layout(rect=(0,0,1,.95));fig.savefig(P/'01_branch_persistence.png',dpi=170);plt.close(fig)

fig,axes=plt.subplots(1,3,figsize=(12,3.8))
size=late[late.nchain>10]
for F,col in [(2,'#2866b3'),(5,'#de8634')]:
 for n,g in size[size.F==F].groupby('nchain'):
  for ax,key in zip(axes,['Nplus','four','C']):
   x=n+(-1 if F==2 else 1);ax.scatter(x+(g.replicate-2)*.3,g[key],color=col,s=28)
   ax.scatter(x,g[key].mean(),marker='_',s=200,color='black')
 for ax in axes:ax.scatter([],[],color=col,label='F=%d'%F)
for ax,key in zip(axes,['Mean positive defects','Four-defect fraction','Global tangent circulation C']):
 ax.set_xlabel('Chain count');ax.set_xticks([30,50]);ax.set_ylabel(key);ax.grid(alpha=.2)
axes[0].legend();fig.suptitle('Late half: dots are independent seed means; n=50 has only 2/3 seeds');fig.tight_layout();fig.savefig(P/'02_size_activity.png',dpi=170);plt.close(fig)

fig,ax=plt.subplots(figsize=(7,4.5));cs=sc[sc.step>=50000000]
for (n,F),g in cs.groupby(['nchain','F']):
 means=g.groupby(['name','h']).Nplus.mean().reset_index().groupby('h').Nplus.mean()
 ax.plot(means.index,means.values,'o-',label='n=%d F=%d'%(n,F))
ax.set_xlabel('Gaussian smoothing length h');ax.set_ylabel('Positive defects, late half');ax.legend();ax.grid(alpha=.2);ax.set_title('Same 11 late-half frames per run at all three scales');fig.tight_layout();fig.savefig(P/'03_scale_dependence.png',dpi=170);plt.close(fig)

def table(d,keys):
 out='| '+' | '.join(keys)+' |\n|'+'|'.join(['---']*len(keys))+'|\n'
 for _,row in d.iterrows():out+='| '+' | '.join(('%.3f'%row[k] if isinstance(row[k],(float,np.floating)) else str(row[k])) for k in keys)+' |\n'
 return out
gs=late.groupby(['nchain','F','branch']).agg(seeds=('name','count'),P=('P','mean'),P_seed_sd=('P','std'),S=('S','mean'),Nplus=('Nplus','mean'),Nplus_seed_sd=('Nplus','std'),four=('four','mean'),C=('C','mean'),opposite_motion=('opposite_motion','mean'),rotation_fraction=('rotation_fraction','mean')).reset_index();gs.to_csv(P/'group_summary.csv',index=False)
scope=pd.DataFrame([dict(name=j['name'],nchain=j['nchain'],F=j['F'],sampled_frames=j['sampled_frames'],last_step=j['last_step'],snapshot_time=j['snapshot_time']) for j in audit]);scope.to_csv(P/'coverage.csv',index=False)
text='''# CPU5 第一轮已完成任务后处理

2026-10-15。结论适用于提取时已完成的16组，不把未完成nchain100混入。

## 结论

**可以分析，而且最初提出的“小球面缺陷纹理与极性运动解耦”已经获得同一CPU后端、每种初态3个新噪声种子的支持。** 在新增1亿步观察窗内，两种初态的P仍明显分离，采样构型的逐链取向分别保持6对4与10对0。这里验证的是两种既有晚期构型的持久性与噪声重复性，尚不是对所有初态、无限时间或严格吸引域的多稳态证明。〔来源：frames.csv、run_summary.csv。〕

## 数据与核验

完整结束的16组包括nchain10的6组、nchain30的6组、nchain50的4组；nchain50第三种子与nchain100仍在运行。每组须有final.bin、完成标记及日志VALIDATION_RUN_COMPLETED，且无ERROR。16组没有FENE键过长警告。存在“No fixes with time integration”通用警告：自定义bd/sphere通过INITIAL_INTEGRATE/FINAL_INTEGRATE回调推进坐标，但没有设置用于该通用检查的time_integrate标志；实际轨迹位移非零，不能按该警告字面判断原子未运动。本次没有改变积分实现。〔来源：audit.json、冻结的fix源码、轨迹。〕

重算5016个主采样构型：nchain10每20万步一帧，每帧另读取其前1万步构型用于实际位移；其余尺寸每50万步一帧。全部离散拓扑净荷为+2。额外在每500万步构型对h=0、1.5、3进行相同尺度扫描，共1008次识别。统计窗口统一为新增轨迹的后5000万步；独立种子先各自取时间均值，再汇总，不能把时间帧当独立重复。〔来源：validation.json、scales.csv、coverage.csv。〕

## 1. 两分支复现

'''
text+=table(gs[gs.nchain==10],['branch','seeds','P','P_seed_sd','S','Nplus','C','opposite_motion','rotation_fraction'])
text+='''
P的种子均值范围：反向组0.58225–0.58339，同向组0.92156–0.92397。向列序分别约0.810与0.820，正缺陷数仍约4。所有6组在501个采样构型中均保持各自逐链取向分类；这不排除采样间隔内很短暂的波动，但没有看到持续状态转换。四缺陷条件下对内夹角都约40°，进一步说明区别不是简单“缺陷图案完全不同”。〔来源：各branch_*_metrics.csv。〕

实际位移在1万步时间尺度上仍支持反向组约4条、同向组接近0条反向运动，但短时热噪声造成少量瞬时反号。整体旋转解释比例约10.3%与48.0%；**不能将它与此前10万步位移估计的18.8%/96.2%直接对比**，时间窗口缩短后噪声贡献增大。两组在同一时间窗口比较的差异仍清楚。〔来源：run_summary.csv，lag_steps=10000。〕

![两分支](01_branch_persistence.png)

这一结果支持把后续主问题集中为“向列纹理相近时，极性组织为何能持续不同”。球面丝状体的极性流动本身已有文献，不能声称首次发现同向/反向运动；本体系的价值在于相同后端下联合量化缺陷几何、极性和材料运动，并研究其初态记忆及尺寸依赖。〔参考：Chiao-Peng Hsu, Alfredo Sciortino, Yu Alice de la Trobe, Andreas R. Bausch. *Activity-induced polar patterns of filaments gliding on a sphere*. Nature Communications 13,2579 (2022). https://doi.org/10.1038/s41467-022-30128-7 。〕

## 2. 尺寸与活性：支持什么，不支持什么

'''
text+=table(gs[gs.nchain>10],['nchain','F','seeds','Nplus','Nplus_seed_sd','four','P','S','C'])
text+='''
在已有种子中，F从2增至5后，nchain30的正缺陷均数从约5.51升到8.53，nchain50从约5.14升到15.34；nchain50/F5的后半程采样构型没有四缺陷态。局部向列序仍较高，因此更像局部重排和短尺度缺陷增多，而不是完全各向同性化。nchain50尚缺第3种子，暂不报告确定显著性或稳态相边界。〔来源：group_summary.csv。〕

**当前不能说缺陷数随尺寸普遍单调增加。** F=2时，nchain30与50的种子平均缺陷数接近且不单调。nchain50/F2两个种子的整体环流C分别约0.089和0.688，显示初态/随机历史造成的运动组织差异很大，仅平均缺陷数会掩盖这一点。必须等待第3种子以及nchain100，再区分尺寸趋势与分支选择。〔来源：run_summary.csv。〕

![尺寸与活性](02_size_activity.png)

## 3. 缺陷数的尺度依赖仍然重要

在每组完全相同的11个后半程构型上，nchain50/F5平均正缺陷数h=0为15.23，h=1.5为5.68，h=3为4.59；nchain30/F5分别8.42、4.73、4.21。故强活性引起的增加主要表现于较短尺度，不能立即全部解释为介观长寿命缺陷，更不能只凭这些计数宣布活性湍流。平滑也可能合并真实近邻缺陷，不能反过来说被滤掉的全部是误检。〔来源：scales.csv；参考：Achini Opathalage, Michael M. Norton, Michael P. N. Juniper, Blake Langeslay, S. Ali Aghvami, Seth Fraden, Zvonimir Dogic. *Self-organized dynamics and the transition to turbulence of confined active nematics*. PNAS 116,4788–4797 (2019). https://doi.org/10.1073/pnas.1816733116 。〕

![尺度依赖](03_scale_dependence.png)

## 下一步

等待其余8组完成后扩展同一统计。对nchain100/F5另行审核已报告的FENE键伸长警告，检查相关时间附近构型；LAMMPS警告阈值以内/以外的处理不能只用“键长小于1.5”就判为无影响。事件寿命分析尚未完成：需要对100/1000/10000步窗口逐核跟踪并检查时间、空间尺度收敛，当前采样结果不能用于真实产生/湮灭率。

本次文件：group_summary.csv（种子汇总）、run_summary.csv（逐种子/时间窗）、frames.csv（逐帧指标）、scales.csv（同帧尺度扫描）、audit.json（来源与日志）、validation.json（核验）。可复现脚本位于上一级extract_completed.py、analyze_partial.py、report_partial.py。原始模拟未修改。
'''
(P/'report_zh.md').write_text(text,encoding='utf-8')
print(gs.to_string(index=False))
