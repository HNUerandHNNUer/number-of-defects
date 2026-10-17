# 球面长链活性体系：本地诊断与文献核验

分析日期：2026-10-12。原始模拟输入、fix 与识别程序均未修改。分析依据为七组 polymer.data、defect_results.dat、bd.in、log.lammps，以及六个 AVI 的抽样帧。

## 主要发现

- 300 个珠子，10 条链，每条 30 珠；名为 nchain10 的目录表示链数量，不能据此认为链长为 10。
- fix 名义半径 R=15.350984/2−2.5=5.175492；初始平均半径约 5.1756。链平均轮廓长度 27.78–27.83，大圆周长约 32.52；L/R≈5.37。
- 七组初态用当前代码识别均为四个 +1/2，并且相对最佳环流轴呈现两侧各两个。0.1、0.17、0.55、1、5 的初始数据逐字节相同；0.3、3 使用另一相同初态。
- 当前初态的周向向列指标 B=mean[2(d·e_phi)^2−1] 分别约 0.859 和 0.566。这里的轴是 mean(d d^T) 最小特征值对应的方向，是解释性拟合轴，不是唯一严格最优 B 轴。极区缺陷位置依据球面三角形重心，不能替代真实核定位。
- 各组缺陷统计以四个缺陷为主，但全部存在统计上报告的额外正负对。数据中未存储每一帧坐标和诊断，因此不能确认这些短寿命对全是物理核。
- 持续旋转的直接驱动来自沿链编号方向的有向推力；弯曲链可提供总活性力矩。第一类初态每单位 F 的总力矩为 (398.409, −109.515, −235.104)，第二类为 (−302.852, 638.731, −773.283)，不是零。
- LAMMPS 日志所有组均报告 No fixes with time integration。所给 fix 已注册位置与速度回调，但构造函数未设置 time_integrate=1；此标志缺失不能推出粒子没有运动，也不应因此再加一个 nve 积分器。
- 当前识别包含球面 Levi-Civita 平行输运与固体角修正；整体刚体旋转及 director 符号翻转测试均通过。第一类初态最大网格边长 39.54°，第二类 22.67°。这不是缺陷核精度证书。
- 当前 XYZ 的标记位于归一化三角形重心，delaunay.dat 的位置位于球面外心；第一类初态两种位置定义差约 5–14°。不得混用两种位置轨迹。AVI 与所给代码的历史版本关系无法仅凭现有文件确认。
- 0.1、0.17、0.55、1 运行 1e8 步；0.3、3、5 运行 1e9 步。视频均 10 fps，但代表的模拟时间范围不同。

## 文件与复现

- summary.csv：逐组帧比例、缺陷均值及初始长度指标。统计包含第 0 帧；不是独立样本置信区间。
- initial_and_counts.json：初始文件 SHA256、拟合轴、四缺陷位置、核验诊断及初始活性力矩。
- kernel_checks.json：两类初态的旋转、符号对称性验证与位置定义差异。
- video_samples.jpg / video_metadata.json：抽样视频帧及帧数、播放速度。
- initial_geometry.png / defect_statistics.png：初始链排布与存储帧缺陷统计。
- verified_references.json：Crossref/OpenAlex 原始核验结果。Crossref 对三篇请求返回 429；这些文章的正式标题和出版信息另由出版社/作者机构库核实。OpenAlex 日期有时是接收/在线日期，正式引用采用出版版年份。

脚本位于父目录：analysis_sphere_local.py、sphere_analysis_checks.py、sphere_refs_verify.py、sphere_video_samples.py。前两者需 NumPy/SciPy/Matplotlib；视频脚本使用 bundled Python，并从本目录 video_runtime 加载隔离的 OpenCV。文献核验需要联网。引用数按 2026-10-12 查询的 OpenAlex 口径记录，不等于 WoS/Scopus 的被引数。

## 可检验机制与分析方案

