# -*- coding: utf-8 -*-
"""
Created on Wed Jan 23 19:31:04 2019

@author: zhuguolong
优化版本：为粒子类型4、5添加了半径和颜色设置
"""

import types
from pymol import cmd
from pymol.cgo import *
cmd.bg_color('white')
cmd.set('light_count','1')
cmd.set('opaque_background','off') # cmd.set('ray_opaque_background',0)
cmd.set('stick_nub', '0')
cmd.set('connect_mode','1')
cmd.set('orthoscopic','1')
import numpy as np
# import cv2
import os
from scipy.spatial import SphericalVoronoi
from scipy.spatial import cKDTree as KDTree
import time
from scipy.spatial import Voronoi

def loadxyz(filename='defect_out-0000000000.xyz',r1=0.45,r2=0.6,r3=0.6,r4=0.6,r5=0.6):
    """
    加载XYZ文件并设置粒子显示
    优化：为类型4、5添加了半径和颜色设置
    """
    with open(filename,'r') as f:
        line = f.readline()
        N = int(line)
        line = f.readline()
        words = line.split()
        Box1 = float(words[4])
        Box2 = float(words[5])
        Box3 = float(words[6])
    f.closed
    
    cmd.delete('all')
    cmd.load(filename)
    cmd.hide('everything')
    cmd.show('spheres')
    
    # 设置所有粒子的基础半径
    cmd.alter('all', 'vdw=%f' % (r1))
    cmd.alter('name 1', 'vdw=%f' % (r1))
    cmd.alter('name 2', 'vdw=%f' % (r2))
    cmd.alter('name 3', 'vdw=%f' % (r3))
    cmd.alter('name 4', 'vdw=%f' % (r4))  # 新增：类型4半径设置
    cmd.alter('name 5', 'vdw=%f' % (r5))  # 新增：类型5半径设置
    cmd.rebuild

    # 【类型1】设置基础颜色和透明度
    cmd.select('n1', 'name 1')
    cmd.color('purple', 'n1')
    cmd.set('sphere_transparency', 0.1, 'n1')
    
    # 【优化】为类型2、3、4、5定义安全颜色（避免过于刺眼）
    cmd.set_color('particle_yellow_safe', [0.9, 0.8, 0.15])    # 黄色
    cmd.set_color('particle_red_safe', [0.85, 0.15, 0.15])     # 红色
    cmd.set_color('particle_blue_safe', [0.15, 0.4, 0.85])     # 蓝色（新增）
    cmd.set_color('particle_green_safe', [0.15, 0.75, 0.3])    # 绿色（新增）
    
    # 【类型2】黄色
    cmd.select('n2', 'name 2')
    cmd.color('particle_yellow_safe', 'n2')
    
    # 【类型3】红色
    cmd.select('n3', 'name 3')
    cmd.color('particle_red_safe', 'n3')
    
    # 【类型4】蓝色（新增）
    cmd.select('n4', 'name 4')
    cmd.color('particle_blue_safe', 'n4')
    
    # 【类型5】绿色（新增）
    cmd.select('n5', 'name 5')
    cmd.color('particle_green_safe', 'n5')
    
    # 【优化】使用内置光谱为类型1创建渐变（基于ID或B因子）
    # 这种方法完全避免了手动颜色索引管理
    cmd.select('type1_particles', 'name 1')
    
    # 方法A：基于原子ID创建渐变
    cmd.spectrum('id', 'blue_cyan_green', 'type1_particles')
    
    # 或者方法B：如果需要更复杂的渐变模式
    # 可以临时修改B因子来控制颜色分布
    for i in range(100):
        for j in range(1, 30):
            atom_id = i * 30 + j
            gradient_value = i  # 渐变值0-99
            cmd.alter(f'name 1 and id {atom_id}', f'b={gradient_value}')
        # 白色粒子设置特殊B因子
        white_atom_id = i * 30 + 30
        cmd.alter(f'name 1 and id {white_atom_id}', f'b=100')
    
    # 使用自定义光谱，避开red和yellow
    cmd.spectrum('b', 'blue_purple_magenta', 'type1_particles', 
                minimum=0, maximum=99)
    
    # 白色粒子保持白色
    cmd.color('white', 'name 1 and b=100')
    
    cmd.zoom(buffer=0.0, state=0, complete=1)
    boundary(Box1,Box2,Box3)
    print(Box1)

def loadavi():
    """生成动画序列"""
    path = r'E:\1\7.9.2025\3000\phi_0.7\nchain_50\nchain50_2.28\F_0.003\defect_out'
    steps = range(0,100000000+1,100000)
    for step in steps:
        # loadxml(os.path.join(path,'%d' %(i+1),'particle.%010d.xml' %1000000),2.5,2.5)
        # loadvoronoi_flat(os.path.join(path,'particle.%010d.xml' %step))
        # loadvoronoi(os.path.join(path,'particle.%010d.xml' %step))
        loadxyz(filename=os.path.join(path,'defect_out-%010d.xyz' %step),r1=0.45,r2=0.6,r3=0.6,r4=0.6,r5=0.6)
        cmd.png(os.path.join(path,'defect_%010d.png' %(step)),800,800,300,1.0,1.0)
    
    # fps = 12
    # size = (800,800)
    # videowriter = cv2.VideoWriter(os.path.join(path,'video.mp4'),cv2.VideoWriter_fourcc('P','I','M','1'),fps,size)
    # for step in steps:
    #     img = cv2.imread(os.path.join(path,'%010d.png' %step))
    #     videowriter.write(img)
    # videowriter.release()

def loadxml(filename='Initial.xml',r1=0.45,r2=0.6,r3=0.6):
    """加载XML格式文件"""
    with open(filename,'r') as f:
        pos = []
        ptype = []
        for i in range(2):
            line = f.readline()
        line = f.readline()
        N = int(line.split('"')[5])
        line = f.readline()
        Box1 = float(line.split('"')[1])
        Box2 = float(line.split('"')[3])
        Box3 = float(line.split('"')[5])
        print(N,Box1,Box2,Box3)
        line = f.readline()
        for i in range(N):
            line = f.readline()
            pos.append([float(line.split()[0]),float(line.split()[1]),float(line.split()[2])])
        for i in range(2):
            line = f.readline()
        for i in range(N):
            line = f.readline()
            ptype.append(ord(line.split('\n')[0])-64)
        with open('data.xyz', 'w') as f:
            f.write("%d\n" % (N))
            f.write("zhuguolong\n")
            for i in range(N):
                # if pos[i][2]<=0: 
                f.write("%s %23.15E %23.15E %23.15E\n" % (ptype[i],pos[i][0],pos[i][1],pos[i][2]))
        f.closed
    f.closed
    cmd.delete('all')
    cmd.load('data.xyz')
    cmd.hide('everything')
    cmd.show('spheres')
    cmd.select('n1', 'name 1')
    cmd.color('purple', 'n1')
    cmd.select('n2', 'name 2')
    cmd.color('green', 'n2')
    cmd.select('n3', 'name 3')
    cmd.color('red', 'n3')
    cmd.select('n4', 'name 4')
    cmd.color('blue', 'n4')
    cmd.select('n5', 'name 5')
    cmd.color('red', 'n5')
    cmd.select('n6', 'name 6')
    cmd.color('red', 'n6')
    cmd.select('n7', 'name 7')
    cmd.color('gray', 'n7')
    cmd.select('n8', 'name 8')
    cmd.color('gray', 'n8')
    cmd.alter('all', 'vdw=%f' % (0.5))
    cmd.alter('n1', 'vdw=%f' % (r1))
    cmd.alter('n3', 'vdw=%f' % (r3))
    cmd.alter('n4', 'vdw=%f' % (r3))
    cmd.alter('n7', 'vdw=%f' % (r3))
    boundary(Box1,Box2,Box3)
    # cmd.hide('cgo','boundary')
    cmd.zoom(buffer=0.0, state=0, complete=1)
  #   cmd.set_view ('''\
  #    1.000000000,    0.000000000,    0.000000000,\
  #    0.000000000,    0.838670611,    0.544639051,\
  #    0.000000000,   -0.544639051,    0.838670611,\
  #    0.000000000,    0.000000000, -1705.423828125,\
  #   -0.004974365,    0.057228088,   -0.017997742,\
  # 1360.168212891, 2050.678955078,  -20.000000000 ''')

  
