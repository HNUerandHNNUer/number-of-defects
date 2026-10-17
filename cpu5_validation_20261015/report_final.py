# -*- coding: utf-8 -*-
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent;P=HERE/'final_analysis_cpu5';ROOT=HERE.parent
d=pd.read_csv(P/'frames.csv');r=pd.read_csv(P/'run_summary.csv');g=pd.read_csv(P/'group_summary.csv');sc=pd.read_csv(P/'scales.csv');q=pd.read_csv(P/'quarter_blocks.csv');t=pd.read_csv(P/'tracking_summary.csv');fine=pd.read_csv(P/'fine_counts.csv');rho=pd.read_csv(P/'density_frames.csv')
late=r[r.window=='late50'];size=late[late.nchain>10];colors={2:'#2866b3',5:'#dc7d2b'}
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(2,2,figsize=(11,7))
for name,z in d[d.nchain==10].groupby('name'):
 b=z.branch.iloc[0];rep=z.replicate.iloc[0];c='#c74242' if b=='counter' else '#168d9c'
 axes[0,0].plot(z.step/1e8,z.P,color=c,alpha=.65,lw=.8,label=b if rep==1 else None)
 axes[0,1].plot(z.step/1e8,z.S,color=c,alpha=.6,lw=.7)
 zz=late[late.name==name].iloc[0];xx=(0 if b=='counter' else 1)+(rep-2)*.07
 axes[1,0].scatter(xx,zz.Nplus,color=c,s=40);axes[1,1].scatter(xx,zz.rotation_fraction*100,color=c,s=40)
axes[0,0].legend();axes[0,0].set_ylabel('Local polarity P');axes[0,1].set_ylabel('Local nematic order S')
for ax in axes[0]:ax.set_xlabel('Continuation steps / 1e8')
for ax in axes[1]:ax.set_xticks([0,1]);ax.set_xticklabels(['counter-prepared','co-prepared'])
axes[1,0].set_ylabel('Positive defects N+, late-half seed mean');axes[1,1].set_ylabel('Rigid rotation explained displacement (%)');axes[1,1].set_title('Displacement lag = 10,000 steps',fontsize=10)
for ax in axes.flat:ax.grid(alpha=.2)
fig.suptitle('n=10, F=2: three noise seeds preserve two distinct polar organizations');fig.tight_layout(rect=(0,0,1,.95));fig.savefig(P/'01_branches.png',dpi=170);plt.close(fig)

fig,axes=plt.subplots(2,2,figsize=(10.5,7))
for F,c in colors.items():
 rows=g[(g.F==F)&(g.nchain>10)]
 for ax,key in zip(axes.flat,['Nplus','pair_density','P','C']):
  ax.errorbar(rows.nchain,rows[key],yerr=rows[key+'_seed_sd'],color=c,marker='o',label='F=%d'%F,capsize=3)
  for n,z in size[size.F==F].groupby('nchain'):ax.scatter(n+(z.replicate-2)*1.2,z[key],color=c,s=15,alpha=.5)
for ax,y in zip(axes.flat,['Positive defects N+','Extra defect-pair density N- / area','Local polarity P','Global tangent circulation C']):
 ax.set_xlabel('Chain count');ax.set_xticks([30,50,100]);ax.set_ylabel(y);ax.grid(alpha=.2)
axes[0,0].legend();fig.suptitle('Full runs: last 50 million steps; mean +/- SD across 3 noise seeds\nn=100 F=5 includes 2 trajectories with FENE warnings',fontsize=11);fig.tight_layout(rect=(0,0,1,.92));fig.savefig(P/'02_size_activity.png',dpi=170);plt.close(fig)

fig,axes=plt.subplots(1,3,figsize=(13,4))
for F,c in colors.items():
 for rep,z in q[q.nchain==100].query('F==@F').groupby('replicate'):
  for ax,key in zip(axes,['Nplus','P','C']):ax.plot(z.block+.5,z[key],marker='o',ls=['-','--',':'][rep-1],color=c,alpha=.8,label='F%d r%d'%(F,rep))
for ax,y in zip(axes,['Positive defects N+','Local polarity P','Global tangent circulation C']):ax.set_xlabel('Production time / 25 million steps');ax.set_ylabel(y);ax.set_xticks([.5,1.5,2.5,3.5]);ax.grid(alpha=.2)
axes[0].legend(fontsize=8,ncol=2);fig.suptitle('n=100: count stationarity does not imply stationary polar flow');fig.tight_layout(rect=(0,0,1,.93));fig.savefig(P/'03_time_blocks.png',dpi=170);plt.close(fig)

