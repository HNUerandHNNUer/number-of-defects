#!/usr/bin/env python3
"""
Convert XYZ file to LAMMPS data file for polymer chains
支持自定义链数量和链长度
"""
import numpy as np
import argparse

def read_xyz(filename):
    """Read XYZ file and return positions"""
    with open(filename, 'r') as f:
        n_atoms = int(f.readline())
        # Read header line and extract box size
        header = f.readline()
        # Find BoxSize values in the header
        box_start = header.find("BoxSize:") + 8
        box_values = header[box_start:].strip().split()
        box_size = [float(box_values[0]), float(box_values[1]), float(box_values[2])]
        
        positions = []
        atom_types = []
        for i in range(n_atoms):
            line = f.readline().split()
            atom_types.append(int(line[0]))
            positions.append([float(line[1]), float(line[2]), float(line[3])])
    
    return n_atoms, np.array(positions), np.array(atom_types), np.array(box_size)

def auto_detect_chain_params(n_atoms):
    """自动检测链参数"""
    # 常见的链长度
    common_chain_lengths = [30, 20, 40, 50, 25, 10]
    
    for chain_length in common_chain_lengths:
        if n_atoms % chain_length == 0:
            n_chains = n_atoms // chain_length
            return n_chains, chain_length
    
    # 如果无法自动检测，返回None
    return None, None

def write_lammps_data(filename, n_atoms, positions, atom_types, box_size, 
                      n_chains=None, chain_length=None):
    """Write LAMMPS data file for polymer system"""
    
    # 如果没有提供链参数，尝试自动检测
    if n_chains is None or chain_length is None:
        auto_n_chains, auto_chain_length = auto_detect_chain_params(n_atoms)
        if auto_n_chains is None:
            raise ValueError(f"无法自动检测链参数。原子总数 {n_atoms} 不能被常见链长度整除。")
        n_chains = auto_n_chains
        chain_length = auto_chain_length
        print(f"自动检测到: {n_chains} 条链，每条链 {chain_length} 个原子")
    
    # 验证参数
    if n_chains * chain_length != n_atoms:
        raise ValueError(f"链参数不匹配: {n_chains} × {chain_length} = {n_chains*chain_length}, "
                        f"但实际原子数为 {n_atoms}")
    
    # 计算键和角的数量
    n_bonds = n_chains * (chain_length - 1)
    n_angles = n_chains * (chain_length - 2)
    
    print(f"生成LAMMPS data文件:")
    print(f"  原子数: {n_atoms}")
    print(f"  链数: {n_chains}")
    print(f"  每条链原子数: {chain_length}")
    print(f"  键数: {n_bonds}")
    print(f"  角数: {n_angles}")
    
    with open(filename, 'w') as f:
        # Header
        f.write("Polymer system with {} chains of length {}\n\n".format(n_chains, chain_length))
        
        f.write("{} atoms\n".format(n_atoms))
        f.write("{} bonds\n".format(n_bonds))
        f.write("{} angles\n\n".format(n_angles))
        
        f.write("1 atom types\n")
        f.write("1 bond types\n")
        f.write("1 angle types\n\n")
        
        # Box dimensions
        f.write("{:.6f} {:.6f} xlo xhi\n".format(-box_size[0]/2, box_size[0]/2))
        f.write("{:.6f} {:.6f} ylo yhi\n".format(-box_size[1]/2, box_size[1]/2))
        f.write("{:.6f} {:.6f} zlo zhi\n\n".format(-box_size[2]/2, box_size[2]/2))
        
        # Masses
        f.write("Masses\n\n")
        f.write("1 1.0\n\n")
        
        # Atoms
        f.write("Atoms\n\n")
        for i in range(n_atoms):
            chain_id = i // chain_length + 1
            f.write("{} {} {} {:.8f} {:.8f} {:.8f}\n".format(
                i+1, chain_id, atom_types[i], 
                positions[i,0], positions[i,1], positions[i,2]))
        
        # Bonds - 只在链内连接
        f.write("\nBonds\n\n")
        bond_id = 1
        for chain in range(n_chains):
            for j in range(chain_length - 1):
                atom1 = chain * chain_length + j + 1
                atom2 = atom1 + 1
                # 确保原子ID不超过总原子数
                if atom1 <= n_atoms and atom2 <= n_atoms:
                    f.write("{} 1 {} {}\n".format(bond_id, atom1, atom2))
                    bond_id += 1
        
        # Angles - 只在链内定义
        f.write("\nAngles\n\n")
        angle_id = 1
        for chain in range(n_chains):
            for j in range(chain_length - 2):
                atom1 = chain * chain_length + j + 1
                atom2 = atom1 + 1
                atom3 = atom1 + 2
                # 确保原子ID不超过总原子数
                if atom1 <= n_atoms and atom2 <= n_atoms and atom3 <= n_atoms:
                    f.write("{} 1 {} {} {}\n".format(angle_id, atom1, atom2, atom3))
                    angle_id += 1

def main():
    parser = argparse.ArgumentParser(description='将XYZ文件转换为LAMMPS data文件')
    parser.add_argument('-i', '--input', default='initial.xyz', 
                       help='输入XYZ文件 (默认: initial.xyz)')
    parser.add_argument('-o', '--output', default='polymer.data',
                       help='输出LAMMPS data文件 (默认: polymer.data)')
    parser.add_argument('-n', '--nchains', type=int, default=None,
                       help='链的数量 (默认: 自动检测)')
    parser.add_argument('-m', '--mchain', type=int, default=None,
                       help='每条链的原子数 (默认: 自动检测)')
    parser.add_argument('--auto', action='store_true',
                       help='自动检测链参数并显示')
    
    args = parser.parse_args()
    
    # 读取初始配置
    n_atoms, positions, atom_types, box_size = read_xyz(args.input)
    
    print(f"读取文件: {args.input}")
    print(f"原子总数: {n_atoms}")
    print(f"盒子尺寸: {box_size}")
    
    # 如果指定了--auto，只显示自动检测结果
    if args.auto:
        n_chains, chain_length = auto_detect_chain_params(n_atoms)
        if n_chains:
            print(f"\n自动检测结果:")
            print(f"  链数: {n_chains}")
            print(f"  每条链原子数: {chain_length}")
        else:
            print("\n无法自动检测链参数")
            print("请手动指定 --nchains 和 --mchain 参数")
        return
    
    # 写入LAMMPS data文件
    try:
        write_lammps_data(args.output, n_atoms, positions, atom_types, box_size,
                         n_chains=args.nchains, chain_length=args.mchain)
        print(f"\n成功写入: {args.output}")
    except ValueError as e:
        print(f"\n错误: {e}")
        print("\n建议尝试以下命令:")
        print("  python convert_xyz_to_data.py --auto  # 查看自动检测结果")
        print("  python convert_xyz_to_data.py --nchains 80 --mchain 30  # 手动指定参数")

if __name__ == "__main__":
    main()