def loadvoronoi(filename):
    """加载并显示Voronoi图（球面）"""
    cmd.delete('all')
    with open(filename,'r') as f:
        pos = []
        ptype = []
        for i in range(2):
            line = f.readline()
        line = f.readline()
        N = int(line.split('"')[5])
        line = f.readline()
        Box1 = float(line.split('"')[1])
        Box2 = float(line.split('"')[3])
        Box3 = float(line.split('"')[5])
        print(N,Box1,Box2,Box3)
        line = f.readline()
        for i in range(N):
            line = f.readline()
            pos.append([float(line.split()[0]),float(line.split()[1]),float(line.split()[2])])
        for i in range(2):
            line = f.readline()
        for i in range(N):
            line = f.readline()
            ptype.append(ord(line.split('\n')[0])-64)
    pos = np.array(pos)
    # pos = pos[[i*1201 for i in range(1002)],:]
    radius = np.linalg.norm(pos[0])
    for i in range(pos.shape[0]):
        pos[i] = pos[i]/np.linalg.norm(pos[i])*radius
    center = np.array([0, 0, 0])
    sv = SphericalVoronoi(pos, radius, center)
    # sv = SphericalVoronoi(pos, radius, center, threshold=0.01)
    sv.sort_vertices_of_regions()
    np.savetxt('voronoi_vesicles.txt',sv.vertices,fmt='%23.15E', delimiter=' ')
    cmd.delete('all')
    with open('voronoi_regions.txt','w') as f:
        for region in sv.regions:
            for num in region:
                f.write('%d ' %(num))
            f.write('\n')
    vesicles = np.loadtxt('voronoi_vesicles.txt')
    linenum = len(open('voronoi_regions.txt', 'r').readlines())
    with open('voronoi_regions.txt') as f:
        for name in range(linenum):
            words = f.readline().split()
            obj = []
            obj.extend([BEGIN, LINES, COLOR, 0, 0, 0])
            # obj.extend([LINEWIDTH, 1.0, BEGIN, LINES, COLOR, 0, 0, 0])
            for i in range(len(words)-1):
                obj.extend([VERTEX, vesicles[int(words[i])][0], vesicles[int(words[i])][1], vesicles[int(words[i])][2], VERTEX, vesicles[int(words[i+1])][0], vesicles[int(words[i+1])][1], vesicles[int(words[i+1])][2]])
            obj.extend([VERTEX, vesicles[int(words[-1])][0], vesicles[int(words[-1])][1], vesicles[int(words[-1])][2], VERTEX, vesicles[int(words[0])][0], vesicles[int(words[0])][1], vesicles[int(words[0])][2]])
            obj.extend([END])
            for i in range(len(words)):
                for j in range(i+1,len(words)):
                    for k in range(j+1,len(words)):
                        obj.extend([BEGIN, TRIANGLE_STRIP])
                        if len(words)<=4: obj.extend([COLOR,0.23,0.28,0.57])
                        if len(words)==5: obj.extend([COLOR,0.75,0.29,0.59])
                        if len(words)==6: obj.extend([COLOR,1.00,1.00,1.00])
                        if len(words)==7: obj.extend([COLOR,0.43,0.71,0.17])
                        if len(words)>=8: obj.extend([COLOR,0.50,0.80,0.87])
                        # if name == 2 or name ==10:
                        #     obj.extend([COLOR,1.00,1.00,1.00])
                        # else:
                        #     if len(words)<=4: obj.extend([COLOR,0.23,0.28,0.57])
                        #     if len(words)==5: obj.extend([COLOR,0.75,0.29,0.59])
                        #     if len(words)==6: obj.extend([COLOR,1.00,1.00,1.00])
                        #     if len(words)==7: obj.extend([COLOR,0.43,0.71,0.17])
                        #     if len(words)>=8: obj.extend([COLOR,0.50,0.80,0.87])
                        obj.extend([
                        VERTEX,vesicles[int(words[i])][0],vesicles[int(words[i])][1],vesicles[int(words[i])][2],
                        VERTEX,vesicles[int(words[j])][0],vesicles[int(words[j])][1],vesicles[int(words[j])][2],
                        VERTEX,vesicles[int(words[k])][0],vesicles[int(words[k])][1],vesicles[int(words[k])][2],
                        END])

            cmd.load_cgo(obj,str(name+1))
    cmd.zoom(buffer=0.0, state=0, complete=1)
    cmd.set_view ('''\
     1.000000000,    0.000000000,    0.000000000,\
     0.000000000,    1.000000000,    0.000000000,\
     0.000000000,    0.000000000,    1.000000000,\
     0.000000000,    0.000000000, -492.155975342,\
    -0.296188354,   -0.975357056,    0.000000000,\
   388.019531250,  596.292419434,  -20.000000000 ''')
    
    # np.savetxt('pos.txt', pos, fmt='%f')
    # with open ('pos.xyz','w') as f:
    #     f.write("%d\n" % (pos.shape[0]))
    #     f.write("zhuguolong\n")
    #     for i in range(pos.shape[0]):
    #         f.write("%s %23.15E %23.15E %23.15E\n" % (1,pos[i][0],pos[i][1],pos[i][2]))
    # cmd.load('pos.xyz')
    # cmd.show('spheres')
    # cmd.select('n1', 'name 1')
    # cmd.alter('name 1', 'vdw=%f' % (0.1))

