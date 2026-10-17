# -*- coding: utf-8 -*-
from pathlib import Path
import json
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent;OUT=HERE/'fixed_grid_results';OLD=HERE.parent/'cpu5_validation_20261015/final_analysis_cpu5'
tables=[pd.read_csv(p) for p in OUT.glob('*_tracking.csv') if p.name!='primary_tracking.csv'];t=pd.concat(tables,ignore_index=True);t.to_csv(OUT/'tracking_summary.csv',index=False)
counts=pd.concat([pd.read_csv(p) for p in OUT.glob('*_counts.csv')],ignore_index=True);counts.to_csv(OUT/'counts_summary.csv',index=False)
pilot=pd.read_csv(OUT/'spatial_pilot.csv');pilot.groupby(['case','level','h']).Nplus.agg(['mean','min','max']).to_csv(OUT/'spatial_summary.csv')
selected=t[(t.sign==1)&(t.gate==1.5)];selected.to_csv(OUT/'primary_tracking.csv',index=False)
fig,axes=plt.subplots(1,3,figsize=(13,3.8))
for ax,case in zip(axes,['branch_n10_F2_co_r1','branch_n10_F2_counter_r1','size_n100_F5_r1']):
 for lev in (4,5):
  s=counts[(counts.case==case)&(counts.level==lev)]
  if len(s):ax.plot((s.step-s.step.min())*.01,s.Nplus,label='Fixed grid L%d'%lev,lw=1)
 ax.set_title(case.replace('branch_','').replace('size_',''));ax.set_xlabel('Time since late-window start');ax.set_ylabel('Positive half defects');ax.legend()
fig.tight_layout();fig.savefig(str(OUT/'fixed_grid_counts.png'),dpi=200);plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(9,3.8))
old=pd.read_csv(OLD/'tracking_summary.csv');s=old[(old.window=='size_n100_F5_r1__late')&(old.h==1.5)&(old.gate==1.5)&(old.sign==1)].sort_values('every')
axes[0].plot(s.every,s.births,'o-',label='Moving bead mesh')
for lev in (4,5):
 s=selected[(selected.case=='size_n100_F5_r1')&(selected.level==lev)].sort_values('every');axes[0].plot(s.every,s.births,'o-',label='Fixed L%d'%lev);axes[1].plot(s.every,s.mean_observed_span_steps*.01,'o-',label='Fixed L%d'%lev)
for ax in axes:ax.set_xscale('log');ax.set_xlabel('Sampling interval (steps)');ax.legend()
axes[0].set_ylabel('New positive tracks (not certified births)');axes[1].set_ylabel('Mean uncensored track span (time)');fig.tight_layout();fig.savefig(str(OUT/'tracking_convergence.png'),dpi=200);plt.close(fig)
def table(df):
 cols=list(df.columns);return '| '+' | '.join(cols)+' |\n|'+ '|'.join(['---']*len(cols))+'|\n'+'\n'.join('| '+' | '.join(('%.5g'%x if isinstance(x,(float,np.floating)) else str(x)) for x in row)+' |' for row in df.itertuples(index=False,name=None))
