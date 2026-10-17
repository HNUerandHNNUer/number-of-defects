#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LAMMPS XYZ文件格式转换脚本
将LAMMPS输出的out-*.xyz文件转换为指定格式
"""

import os
import glob
import sys


def read_lammps_xyz(filename):
    """读取LAMMPS格式的xyz文件"""
    with open(filename, 'r') as f:
        lines = f.readlines()
    
    # 解析数据
    timestep = None
    num_atoms = None
    box_bounds = []
    atoms = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if line == "ITEM: TIMESTEP":
            timestep = int(lines[i+1].strip())
            i += 2
        elif line == "ITEM: NUMBER OF ATOMS":
            num_atoms = int(lines[i+1].strip())
            i += 2
        elif line.startswith("ITEM: BOX BOUNDS"):
            # 读取三行盒子边界
            box_bounds = []
            for j in range(3):
                bounds = lines[i+1+j].strip().split()
                xlo, xhi = float(bounds[0]), float(bounds[1])
                box_bounds.append((xlo, xhi))
            i += 4
        elif line.startswith("ITEM: ATOMS"):
            # 读取原子数据
            atoms = []
            for j in range(num_atoms):
                atom_data = lines[i+1+j].strip().split()
                # atom_data格式: [id, type, x, y, z]
                atoms.append({
                    'id': int(atom_data[0]),
                    'type': int(atom_data[1]),
                    'x': float(atom_data[2]),
                    'y': float(atom_data[3]),
                    'z': float(atom_data[4])
                })
            i += num_atoms + 1
        else:
            i += 1
    
    return timestep, num_atoms, box_bounds, atoms


def write_converted_xyz(filename, timestep, num_atoms, box_bounds, atoms):
    """写入转换后的xyz格式"""
    # 计算盒子尺寸
    box_x = box_bounds[0][1] - box_bounds[0][0]
    box_y = box_bounds[1][1] - box_bounds[1][0]
    box_z = box_bounds[2][1] - box_bounds[2][0]
    
    with open(filename, 'w') as f:
        # 第一行：原子数量
        f.write(f"{num_atoms}\n")
        
        # 第二行：描述信息
        f.write(f"Atoms. Timestep: {timestep:>9d}, BoxSize: "
                f"{box_x:>23.15E}{box_y:>23.15E}{box_z:>23.15E}\n")
        
        # 原子数据（只输出type, x, y, z）
        for atom in atoms:
            f.write(f"{atom['type']:>4d}"
                    f"{atom['x']:>23.15E}"
                    f"{atom['y']:>23.15E}"
                    f"{atom['z']:>23.15E}\n")


def convert_file(input_file):
    """转换单个文件"""
    print(f"正在处理: {input_file}")
    
    try:
        # 读取原始文件
        timestep, num_atoms, box_bounds, atoms = read_lammps_xyz(input_file)
        
        # 写入转换后的文件（使用相同的文件名）
        write_converted_xyz(input_file, timestep, num_atoms, box_bounds, atoms)
        
        print(f"  ✓ 成功转换 {num_atoms} 个原子，时间步 {timestep}")
        return True
    
    except Exception as e:
        print(f"  ✗ 转换失败: {str(e)}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("LAMMPS XYZ文件格式转换工具")
    print("=" * 60)
    
    # 获取所有out-*.xyz文件
    xyz_files = glob.glob("out-*.xyz")
    
    if not xyz_files:
        print("\n未找到defect_out-*.xyz文件！")
        print("请确保脚本在包含out-*.xyz文件的目录中运行。")
        sys.exit(1)
    
    print(f"\n找到 {len(xyz_files)} 个文件待转换\n")
    
    # 转换所有文件
    success_count = 0
    for xyz_file in sorted(xyz_files):
        if convert_file(xyz_file):
            success_count += 1
    
    # 输出统计
    print("\n" + "=" * 60)
    print(f"转换完成: {success_count}/{len(xyz_files)} 个文件成功")
    print("=" * 60)


if __name__ == "__main__":
    main()