def loadvoronoi_flat(filename):
    """加载并显示Voronoi图（平面）"""
    cmd.delete('all')
    with open(filename,'r') as f:
        pos = []
        for i in range(2):
            line = f.readline()
        line = f.readline()
        N = int(line.split('"')[5])
        line = f.readline()
        Box1 = float(line.split('"')[1])
        Box2 = float(line.split('"')[3])
        Box3 = float(line.split('"')[5])
        line = f.readline()
        for i in range(N):
            line = f.readline()
            pos.append([float(line.split()[0]),float(line.split()[1]),float(line.split()[2])])
    pos = np.array(pos)
    pos = np.concatenate((pos,pos+np.array([Box1,0,0]),pos+np.array([0,Box2,0]),pos+np.array([Box1,Box2,0])),axis=0)
    vor = Voronoi(pos[:,:2])
    vertices = vor.vertices
    regions = vor.regions
    point_region = vor.point_region
    for i in range(N):
        temp = i
        if pos[i][0]<0 and pos[i][1]<0: temp = i+3*N
        if pos[i][0]>=0 and pos[i][1]<0: temp = i+2*N
        if pos[i][0]<0 and pos[i][1]>=0: temp = i+1*N
        temp = point_region[temp]
        words = regions[temp]
        obj = []
        obj.extend([BEGIN, LINES, COLOR, 0, 0, 0])
        if pos[i][0]<0 and pos[i][1]<0:
            for j in range(len(words)-1):
                obj.extend([VERTEX, vertices[words[j]][0]-Box1, vertices[words[j]][1]-Box2, 0.0, VERTEX, vertices[words[j+1]][0]-Box1, vertices[words[j+1]][1]-Box2, 0.0])
            obj.extend([VERTEX, vertices[words[-1]][0]-Box1, vertices[words[-1]][1]-Box2, 0.0, VERTEX, vertices[words[0]][0]-Box1, vertices[words[0]][1]-Box2, 0.0])
            obj.extend([END])
        if pos[i][0]>=0 and pos[i][1]<0:
            for j in range(len(words)-1):
                obj.extend([VERTEX, vertices[words[j]][0], vertices[words[j]][1]-Box2, 0.0, VERTEX, vertices[words[j+1]][0], vertices[words[j+1]][1]-Box2, 0.0])
            obj.extend([VERTEX, vertices[words[-1]][0], vertices[words[-1]][1]-Box2, 0.0, VERTEX, vertices[words[0]][0], vertices[words[0]][1]-Box2, 0.0])
            obj.extend([END])    
        if pos[i][0]<0 and pos[i][1]>=0:
            for j in range(len(words)-1):
                obj.extend([VERTEX, vertices[words[j]][0]-Box1, vertices[words[j]][1], 0.0, VERTEX, vertices[words[j+1]][0]-Box1, vertices[words[j+1]][1], 0.0])
            obj.extend([VERTEX, vertices[words[-1]][0]-Box1, vertices[words[-1]][1], 0.0, VERTEX, vertices[words[0]][0]-Box1, vertices[words[0]][1], 0.0])
            obj.extend([END])    
        if pos[i][0]>=0 and pos[i][1]>=0:
            for j in range(len(words)-1):
                obj.extend([VERTEX, vertices[words[j]][0], vertices[words[j]][1], 0.0, VERTEX, vertices[words[j+1]][0], vertices[words[j+1]][1], 0.0])
            obj.extend([VERTEX, vertices[words[-1]][0], vertices[words[-1]][1], 0.0, VERTEX, vertices[words[0]][0], vertices[words[0]][1], 0.0])
            obj.extend([END])    
        # for j in range(len(words)-1):
        #     obj.extend([VERTEX, vertices[words[j]][0], vertices[words[j]][1], 0.0, VERTEX, vertices[words[j+1]][0], vertices[words[j+1]][1], 0.0])
        # obj.extend([VERTEX, vertices[words[-1]][0], vertices[words[-1]][1], 0.0, VERTEX, vertices[words[0]][0], vertices[words[0]][1], 0.0])
        # obj.extend([END])
        for j in range(len(words)):
            for k in range(j+1,len(words)):
                for l in range(k+1,len(words)):
                    obj.extend([BEGIN, TRIANGLE_STRIP])
                    if len(words)<=4: obj.extend([COLOR,0.23,0.28,0.57])
                    if len(words)==5: obj.extend([COLOR,0.75,0.29,0.59])
                    if len(words)==6: obj.extend([COLOR,1.00,1.00,1.00])
                    if len(words)==7: obj.extend([COLOR,0.43,0.71,0.17])
                    if len(words)>=8: obj.extend([COLOR,0.50,0.80,0.87])
                    if pos[i][0]<0 and pos[i][1]<0:
                        obj.extend([
                        VERTEX,vertices[words[j]][0]-Box1,vertices[words[j]][1]-Box2,0.0,
                        VERTEX,vertices[words[k]][0]-Box1,vertices[words[k]][1]-Box2,0.0,
                        VERTEX,vertices[words[l]][0]-Box1,vertices[words[l]][1]-Box2,0.0,
                        END]) 
                    if pos[i][0]>=0 and pos[i][1]<0:
                        obj.extend([
                        VERTEX,vertices[words[j]][0],vertices[words[j]][1]-Box2,0.0,
                        VERTEX,vertices[words[k]][0],vertices[words[k]][1]-Box2,0.0,
                        VERTEX,vertices[words[l]][0],vertices[words[l]][1]-Box2,0.0,
                        END]) 
                    if pos[i][0]<0 and pos[i][1]>=0:
                        obj.extend([
                        VERTEX,vertices[words[j]][0]-Box1,vertices[words[j]][1],0.0,
                        VERTEX,vertices[words[k]][0]-Box1,vertices[words[k]][1],0.0,
                        VERTEX,vertices[words[l]][0]-Box1,vertices[words[l]][1],0.0,
                        END]) 
                    if pos[i][0]>=0 and pos[i][1]>=0:
                        obj.extend([
                        VERTEX,vertices[words[j]][0],vertices[words[j]][1],0.0,
                        VERTEX,vertices[words[k]][0],vertices[words[k]][1],0.0,
                        VERTEX,vertices[words[l]][0],vertices[words[l]][1],0.0,
                        END])
                    # obj.extend([
                    # VERTEX,vertices[words[j]][0],vertices[words[j]][1],0.0,
                    # VERTEX,vertices[words[k]][0],vertices[words[k]][1],0.0,
                    # VERTEX,vertices[words[l]][0],vertices[words[l]][1],0.0,
                    # END])    
        cmd.load_cgo(obj,str(i+1))
    cmd.zoom(buffer=0.0, state=0, complete=1)
    cmd.set_view ('''\
     1.000000000,    0.000000000,    0.000000000,\
     0.000000000,    1.000000000,    0.000000000,\
     0.000000000,    0.000000000,    1.000000000,\
     0.000000000,    0.000000000, -492.155975342,\
    -0.296188354,   -0.975357056,    0.000000000,\
   388.019531250,  596.292419434,  -20.000000000 ''')
  
