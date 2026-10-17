# -*- coding: utf-8 -*-
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
HERE=Path(__file__).resolve().parent;OUT=HERE/'characterization';ROOT=HERE.parent
t=pd.read_csv(OUT/'time_window_metrics.csv');f=pd.read_csv(OUT/'fixed_scan_frames.csv');g=pd.read_csv(OUT/'grid_convergence.csv')
t=t[~((t.n==200)&(t.F==.003))].copy();f=f[~((f.n==200)&(f.F==.003))].copy() # Folder/input activity conflict: preserve raw exports, exclude parameter inference.
early=f[f.step<=100000000].groupby(['n','F','h'],as_index=False).agg(R=('R','mean'),Nplus=('Nplus','mean'),Nminus=('Nminus','mean'),pair_density=('pair_density','mean'),P4=('P4','mean'),frames=('step','count'));early.to_csv(OUT/'fixed_early_summary.csv',index=False)
strong=f[f.F==10].groupby(['n','h'],as_index=False).agg(R=('R','mean'),Nplus=('Nplus','mean'),Nplus_frame_sd=('Nplus','std'),pair_density=('pair_density','mean'),frames=('step','count'));strong.to_csv(OUT/'F10_fixed_size_summary.csv',index=False)
low=f[(f.n.isin([200,350]))&(f.F.isin([0,.03,.1,.3]))].copy();low['window']=np.where(low.step>=500000000,'late','early');ls=low.groupby(['n','F','h','window'],as_index=False)[['Nplus','pair_density','P4']].mean();ls.to_csv(OUT/'low_activity_fixed_summary.csv',index=False)
fig,axes=plt.subplots(1,3,figsize=(13,4))
for ax,h in zip(axes[:2],[1.5,3.]):
 a=early[(early.F>0)&(early.h==h)];im=ax.scatter(a.F,a.R,c=a.pair_density+1e-5,norm=LogNorm(1e-5,.02),s=28,cmap='viridis');ax.set_xscale('log');ax.set_xlabel('Activity F');ax.set_ylabel('Radius R');ax.set_title('Fixed grid: h=%g'%h);fig.colorbar(im,ax=ax,label='Pair density + 1e-5')
a=t[(t.window=='common')&(t.F>0)];im=axes[2].scatter(a.F,a.R,c=a.P4,vmin=0,vmax=1,s=28,cmap='viridis');axes[2].set_xscale('log');axes[2].set_xlabel('Activity F');axes[2].set_ylabel('Radius R');axes[2].set_title('Raw-field four-defect fraction');fig.colorbar(im,ax=axes[2],label='P4')
fig.tight_layout();fig.savefig(str(OUT/'01_parameter_maps.png'),dpi=180);plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(10,4))
for ax,n in zip(axes,[200,350]):
 for F in (0,.03,.1,.3):
  a=t[(t.n==n)&(t.F==F)&t.window.str.startswith('relative_decile')];ax.plot((a.t_start+a.t_end)/2/1e6,a.Nplus,'o-',label='F=%g'%F)
 ax.set_title('nchain=%d'%n);ax.set_xlabel('Physical time / 1e6');ax.set_ylabel('Raw-field mean positive defects');ax.legend()
fig.tight_layout();fig.savefig(str(OUT/'02_relaxation.png'),dpi=180);plt.close(fig)
sp=pd.read_csv(ROOT/'defect_dynamics_20261015/spatial_summary.csv');sp=sp[(sp.window=='matched')&(sp.F>0)];fig,axes=plt.subplots(1,2,figsize=(10,4))
for n in (10,30,50,100):
 a=sp[(sp.n==n)&(sp.four_geometry_frames>=3)].sort_values('F');axes[0].plot(a.F,a.pair_angle_deg,'o-',label='n=%d'%n);axes[1].plot(a.F,a.bipolar_moment,'o-',label='n=%d'%n)
for ax in axes:ax.set_xscale('log');ax.set_xlabel('Activity F');ax.legend()
axes[0].set_ylabel('Within-pair angle (degrees)');axes[1].set_ylabel('Largest defect-position moment eigenvalue');fig.suptitle('Conditional on four-defect frames; raw marker geometry');fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(str(OUT/'03_pair_geometry.png'),dpi=180);plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(10,4))
for h in (1.5,3.):
 a=strong[strong.h==h].sort_values('R');axes[0].plot(a.R,a.Nplus,'o-',label='h=%g'%h);axes[1].plot(a.R,a.pair_density,'o-',label='h=%g'%h)