当前证据最支持“初始已建立的长链周向纹理，在活性力矩驱动下持续运动”的解释。有限尺寸、长链弯曲刚度、排斥导致的重排障碍、局部极性排序都可能维持这类状态，但现有资料尚不足以决定它是唯一吸引子、稳定旋转态、多稳态还是初态记忆。球面均匀高斯曲率没有指定南北轴，任何选定的环流轴均可定义两个极点。

拓扑只规定总电荷 +2，不能选择四缺陷四面体或两极构型。标准被动薄向列、单弹性常数条件下四个 +1/2 的四面体通常优于两个 +1；本体系不能把活性配对归因于同号缺陷的被动相吸。若一圈同时包围两枚 +1/2，总环绕数为 +1，但这不表示两个微观核真正合并。若极区近乎空白，必须在有可靠向列序的边界上算电荷，不能把稀疏插值点当作精确缺陷核。

建议恢复原始 out-*.xyz 或更频繁轨迹后，计算：

1. 共转坐标。由粒子位移（非布朗算法每步瞬时速度）拟合 v_i≈Ω×r_i；A=sum(r_i² I−r_i r_i^T)，Ω=A^−1 sum(r_i×v_i)。初态及无噪声无钳制情形满足 γAΩ=τ_active。有限时间速度可用相邻帧球面位移估计，帧间隔应远小于旋转周期且先做展开/配准。测实际 Ω(F)，不要把初态力矩预测冒充稳态速度。
2. 缺陷相对几何。只在四 +1/2 无负缺陷帧比较三种匹配 (12|34、13|24、14|23)；取总球面距离最小的匹配，记录两个对内间距、对中心夹角和六个 pair angle。追踪时需要时间连续性，不可每帧任意交换标签。对中心取 unit(u_i+u_j)，对跖边界异常单独处理。
3. 局部而非全局极性。在各测点切平面中平行输运后分别构造 p=<t> 与 Q=<t t−P/2>，P=I−u u^T。全局 mean(t) 可因环流抵消，即使局部极性很强；不宜单用全局极性均值判断是不是极性带。同步测表面密度、周向向列序及环流。
4. 缺陷谱。分别测 n_+、n_-、产生率、湮灭率、寿命、polar cap density 与共转系扩散。仅有半整数基本核时 n_+−n_-=4。所有位置/寿命结果要通过 Q 粗粒化长度、采样密度及时间分辨率的敏感性检查。
5. 干预实验。F=0；两类现有初态与独立制备初态；每点 5–10 个种子；初态整体旋转；逐链反向编号并一致更新 Bonds/Angles 和分子拓扑，使构型相同而驱动极性翻转/随机化；改变链长并固定密度。编号实验应作为独立输入制备，不能只修改局部 active id 算式。
6. 实现控制。记录活性力成功施加比例（每个完整链应有 28 活性内珠）、速度钳制比例、径向分布；检查 MPI ghost 查找缺失、单/多 MPI 与 CPU/Kokkos 统计一致性。若需要严格表面运动，另实现带正确随机几何漂移的球面布朗运动或经过验证的约束算法；不要简单投影噪声后以为算法已经无偏。

## 大球面研究设计

固定珠径 sigma=1、链长 30、弯曲系数 30、T=1 和表面覆盖率 phi 时，珠数应满足 N≈16 phi R²；链数 N/30 四舍五入到整数后报告实际 phi。基准 R=5.175492、N=300、10 条链；2R 时 N=1200、40 条链；4R 时 N=4800、160 条链。保持 300 珠而只增大 R 会同时降低覆盖率，无法单独解释曲率效应。

应以 R–F 相图为主体，并同时报告 L/R、实测 orientational persistence length/R、Pe=F sigma/(kBT)、局部 p/Q 与缺陷产生统计。在可用连续活性应力 ζ 与有效 K 标定时，ell_a≈sqrt(K/|ζ|) 给出候选长度尺度；不能把代码中的逐珠推进力 F 直接替代 ζ，干模型还需要摩擦与持久性参数。R/ell_a 增大可能容纳更多局部涡旋与缺陷对，属于待检验预测；拓扑净电荷始终 +2，而额外缺陷密度并不受该整数固定。