def loadvoronoi_psi_6(filename):
    """加载Voronoi图并使用psi_6参数着色"""
    with open(filename,'r') as f:
        pos = []
        ptype = []
        for i in range(2):
            line = f.readline()
        line = f.readline()
        N = int(line.split('"')[5])
        line = f.readline()
        Box1 = float(line.split('"')[1])
        Box2 = float(line.split('"')[3])
        Box3 = float(line.split('"')[5])
        print(N,Box1,Box2,Box3)
        line = f.readline()
        for i in range(N):
            line = f.readline()
            pos.append([float(line.split()[0]),float(line.split()[1]),float(line.split()[2])])
        for i in range(2):
            line = f.readline()
        for i in range(N):
            line = f.readline()
            ptype.append(ord(line.split('\n')[0])-64)
    pos = np.array(pos)
    pos = pos[[i*1201 for i in range(1002)],:]
    radius = np.linalg.norm(pos[0])
    for i in range(pos.shape[0]):
        pos[i] = pos[i]/np.linalg.norm(pos[i])*radius
    center = np.array([0, 0, 0])
    sv = SphericalVoronoi(pos, radius, center, threshold=0.01)
    sv.sort_vertices_of_regions()
    np.savetxt('voronoi_vesicles.txt',sv.vertices,fmt='%23.15E', delimiter=' ')
    cmd.delete('all')
    with open('voronoi_regions.txt','w') as f:
        for region in sv.regions:
            for num in region:
                f.write('%d ' %(num))
            f.write('\n')
    vesicles = np.loadtxt('voronoi_vesicles.txt')
    linenum = len(open('voronoi_regions.txt', 'r').readlines())
    psi_6 = np.loadtxt('psi_6.txt')
    with open('voronoi_regions.txt') as f:
        for name in range(linenum):
            words = f.readline().split()
            obj = []
            obj.extend([BEGIN, LINES, COLOR, 0, 0, 0])
            for i in range(len(words)-1):
                obj.extend([VERTEX, vesicles[int(words[i])][0], vesicles[int(words[i])][1], vesicles[int(words[i])][2], VERTEX, vesicles[int(words[i+1])][0], vesicles[int(words[i+1])][1], vesicles[int(words[i+1])][2]])
            obj.extend([VERTEX, vesicles[int(words[-1])][0], vesicles[int(words[-1])][1], vesicles[int(words[-1])][2], VERTEX, vesicles[int(words[0])][0], vesicles[int(words[0])][1], vesicles[int(words[0])][2]])
            obj.extend([END])
            for i in range(len(words)):
                for j in range(i+1,len(words)):
                    for k in range(j+1,len(words)):
                        obj.extend([BEGIN, TRIANGLE_STRIP])
                        obj.extend([COLOR,
                                    ((120-236)*int(psi_6[name]*7)/6+236)/255,
                                    ((32-223)*int(psi_6[name]*7)/6+223)/255,
                                    ((110-38)*int(psi_6[name]*7)/6+38)/255])
                        # if len(words)<=4: obj.extend([COLOR,0.23,0.28,0.57])
                        # if len(words)==5: obj.extend([COLOR,0.75,0.29,0.59])
                        # if len(words)==6: obj.extend([COLOR,1.00,1.00,1.00])
                        # if len(words)==7: obj.extend([COLOR,0.43,0.71,0.17])
                        # if len(words)>=8: obj.extend([COLOR,0.50,0.80,0.87])
                        obj.extend([
                        VERTEX,vesicles[int(words[i])][0],vesicles[int(words[i])][1],vesicles[int(words[i])][2],
                        VERTEX,vesicles[int(words[j])][0],vesicles[int(words[j])][1],vesicles[int(words[j])][2],
                        VERTEX,vesicles[int(words[k])][0],vesicles[int(words[k])][1],vesicles[int(words[k])][2],
                        END])

            cmd.load_cgo(obj,str(name+1))
    
    # cmd.zoom(buffer=0.0, state=0, complete=1)
    # cmd.set_view ('''\
    #  0.675327539,    0.545799673,   -0.496017426,\
    #  0.400479645,    0.293375909,    0.868067861,\
    #  0.619309485,   -0.784874499,   -0.020457666,\
    #  0.000000000,    0.000000000,  -52.496139526,\
    #  0.002054691,   -0.002470493,   -0.002108097,\
    # 40.708732605,   64.283554077,   20.000000000 ''')
    
    # np.savetxt('pos.txt', pos, fmt='%f')
    # with open ('pos.xyz','w') as f:
    #     f.write("%d\n" % (pos.shape[0]))
    #     f.write("zhuguolong\n")
    #     for i in range(pos.shape[0]):
    #         f.write("%s %23.15E %23.15E %23.15E\n" % (1,pos[i][0],pos[i][1],pos[i][2]))
    # cmd.load('pos.xyz')
    # cmd.show('spheres')
    # cmd.select('n1', 'name 1')
    # cmd.alter('name 1', 'vdw=%f' % (0.1))
    
def loadopengl(filename='000000.opengl',r1=0.5):
    """加载OpenGL格式文件"""
    with open(filename,'r') as f:
        pos = []
        line = f.readline()
        N = int(line)
        line = f.readline()
        Box1 = float(line.split()[1]) - float(line.split()[0])
        line = f.readline()
        Box2 = float(line.split()[1]) - float(line.split()[0])
        line = f.readline()
        Box3 = float(line.split()[1]) - float(line.split()[0])
        print(N,Box1,Box2,Box3,2/3*N/Box1/Box2/Box3)
        for i in range(N):
            line = f.readline()
            line = f.readline()
            pos.append([float(line.split()[1]),float(line.split()[2]),float(line.split()[3])])
            line = f.readline()
            line = f.readline()
            line = f.readline()
    with open('data.xyz', 'w') as f:
        f.write("%d\n" % (N))
        f.write("zhuguolong\n")
        for i in range(N):
            f.write("%s %23.15E %23.15E %23.15E\n" % (1,pos[i][0],pos[i][1],pos[i][2]))
    cmd.delete('all')
    cmd.load('data.xyz')
    cmd.show('spheres')
    cmd.select('n1', 'name 1')
    cmd.color('purple', 'n1')
    cmd.alter('n1', 'vdw=%f' % (float(r1)))
    cmd.select('n2', 'name 2')
    cmd.color('purple', 'n2')
    cmd.alter('n2', 'vdw=%f' % (float(r1)))
#    boundary(Box1,Box2,Box3)
    cmd.zoom(buffer=0.0, state=0, complete=1)
  #   cmd.set_view ('''\
  #    1.000000000,    0.000000000,    0.000000000,\
  #    0.000000000,    1.000000000,    0.000000000,\
  #    0.000000000,    0.000000000,    1.000000000,\
  #    0.000000000,    0.000000000,  -68.052772522,\
  #    0.002688885,    0.013267040,    0.011865616,\
  # -407.410278320,  543.515991211,   20.000000000 ''')

def loadtxt(filename,r1=0.3):
    """从文本文件加载坐标"""
    pos = np.loadtxt(filename)
    N = pos.shape[0]
    with open('data.xyz', 'w') as f:
        f.write("%d\n" % (N))
        f.write("zhuguolong\n")
        for i in range(N):
            f.write("%s %23.15E %23.15E %23.15E\n" % (1,pos[i,0]*5.0,pos[i,1]*5.0,pos[i,2]*5.0))
    cmd.delete('all')
    cmd.load('data.xyz')
    cmd.select('n1', 'name 1')
    cmd.color('purple', 'n1')
    cmd.select('n2', 'name 2')
    cmd.color('green', 'n2')
    cmd.alter('name 1', 'vdw=%f' % (r1))