axes[0].set_ylabel('Mean positive defects');axes[1].set_ylabel('Excess pair density')
for ax in axes:ax.set_xlabel('Radius R');ax.legend();ax.set_title('F=10, same 11 late snapshots')
fig.tight_layout();fig.savefig(str(OUT/'04_size_scaling.png'),dpi=180);plt.close(fig)
def table(d):
 return '| '+' | '.join(d.columns)+' |\n|'+'|'.join(['---']*len(d.columns))+'|\n'+'\n'.join('| '+' | '.join('%.5g'%v if isinstance(v,(float,np.floating)) else str(v) for v in r)+' |' for r in d.itertuples(index=False,name=None))
text='''# 半径—活性—缺陷演化：现有数据表征与补算

## 本次工作范围

对155条计数序列重新按物理时间统计共同窗口、各自后半段和10个等长时间段，共1860行统计；核对输入中的驱动、运行段及初始数据哈希。155组坐标完成固定球面L5网格、h=1.5/3两尺度识别，共1154次；F=10各尺寸用相同11个晚期快照，n200/350低活性另外补6个晚期快照，其余参数一般只取3个共同窗口快照，属于全扫描初筛，不是充分采样的稳态相图。另对n100/350、F10的相同三帧检查L4/L5/L6，共36次。〔文件：input_audit.json、time_window_metrics.csv、fixed_scan_frames.csv、grid_convergence.csv。〕

## 结论一：强活性缺陷总数增加，但面密度不是严格单调

参数审计另发现nchain200/F_0.003_cpu2_2的文件夹标记F=.003，但保存的bd.in生产段为F=.1，目录没有原始log.lammps，无法判断是标签错误还是输入后来修改。原始导出保留该点，参数汇总与图1排除，不擅自改标为.1。n50/F7的dt=.01已由保存的bd.in核实，但原始审计表仍保留当时unverified_default来源以记录初次处理。〔来源：对应bd.in、input_audit.json。〕

F=10相同时间5×10^7—10^8步的11个构型，固定物理平滑长度后的结果如下。rho_pair只计额外正负缺陷对：Nminus/(4*pi*R²)。两种h均显示明显的总数增长，小球面接近四缺陷底数；面密度在n100—200附近并非逐点增加，随后较大尺寸有所增加。旧原始标记得到的“全尺寸严格单调面密度”没有通过当前尺度复核，应撤回该强表述。现阶段是有限采样的总体尺寸趋势，不能拟合普适指数。〔数据：F10_fixed_size_summary.csv；参考：R2。〕

'''+table(strong[['n','R','h','Nplus','pair_density','frames']])+'''

![尺寸效应](04_size_scaling.png)

L5→L6在同三帧中，n100/h1.5平均N+为18.67→18.33，n350为74.67→74.00；h3两尺寸均不变。说明这两处网格加密的平均计数变化较小，但只是空间试验，不认证全部参数收敛，也不消除平滑尺度定义本身的差异。所有扫描带电面均为半缺陷，未出现合并高阶面荷。〔数据：grid_convergence.csv、fixed_scan_frames.csv。〕

## 结论二：低缺陷窗口有时间依赖，尚无普适最优F

n350原计数F=.03/.1/.3在早期共同窗口的N+为42.59/37.78/15.82，晚期为19.88/7.24/10.69；不同观察窗口下排序改变。固定网格的抽样也支持该现象：h1.5早期F=.1/.3为12.33/11.00，晚期为4.83/6.83；h3早期8/7，晚期4.50/5.17。与此同时，n200晚期h3的.03/.1/.3分别为4.17/4.50/4.33，几乎都接近四缺陷，不能给出统一且精确的最优活性。不能把稀疏快照间的小差异称为显著。〔数据：low_activity_fixed_summary.csv、time_window_metrics.csv；参考：R4。〕

![弛豫](02_relaxation.png)

输入审计发现n200和350的这些低活性任务先在F=1下运行1000万步，再切换目标活性，且随机种子独立；因此不是同一初态上的单变量活性扫描。长时变化可能含有驱动切换后的结构弛豫。审计记录来自保存的输入文件，若输入后来编辑过还需与原日志逐项核对。计数自相关时间只作为波动指标，不能在非平稳序列上直接叫物理弛豫时间；nonstationary_flag仅为首末块差异的启发式筛查，不是显著性检验，更不能由未触发标志证明平稳。〔文件：input_audit.json、time_window_metrics.csv。〕

## 结论三：四缺陷结构随活性变化，并非统一的两极配对

n10共同窗口F=.1/.3/10的条件配对角约39/90/28度，缺陷位置二阶矩最大特征值约.884/.504/.930。说明既有紧配对，也有更展开的四缺陷结构。后续应比较相同R/F重复的配对角分布和时间相关，而不是从一张投影截图判断状态。原位置分析来自粒子网格，图3为该条件统计；固定网格逐帧输出亦保存配对几何以便稳健性比较。四缺陷占比必须同时报告。〔数据：原spatial_summary.csv、本次fixed_scan_frames.csv；参考：R1、R3、R5。〕

![参数初筛](01_parameter_maps.png)

![四缺陷条件几何](03_pair_geometry.png)

## 缺失数据与已提交补算

缺口是同一起点的独立重复，而非继续密集增加F点。已于2026-10-16 13:16（UTC+8）提交24组：n200和350，F=0/.03/.1/.3，各3种子。每个尺寸全部从同一个现有F0轨迹第10亿步坐标开始，保留已有几何，仅重置速度并赋新噪声；不再进行不同活性预弛豫。初态是被动驱动下已演化构型，不保证达到平衡，跨R也不是等缺陷密度初态，因此优先回答同R内的活性效应及其在两R的差异，不把它当纯曲率因果实验。不是精确restart。〔任务：sphere_relaxation_20261016/manifest.json；脚本：prepare_relaxation.py。〕

每组dt=.01、生产10亿步，对应物理时间10^7，分10段各1亿步，保存milestone文件以提前分析；每10万步输出坐标、每1000万步双备份restart。F0组三个种子提供被动基线，检查缺陷降低是否超出继续被动弛豫。保持原WCA/FENE/cosine以及bd/sphere唯一积分器和冻结二进制。8个参数组合短跑2万步通过，无ERROR、Lost atoms或FENE警告，初态最大键长n200约1.113、n350约1.124。〔文件：各in.production、in.smoke、provenance.json及服务器smoke.log。〕

启动时新组13运行、11排队，与旧dt=.0025的3组合计16组、32个MPI进程。运行器按全服务器lmp进程余量启动，不超过32；PID401242。服务器新目录/home/user/wxd/9.19.2026/sphere_relaxation_20261016。短测n200约4500步/秒、n350约2500步/秒，对应单组10亿步理想估计约62/111小时，满负载、文件输出和排队会延长，完成时间需以持续运行速度更新。已有监控扩展为两批任务，1亿步里程碑后即可先分析，不等全部结束。〔来源：2026-10-16服务器短测及启动记录。〕

## 下一步工作与可用结论

先依据现有参数初筛，集中比较两R下四个F的Nminus(t)、相同物理时间的rho_pair、P4和配对角。每个种子先做时间统计，再报告种子间标准差；低缺陷窗口随时间和R变化为首要问题。若三种子仍在漂移，报告弛豫而不是稳态低谷；若出现可重复的晚期分离，再在相邻F间少量加点。短步长三组完成后更新强活性数值验证。现有数据支持尺寸相关的多缺陷结构和时间依赖低缺陷窗口，不支持普适最优F、严格单调面密度、纯曲率机制、MIPS或已收敛的缺陷寿命/事件率。〔依据：上述表征及前轮数值复核。〕

## 参考文献

沿用已核验期刊文献；R1及R4为高引基础工作，其余优先考虑与球面和链模型的直接关联，不声称全部被引超过100次。文献元数据及链接详见../research_focus_zh.md。〔来源：期刊、PubMed及已有核验记录。〕

- R1. F. C. Keber et al. Topology and dynamics of active nematic vesicles. Science 345,1135–1139 (2014). https://doi.org/10.1126/science.1254784
- R2. S. Henkes; M. C. Marchetti; R. Sknepnek. Dynamical patterns in nematic active matter on a sphere. Physical Review E 97,042605 (2018). https://doi.org/10.1103/PhysRevE.97.042605
- R3. R. Zhang; Y. Zhou; M. Rahimi; J. J. de Pablo. Dynamic structure of active nematic shells. Nature Communications 7,13483 (2016). https://doi.org/10.1038/ncomms13483
- R4. L. Giomi; M. J. Bowick; X. Ma; M. C. Marchetti. Defect Annihilation and Proliferation in Active Nematics. Physical Review Letters 110,228101 (2013). https://doi.org/10.1103/PhysRevLett.110.228101
- R5. A. T. Brown. A theoretical phase diagram for an active nematic on a spherical surface. Soft Matter 16,4682–4691 (2020). https://doi.org/10.1039/D0SM00166J
'''
(OUT/'report_zh.md').write_text(text,encoding='utf-8');print('REPORT_COMPLETE',len(t),len(f))