report='''# 固定球面网格复核及后续对照提交记录

现阶段主线建议：**球面受限下，向列缺陷纹理与极性运动的解耦，以及尺寸增大后额外缺陷对的出现。** 本轮已完成固定网格方法、空间精度和时间采样复核；另外18组动力学对照已提交，尚未完成，不能用其设计代替结果。〔来源：本目录CSV、manifest与服务器提交记录。〕

## 已有24组给出的结论

小球面F=2两分支的局部极性P分别为0.923和0.583，向列序S约0.820和0.810；相似四缺陷配对纹理对应同向与部分反向运动。三种子重复支持有限观察期内的持久性，不能证明无限时稳态或排除制备记忆。球面极性丝状体的旋转带、极性涡旋和堵塞此前已有研究，不能把“球面上出现集体运动”本身作为新颖性。〔数据：旧group_summary.csv；参考：Hsu, C.-P.; Sciortino, A.; de la Trobe, Y. A.; Bausch, A. R. Activity-induced polar patterns of filaments gliding on a sphere. Nature Communications 13, 2579 (2022). https://doi.org/10.1038/s41467-022-30128-7〕

F=5、nchain30/50/100的旧粒子网格平均正缺陷数分别为8.53±1.25、15.85±1.07、47.22±1.60，误差是3个种子均值的样本标准差；额外缺陷对面密度也增加。F=2不呈现同样的单调关系。绝对缺陷数依赖平滑尺度，且n100/F5有两条旧轨迹出现FENE截断，所以目前应称“尺寸相关趋势”，还不能给出通用标度律或证明数值收敛。〔数据：旧group_summary.csv、scale_group_summary.csv、fene_warnings.csv；相关背景：Henkes, S.; Marchetti, M. C.; Sknepnek, R. Dynamical patterns in nematic active matter on a sphere. Physical Review E 97, 042605 (2018). https://doi.org/10.1103/PhysRevE.97.042605〕

## 新的固定网格方法与结果

使用静止的细分二十面体球面网格：L3/L4/L5分别642/2562/10242个顶点。将链切向的向列Q通过球面平行输运插值到网格，采用物理长度h=1.5和3的高斯权重，最多128个近邻；按边转角及三角形固体角求拓扑荷，不人为补偿净荷。核心位置由带电三角形内Q的线性零点估计，解落出三角形时记录并退回面心。网格和粒子同时旋转协变、链头尾翻转不变、重复运行一致性检查通过。这些检查验证实现，不等于所有微小缺陷已具有物理意义。〔方法：fixed_grid.py、validate_methods.py；验证：validation.json。〕

下表为晚期窗口每10000步抽样的11帧。不同网格保持相同平滑长度，因此是在检验网格精度，而不是混合改变场的定义。〔数据：spatial_pilot.csv。〕

'''+table(pilot.groupby(['case','level','h'],as_index=False).Nplus.mean())+'\n\n'
report+='''精细时间追踪采用100/1000/10000步采样，球面距离门限0.75/1.5/3；保留左右删失，不把边界截断轨迹用于完整寿命均值。下表是门限1.5、正缺陷；births仅指新匹配轨迹，尚非经过正负配对和连续场复核的真实产生事件。〔数据：tracking_summary.csv、逐窗口counts.csv。〕

'''+table(selected[['case','level','every','mean_count','births','deaths','complete_tracks','mean_observed_span_steps']])+'\n\n'
report+='''本轮完成9个早/中/晚窗口的L4分析（9009帧），并额外对n100/F5晚期1001帧进行L5复核，共10010次逐帧识别。晚期n100/F5的平均N+在L4和L5分别为8.547和8.592，相差约0.53%；但每100步采样的新正轨迹为115和120，每1000步降至28和28，每10000步降至5和6。由此支持该窗口内平滑缺陷均值的网格稳定性，不支持事件率的时间采样收敛。126个带电面定位触发面心回退，没有出现合并高阶面荷；原始逐帧记录保留回退标记。〔数据：counts_summary.csv、primary_tracking.csv。〕

小球面反向分支晚期窗口在三种时间采样和门限1.5下均保持4个正缺陷，无新轨迹或轨迹终止；同向分支细采样下平均4.002，仍有极少短暂附加标记。这说明四缺陷背景相当稳健，但不能把所有短暂小对都直接解释为真实核心。〔数据：primary_tracking.csv。〕

![固定网格计数](fixed_grid_results/fixed_grid_counts.png)

![轨迹采样收敛](fixed_grid_results/tracking_convergence.png)

固定网格降低了移动三角网格导致的标记跳跃；仍应同时检查网格等级、匹配门限和时间采样。若新轨迹数或持续时间随采样变化明显，就不能报告“真实出生率/平均物理寿命”。零反应窗口内持续存在的四个缺陷属于删失轨迹，其寿命只有观察期下限，不是零寿命，也不能用单个窗口推断反应率严格为零。当前只复核代表种子的三个短窗口，不能代表所有种子、全部1亿步的事件统计。〔数据：tracking_summary.csv；窗口范围见旧NPZ的steps。〕

## 已提交的18组对照

2026-10-16 03:04（UTC+8）启动，16组同时运行、2组排队；每组2 MPI进程，总32进程。六种输入组合各短跑20000步通过，无ERROR、Lost atoms或FENE过长警告。服务器目录为 /home/user/wxd/9.19.2026/sphere_followup_20261016，运行器PID397213；旧轨迹未覆盖。〔来源：smoke.log、runner.log、status.json；本地sphere_followup_20261016/manifest.json。〕

短步长：n100/F5，dt=0.005和0.0025各3种子。各自先以F=0.1预弛豫相同物理时间100000，再生产1000000；对应生产2亿、4亿步，分别与旧dt=.01的1亿步比较。初始几何相同，但噪声与预弛豫轨迹独立，并非配对布朗路径。输出间隔均为100物理时间。自定义积分器的最大每步位移固定为0.05，其速度上限随dt改变，因此同时检查截断/极端位移敏感性，不能仅比较缺陷均值。〔依据：输入脚本及原bd/sphere源码。〕

制备对照：n10/F2，两种旧几何各构造沿参考旋转轴同向的aligned和5对5的balanced初始极性，每种3种子，共12组，各1亿步。仅翻转指定链的珠坐标次序，保持全部空间坐标、键长、弯曲几何和初始无头尾向列纹理不变，改变活性推进方向。aligned/balanced指初始方向制备，不是最终状态分类；所有构型重新赋予噪声、从数据文件开始，不是精确restart。此设计优先检验初始极性记忆；并未改变链长，不能据此单独证明链长控制或拓扑环绕机制。〔来源：prepare_followup.py、各provenance.json、validation.json。〕

启动约167秒时，n100约5400–5600步/秒，小球面约41000步/秒。若速度保持不变，dt=.005约11小时、dt=.0025约22小时（含预弛豫），小球面单组约40分钟，队列末两组约80分钟；短作业退出后大作业可能加快，当前只是早期估算。已建立每小时后续检查，完成后再统计种子误差并更新报告，不提前声称对照已经证明机制。〔来源：服务器log步数和launch.json时间。〕

## 如何收束研究主线

先用相同Q纹理下改变链极性的实验建立“纹理—运动解耦”的因果证据，再以半径、局部极性和额外缺陷对密度说明这种组织的适用范围；如果两种初始极性最终收敛，应转向“长寿命制备记忆及弛豫”，如果长期维持差异，则称“持久分支”，并用更多独立初态和转换统计检验多稳态。聚团可以作为相关现象，现阶段不应把MIPS作为论文成立的前提。〔数据依据：已有24组及本次对照设计；相关文献：上述Hsu等(2022)、Henkes等(2018)。〕
'''
(HERE/'report_progress_zh.md').write_text(report,encoding='utf-8');print('REPORT_WRITTEN',len(counts),len(t))