def boundary(t1,t2,t3):
    """绘制边界框"""
    Box1 = float(t1)/2
    Box2 = float(t2)/2
    Box3 = float(t3)/2
    obj = [BEGIN, LINES, COLOR, 0, 0, 0,
           VERTEX, Box1, Box2, Box3, VERTEX, Box1, Box2,-Box3,
           VERTEX, Box1, Box2, Box3, VERTEX, Box1,-Box2, Box3,
           VERTEX, Box1, Box2, Box3, VERTEX,-Box1, Box2, Box3,
           VERTEX, Box1, Box2,-Box3, VERTEX, Box1,-Box2,-Box3,
           VERTEX, Box1, Box2,-Box3, VERTEX,-Box1, Box2,-Box3,
           VERTEX, Box1,-Box2, Box3, VERTEX, Box1,-Box2,-Box3,
           VERTEX, Box1,-Box2, Box3, VERTEX,-Box1,-Box2, Box3,
           VERTEX,-Box1, Box2, Box3, VERTEX,-Box1, Box2,-Box3,
           VERTEX,-Box1, Box2, Box3, VERTEX,-Box1,-Box2, Box3,
           VERTEX,-Box1,-Box2,-Box3, VERTEX, Box1,-Box2,-Box3,
           VERTEX,-Box1,-Box2,-Box3, VERTEX,-Box1, Box2,-Box3,
           VERTEX,-Box1,-Box2,-Box3, VERTEX,-Box1,-Box2, Box3,
#           VERTEX,    0,    0,    0, VERTEX,   10,    0,    0,
#           VERTEX,    0,    0,    0, VERTEX,    0,   20,    0,
#           VERTEX,    0,    0,    0, VERTEX,    0,    0,   30,
           END]
    cmd.load_cgo(obj,'boundary')

def loadpbc(filename='out.xyz',tx=0,ty=0,tz=0):
    """加载周期性边界条件的文件"""
    ptype = []
    pos = []
    tx = float(tx)
    ty = float(ty)
    tz = float(tz)
    with open(filename,'r') as f:
        line = f.readline()
        N = int(line)
        line = f.readline()
        words = line.split()
        Box1 = float(words[4])
        Box2 = float(words[5])
        Box3 = float(words[6])
        for i in range(N):
            line = f.readline()
            words = line.split()
            ptype.append(words[0])
            pos.append([float(words[1]),float(words[2]),float(words[3])])
    f.closed
    for coord in pos:
        coord[0] = coord[0] + tx
        coord[1] = coord[1] + ty
        coord[2] = coord[2] + tz
        if (coord[0] <-Box1/2): coord[0] = coord[0] + Box1;
        if (coord[0] > Box1/2): coord[0] = coord[0] - Box1;
        if (coord[1] <-Box2/2): coord[1] = coord[1] + Box2;
        if (coord[1] > Box2/2): coord[1] = coord[1] - Box2;
        if (coord[2] <-Box3/2): coord[2] = coord[2] + Box3;
        if (coord[2] > Box3/2): coord[2] = coord[2] - Box3;
    with open('outpbc.xyz', 'w') as f:
        f.write("%d\n" % (N))
        f.write("output pbc\n")
        for i in range(N):
            f.write("%s %6f %6f %6f\n" % (ptype[i],pos[i][0],pos[i][1],pos[i][2]))
    f.closed
    loadxyz('outpbc,xyz')
    boundary([Box1,Box2,Box3])

def loadcylinder_MC(filename='0000.opengl',r=0.5,h=3.0):
    """加载圆柱体（蒙特卡洛格式）"""
    cmd.delete('all')
    with open(filename,'r') as f, open ('data.xyz','w') as f1:
        obj = []
        line = f.readline()
        N = int(line)
        line = f.readline()
        Box1 = float(line.split()[1]) - float(line.split()[0])
        line = f.readline()
        Box2 = float(line.split()[1]) - float(line.split()[0])
        line = f.readline()
        Box3 = float(line.split()[1]) - float(line.split()[0])
        print(N,Box1,Box2,Box3,N*(r**2*h+4/3*r**3)*4/Box1/Box2/Box3)
        f1.write('%d\n' %(N*2))
        f1.write('zhuguolong\n')
        r1, g1, b1 = 0, 1, 0
        r2, g2, b2 = 0, 1, 0
        for i in range(N):
            line = f.readline()
            line = f.readline()
            center = np.array([float(line.split()[1]),float(line.split()[2]),float(line.split()[3])])
            line = f.readline()
            vector = np.array([float(line.split()[0]),float(line.split()[1]),float(line.split()[2])])*h
            line = f.readline()
            line = f.readline()
            obj.extend([ALPHA, 1.0, CYLINDER,
                            center[0]+0.5*vector[0],center[1]+0.5*vector[1],center[2]+0.5*vector[2],
                            center[0]-0.5*vector[0],center[1]-0.5*vector[1],center[2]-0.5*vector[2], r,
                            r1, g1, b1,
                            r2, g2, b2])
            f1.write('%d %.6f %.6f %.6f\n' %(1,center[0]+0.5*vector[0],center[1]+0.5*vector[1],center[2]+0.5*vector[2]))
            f1.write('%d %.6f %.6f %.6f\n' %(1,center[0]-0.5*vector[0],center[1]-0.5*vector[1],center[2]-0.5*vector[2]))
    cmd.load_cgo(obj,'cylinder')
    cmd.load('data.xyz')
    cmd.show('spheres')
    cmd.select('n1', 'name 1')
    cmd.color('green', 'n1')
    cmd.alter('n1', 'vdw=%f' % (r))
    boundary(Box1,Box2,Box3)
    cmd.zoom(buffer=0.0, state=0, complete=1)

def loadcylinder_MC1(filename='0000.opengl'):
    """加载圆柱体（蒙特卡洛格式，版本1）"""
    with open(filename,'r') as f:
        pos = []
        line = f.readline()
        N = int(line)
        line = f.readline()
        Box1 = float(line.split()[1]) - float(line.split()[0])
        line = f.readline()
        Box2 = float(line.split()[1]) - float(line.split()[0])
        line = f.readline()
        Box3 = float(line.split()[1]) - float(line.split()[0])
        print(N,Box1,Box2,Box3)
        for i in range(N):
            line = f.readline()
            line = f.readline()
            center = np.array([float(line.split()[1]),float(line.split()[2]),float(line.split()[3])])
            line = f.readline()
            vector = np.array([float(line.split()[0]),float(line.split()[1]),float(line.split()[2])])
            line = f.readline()
            line = f.readline()
            pos.append(list(center+0.5*vector))
            pos.append(list(center-0.5*vector))
    with open('data.xyz', 'w') as f:
        f.write("%d\n" % (2*N))
        f.write("zhuguolong\n")
        for i in range(2*N):
            f.write("%s %23.15E %23.15E %23.15E\n" % (1,pos[i][0],pos[i][1],pos[i][2]))
    cmd.delete('all')
    cmd.load('data.xyz')
    cmd.hide('spheres')
    for i in range(N):
        cmd.bond('id %d' %(2*i+1),'id %d' %(2*i+2))
    cmd.select('zhuguolong',' name 1')
    cmd.show('sticks','zhuguolong')
    cmd.set('stick_radius', 0.5)
    cmd.set('stick_color', 'green')
    boundary(Box1,Box2,Box3)
    cmd.zoom(buffer=0.0, state=0, complete=1)

def loaddomains(filename='domains-0000000000.xyz',r1=0.5):
    """加载域文件"""
