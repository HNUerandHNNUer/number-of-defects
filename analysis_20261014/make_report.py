# -*- coding: utf-8 -*-
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=Path(__file__).resolve().parent
a=pd.read_csv(OUT/'audit.csv');s=pd.read_csv(OUT/'spatial.csv')
fig,axs=plt.subplots(1,3,figsize=(15,4.3))
for n in [150,200,250,300,350]:
 d=a[(a.label==n)&(a.F>0)].sort_values('F');actual=int(d.actual_chains.iloc[0]);lab=f'{n} folder (actual {actual})'
 color={150:'tab:blue',200:'tab:orange',250:'tab:green',300:'tab:red',350:'tab:purple'}[n]
 axs[0].plot(d.F,d.mean75,'o-',ms=3,label=lab,color=color)
 d=d[d.F<=.5];axs[1].plot(d.F,d.mean75,'o-',ms=3,label=lab,color=color);axs[1].plot(d.F,d.mean25,':',lw=1,color=color)
for n in [200,250,350]:
 d=s[(s.label==n)&(s.F==10)].groupby('ell').Nplus.mean();axs[2].plot(d.index,d.values,'o-',label=f'folder {n}')
for ax in axs[:2]:ax.set_xscale('log');ax.set_xlabel('Input active force F (Pe conversion not verified)');ax.set_ylabel('Mean positive half-charge count');ax.legend(fontsize=7)
axs[0].set_title('Recomputed, last 75% of frames')
axs[1].set_title('Solid: last 75%; dotted: last 25%')
axs[2].set_title('F=10: 3 late snapshots per system');axs[2].set_xlabel('Gaussian smoothing length');axs[2].set_ylabel('Mean positive half-charge count');axs[2].legend(fontsize=8)
fig.tight_layout();fig.savefig(OUT/'audit_summary.png',dpi=160);plt.close(fig)
refs=json.loads((OUT/'references_verified.json').read_text())
reftext=[]
for i,r in enumerate(refs,1):
 authors='; '.join(x.get('given','')+' '+x.get('family','') for x in r['authors'])
 year=r['year']['date-parts'][0][0]
 reftext.append(f"[{i}] {authors}. **{r['title'][0]}**. *{r['journal'][0]}*, {year}, {r.get('volume','')}, {r.get('pages') or {'10.1103/PhysRevE.97.042605':'042605','10.1038/s41467-022-30128-7':'2579','10.1103/PhysRevX.5.031003':'031003'}.get(r['doi'],'')}. https://doi.org/{r['doi']}。OpenAlex 被引数：{r.get('openalex_citations','查询失败')}；Crossref 被引数：{r.get('crossref_citations','未知')}。")
