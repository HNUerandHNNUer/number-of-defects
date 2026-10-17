# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent/'dt_final_20261016';s=pd.read_csv(P/'seed_summary.csv');g=s.groupby(['dt','h']).agg(['mean','std'])
fig,axes=plt.subplots(1,3,figsize=(11,3.6))
for h in (1.5,3.):
 a=g.xs(h,level='h');axes[0].errorbar(a.index,a.Nplus['mean'],yerr=a.Nplus['std'],fmt='o-',capsize=4,label='h=%g'%h)
a=g.xs(1.5,level='h')
for q in ('P','S'):axes[1].errorbar(a.index,a[q]['mean'],yerr=a[q]['std'],fmt='o-',capsize=4,label=q)
axes[2].errorbar(a.index,a.cv3['mean'],yerr=a.cv3['std'],fmt='o-',capsize=4)
for ax in axes:ax.set_xlabel('dt');ax.set_xticks([.0025,.005,.01]);ax.ticklabel_format(axis='x',style='plain')
axes[0].set_ylabel('Positive defects');axes[0].legend();axes[1].set_ylabel('Local order');axes[1].legend();axes[2].set_ylabel('Density CV (cap radius 3)');fig.suptitle('Same 16 physical times; error bars: SD across 3 seed means');fig.tight_layout(rect=[0,0,1,.91]);fig.savefig(str(P/'matched_dt.png'),dpi=180)
lines=[]
for (dt,h),a in g.iterrows():lines.append('| %.4f | %.1f | %.2f ± %.2f | %.3f ± %.3f | %.3f ± %.3f | %.3f ± %.3f |'%(dt,h,a[('Nplus','mean')],a[('Nplus','std')],a[('P','mean')],a[('P','std')],a[('S','mean')],a[('S','std')],a[('cv3','mean')],a[('cv3','std')]))
text='''# 三步长完成验证（2026-10-16 22:29 UTC+8）

18组followup全部完成。新dt=.0025三个种子均400000000步，final.bin及完成标记齐全，无ERROR、Lost atoms及FENE警告。旧dt=.005一组有1次FENE警告，另两组无；旧dt=.01三组共15次，均作为带警告结果保留。

## 相同物理时刻比较

nchain100、F5，三步长各3种子，在t=250000至1000000每50000取一帧，共16帧/种子，L5网格、h1.5/3。覆盖生产后75%的抽样，非全部帧的连续时间均值。先按种子平均，再报告种子间样本标准差，不是SEM。新npz使用实际步数，旧npz使用t/.01归一化步数，脚本显式转换并核对时刻。

| dt | h | N+ | P | S | density CV |
|---|---|---|---|---|---|
'''+ '\n'.join(lines)+'''

三个步长在两个尺度上的平均缺陷数接近，没有随dt缩小而持续减少的趋势。局部S约.81–.82，密度CV随dt缩小从.222降至.211，约5%的变化；目前三种子样本不足以认证统计等效。支持多缺陷状态的定性稳健性，不证明事件率、寿命或所有观测量严格收敛。此验证限于n100/F5，不能直接认证其他半径与更强活性。

![三步长比较](matched_dt.png)

## FENE警告与时间窗口

日志核对表明警告均在生产reset之后、生产前25%内。dt=.01的r1共14条（t约218312–218583），r2为1条（t19781），r3为0；dt=.005的r1为1条（t239916.62），其余为0；dt=.0025全部0。以每种子生产时长1000000计，合并三种子的每百万物理时间警告条数为5、0.333、0。后75%对应的警告条数率三种dt均为0。这是日志条数率，多条可能是同一键连续截断，不能当独立物理事件率。没有ERROR/Lost atoms。

截去前25%后无新增警告，不等于早期截断对后续构型绝无影响；独立种子及独立预弛豫也不是配对噪声或精确restart。上述误差条不能作为严格等效检验。

## 当前任务状态与后续

新24组弛豫任务16运行8排队，共32个lmp进程。n200最先进约8761万步，尚无1亿步milestone；n350最先进约4947万步。当前无ERROR/Lost atoms/FENE，未达到全部结束条件，保留监控。达到1亿步后更新Nminus、密度、P4、配对角和漂移，不重启或覆盖现有轨迹。

文件：frames.csv（288条）、seed_summary.csv、group_summary.csv、dt_final_warning_audit.json；脚本../dt_final.py、../report_dt_final.py。全部数据均来自本地坐标后处理和服务器日志，本报告未新增文献机制主张。
'''
(P/'report_zh.md').write_text(text,encoding='utf-8')