ss=sc[sc.step>=50000000].groupby(['name','nchain','F','h']).Nplus.mean().reset_index();sg=ss.groupby(['nchain','F','h']).Nplus.mean().reset_index();sg.to_csv(P/'scale_group_summary.csv',index=False)
fig,axes=plt.subplots(1,2,figsize=(10,4))
for ax,F in zip(axes,[2,5]):
 for n,z in sg[(sg.F==F)&(sg.nchain>10)].groupby('nchain'):ax.plot(z.h,z.Nplus,'o-',label='n=%d'%n)
 ax.set_xlabel('Gaussian smoothing length h');ax.set_ylabel('Positive defects N+');ax.set_title('F=%d'%F);ax.legend();ax.grid(alpha=.2)
fig.suptitle('Same 11 late-half configurations per seed at all spatial scales');fig.tight_layout(rect=(0,0,1,.93));fig.savefig(P/'04_spatial_scale.png',dpi=170);plt.close(fig)

key='size_n100_F5_r1__late';z=t[(t.window==key)&(t.sign==1)&(t.gate==1.5)]
fig,axes=plt.subplots(1,3,figsize=(12,4))
for h,c in [(0,'#2866b3'),(1.5,'#d9782c')]:
 zz=z[z.h==h]
 for ax,field in zip(axes,['mean_count','births','mean_observed_span_steps']):ax.plot(zz.every,zz[field],'o-',color=c,label='h=%g'%h)
for ax,label in zip(axes,['Mean positive-defect count','New marker tracks (NOT physical births)','Mean observed uncensored span / steps']):ax.set_xscale('log');ax.set_xlabel('Saved-frame interval / steps');ax.set_ylabel(label,fontsize=9);ax.grid(alpha=.2)
axes[0].legend();fig.suptitle('Final 100,000-step window: counts are robust; event statistics are not');fig.tight_layout(rect=(0,0,1,.93));fig.savefig(P/'05_temporal_convergence.png',dpi=170);plt.close(fig)

def table(frame,keys):
 out='| '+' | '.join(str(k) for k in keys)+' |\n|'+'|'.join(['---']*len(keys))+'|\n'
 for _,row in frame.iterrows():out+='| '+' | '.join('%.4g'%row[k] if isinstance(row[k],(float,np.floating)) else str(row[k]) for k in keys)+' |\n'
 return out
refs=json.loads((ROOT/'defect_dynamics_20261015/references_verified.json').read_text())
def ref(doi):
 z=next(x for x in refs if x['doi']==doi);authors='; '.join(a.get('given','')+' '+a.get('family','') for a in z['authors']);title=z['title'][0] if isinstance(z['title'],list) else z['title']
 return authors+'. *'+title+'*. [DOI](https://doi.org/'+doi+').'