report='''# 球面活性链缺陷数据审计（2026-10-14）

**主要结论：nchain250 实际是 150 条链；高活性数量倒置主要是标签错误。0.1 附近存在有限观测时间下的缺陷低谷，但稳态非单调性尚未证实。缺陷计数对粗粒化强烈敏感，应先明确物理测量尺度。**

## 数据范围与证据

检查九个 nchain 目录下 172 个直接 F_* 目录，读取可用的 defect_results.dat、polymer.data、日志前段及输出坐标；重新计算后75%、后50%、后25%均值。统计不覆盖嵌套 go_on/test/cpu* 续跑目录，也未直接解析 Origin 的 opju 内部工作表。截图数值用现有汇总文件及原始计数交叉核对。22 段可读视频各抽取5个分布于全程的位置（5%、25%、50%、75%、95%），共110张；是抽帧检查，不是逐帧动力学跟踪。nchain350 未找到这些命名的视频，高活性空间判断使用其原始输出坐标。全部原数据未改写。[数据来源：audit.csv、video_metadata.json、video_*.jpg；无需文献支持。]

## 1. “200比250多”的原因已找到

nchain250 下16个 F_* 目录的 polymer.data、运行日志和 defect_out 真实粒子坐标一致：4500粒子，每链30珠，即150条链，R≈20.045。nchain200 对应6000粒子、200条链、R≈23.146。不是仅文件头写错：日志实际读入数与输出中的type=1粒子数均一致。nchain150 是另一组同尺寸数据；不能把 nchain250 曲线继续当作 R 更大的结果。[数据来源：nchain250/F_10_cpu3/polymer.data 第1–5行、log.lammps 第28–29行、defect_out；全部16个活性的核验见audit.csv。]

|目录标签|实际链数|半径|F=10，后75%平均 N+|N+/(4πR²)|
|---|---:|---:|---:|---:|
|150|150|20.045|146.76|0.02907|
|200|200|23.146|198.79|0.02953|
|250|150|20.045|142.50|0.02822|
|300|300|28.348|321.09|0.03180|
|350|350|30.619|389.85|0.03309|

200/“250”的数量比为1.395，面积比为1.333，面积归一化后差约4.6%。所以无需用受困态解释这一倒置。150与“250”在F=10的均值也仅差约2.9%。此处不能证明所有活性下密度严格一致，更不能把剩余差异直接判作曲率效应。[数据来源：audit.csv；理论背景：[9] Giomi, Physical Review X (2015), https://doi.org/10.1103/PhysRevX.5.031003。]

截图纵轴约199、143对应 N+，不是正负总数；对应总数约393.58、281.01。若只有±1/2缺陷且场覆盖整个球面，则N+−N−=4，Ntotal=2N+−4。建议纵轴明确标注 N+，或重新绘制总数。输入参数是F；本次未找到并验证Pe换算定义，因此不把F与Pe无条件等同。固定舍弃25%不是稳态检验，原文件误差为原始帧SD，不是SEM。[数据来源：average_defects.py、nchain200/10.txt、nchain250/10.txt；球面拓扑背景：[1] Keber等, Science (2014), https://doi.org/10.1126/science.1254784。]

## 2. 0.1附近低谷：有迹象，但包含明显弛豫偏差

|真实体系（目录）|F=0.03 后75%/末25%|F=0.1 后75%/末25%|F=0.3 后75%/末25%|
|---|---:|---:|---:|
|150（150）|9.04 / 7.59|5.47 / 5.87|9.48 / 9.23|
|200（200）|17.50 / 12.91|8.84 / 8.70|9.46 / 10.15|
|150（250）|14.70 / 10.58|6.58 / 7.07|7.77 / 8.73|
|300（300）|23.42 / 14.43|9.52 / 11.27|12.26 / 13.67|
|350（350）|23.31 / 17.19|7.30 / 8.88|12.48 / 10.93|

这些数据不支持“在整个活性范围内缺陷数已经被证实单调增加”。但也不能据此宣布稳态最佳活性恰为0.1。F=0.03、nchain200四个连续四分之一时间段均值为37.16→23.06→16.54→12.91，300为40.13→31.36→24.48→14.43：明显仍在老化/弛豫。已有时间曲线实际存在持续下降，只是在特定活性和时间尺度上更显著。nchain200/F=0.003仅到1.278×10^8步，与其他低活性常见的10^9步不同，且其目录标有_2；不能直接视作同历史、同观测时长的稳态比较。[数据来源：audit.csv、time_comparison.png、nchain200/0.003.txt。]

合理但未证实的机制是弱驱动帮助初始多畴结构重排和缺陷相遇，中高驱动则维持产生—湮灭过程。低活性长寿命纹理与此相容。计数不再下降只能说明该标量没有明显漂移，不能区分持续更新的动态稳态与寿命很长的亚稳结构；需要缺陷轨迹、寿命、生成/湮灭率、取向相关函数和初态依赖。不能只由N(t)给出受困态诊断。[参考：[3] Giomi、Bowick、Mishra、Sknepnek、Marchetti, Defect dynamics in active nematics, Philosophical Transactions of the Royal Society A 372, 20130365 (2014), https://doi.org/10.1098/rsta.2013.0365。]

建议先统一真实链数、识别尺度和初态，再在F=0.05、0.07、0.15、0.20补点，保留0.03、0.1、0.3作为锚点；先选真实nchain200和350，至少3个独立种子，关键点优先5个。对0.03延长原轨迹，并从0.1已重排构型降到0.03，与从原始构型启动的结果比较；反向升驱动也做，以检查历史依赖。若最终同一F不同初态收敛，低谷仍显著，才支持稳态非单调性。先做这些比把0.03–0.3均匀密集扫很多单次轨迹有效。误差以独立重复均值为主要单位；单轨迹须检查分块长度/自相关，不能将全部帧视为独立样本。[性质：基于上述数据的实验设计建议；机制背景同[3]。]

## 3. 缺陷计数尺度比继续拟合曲线更优先

本地算法默认smooth_k=0，以每个珠子的链切向构造球面三角网绕转；跨稀疏区的三角形会延拓取向场。对200、目录250、350的F=0.1和10，各取50%、75%、100%时刻，共18帧，复算未平滑计数与已有type=2标记完全一致。使用代码已有平行输运Q粗粒化（128邻居，高斯长度1、2、3，单位为原始坐标长度）得到以下F=10三帧平均值：

|目录|原始|长度1|长度2|长度3|
|---|---:|---:|---:|---:|
|200|188.3|55.0|22.3|14.3|
|250（实际150）|128.7|47.3|23.7|17.0|
|350|397.0|110.0|57.3|35.7|

这证明观测量强烈依赖分辨尺度，并不证明被滤掉的都是“假缺陷”：粗粒化也会抹掉真实近邻缺陷对。应报告N(ell)、正负对间距、缺陷寿命及与局部Q低序核的对应，寻找与珠径、链长、缺陷核尺度相容的稳定区间。不能任意挑一个较平滑结果代替原数据。高活性时净拓扑荷仍为+2只证明完整离散延拓场的拓扑一致性，不证明空洞中的每个标记都是有序材料内的物理核。[数据来源：spatial.py、spatial.csv、nchain200/sphere_nematic_parallel.py；物理背景：[1]、[3]、[5]。]

## 4. 相分离与创新方向

22段视频抽帧表现出低活性较持久的排列纹理、较高活性下的重排及密度不均匀。用4096个等面积球面采样点、物理测地半径3的球冠粒子密度，在上述18帧中得到密度变异系数：200由F=0.1的0.078升至F=10的0.281；目录250由0.075至0.260；350由0.079至0.273。这支持活性增强密度非均匀，但仅三帧不足以证明相共存、宏观相分离或MIPS；高活性这些样本的指标也不随R单调增加。需P(rho)、球谐低阶结构因子、团簇尺度随R的标度、长时粗化及局部速度—密度关系。巨数涨落、瞬态聚团、运动带和宏观相分离应区分。[参考：[4] Cates与Tailleur, Motility-Induced Phase Separation, Annual Review of Condensed Matter Physics 6, 219–244 (2015), https://doi.org/10.1146/annurev-conmatphys-031214-014710；[8] Sinha与Chaudhuri, Soft Matter 20, 8078–8088 (2024), https://doi.org/10.1039/D4SM00775A。]

**最优先候选：球面上密度空洞、界面与缺陷之间的拓扑荷分配。** 已有研究报告相分离活性聚合物中的凝聚型−1/2缺陷，因此“相分离伴随缺陷”本身不是空白。你的推进方向可为：曲率是否改变正负缺陷与高密度区/界面的相关性？带状结构断裂、空洞合并前后，材料区的缺陷与边界绕转怎样共同改变？逐事件统计条件密度、局部Q、界面曲率和延迟相关，先证明事件排序，再考虑机制。真实空洞意味着材料有序域不再是完整闭球面，不能只对材料内核强套净荷+2；需要边界项。上述是待验证课题，不是已从视频证明的创新。[参考：[5] Krüger、Maryshev、Frey, Hierarchical defect-induced condensation in active nematics, Soft Matter 19, 8954–8964 (2023), https://doi.org/10.1039/D3SM00895A；[2] Henkes、Marchetti、Sknepnek, Physical Review E 97, 042605 (2018), https://doi.org/10.1103/PhysRevE.97.042605。]

**第二候选：曲率依赖的有限时间退火窗口，是否跨越为稳态缺陷最小值。** 测N(t;F,R)和弛豫时间，改变观测时长，考察低谷位置Fmin(R,Tobs)是否移动；比较初态、升降驱动、刚度。若低谷仅是不同弛豫速率造成，也可以形成清楚的动力学结果，不能包装成稳态相变。球面上振荡、极性带、折叠带与缺陷增殖已有先例，所以需给出新的定量标度或机制。[参考：[2] Henkes等, Dynamical patterns in nematic active matter on a sphere (2018), https://doi.org/10.1103/PhysRevE.97.042605；[6] Hsu、Sciortino、de la Trobe、Bausch, Activity-induced polar patterns of filaments gliding on a sphere, Nature Communications 13, 2579 (2022), https://doi.org/10.1038/s41467-022-30128-7。]

**第三候选：柔性链弯折与介观缺陷的尺度分离。** 当前高活性计数对ell显著敏感，可测链的测地弯曲、端到端长度、局部向列相关长度与缺陷对尺度，判别驱动主要增加链尺度绕转还是长寿命介观缺陷。用测地弯曲而非仅三维总曲率，避免球面固有法向弯曲造成尺寸混淆。改变角刚度并与平面或不同几何对照；固定覆盖率改变R也改变总粒子数，单靠现有球面尺寸扫描无法完全分离曲率与有限尺寸效应。[参考：[7] Dunajova等, Chiral and nematic phases of flexible active filaments, Nature Physics 19, 1916–1926 (2023), https://doi.org/10.1038/s41567-023-02218-w。]

## 文献核验与限制

学术检索MCP本次未提供，使用期刊/作者机构/PubMed/arXiv网页检索，再通过Crossref DOI接口逐条核实元数据、OpenAlex查询引文数。9篇Crossref全部成功；Hsu等的OpenAlex请求SSL失败，保留Crossref计数。引用量是2026-10-14查询返回的数据库值，存在收录滞后，不代表实时全库或WoS/Scopus计数。优先采用高引基础文献，同时保留高度相关但低引论文用于避免误判创新；未把低引文献说成100次以上。没有完成穷尽性新颖性检索，因此不声明任何候选方向“无人研究”。

'''
(OUT/'report_zh.md').write_text(report+'\n\n'.join(reftext)+'\n',encoding='utf-8')
print('report and figure saved')