最有价值的研究问题是：当链不再接近绕球一周时，两极缺陷对如何失稳；配对距离和角速度是否有可折叠的尺度律；体系是否存在极性环流/向列旋转/缺陷增殖之间的多稳态与滞回。仅声称首次发现两极旋转缺陷并不稳妥，相关理论与模拟早已存在。

## 已核实的相关文献

| 编号 | 作者、正式标题与出版信息 | DOI | OpenAlex 被引数 |
|---|---|---|---:|
| R1 | Felix C. Keber; Etienne Loiseau; Tim Sanchez; Stephen J. DeCamp; Luca Giomi; Mark J. Bowick; M. Cristina Marchetti; Zvonimir Dogic; Andreas R. Bausch. Topology and dynamics of active nematic vesicles. Science 345(6201), 1135–1139 (2014). | https://doi.org/10.1126/science.1254784 | 576 |
| R2 | Silke Henkes; M. Cristina Marchetti; Rastko Sknepnek. Dynamical patterns in nematic active matter on a sphere. Physical Review E 97, 042605 (2018). | https://doi.org/10.1103/PhysRevE.97.042605 | 64 |
| R3 | Diana Khoromskaia; Gareth P. Alexander. Vortex formation and dynamics of defects in active nematic shells. New Journal of Physics 19, 103043 (2017). | https://doi.org/10.1088/1367-2630/aa89aa | 46 |
| R4 | Aidan T. Brown. A theoretical phase diagram for an active nematic on a spherical surface. Soft Matter 16, 4682–4691 (2020). | https://doi.org/10.1039/D0SM00166J | 11 |
| R5 | Rui Zhang; Ye Zhou; Mohammad Rahimi; Juan J. de Pablo. Dynamic structure of active nematic shells. Nature Communications 7, 13483 (2016). | https://doi.org/10.1038/ncomms13483 | 87 |
| R6 | Luca Giomi. Geometry and Topology of Turbulence in Active Nematics. Physical Review X 5, 031003 (2015). | https://doi.org/10.1103/PhysRevX.5.031003 | 251 |
| R7 | Chiao-Peng Hsu; Alfredo Sciortino; Yu Alice de la Trobe; Andreas R. Bausch. Activity-induced polar patterns of filaments gliding on a sphere. Nature Communications 13, 2579 (2022). | https://doi.org/10.1038/s41467-022-30128-7 | 27 |
| R8 | Rastko Sknepnek; Silke Henkes. Active swarms on a sphere. Physical Review E 91, 022306 (2015). | https://doi.org/10.1103/PhysRevE.91.022306 | 86 |

优先参考 R1、R6 两篇高被引基础文献；R2/R3/R4/R7/R8 虽未达 100 次但与特定问题更直接相关，故保留。R2 的 arXiv 标题与正式发表标题不同；R3 亦如此。正式引用采用出版版题名。R4 有包含平行输运的共旋转缺陷对 C 态，并批评先前模型中部分反向旋转缺陷对源于遗漏输运；该批评不能直接推广为本粒子模型中的旋转一定是伪影。

可核对的全文与出版元数据：R2 https://journals.aps.org/pre/abstract/10.1103/PhysRevE.97.042605 ；R3 https://wrap.warwick.ac.uk/id/eprint/94684/ ；R4 https://www.pure.ed.ac.uk/ws/portalfiles/portal/151240613/d0sm00166j_2.pdf_Brown.pdf ；R7 https://www.nature.com/articles/s41467-022-30128-7 。算法文档：https://docs.lammps.org/Modify_fix.html 、https://docs.lammps.org/angle_cosine.html 。
