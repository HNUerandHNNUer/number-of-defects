# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent/'dt_matched_20261016';s=pd.read_csv(P/'seed_summary.csv');g=s.groupby(['dt','h']).agg(['mean','std'])
fig,axes=plt.subplots(1,3,figsize=(11,3.6))
for h in (1.5,3.):
 a=g.xs(h,level='h');axes[0].errorbar(a.index,a.Nplus['mean'],yerr=a.Nplus['std'],fmt='o-',capsize=4,label='h=%g'%h)
a=g.xs(1.5,level='h')
for q in ('P','S'):axes[1].errorbar(a.index,a[q]['mean'],yerr=a[q]['std'],fmt='o-',capsize=4,label=q)
axes[2].errorbar(a.index,a.cv3['mean'],yerr=a.cv3['std'],fmt='o-',capsize=4)
for ax in axes:ax.set_xlabel('dt');ax.set_xticks([.0025,.005,.01]);ax.ticklabel_format(axis='x',style='plain')
axes[0].set_ylabel('Positive defects');axes[0].legend();axes[1].set_ylabel('Local order');axes[1].legend();axes[2].set_ylabel('Density CV (cap radius 3)');fig.suptitle('Same 11 physical times; error bars: SD across 3 seed means');fig.tight_layout(rect=[0,0,1,.91]);fig.savefig(str(P/'matched_dt.png'),dpi=180)
lines=[]
for (dt,h),a in g.iterrows():lines.append('| %.4f | %.1f | %.2f ± %.2f | %.3f ± %.3f | %.3f ± %.3f | %.3f ± %.3f |'%(dt,h,a[('Nplus','mean')],a[('Nplus','std')],a[('P','mean')],a[('P','std')],a[('S','mean')],a[('S','std')],a[('cv3','mean')],a[('cv3','std')]))
text='''# nchain100、F=5：三个步长的等物理时间阶段验证

本次比较dt=.01/.005/.0025，每个步长3种子；使用完全相同的11个物理时刻t=250000,300000,...,750000。每个种子先对这11帧取平均，再报告3个种子均值的均值和样本标准差（不是SEM，也不是显著性检验）。旧npz的step为t/.01，新抽取dt=.0025的step为实际步数，代码显式换算并断言每个目标时刻恰好存在一帧。固定球面网格均为L5、物理平滑长度h=1.5和3，共198条结果。〔文件：dt_matched.py、frames.csv、seed_summary.csv。〕

| dt | h | N+ | 局部P | 局部S | 密度CV |
|---|---|---|---|---|---|
'''+ '\n'.join(lines)+'''

P/S和密度CV使用相同方法，各h行重复同一数值；h只改变缺陷识别。密度CV为物理半径3球冠内粒子数的空间变异系数，不是MIPS判据。所有帧拓扑净荷检查通过。〔方法：固定网格detect与现有local/GRID函数；数据：frames.csv。〕

阶段结论：三个步长在两个识别尺度的平均缺陷数均接近，未见随步长缩小而持续下降的趋势；局部S约.81–.82、密度CV约.21–.22。因而当前多缺陷状态在缩小步长后仍保留，不能归因于dt=.01独有的数值假象。P均值存在一定差别，且仅3种子；这些结果支持定性稳健性，不认证全部动力学量或事件率收敛。〔数据：上表及种子统计。〕

![等时刻比较](matched_dt.png)

这是生产物理时间25万至75万的阶段统计，尚未覆盖最终目标100万；不同dt是独立噪声和各自预弛豫，不是配对随机轨迹。不能由误差条重叠宣布统计等效，也不能由三种子均值的少量变化推断单调步长偏差。具体趋势应结合表中种子离散度；最终完成后补齐相同后75%及后半段窗口，并增加时间采样验证。〔依据：运行设计与当前数据覆盖。〕

截至2026-10-16 18:14（UTC+8），dt=.0025三组分别运行32683万、33126万、34083万步，目标40000万步；当前未发现ERROR或FENE警告。dt=.005完成组三种子中已有1次FENE警告，dt=.01旧组已有15次；这些为不同已运行时长的累计数，不能直接当等时间警告率，也不能将未出现警告理解为严格数值收敛。〔来源：本次服务器日志与此前完成审计。〕

此次检验服务于半径—活性—缺陷主线：判断强活性多缺陷现象是否依赖大步长。低活性24组继续运行，仍按同R相同初始几何、F0基线、相同物理时间和多尺度识别比较；无须新增任务。已观察到的低缺陷窗口保留为有限时间结果，不把预运行设置本身当作否定理由，后续以截尾后的时间漂移判断平稳性。〔关联报告：../progress_20261016_1716/report_zh.md。〕
'''
(P/'report_zh.md').write_text(text,encoding='utf-8');print('\n'.join(lines))
