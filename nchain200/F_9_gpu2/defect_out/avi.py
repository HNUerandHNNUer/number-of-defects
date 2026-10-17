# -*- coding: utf-8 -*-
import os
import cv2

# 1. 路径设置 (确保使用原始字符串 r'' 处理反斜杠)
path = r'E:\1\7.9.2025\3000\phi_0.7\number of defects\new\nchain200\F_9_gpu2\defect_out'
video_name = 'video.avi'  # 强烈建议使用 .avi 格式以提高兼容性
video_path = os.path.join(path, video_name)

# 2. 预检：寻找第一张存在的图片以确定视频的准确尺寸
# 这一步非常重要，VideoWriter 的 size 必须与输入 img 的 (width, height) 严格一致
steps = range(0, 1000000000 + 1, 100000)
first_img_path = None
for step in steps:
    test_path = os.path.join(path, 'defect_%010d.png' % step)
    if os.path.exists(test_path):
        first_img_path = test_path
        break

if first_img_path is None:
    print(f"错误：在路径 {path} 下未找到任何匹配的图片文件。")
    exit()

# 读取第一张图获取尺寸
temp_img = cv2.imread(first_img_path)
h, w = temp_img.shape[:2]
size = (w, h)  # 注意：VideoWriter 要求是 (宽, 高)
print(f"检测到图像尺寸: {w}x{h}")

# 3. 初始化 VideoWriter
# 使用 XVID 编码器（通用性最强）
fourcc = cv2.VideoWriter_fourcc(*'XVID') 
fps = 12

videowriter = cv2.VideoWriter(video_path, fourcc, fps, size)

# 4. 检查是否成功开启
if not videowriter.isOpened():
    print("--------------------------------------------------")
    print("VideoWriter 开启失败！尝试备用方案 (MJPG 编码器)...")
    # 备用方案：MJPG 是 OpenCV 内置的，通常不需要外部库支持
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    videowriter = cv2.VideoWriter(video_path, fourcc, fps, size)
    
    if not videowriter.isOpened():
        print("严重错误：无法初始化 VideoWriter。请尝试将文件保存到 C 盘非系统文件夹测试权限。")
        exit()

# 5. 循环写入
print(f"开始生成视频: {video_path}")
count = 0
for step in steps:
    img_name = 'defect_%010d.png' % step
    img_full_path = os.path.join(path, img_name)
    
    if not os.path.exists(img_full_path):
        continue
        
    img = cv2.imread(img_full_path)
    if img is None:
        continue
        
    # 再次确保尺寸一致，如果不一致则强制缩放（防止程序崩溃）
    if (img.shape[1], img.shape[0]) != size:
        img = cv2.resize(img, size)
        
    videowriter.write(img)
    count += 1
    if count % 10 == 0:
        print(f"已处理 {count} 帧...", end='\r')

videowriter.release()
print(f"\n视频生成完毕，共 {count} 帧。路径: {video_path}")