#     with open(filename,'r') as f:
#         line = f.readline()
#         N = int(line)
#         line = f.readline()
# #        name = int(line.split()[1])
#         Box1 = float(line.split()[2])
#         Box2 = float(line.split()[3])
#         Box3 = float(line.split()[4])
#     f.closed
#     print(N,Box1,Box2,Box3,2/3*N/Box1/Box2/Box3)
    cmd.delete('all')
    cmd.load(filename)
    cmd.hide('everything')
    cmd.show('spheres')
    cmd.alter('all', 'vdw=%f' % (0.5))
    colors= [200,400,600,800,1000,300,500,700,900,250,450,650,850,350,550,750,950]
    for i in range(1,18):
        cmd.select('n%d' % (i), 'name %d' % (i))
        cmd.color('%03d' % colors[i-1], 'n%d' % (i))
        # cmd.color('purple', 'n%d' % (i))
    # colors= ['purple','yellow','red','blue','green','orange','cyan','lightblue']
    # colors= ['white','yellow','red','blue','green','orange','purple','purple']
    # for i in range(1,8+1):
    #     cmd.select('n%d' % (i), 'name %d' % (i))
    #     cmd.color(colors[i-1], 'n%d' % (i))
    for i in range(1,2):
        cmd.select('n%d' % (i), 'name %d' % (i))
        cmd.color('purple', 'n%d' % (i))
#    pos = np.loadtxt(filename,skiprows=2)
#    for i in range(N):
#        if np.linalg.norm(pos[i,1:3])>Box1/2-2:
#            cmd.color('lightorange','id %d' %(i+1))

    cmd.alter('all', 'vdw=%f' % (float(r1)))
    # boundary(Box1,Box2,Box3)
    # cmd.hide('cgo', 'boundary')
#    cmd.zoom(buffer=0.0, state=0, complete=1)
    cmd.set_view ('''\
    1.000000000,    0.000000000,    0.000000000,\
    0.000000000,    1.000000000,    0.000000000,\
    0.000000000,    0.000000000,    1.000000000,\
    0.000000000,    0.000000000, -198.813079834,\
    0.052627161,    0.010782242,   -0.008602142,\
    -5991.209960938, 6388.815917969,   20.000000000 ''')

def loadunfold(filename='domains-0000000000.xyz',r1=0.5):
    """加载展开结构"""
    cmd.delete('all')
    cmd.load(filename)
    cmd.hide('everything')
    cmd.show('spheres')
    cmd.alter('all', 'vdw=%f' % (0.5))
    colors= [200,400,600,800,1000,300,500,700,900,250,450,650,850,350,550,750,950]
    for i in range(1,18):
        cmd.select('n%d' % (i), 'name %d' % (i))
        cmd.color('%03d' % colors[i-1], 'n%d' % (i))
    cmd.select('n%d' % (1), 'name %d' % (1))
    cmd.color('purple', 'n%d' % (1))
    cmd.alter('all', 'vdw=%f' % (float(r1)))
#    boundary(Box1,Box2,Box3)
    cmd.zoom(buffer=0.0, state=0, complete=1)
#    cmd.set_view ('''\
#     1.000000000,    0.000000000,    0.000000000,\
#     0.000000000,    1.000000000,    0.000000000,\
#     0.000000000,    0.000000000,    1.000000000,\
#     0.000000000,    0.000000000,  -79.930450439,\
#    -0.052627161,    0.010782242,   -0.008602142,\
#  -6110.092285156, 6269.933593750,   20.000000000 ''')

def drawsphere(radius):
    """绘制球体"""
    with open('sphere.xyz','w') as f:
        f.write('1\n')
        f.write('zhuguolong\n')
        f.write('S 0 0 0\n')
    cmd.load('sphere.xyz')
    cmd.select('S', 'name S')
    cmd.alter('S', 'vdw=%f' % (radius))
    cmd.color('gray','S')
    cmd.set('sphere_transparency', 0,'S')

def drawcylinder(radius,height):
    """绘制圆柱体"""
    with open('stick.xyz','w') as f:
        f.write('2\n')
        f.write('zhuguolong\n')
        f.write('C 0 0 %f\n' %( 0.5*height))
        f.write('C 0 0 %f\n' %(-0.5*height))
    cmd.load('stick.xyz')
    cmd.bond('id 1','id 2')
    cmd.select('C',' name C')
    cmd.show('sticks','C')
    cmd.set('stick_radius', radius,'C')
    cmd.set('stick_color', 'gray','C')
    cmd.set('stick_transparency', 0.85,'C')

def loadsticks(filename='defect_out-0000000000',r1=2.5,r2=0.5,r3=0.3):
    """加载棒状结构"""
    with open(filename,'r') as f:
        line1 = f.readline()
        N = int(line1)
        line2 = f.readline()
        words = line2.split()
        Box1 = float(words[4])
        Box2 = float(words[5])
        Box3 = float(words[6])
    f.closed
    nchain = 135
    mchain = 1201
    cmd.delete('all')
    cmd.load(filename)
    cmd.hide('everything')
    cmd.select('n1','name 1')
    cmd.show('spheres','n1')
    cmd.color('purple','n1')
    cmd.alter('n1','vdw=%f' % (r1))

    for i in range(nchain):
        print(i)
        for j in range(60):
            cmd.bond('id %d' %(i*mchain+1),'id %d' %(i*mchain+j*20+2))
            for k in range(1,11):
                cmd.bond('id %d' %(i*mchain+j*20+k+1),'id %d' %(i*mchain+j*20+k+2))

    cmd.show('sticks',filename)
    cmd.set('stick_radius', 0.1)
    cmd.set('stick_color', 'green')

    drawsphere(0.5*Box1)
    cmd.set_view ('''\
     1.000000000,    0.000000000,    0.000000000,\
     0.000000000,    1.000000000,    0.000000000,\
     0.000000000,    0.000000000,    1.000000000,\
     0.000000000,    0.000000000, -550.654235840,\
    -0.568222046,   -2.552707672,  -19.043380737,\
   297.724639893,  803.583618164,  -20.000000000 ''')

def loadcylinder(filename='defect_out-0000000000',nchain=297,r1=2.5):
    """加载圆柱体结构"""
    with open(filename,'r') as f:
        line1 = f.readline()
        N = int(line1)
        line2 = f.readline()
        words = line2.split()
        Box1 = float(words[4])
        Box2 = float(words[5])
        Box3 = float(words[6])
    f.closed
    data = np.loadtxt(filename,skiprows=2)[:,:]
    mchain = 1201
    cmd.delete('all')
    cmd.load(filename)
    cmd.hide('everything')
    cmd.select('n1','name 1')
    cmd.show('spheres','n1')
    cmd.color('purple','n1')
    cmd.alter('n1','vdw=%f' % (r1))
#    with open('cut.xyz','w') as f:
#        f.write(line1)
#        f.write(line2)
#        for i in range(nchain):
#            if np.linalg.norm(data[i*mchain,1:])<1.3*21.7:
#                f.write('%d %23.15E%23.15E%23.15E\n' %(data[i*mchain,0],data[i*mchain,1],
#                                                       data[i*mchain,2],data[i*mchain,3]))
#    f.closed
#    cmd.load('cut.xyz')
#    cmd.hide('everything')
#    cmd.select('n1','name 1')
#    cmd.show('spheres','n1')
#    cmd.color('purple','n1')
#    cmd.alter('n1','vdw=%f' % (r1))


    obj = []
    for i in range(nchain):
