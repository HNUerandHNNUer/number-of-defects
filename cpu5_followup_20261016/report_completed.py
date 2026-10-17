# -*- coding: utf-8 -*-
from pathlib import Path
import json,re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent;OUT=HERE/'completed_analysis_20261016';OLD=HERE.parent/'cpu5_validation_20261015/final_analysis_cpu5'
audit=json.loads((OUT/'audit.json').read_text());meta={j['name']:j for j in audit}
frames=pd.read_csv(OUT/'frames.csv');runs=pd.read_csv(OUT/'run_summary.csv');late=runs[runs.window=='late50'].copy();sectors=pd.read_csv(OUT/'branch_sector_frames.csv');sec=json.loads((OUT/'branch_sector_summary.json').read_text())
for key in ['dt','geometry','pattern']:late[key]=late.name.map(lambda n:meta[n].get(key,'size'))
small=late[late.nchain==10].copy();sector=pd.DataFrame(sec);small=small.merge(sector[['name','final_minority','late_minor_mean']],on='name')
motion=sectors[sectors.step>=50000000].groupby('name')[['motion_minority','motion_sign_agreement']].mean().reset_index();small=small.merge(motion,on='name');small.to_csv(OUT/'small_seed_summary.csv',index=False)
cols=['P','S','C','Nplus','four','rotation_fraction','pair_angle_deg','pair_center_deg','late_minor_mean','motion_minority','motion_sign_agreement']
small.groupby(['geometry','pattern'])[cols].agg(['mean','std']).to_csv(OUT/'small_group_summary.csv')
baseline=pd.read_csv(OLD/'run_summary.csv');baseline=baseline[(baseline.window=='late50')&(baseline.nchain==100)&(baseline.F==5)].copy();baseline['dt']=.01
dt=pd.concat([baseline,late[late.nchain==100]],ignore_index=True);dt.to_csv(OUT/'dt_seed_summary.csv',index=False)
dt.groupby('dt')[['Nplus','P','S','C','pair_density']].agg(['mean','std']).to_csv(OUT/'dt_group_summary.csv')
fixed=pd.read_csv(OUT/'fixed_comparison.csv');fs=fixed.groupby(['name','dt','nchain','h'],as_index=False)[['Nplus','pair_density','cv3','four']].mean();fs.to_csv(OUT/'fixed_seed_summary.csv',index=False)
fg=fs[fs.nchain==100].groupby(['dt','h'])[['Nplus','pair_density','cv3']].agg(['mean','std']);fg.to_csv(OUT/'fixed_dt_summary.csv')
quarters=[]
for name,z in frames.groupby('name'):
 for b in range(4):
  a=z[(z.step>=b*25000000)&(z.step<=(b+1)*25000000)];r=dict(name=name,block=b)
  r.update({c:a[c].mean() for c in ['P','S','C','Nplus']});quarters.append(r)
pd.DataFrame(quarters).to_csv(OUT/'quarter_blocks.csv',index=False)
warn=[]
for folder,jobs,dtvalue in [(OLD,json.loads((OLD/'audit.json').read_text()),.01),(OUT,audit,None)]:
 for j in jobs:
  if j['nchain']!=100 or j['F']!=5:continue
  lines=[l for l in j['warnings'] if 'FENE bond too long' in l];warn.append(dict(name=j['name'],dt=j.get('dt',dtvalue),count=len(lines),physical_duration=1e6,warning_lines=lines))
(OUT/'fene_comparison.json').write_text(json.dumps(warn,indent=2))
fig,axes=plt.subplots(2,2,figsize=(11,7),sharex=True)
for ax,(geom,pat) in zip(axes.flat,[('co','aligned'),('co','balanced'),('counter','aligned'),('counter','balanced')]):
 for rep in (1,2,3):
  z=sectors[(sectors.geometry==geom)&(sectors.pattern==pat)&(sectors.replicate==rep)];ax.plot(z.time/1e6,z.minority,label='seed %d'%rep)
 ax.set_title('%s geometry / %s polarity'%(geom,pat));ax.set_ylim(-.2,5.3);ax.set_ylabel('Minority circulation chains');ax.legend()
for ax in axes[1]:ax.set_xlabel('Physical time / 1e6')
fig.tight_layout();fig.savefig(str(OUT/'01_preparation_sectors.png'),dpi=180);plt.close(fig)
fig,axes=plt.subplots(1,3,figsize=(12,3.8))
groups=[('co','aligned'),('co','balanced'),('counter','aligned'),('counter','balanced')]
for ax,col in zip(axes,['P','S','rotation_fraction']):
 for i,(g,p) in enumerate(groups):
  z=small[(small.geometry==g)&(small.pattern==p)][col];ax.scatter(i+np.linspace(-.1,.1,len(z)),z);ax.errorbar(i,z.mean(),yerr=z.std(),color='black',fmt='_',capsize=4)
 ax.set_xticks(range(4));ax.set_xticklabels(['co\naligned','co\nbalanced','counter\naligned','counter\nbalanced']);ax.set_ylabel(col)
