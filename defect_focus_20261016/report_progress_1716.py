# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent/'progress_20261016_1716'
a=pd.read_csv(P/'fixed_frames.csv');r=a[a.name.str.startswith('relax')].copy()
r['n']=r.name.str.extract(r'n(\d+)_').astype(int);r['F']=r.name.str.extract(r'_F([\d.]+)_').astype(float);r['seed']=r.name.str.extract(r'_r(\d+)').astype(int)
s=r[r.step>=5000000].groupby(['n','F','seed','h'],as_index=False)[['Nplus','Nminus','P4','pair_density']].mean();s.to_csv(P/'seed_early_summary.csv',index=False)
g=s.groupby(['n','F','h'],as_index=False).agg(Nplus=('Nplus','mean'),seed_sd=('Nplus','std'),seeds=('seed','count'),P4=('P4','mean'),pair_density=('pair_density','mean'));g.to_csv(P/'group_early_summary.csv',index=False)
old=pd.read_csv(P/'legacy_discard25.csv');tab=old[old.n.isin([200,350]) & old.F.isin([0,.03,.1,.3])].pivot_table(index=['n','F'],columns='window',values='Nplus').reset_index()
def table(d):
 return '| '+' | '.join(d.columns)+' |\n|'+'|'.join(['---']*len(d.columns))+'|\n'+'\n'.join('| '+' | '.join('%.3f'%x if isinstance(x,float) else str(x) for x in row)+' |' for row in d.itertuples(index=False,name=None))
fig,ax=plt.subplots(2,2,figsize=(10,7))
for i,n in enumerate([200,350]):
 for j,h in enumerate([1.5,3.]):
  z=r[(r.n==n)&(r.h==h)].groupby(['F','step'],as_index=False).Nplus.mean()
  for F,b in z.groupby('F'):ax[i,j].plot(b.step/1e6,b.Nplus,'o-',label='F=%g'%F)
  ax[i,j].set_title('n=%d, h=%g'%(n,h));ax[i,j].set_xlabel('Production steps / 1e6');ax[i,j].set_ylabel('Positive defects');ax[i,j].legend()
fig.suptitle('Early progress: unequal seed counts; same geometry within each size');fig.tight_layout(rect=[0,0,1,.95]);fig.savefig(str(P/'early_fixed_counts.png'),dpi=180)
text='''# 缺陷演化进展：舍弃前25%后的复核与服务器阶段数据

研究问题：固定面积分数下，球面尺寸与活性怎样改变缺陷数量、额外缺陷对面密度、四缺陷占比和几何组织；区分有限时间弛豫与长期增殖。极性与密度聚集只作辅助解释。本轮不把预运行F=1设置作为否定旧平均值的理由，只检验剩余时间窗口的数据。〔数据：legacy_discard25.csv、fixed_frames.csv。〕

## 旧数据：严格舍弃各轨迹前25%

下表为原始识别的正半缺陷数；q2/q3/q4分别为总时长25–50%、50–75%、75–100%。八条轨迹均为10亿步，因而此处窗口可直接比较。边界帧在相邻窗口重复一次，对均值影响很小。均值不同不等于统计显著，时间帧不能作为独立种子。

'''+table(tab)+'''

F=.1在这两个尺寸的后75%平均中最低，因此低谷是现有有限时间数据的真实统计现象，不应笼统否定。但n200/F.03从23.06降到12.91，n350/F.03从30.16降到17.19，截去25%后仍有明显时间变化。n200/F.1的三个分段较接近；n350/F.1先降后升，不支持继续单调衰减的概括。不能由这些数据推断所有组都未稳态，也不能由统一截尾比例证明所有组都稳态。〔来源：上表；机制背景：[Giomi等，Defect Annihilation and Proliferation in Active Nematics，Physical Review Letters 110,228101，2013](https://doi.org/10.1103/PhysRevLett.110.228101)。〕

## 新服务器数据：同初始几何的早期检验

2026-10-16 17:16（UTC+8）读取：n200约3690万–3842万步，n350约2031万–2167万步；共同提取0至2000万步，每250万步一帧，共9帧。下表平均窗口为500万至2000万步，每种子7帧。此处截去的是当前共同阶段的前25%，不是计划10亿步的前25%；因此是早期响应，绝不能叫稳态统计。n200每个F只有2种子，n350除F0为2种子外其余只有1种子；单种子误差留空，不能当零误差。

'''+table(g)+'''

同R的初始N+完全一致：n200在h1.5/3为10/7，n350为18/11。n200较细尺度h1.5下F.1均值8.57，低于F0的9.93，但h3下F.03和.1均为6.43，与F0的6.57接近；差别对尺度敏感。n350在h1.5下F.3为13.86、F.1为16.57、F0为18.14；h3下F.1为9.71、F.3为10.57、F0为10.93。当前支持活动驱动下早期缺陷组织变化的迹象，尚不支持某个F在所有尺度上都最快或最好。全部分析帧净半荷差为4、无高阶合并面荷；分析窗口P4均为0，所以不能比较四缺陷配对角。〔数据：seed_early_summary.csv、group_early_summary.csv、fixed_frames.csv。〕

![阶段缺陷数](early_fixed_counts.png)

新组从同一尺寸的相同坐标重新播种，非精确restart；多个噪声种子不等于多个独立初始构型。因新组初始状态与旧组不同，不拼接为一条时间轨迹。跨R也未控制相同初始缺陷密度，不能宣称纯曲率因果。〔来源：任务provenance与manifest。〕

## 小步长验证

dt=.0025三个种子当前约3.10/3.14/3.23亿步，目标4亿步，检查未见FENE警告或ERROR。补取各组0–3亿步的13个完整帧，另有78条双尺度固定网格结果。相同当前后段2–3亿步内h1.5各种子均值13.0/8.0/12.4，h3为7.6/5.2/8.2，显示种子差异不能忽略；暂不与不同采样时间的旧均值直接宣布步长收敛。完成后再做三个dt的完整等物理时间比较。服务器仍32个lmp进程，新组13运行11排队，无需增开任务。〔来源：服务器日志与fixed_frames.csv。〕

## 当前结论与接下来要回答的问题

已有证据支持：强活性下较大球面容纳更多缺陷；额外缺陷面密度不是严格逐点单调；后75%统计存在中低活性低缺陷窗口；该窗口的时间稳定性和尺度稳健性因R/F而异。新增早期结果不能证明统一F=.1最优。建议主线表述为“球面受限活性向列中，尺寸与活性对缺陷弛豫和增殖的竞争调控”，其中竞争是待定量检验的工作假说，而非已测得产生湮灭率。球面上尺寸/活性引起组织变化已有直接先例；创新需来自可靠的时间依赖、尺度检验及重复结果，不能仅凭画R–F图宣称首次。〔参考：Henkes、Marchetti、Sknepnek，[Dynamical patterns in nematic active matter on a sphere，Physical Review E 97,042605，2018](https://doi.org/10.1103/PhysRevE.97.042605)。〕

下一步先利用已排队24组补齐3种子，逐个1亿步里程碑比较相同时间窗口的Nminus、面密度及P4；按每种子先做时间统计再统计种子间离散度。并行推进三dt等时间验证。若低谷随时间漂移则报告动力学低谷；若持续稳定且跨尺度、种子一致，再在最小值两侧补少量F点。当前不需要再提交新模拟，也不将MIPS或未收敛的缺陷寿命作为结论。〔依据：现有计算缺口及本轮阶段统计。〕
'''
(P/'report_zh.md').write_text(text,encoding='utf-8');print(g.to_string(index=False))