#        if np.linalg.norm(data[i*mchain,1:])<1.3*21.7:
            for j in range(60):
                obj.extend(cylinder(data[i*mchain,1:],data[i*mchain+j*20+1,1:]))
                for k in range(1,11):
                    obj.extend(cylinder(data[i*mchain+j*20+k,1:],data[i*mchain+j*20+k+1,1:]))
    cmd.load_cgo(obj,'cylinder')

    drawsphere(0.5*Box1)
    cmd.set_view ('''\
     -0.259808838,   -0.965332568,    0.025087861,\
    -0.512413502,    0.159838855,    0.843731105,\
    -0.818492353,    0.206352517,   -0.536179483,\
     0.000000000,    0.000000000, -571.890075684,\
     0.073394775,    0.070922852,   -0.018013000,\
   336.696258545,  807.084411621,  -20.000000000 ''')

def loadcylinder1(filename='defect_out-0000000000',nchain=236,r1=2.5):
    """加载圆柱体结构（版本1）"""
    with open(filename,'r') as f:
        line1 = f.readline()
        N = int(line1)
        line2 = f.readline()
        words = line2.split()
        Box1 = float(words[4])
        Box2 = float(words[5])
        Box3 = float(words[6])
    f.closed
    data = np.loadtxt(filename,skiprows=2)[:,:]
    mchain = 1681
    cmd.delete('all')
    cmd.load(filename)
    cmd.hide('everything')
    cmd.select('n1','name 1')
    cmd.show('spheres','n1')
    cmd.color('purple','n1')
    cmd.alter('n1','vdw=%f' % (r1))
#    with open('cut.xyz','w') as f:
#        f.write(line1)
#        f.write(line2)
#        for i in range(nchain):
#            if np.linalg.norm(data[i*mchain,1:])<1.3*32.7:
#                f.write('%d %23.15E%23.15E%23.15E\n' %(data[i*mchain,0],data[i*mchain,1],
#                                                       data[i*mchain,2],data[i*mchain,3]))
#    f.closed
#    cmd.load('cut.xyz')
#    cmd.hide('everything')
#    cmd.select('n1','name 1')
#    cmd.show('spheres','n1')
#    cmd.color('purple','n1')
#    cmd.alter('n1','vdw=%f' % (r1))

    obj = []
    for i in range(nchain):
#        if np.linalg.norm(data[i*mchain,1:])<1.3*32.7:
            for j in range(60):
                obj.extend(cylinder(data[i*mchain,1:],data[i*mchain+j*28+1,1:]))
                for k in range(1,19):
                    obj.extend(cylinder(data[i*mchain+j*28+k,1:],data[i*mchain+j*28+k+1,1:]))
    cmd.load_cgo(obj,'cylinder')

    drawsphere(0.5*Box1)
    cmd.set_view ('''\
     0.999863625,   -0.000151481,   -0.016477469,\
     0.000054069,    0.999980867,   -0.005913902,\
     0.016478114,    0.005912235,    0.999846637,\
     0.000000000,    0.000000000, -759.183776855,\
     0.073394775,    0.070922852,   -0.018013000,\
   414.836395264, 1103.531616211,  -20.000000000 ''')

def cylinder(p1, p2, c1=(0.0,1.0,0.0), c2=(0.0,1.0,0.0), r1=0.1):
    """创建圆柱体对象"""
    x1, y1, z1 = p1
    x2, y2, z2 = p2
    r1_c, g1, b1 = c1
    r2, g2, b2 = c2
    return [ALPHA, 1.0, CYLINDER, float(x1), float(y1), float(z1), float(x2), float(y2), float(z2), r1,
            0.0 ,1.0, 0.0, 0.0, 1.0, 0.0] #float(r1_c), float(g1), float(b1), float(r2), float(g2), float(b2)

def loadxmljanus(filename='out.xml',r1=2.5,r2=0.5,r3=0.3):
    """加载XML格式的Janus粒子"""
    nchain = 362
    mchain = 1201
    with open(filename,'r') as f:
        pos = []
        ptype = []
        for i in range(2):
            line = f.readline()
        line = f.readline()
        N = int(line.split('"')[5])
        line = f.readline()
        Box1 = float(line.split('"')[1])
        Box2 = float(line.split('"')[3])
        Box3 = float(line.split('"')[5])
        print(N,Box1,Box2,Box3,np.pi/6*N/Box1/Box2/Box3)
        line = f.readline()
        for i in range(N):
            line = f.readline()
            pos.append([float(line.split()[0]),float(line.split()[1]),float(line.split()[2])])
        for i in range(2):
            line = f.readline()
        for i in range(N):
            line = f.readline()
            ptype.append(ord(line.split('\n')[0])-64)
        coeff = np.array([[-1.84642728], [0.7011112], [-1.23419102]])
        for i in range(nchain):
            ans = np.matmul(np.array([np.array(pos[i*mchain+1])-np.array(pos[i*mchain]),
                                      np.array(pos[i*mchain+21])-np.array(pos[i*mchain]),
                                      np.array(pos[i*mchain+41])-np.array(pos[i*mchain])]).T/3,coeff).flatten()
            pos.append(list(np.array(pos[i*mchain])+ans*0.1))
            ptype.append('9')
        with open('data.xyz', 'w') as f:
            f.write("%d\n" % (N+nchain))
            f.write("zhuguolong\n")
            for i in range(N+nchain):
                f.write("%s %23.15E %23.15E %23.15E\n" % (ptype[i],pos[i][0],pos[i][1],pos[i][2]))
        f.closed
    f.closed
    cmd.delete('all')
    cmd.load('data.xyz')
    cmd.show('spheres')
    cmd.select('n1', 'name 1')
    cmd.color('purple', 'n1')
    cmd.select('n2', 'name 2')
    cmd.color('purple', 'n2')
    cmd.select('n3', 'name 3')
    cmd.color('red', 'n3')
    cmd.select('n4', 'name 4')
    cmd.color('red', 'n4')
    cmd.select('n7', 'name 7')
    cmd.color('gray', 'n7')
    cmd.select('n8', 'name 8')
    cmd.color('green', 'n8')
    cmd.select('n9', 'name 9')
    cmd.color('green', 'n9')
    cmd.alter('n1', 'vdw=%f' % (r1))
    cmd.alter('n2', 'vdw=%f' % (r2))
    cmd.alter('n3', 'vdw=%f' % (r3))
    cmd.alter('n4', 'vdw=%f' % (r3))
    cmd.alter('n7', 'vdw=%f' % (r3))
    cmd.alter('n8', 'vdw=%f' % (r2))
    cmd.alter('n9', 'vdw=%f' % (r1))
    # cmd.alter('all', 'vdw=%f' % (0.5))
    # cmd.hide('spheres','n8')
    boundary(Box1,Box2,Box3)
    cmd.hide('cgo','boundary')
    cmd.zoom(buffer=0.0, state=0, complete=1)
   #  cmd.set_view ('''\
   #   1.000000000,    0.000000000,    0.000000000,\
   #   0.000000000,    1.000000000,    0.000000000,\
   #   0.000000000,    0.000000000,    1.000000000,\
   #   0.000000000,    0.000000000, -199.794799805,\
   #  -0.009078979,   -0.003658295,    0.013563156,\
   # 146.704483032,  252.885131836,   20.000000000 ''')