fig.tight_layout();fig.savefig(str(OUT/'02_preparation_order.png'),dpi=180);plt.close(fig)
fig,axes=plt.subplots(1,3,figsize=(11,3.8))
for ax,col in zip(axes,['Nplus','P','S']):
 for i,d in enumerate((.01,.005)):
  z=dt[dt.dt==d][col];ax.scatter(i+np.linspace(-.1,.1,len(z)),z);ax.errorbar(i,z.mean(),yerr=z.std(),color='black',fmt='_',capsize=4)
 ax.set_xticks([0,1]);ax.set_xticklabels(['dt=0.01','dt=0.005']);ax.set_ylabel(col)
fig.tight_layout();fig.savefig(str(OUT/'03_timestep_comparison.png'),dpi=180);plt.close(fig)
def table(d):
 return '| '+' | '.join(d.columns)+' |\n|'+'|'.join(['---']*len(d.columns))+'|\n'+'\n'.join('| '+' | '.join('%.4g'%v if isinstance(v,(float,np.floating)) else str(v) for v in row)+' |' for row in d.itertuples(index=False,name=None))
def stat(z,col):return '%.4f ± %.4f'%(z[col].mean(),z[col].std())
summary=[]
for (g,p),z in small.groupby(['geometry','pattern']):summary.append(dict(geometry=g,preparation=p,P=stat(z,'P'),S=stat(z,'S'),rotation=stat(z,'rotation_fraction'),final_minority=','.join(str(int(v)) for v in z.sort_values('replicate').final_minority)))
dtrows=[]
for d,z in dt.groupby('dt'):dtrows.append(dict(dt=d,Nplus=stat(z,'Nplus'),P=stat(z,'P'),S=stat(z,'S')))
fr=[]
for (d,h),z in fs[fs.nchain==100].groupby(['dt','h']):fr.append(dict(dt=d,h=h,Nplus=stat(z,'Nplus'),cv3=stat(z,'cv3')))
report='''# 已完成15组对照的阶段性验证

## 结论

本轮已完成并分析12组小球面制备对照及3组dt=.005对照，主分析6615帧，固定网格另比较新15组及旧3组各11个晚期构型、两种平滑长度，共396次识别。dt=.0025尚未完成，未混入完整时长比较。最明确的新结果是：**小球面的四缺陷背景允许多个持久环流组成，改变链的初始极性可以改变长期运动；长期环流组成同时依赖制备几何和随机种子。** 这比“只有两种运动模式”的原始判断更具体。〔数据：audit.json、frames.csv、fixed_comparison.csv、branch_sector_summary.json。〕

## 1. 小球面：保持初始几何，只改变链极性

同向/反向旧构型分别记co/counter。aligned将链初始环流方向全部设为同向；balanced设为5对5。球面半径、链长、坐标集合、键/角几何以及初始无头尾向列Q不变；各组三个独立噪声种子，从坐标数据重新开始，非精确restart。下表取物理时间后半段500000—1000000，±为3个种子均值的样本标准差。rotation是100物理时间位移窗口内整体刚体旋转解释比例，受热噪声影响，不代表全部动能中的旋转份额。〔方法：prepare_followup.py、analyze_completed.py。〕

'''+table(pd.DataFrame(summary))+'''

三个co/aligned种子均保持10:0；counter/aligned两个为10:0、一个为9:1。counter/balanced全部保持5:5；co/balanced三个种子分别达到8:2、5:5、6:4。后半段主轴分类在各轨迹中均保持不变；部分种子在前半段发生持续方向重排。因此存在有限时间的制备记忆及多种长寿命环流组成，但观察到的早期重排不能自动解释为平稳状态间反复跃迁，尚不足以宣称严格多稳态或测量势垒。〔数据：branch_sector_frames.csv、branch_sector_summary.json。〕

为防止5:5近抵消时净环流轴不稳定，反向链重新按链环流张量的第一主轴分类，取两个方向中较少的链数；主轴逐帧保持符号连续。全部晚期样本的最弱链轴向投影绝对余弦仍大于0.91，分类清晰。原co/balanced/r2若按净环流轴会得到波动的“4.44条”，主轴复核得到稳定5条；已用后者解释状态。实际链刚体位移方向也另行检查，保留motion_sign_agreement及motion_minority列。持续重排要求新分类至少连续3个样本且方向投影超过0.2，检测间隔2000物理时间，因此变化时间仅有该量级分辨率。〔数据：small_seed_summary.csv；方法：branch_sectors.py。〕

固定网格h=1.5下，各组晚期平均正缺陷数约4.00—4.06，h=3下所抽样构型全部为4。向列序S均约0.82，而P和旋转比例差异明显。因此当前证据支持“相似四缺陷向列背景并不能唯一决定极性运动”。缺陷数一致不意味着全部场构型完全相同；环流方向的空间分布同样重要，例如两个5:5状态也可能有不同局部极性。四缺陷条件下种子平均对内夹角约38—49度，两对中心间约169—173度。链切向分类与实际位移方向的一致率约98.1%—99.4%，因此这些环流组成有实际材料运动的支持。〔数据：fixed_seed_summary.csv、small_seed_summary.csv。〕

![环流组成](01_preparation_sectors.png)

![极性及旋转](02_preparation_order.png)

## 2. nchain100/F=5：时间步长减半后主要统计相近

两组生产物理时间均为1000000，预弛豫物理时间均为100000，独立噪声和独立预弛豫轨迹。所有CSV中的step已统一为“物理时间/0.01”；原始实际步数见audit，不能再乘各组dt。后半段原粒子网格统计如下。〔来源：extract_completed_followup.py、dt_seed_summary.csv。〕

'''+table(pd.DataFrame(dtrows))+'''

相同固定球面网格L4、相同物理平滑长度，晚期11点/种子的比较如下。密度CV采用固定物理半径3的球面帽统计；它描述不均匀性，不能单独证明MIPS。〔数据：fixed_dt_summary.csv、fixed_seed_summary.csv。〕

'''+table(pd.DataFrame(fr))+'''

主要均值没有出现大幅系统性变化，支持“n100/F5的较多缺陷并非仅由dt=.01造成”的阶段性判断。然而每组只有3个种子，dt=.005原网格缺陷数的种子间离散更大，均值接近并非统计等效检验；dt=.0025未完成，不能宣称时间步长已经收敛。应联合检验第三种dt、晚期时间漂移及种子间误差。〔数据：dt_group_summary.csv、quarter_blocks.csv。〕

旧dt=.01三组共有15条FENE过长日志，新dt=.005三组共有1条：r1第47983324步、键长1.426256。触发阈值约1.423025，而不是1.5；触发时LAMMPS会截断FENE分母。计数下降是积极信号，但警告可能聚集于同一次异常伸长过程，不能把15条和1条直接当作15和1个独立事件；原始逐条日志及按相同生产物理时长的比较均保留。dt=.005其余两种子无FENE警告。所有15组无ERROR/Lost atoms，完成文件齐全；自定义积分器存在通用的“No fixes with time integration”提示，其回调实际执行，已由位移与轨迹变化验证，不能把该提示当作粒子静止。〔来源：fene_comparison.json、逐组log与冻结源码。〕

![步长比较](03_timestep_comparison.png)

## 3. 研究主线与尚未证明的机制

建议将主线收束为“球面受限活性链的四缺陷纹理与极性环流组成：制备依赖及尺寸诱导的额外缺陷对”。本轮干预加强了初始极性影响长期运动的证据；counter几何也能形成同向运动，说明该几何并未把体系完全锁死在原反向状态。当前仍只有每类一个起始几何，balanced翻转哪几条链由固定规则选择，因此几何效应和具体极性空间排布还未完全拆开；尚未改变链长，也未计算链通过/环绕不变量，不能声称证实拓扑保护。〔数据依据：本轮干预和种子表；相关文献：Hsu, C.-P.; Sciortino, A.; de la Trobe, Y. A.; Bausch, A. R. Activity-induced polar patterns of filaments gliding on a sphere. Nature Communications 13, 2579 (2022). https://doi.org/10.1038/s41467-022-30128-7〕

球面上的极性带、涡旋和堵塞已有实验工作；球面活性向列的动力学模式也已有理论研究，因此本项目值得强调的是在相同微观几何干预极性、同时测量缺陷纹理与材料运动，而非泛称首次发现球面旋转或反向流。这里的微观模型是具有局部向列序的极性自推进链，与文献中的无极性活性向列模型不能直接等同。MIPS、严格多稳态、真实缺陷产生率和寿命仍未证实；后两者受前轮网格及时间采样检验限制。〔参考：Hsu等，Nature Communications 13,2579 (2022)，上引；Henkes, S.; Marchetti, M. C.; Sknepnek, R. Dynamical patterns in nematic active matter on a sphere. Physical Review E 97,042605 (2018). https://doi.org/10.1103/PhysRevE.97.042605〕

## 复现

依次执行extract_completed_followup.py（服务器，仅提取已完成组）、analyze_completed.py或run_completed_analysis.py、compare_fixed_completed.py、branch_sectors.py、report_completed.py；保留旧24组目录以供基准比较。报告、CSV、图均在completed_analysis_20261016。后续加入dt=.0025时重新提取并运行统计，不能混入未达到完整物理时长的轨迹。〔来源：上述脚本。〕
'''
(OUT/'report_completed_zh.md').write_text(report,encoding='utf-8');print(table(pd.DataFrame(summary)));print(table(pd.DataFrame(dtrows)));print(table(pd.DataFrame(fr)))