text='''# CPU5 24组验证的最终分析

## 核心结论

**最稳健的结论是“向列纹理与极性运动不一一对应”：相似的四缺陷纹理可以长期承载不同的极性组织。第二个结果是强活性下，尺寸增大既增加缺陷总数，也增加单位面积的额外缺陷对；弱活性不呈现同样的简单单调规律。第三个结果是缺陷平均数的时间采样已较稳定，但缺陷轨迹的出生数和持续时间尚未收敛，不能将它们报告为真实反应率或物理寿命。** 这些结论来自本次新模拟，不能直接升级成稳态相图、严格多稳态、活性湍流或MIPS证明。〔数据：group_summary.csv、quarter_blocks.csv、tracking_summary.csv。〕

## 数据完整性与统计方式

2026-10-15 23:39服务器核验：24/24组均完成，final.bin和VALIDATION_RUN_COMPLETED齐全，无ERROR或Lost atoms。18组来自nchain10/30/50，6组来自nchain100；所有生产段都达到1亿步。nchain30/50/100另外各有1000万步F=0.1预演化。本轮使用完整轨迹更新nchain100，未复用此前6000万步快照的指标缓存。〔来源：audit.json、各组完整log、validation.json。〕

模型是具有局部向列序的**极性自推进半柔性链**：链内珠编号决定推进方向，链端无直接活性力，内珠沿局部链切向推进；没有求解流体速度场。LJ约化单位，dt=0.01、gamma=1000、T=1、每链30珠，WCA排斥、FENE键、cosine弯曲系数30及球形软壁。不能直接把微观F当成连续介质中的活性应力系数，也不能仅凭图像把此系统等同于流体耦合的无极性活性向列。〔依据：冻结的bd/sphere源码和in.production。〕

长轨迹分析6624个构型；nchain10每20万步，其余每50万步。除时间漂移分析外，主表统一取后5000万步，各种子先取时间均值，再对3个种子汇总；“±”表示种子均值的样本标准差，不是95%置信区间。小球面两组重复来自各自同一个晚期构型，只检验新噪声下的持续性，不代表独立初态的吸引域统计。〔数据：run_summary.csv、frames.csv。〕

另在相同时间点进行1512次空间尺度识别；9个早/中/晚密集窗口共9009个构型，每个比较h=0和h=1.5，再按100/1000/10000步降采样追踪。粗采样和密集窗口均满足离散净拓扑荷+2；这只验证拓扑一致，不认证每个标记的物理核心位置。〔数据：scales.csv、fine_counts.csv、tracking_summary.csv。〕

## 1. 小球面分支：重复性很强，但“多稳态”还需谨慎

'''+table(g[g.nchain==10],['branch','P','P_seed_sd','S','Nplus','Nplus_seed_sd','four','C','pair_angle_deg'])+'''
反向初态始终维持6对4的链切向分类，同向初态维持10对0；全部6条续演化在采样构型中没有持续分支切换。P分别0.583与0.923，S分别0.810与0.820，平均正缺陷数4.13与4.24；四缺陷条件下对内角均约40°。差异主要在极性组织，并非缺陷数量数量级不同。〔数据：branch组逐帧及逐种子统计。〕

相同1万步位移窗口下，实际运动反向链平均数约3.967和0.066，链切向与实际位移的分类大体一致；整体刚体旋转解释位移比例约10.3%与48.0%。短时间热噪声会压低拟合比例，不能与旧分析10万步窗口的18.8%/96.2%直接比较。这里只在相同窗口比较两个分支。〔数据：frames.csv的lag_steps=10000。〕

![分支验证](01_branches.png)

这些结果排除了“先前差异仅由CPU/GPU运行实现不同造成”的简单解释，但不能排除长时间亚稳态或制备记忆。小球面上链长与半径之比较大，改变环绕/运动方向可能需要协同重排，这是值得验证的机制假说，并非已证实机制。球面极性丝状体的同向流和复杂运动已有报道；本研究应强调缺陷几何、极性及材料运动的联合测量，而非声称首次发现反向流。〔参考：Hsu等，Nature Communications 13,2579 (2022)，文献R1。〕

## 2. 全尺寸统计：强活性放大尺寸效应

以下Nplus为正缺陷数，Nminus=Nplus−4。rho_pair=Nminus/(4πR²)剔除了球面必需的净荷贡献。R约为8.964、11.573、16.366。所有条件均为3个种子，nchain100/F5的两个警告样本暂包含在表中，敏感性见第6节。

'''+table(g[g.nchain>10],['nchain','F','Nplus','Nplus_seed_sd','pair_density','four','P','S','C'])+'''
F=5时Nplus从8.53→15.85→47.22，额外对密度从0.00448→0.00704→0.01284。后者也增长，说明不能完全归因于面积增大。F=2的Nplus为5.51→5.33→7.89，额外对密度不单调，不能将所有活性下的半径效应概括成同一个单调定律。〔数据：group_summary.csv。〕

F=5下四缺陷态占比分别约11.2%、0.33%、0%；F=2下仍约41.9%、33.3%、8.25%。局部S保持较高（F5约0.847、0.840、0.807），而P与整体环流C在强活性尺寸序列中减弱，更符合“整体组织被局部重排与缺陷打断”，而不是完全各向同性化。C是链方向的环流组织量，不是速度或涡量。种子间C差异较大，不应把每个单独轨迹的变化都当作单调尺寸效应。〔数据：run_summary.csv；相关已有球面图案见Henkes等，Physical Review E 97,042605 (2018)，文献R2。〕

![尺寸与活性](02_size_activity.png)

## 3. 是否达到稳态：缺陷数与运动组织必须分开判断

小球面两分支在新增1亿步中持续分离，支持观察窗内的持久性。nchain100/F5在前2500万步后，三种子平均Nplus的后续三个时间块约47.47、49.09、45.39，接近平台但单条轨迹仍有变化。只能报告后半程准稳定的计数统计，不能凭3个短时间块认证严格稳态。〔数据：quarter_blocks.csv。〕

nchain100/F2的平均局部S一直约0.916–0.919，但P从首个2500万步块的0.925降到末块0.811；C的四个块均值约0.694→0.395→0.233→0.511，出现明显重组和回升，而非单调弛豫。因此“缺陷数量较平稳”不能推导出极性/环流也已达到动态平衡。这个解耦比只寻找缺陷数平台更有研究价值。〔数据：quarter_blocks.csv；缺陷与流动阈值分离的文献背景见Opathalage等，PNAS 116,4788–4797 (2019)，文献R3。〕

![时间块](03_time_blocks.png)

## 4. 空间尺度：强活性仍有粗尺度增殖，但原始核数不能全部解释成长寿命核心

下面每个条件都用每种子后半程同11个构型做三种平滑，不能将这个稀疏表与主表101帧/种子的Nplus差异误读成算法不一致。

'''+table(sg[sg.nchain>10].pivot_table(index=['nchain','F'],columns='h',values='Nplus').reset_index().rename(columns={0.:'h0',1.5:'h1.5',3.:'h3'}),['nchain','F','h0','h1.5','h3'])+'''
nchain100/F5由原始43.94降至h=1.5的12.36、h=3的7.48；F2的h=3仅约4.18。粗尺度的强活性增殖仍存在，但大部分原始计数增加发生在短尺度。平滑会合并真实近邻对，也会减少离散识别抖动，不能将消失的所有标记都叫伪缺陷；需要核心定位与轨迹收敛进一步区分。〔数据：scale_group_summary.csv。〕

![尺度依赖](04_spatial_scale.png)

## 5. 产生、湮灭与寿命：已做收敛测试，结果是不宜直接报告物理事件率

方法：对同号缺陷的球面面心标记采用最小总距离匹配，分别测试最大匹配距离0.75、1.5、3.0；首末窗口仍存在的轨迹标记为左/右删失，不将其当完整寿命。追踪得到的是“离散识别标记轨迹”，没有强制配对的±1/2反应认证。以下取nchain100/F5/种子1末10万步，匹配距离1.5、正缺陷，原始场h=0：

'''+table(z[z.h==0],['every','mean_count','births','deaths','complete_tracks','mean_observed_span_steps','single_frame_fraction'])+'''
平均Nplus约41.27、41.33、40.91，对100–10000步降采样变化很小；但新出现标记轨迹数1464→274→59，完整标记轨迹平均观测跨度约934→2843→5000步，明显未收敛。100步分辨率下约40%的完整标记轨迹只出现一帧，说明短时标记闪烁/短命结构对结果影响很大。未证明这40%全是算法伪影，但也不能直接当真实短命物理核。〔数据：tracking_summary.csv。〕

h=1.5时平均计数约9.16、9.18、8.91，仍较稳定，而新轨迹数237→45→11；空间平滑后事件统计仍未收敛。把匹配距离从0.75改为1.5/3.0也会改变轨迹数；小球面的近四缺陷态同样出现标记跳跃造成的轨迹碎裂。因此本次不给出所谓“真实平均寿命”或“产生率”：当前输出足以支撑平均缺陷数，尚不足以支撑物理事件动力学的定量结论。〔数据：tracking_summary.csv、各窗口tracks.csv。〕

![时间采样收敛](05_temporal_convergence.png)

这里的mean_observed_span_steps是完整标记轨迹最后观测时刻减首次观测时刻，非精确物理寿命；单帧跨度为0，实际持续时间不一定为0。100步采样不是自动正确的“真值”，还需要空间场与核心定义收敛。密集窗口每段仅10万步（1000约化时间），长寿命核多数被删失，不能仅从完整轨迹均值推断总体寿命。〔方法解释；缺陷动力学背景见Giomi等，Philosophical Transactions A 372,20130365 (2014)，文献R4。〕

## 6. FENE警告与数值风险

22条轨迹无FENE警告；nchain100/F5种子1有14条，发生于21831156—21858344步，最大警告键长1.436747；种子2有1条，1978142步、1.424587；种子3没有。R0=1.5时警告阈值是1.5√0.9≈1.4230：源码在1−r²/R0²<0.1时把该分母截为0.1。此前“尚小于1.5所以可视为无影响”的判断不充分，本报告明确修正。〔依据：fene_warnings.csv、服务器冻结源码对应bond_fene.cpp。〕

三种子后半程Nplus分别45.40、48.39、47.88。无警告的第三种子仍支持强活性多缺陷，所以这一现象不依赖两个警告样本；但单个无警告种子不能证明定量数值收敛，也不能认证警告样本的瞬态事件。密集窗口的nchain100案例正来自种子1，故它用于揭示采样不收敛，不能作为已认证的物理寿命基准。〔数据：run_summary.csv。〕

所有日志中的“No fixes with time integration”通用警告来自自定义fix未设置相关检测标志；该fix实际注册INITIAL_INTEGRATE/FINAL_INTEGRATE并推进坐标，轨迹确有运动。它与FENE力截断不是同一种问题。正式投稿前宜修正该标志并做短程回归，但不能因为文字警告就认定整批粒子未动。〔依据：固定bd/sphere源码及实际位移。〕

## 7. 密度不均匀性及MIPS边界

作为辅助指标，本次用固定测地半径3的球冠统计局部密度。F5的密度变异系数CV在nchain30、50、100约0.175、0.186、0.224，确有随尺寸增强的不均匀性；F2约0.132、0.167、0.174。但单个粗粒化尺度上的CV增长，不能区分巨数涨落、运动带、瞬态聚集与宏观相分离。本批验证也未完成共存密度、团簇有限尺寸标度或速度—密度反馈的机制证明，故仍不认定MIPS。〔数据：density_frames.csv。〕

## 8. 研究主线与最优先的后续

建议主线：**球面受限自推进链中向列缺陷纹理与极性运动的解耦，以及活性驱动的缺陷增殖与运动重组。** 三个可支撑的结果层次是：(1)小球面同缺陷纹理下的两个持久极性分支；(2)强活性放大尺寸引起的额外缺陷对密度增长；(3)缺陷计数、运动组织和短时核心事件具有不同的收敛要求。球面缺陷图案、极性带和缺陷增殖已有文献，创新点应落在本体系可验证的联合关系及机制，而不是“四个缺陷”或笼统“团聚”。〔文献R1–R4。〕

优先级1：把空间场定义在固定球面网格，用多尺度绕转和局部序参量识别核心，减少随粒子三角网格移动的面心抖动；要求一段持续时间及相邻正负核的空间关联后再统计事件，并复查采样与匹配门限收敛。优先级2：对nchain100/F5进行短步长对照（例如dt减半，匹配相同物理时长而非相同步数）；原轨迹保留。优先级3：改变小球面链长或制备方式验证初态记忆/环绕约束机制，扩大初态集合而不是仅增加同一构型的噪声种子。上述都是建议，本轮未擅自提交新模拟。〔依据：本轮未收敛项及分支验证的适用范围。〕

研究设计仍同时改变R、总链数和链长/R，不能把全部尺寸趋势单独归因于曲率；每个条件只有3个噪声种子，也不足以确定临界指数或严格相边界。现阶段可以围绕这些结果组织论文主线，但仍需上述数值和事件定义验证来强化机制结论。

## 文件与复现

- group_summary.csv：后半程三个种子的均值和样本标准差。
- run_summary.csv、quarter_blocks.csv：逐种子及分段时间演化。
- frames.csv、scales.csv、scale_group_summary.csv：长轨迹指标和同帧尺度比较。
- tracking_summary.csv、fine_counts.csv、各tracks.csv：全部门限/采样设置和删失记录。
- fene_warnings.csv、audit.json、validation.json：质量核验。
- 上一级extract_final.py、analyze_partial.py、fine_worker.py、run_fine.py、final_statistics.py、report_final.py：复现代码。长轨迹脚本设置CPU5_ANALYSIS_DIR=final_analysis_cpu5。

## 参考文献（复用此前已核验的DOI元数据）

R1. '''+ref('10.1038/s41467-022-30128-7')+''' Nature Communications 13,2579 (2022).

R2. '''+ref('10.1103/PhysRevE.97.042605')+''' Physical Review E 97,042605 (2018).

R3. '''+ref('10.1073/pnas.1816733116')+''' Proceedings of the National Academy of Sciences 116,4788–4797 (2019).

R4. '''+ref('10.1098/rsta.2013.0365')+''' Philosophical Transactions of the Royal Society A 372,20130365 (2014).

R5. '''+ref('10.1126/science.1254784')+''' Science 345,1135–1139 (2014). 四缺陷拓扑与动态的基础背景。
'''
(P/'report_final_zh.md').write_text(text,encoding='utf-8')
print('FINAL_REPORT_READY',P/'report_final_zh.md')