def loadxmlcylinder(filename='out.xml'):
    """加载XML格式的圆柱体链"""
    InitialBoxsize = [40,40,160]
    N = 3*InitialBoxsize[0]*InitialBoxsize[1]*InitialBoxsize[2]
    mchain = 40
    nchain = int(round(2.88*InitialBoxsize[0]*InitialBoxsize[1]*10/mchain))
    with open(filename,'r') as f:
        pos = []
        ptype = []
#        bonds = []
        for i in range(2):
            line = f.readline()
        line = f.readline()
        N = int(line.split('"')[5])
        line = f.readline()
        Box1 = float(line.split('"')[1])
        Box2 = float(line.split('"')[3])
        Box3 = float(line.split('"')[5])
        print(N,Box1,Box2,Box3)
        line = f.readline()
        for i in range(N):
            line = f.readline()
            pos.append([float(line.split()[0]),float(line.split()[1]),float(line.split()[2])])
        for i in range(2):
            line = f.readline()
        for i in range(N):
            line = f.readline()
            ptype.append(ord(line.split('\n')[0])-64)
        for i in range(2):
            line = f.readline()
#        bond_num = nchain*(mchain-1)+int(round(mchain*nchain*0.075/2))
#        bond_num = nchain*(mchain-1)
#        for i in range(bond_num):
#            line = f.readline()
#            bonds.append([int(line.split()[1]),int(line.split()[2])])
        with open('data.xyz', 'w') as f:
            f.write("%d\n" % (N))
            f.write("zhuguolong\n")
            for i in range(N):
                f.write("%s %23.15E %23.15E %23.15E\n" % (ptype[i],pos[i][0],pos[i][1],pos[i][2]))
        f.closed
    f.closed
    cmd.delete('all')
    cmd.load('data.xyz')
    cmd.show('spheres')
    cmd.select('n1', 'name 1')
    cmd.color('blue', 'n1')
    cmd.select('n2', 'name 2')
    cmd.color('green', 'n2')
    cmd.select('n3', 'name 3')
    cmd.color('red', 'n3')
    cmd.select('n4', 'name 4')
    cmd.color('gray', 'n4')
    cmd.hide('spheres','n1')
    cmd.hide('spheres','n2')
    cmd.hide('spheres','n4')
    cmd.alter('all', 'vdw=%f' % (0.5))
#    cmd.alter('name 1', 'vdw=%f' % (0.05))
    obj = []
#    for bond in bonds:
#        if(abs(pos[bond[0]][0]-pos[bond[1]][0])<0.5*InitialBoxsize[0] and
#           abs(pos[bond[0]][1]-pos[bond[1]][1])<0.5*InitialBoxsize[1] and
#           abs(pos[bond[0]][2]-pos[bond[1]][2])<0.5*40):
#            r1, g1, b1 = 0, 1, 0
#            r2, g2, b2 = 0, 1, 0
#            if(ptype[bond[0]]==2): r1, g1, b1 = 0, 0, 1
#            if(ptype[bond[1]]==2): r2, g2, b2 = 0, 0, 1
#            obj.extend([ALPHA, 1.0, CYLINDER,
#                        pos[bond[0]][0],pos[bond[0]][1],pos[bond[0]][2],
#                        pos[bond[1]][0],pos[bond[1]][1],pos[bond[1]][2], 0.05,
#                        r1, g1, b1,
#                        r2, g2, b2])
    for i in range(4*nchain):
        for j in range(mchain-1):
            if(abs(pos[i*mchain+j][0]-pos[i*mchain+j+1][0])<0.5*InitialBoxsize[0] and
               abs(pos[i*mchain+j][1]-pos[i*mchain+j+1][1])<0.5*InitialBoxsize[1] and
               abs(pos[i*mchain+j][2]-pos[i*mchain+j+1][2])<0.5*40):
                r1, g1, b1 = 0, 1, 0
                r2, g2, b2 = 0, 1, 0
                if(ptype[i*mchain+j]==2): r1, g1, b1 = 0, 0, 1
                if(ptype[i*mchain+j+1]==2): r2, g2, b2 = 0, 0, 1
                obj.extend([ALPHA, 1.0, CYLINDER,
                            pos[i*mchain+j][0],pos[i*mchain+j][1],pos[i*mchain+j][2],
                            pos[i*mchain+j+1][0],pos[i*mchain+j+1][1],pos[i*mchain+j+1][2], 0.05,
                            r1, g1, b1,
                            r2, g2, b2])
    cmd.load_cgo(obj,'cylinder')

    boundary(Box1,Box2,Box3)
    cmd.zoom(buffer=0.0, state=0, complete=1)
    cmd.set_view ('''\
     0.000000000,    0.000000000,   -1.000000000,\
     0.000000000,    1.000000000,    0.000000000,\
     1.000000000,    0.000000000,    0.000000000,\
     0.000000000,    0.000000000, -453.849548340,\
     0.004007339,   -0.002251625,    0.025917053,\
   357.818450928,  549.880676270,   20.000000000 ''')
   
def loadcut(filename='data.xyz',cut=10.0):
    """加载并按阈值截断坐标"""
    ptype = []
    pos = []
    with open(filename,'r') as f:
        line1 = f.readline()
        N = int(line1)
        N1 = 0
        line2 = f.readline()
        for i in range(N):
            line = f.readline()
            words = line.split()
            ptype.append(words[0])
            if (float(words[3])**2<=cut**2):
                N1 += 1
                pos.append([float(words[1]),float(words[2]),float(words[3])])
    with open('cut%s.xyz' %cut, 'w') as f:
        f.write('%s\n' %N1)
        f.write(line2)
        for i in range(N1):
            f.write("%s %23.15E%23.15E%23.15E\n" % (ptype[i],pos[i][0],pos[i][1],pos[i][2]))
    cmd.delete('all')
    cmd.load('cut%s.xyz' %cut)
    cmd.show('spheres')
    cmd.select('n1', 'name 1')
    cmd.color('purple', 'n1')
    cmd.alter('n1', 'vdw=%f' % (0.5))
    cmd.zoom(buffer=0.0, state=0, complete=1)

# 注册PyMOL扩展命令
cmd.extend("loadxyz",loadxyz)
cmd.extend("loadpbc",loadpbc)
cmd.extend("boundary",boundary)
cmd.extend("loadxml",loadxml)
cmd.extend("loadvoronoi",loadvoronoi)
cmd.extend("loadopengl",loadopengl)
cmd.extend("loadcylinder_MC",loadcylinder_MC)
cmd.extend("loadcylinder_MC1",loadcylinder_MC1)
cmd.extend("loaddomains",loaddomains)
cmd.extend("loadunfold",loadunfold)
cmd.extend("drawsphere",drawsphere)
cmd.extend("drawcylinder",drawcylinder)
cmd.extend("loadsticks",loadsticks)
cmd.extend("loadcylinder",loadcylinder)
cmd.extend("loadcylinder1",loadcylinder1)
cmd.extend("loadxmljanus",loadxmljanus)
cmd.extend("loadxmlcylinder",loadxmlcylinder)
cmd.extend("loadcut",loadcut)
cmd.extend("loadvoronoi_flat",loadvoronoi_flat)
cmd.extend("loadvoronoi_psi_6",loadvoronoi_psi_6)
cmd.extend("loadtxt",loadtxt)
cmd.extend("loadavi",loadavi)