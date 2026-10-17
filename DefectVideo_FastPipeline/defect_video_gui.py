#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DefectVideo Easy: choose one nchain directory, output, parallel count, Start.

Uses existing PyMOL renderer and resilient SSD-backed batch engine. No elevated
permissions required; a cache rejected by D:/ automatically falls back to the
user's LocalAppData. GUI is responsive while work happens in another process.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import uuid
from datetime import datetime

HERE = Path(__file__).resolve().parent
ENGINE = HERE / 'batch_defect_videos.py'
PREFIX = '@@DEFECT_PROGRESS@@'
DEFAULT_ROOT = r'E:\1\7.9.2025\3000\phi_0.7\number of defects\new\nchain10'
PYMOL_GUESS = r'D:\Anaconda3\Scripts\pymol.EXE'


class App:
    def __init__(self, master: tk.Tk):
        self.win = master
        master.title('DefectVideo · 流水线并行加速')
        master.geometry('850x595')
        master.minsize(760, 530)
        self.source = tk.StringVar(value=DEFAULT_ROOT)
        self.target = tk.StringVar(value=str(Path(DEFAULT_ROOT) / 'video'))
        self.processes = tk.StringVar(value='3')
        self.pymol = tk.StringVar(value=PYMOL_GUESS if Path(PYMOL_GUESS).is_file() else 'pymol')
        self.replace = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value='选择 nchain 文件夹，点击「开始生成」即可。')
        self.details = tk.StringVar(value='完成 0 / 0 帧  ·  当前未运行')
        self.events: queue.Queue = queue.Queue()
        self.proc = None
        self.cancel = None
        self.logfile = None
        self.planned = {}
        self.finished = set()
        self.progress_counts = {}
        self.n_total = 0
        self.running = False
        self.is_preview = False
        self.last_seen = None
        self.started_at = None
        self._build()
        master.after(100, self._poll)
        master.protocol('WM_DELETE_WINDOW', self._quit)

    def _build(self):
        outer = ttk.Frame(self.win, padding=16)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='DefectVideo · 并行渲染与实时编码',
                  font=('Microsoft YaHei UI', 17, 'bold')).pack(anchor='w', pady=(0, 12))
        paths = ttk.LabelFrame(outer, text='只需设置这些', padding=12)
        paths.pack(fill='x')
        paths.columnconfigure(1, weight=1)
        ttk.Label(paths, text='F_* 所在目录').grid(row=0, column=0, sticky='w', pady=8)
        ttk.Entry(paths, textvariable=self.source).grid(row=0, column=1, sticky='ew', padx=8)
        ttk.Button(paths, text='选择...', command=self._choose_source).grid(row=0, column=2)
        ttk.Label(paths, text='视频保存目录').grid(row=1, column=0, sticky='w', pady=8)
        ttk.Entry(paths, textvariable=self.target).grid(row=1, column=1, sticky='ew', padx=8)
        ttk.Button(paths, text='选择...', command=self._choose_target).grid(row=1, column=2)
        ttk.Label(paths, text='并行 PyMOL 数').grid(row=2, column=0, sticky='w', pady=8)
        ttk.Combobox(paths, textvariable=self.processes, values=['1', '2', '3', '4', '5', '6'],
                     state='readonly', width=8).grid(row=2, column=1, sticky='w', padx=8)
        ttk.Label(paths, text='建议先选 3；无需等全部 PNG 渲染完。',
                  foreground='#555').grid(row=2, column=1, sticky='e')
        ttk.Label(paths, text='PyMOL 路径').grid(row=3, column=0, sticky='w', pady=8)
        ttk.Entry(paths, textvariable=self.pymol).grid(row=3, column=1, sticky='ew', padx=8)
        ttk.Button(paths, text='选择 EXE', command=self._choose_exe).grid(row=3, column=2)
        ttk.Checkbutton(paths, text='重新生成已存在的视频（覆盖）', variable=self.replace).grid(
            row=4, column=1, sticky='w', padx=8, pady=(6, 0))

        ttk.Label(outer, text='自动使用可写的 SSD 缓存，D 盘无权限时改用用户缓存；'
                  ' AVI / 800×800 / 12 FPS / 全部帧 / 保留光追。',
                  foreground='#505050').pack(anchor='w', pady=(8, 10))

        controls = ttk.Frame(outer)
        controls.pack(fill='x')
        self.begin_button = ttk.Button(controls, text='▶ 开始生成', command=lambda: self._start(False))
        self.begin_button.pack(side='left', ipadx=14, ipady=6)
        self.preview_button = ttk.Button(controls, text='检查工况', command=lambda: self._start(True))
        self.preview_button.pack(side='left', padx=9)
        self.stop_button = ttk.Button(controls, text='■ 停止', command=self._stop, state='disabled')
        self.stop_button.pack(side='left')
        ttk.Button(controls, text='打开视频文件夹', command=self._open_video).pack(side='right')

        pro = ttk.LabelFrame(outer, text='实时进度', padding=10)
        pro.pack(fill='x', pady=11)
        ttk.Label(pro, textvariable=self.status).pack(anchor='w')
        self.bar = ttk.Progressbar(pro, maximum=100)
        self.bar.pack(fill='x', pady=6)
        ttk.Label(pro, textvariable=self.details).pack(anchor='w')

        logbox = ttk.LabelFrame(outer, text='运行信息（有错误会显示在这里）', padding=7)
        logbox.pack(fill='both', expand=True)
        self.log = tk.Text(logbox, wrap='word', height=9, state='disabled',
                           font=('Consolas', 9))
        self.log.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(logbox, command=self.log.yview)
        scroll.pack(side='right', fill='y')
        self.log.configure(yscrollcommand=scroll.set)

    def _choose_source(self):
        path = filedialog.askdirectory(title='选择包含 F_* 的 nchain 文件夹',
                                      initialdir=self.source.get() if Path(self.source.get()).is_dir() else str(Path.home()))
        if path:
            self.source.set(path)
            self.target.set(str(Path(path) / 'video'))

    def _choose_target(self):
        path = filedialog.askdirectory(title='选择视频输出文件夹')
        if path:
            self.target.set(path)

    def _choose_exe(self):
        path = filedialog.askopenfilename(title='选择 pymol.EXE', filetypes=[('EXE', '*.exe'), ('所有文件', '*.*')])
        if path:
            self.pymol.set(path)

    def _write_log(self, line):
        if self.logfile:
            self.logfile.write(line + '\n')
            self.logfile.flush()
        self.log.configure(state='normal')
        self.log.insert('end', line + '\n')
        if int(self.log.index('end-1c').split('.')[0]) > 800:
            self.log.delete('1.0', '200.0')
        self.log.see('end')
        self.log.configure(state='disabled')

    def _start(self, preview):
        if self.running:
            return
        source = Path(self.source.get().strip().strip('"'))
        target = Path(self.target.get().strip().strip('"'))
        if not source.is_dir():
            messagebox.showerror('目录不存在', '请选择正确的 nchain 输入文件夹。')
            return
        if not target.is_absolute():
            messagebox.showerror('目录不正确', '请选择完整的输出目录。')
            return
        if not preview and self.pymol.get().lower() != 'pymol' and not Path(self.pymol.get()).is_file():
            messagebox.showerror('找不到 PyMOL', '请选择真实存在的 pymol.EXE 文件。')
            return
        if not ENGINE.is_file() or not (HERE / 'render_defect_pymol.py').is_file():
            messagebox.showerror('缺少源码', '请把 3 个 .py 文件放在同一个文件夹。')
            return
        self.is_preview = preview
        self.running = True
        self.planned.clear()
        self.finished.clear()
        self.progress_counts.clear()
        self.n_total = 0
        self.last_seen = None
        self.started_at = time.monotonic()
        self.bar['value'] = 0
        self.status.set('正在扫描工况...' if preview else '正在启动，检查 SSD 缓存权限...')
        self.details.set('正在准备...')
        self.begin_button.configure(state='disabled')
        self.preview_button.configure(state='disabled')
        self.stop_button.configure(state='normal')
        logdir = HERE / 'logs'
        try:
            logdir.mkdir(exist_ok=True)
        except OSError:
            logdir = Path(tempfile.gettempdir()) / 'DefectVideoLogs'
            logdir.mkdir(exist_ok=True)
        self.logfile = (logdir / ('run_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.log')).open(
            'w', encoding='utf-8', buffering=1)
        self.cancel = Path(tempfile.gettempdir()) / ('DefectVideo_Stop_' + uuid.uuid4().hex + '.flag')
        cmd = [sys.executable, '-u', str(ENGINE), '--root', str(source),
               '--output', str(target), '--cache-dir', 'auto', '--pymol', self.pymol.get().strip(),
               '--jobs', '1', '--frame-workers', self.processes.get(), '--chunk-frames', '256', '--cpu-cores', '14',
               '--ray', '1', '--format', 'avi', '--fps', '12', '--width', '800',
               '--height', '800', '--stride', '1', '--max-frames', '0',
               '--beads-per-chain', '30', '--cancel-file', str(self.cancel), '--progress-json']
        if self.replace.get():
            cmd.append('--overwrite')
        if preview:
            cmd.append('--dry-run')
        try:
            self.proc = subprocess.Popen(cmd, cwd=str(HERE), stdin=subprocess.DEVNULL,
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         encoding='utf-8', errors='replace', text=True, bufsize=1)
        except OSError as exc:
            self.running = False
            self.stop_button.configure(state='disabled')
            self.begin_button.configure(state='normal')
            self.preview_button.configure(state='normal')
            self.logfile.close()
            self.logfile = None
            messagebox.showerror('无法启动', str(exc))
            return
        self._write_log('[START] ' + source.name + ' -> ' + str(target))
        thread = threading.Thread(target=self._reader, args=(self.proc,), daemon=True)
        thread.start()

    def _reader(self, proc):
        try:
            for line in proc.stdout:
                self.events.put(('line', line.rstrip('\r\n')))
            proc.stdout.close()
            self.events.put(('exit', proc.wait()))
        except Exception as exc:
            self.events.put(('line', '[READER ERROR] ' + str(exc)))
            self.events.put(('exit', proc.poll()))

    def _poll(self):
        try:
            for _ in range(160):
                kind, value = self.events.get_nowait()
                if kind == 'line':
                    if value.startswith(PREFIX):
                        try:
                            self._progress_event(json.loads(value[len(PREFIX):]))
                        except (ValueError, TypeError) as exc:
                            self._write_log('[PROGRESS ERROR] ' + str(exc))
                    else:
                        if value and not value.startswith('[PLAN]'):
                            self._write_log(value)
                else:
                    self._done(value)
        except queue.Empty:
            pass
        if self.running and not self.is_preview:
            elapsed = max(0., time.monotonic() - self.started_at)
            progress = sum(self.progress_counts.values())
            maximum = max(1, 3 * self.n_total)
            self.bar['value'] = min(100, progress * 100 / maximum)
            copy_n = sum(v for (key, stage), v in self.progress_counts.items() if stage == 'copy')
            render_n = sum(v for (key, stage), v in self.progress_counts.items() if stage == 'render')
            encode_n = sum(v for (key, stage), v in self.progress_counts.items() if stage == 'encode')
            self.details.set(f'已编码 {encode_n:,}/{self.n_total:,} 帧 · '
                             f'已渲染 {render_n:,} · SSD缓存 {copy_n:,} · '
                             f'已运行 {int(elapsed//60)} 分 {int(elapsed%60)} 秒')
        self.win.after(100, self._poll)

    def _progress_event(self, item):
        event = item.get('event')
        if event == 'plan':
            name = item['name']
            total = int(item['frames'])
            self.planned[name] = total
            self.n_total += total
            if self.is_preview:
                self.status.set(f'已经识别 {len(self.planned)} 个工况，共 {self.n_total:,} 帧')
        elif event == 'job_start':
            self.last_seen = item['name']
            self.status.set('正在缓存 XYZ：' + self.last_seen)
        elif event == 'job_phase':
            self.last_seen = item['name']
            phase = {'rendering': '并行渲染 + 流水线编码', 'encoding': '合成 AVI',
                     'publishing': '保存成品'}.get(item.get('status'), item.get('status', '工作中'))
            self.status.set(phase + '：' + self.last_seen)
        elif event == 'frame':
            name, stage = item['name'], item['stage']
            key = (name, stage)
            self.progress_counts[key] = self.progress_counts.get(key, 0) + int(item['delta'])
        elif event == 'job_end':
            name = item.get('name')
            state = item.get('status', '?')
            if state in ('success', 'skipped'):
                for stage in ('copy', 'render', 'encode'):
                    self.progress_counts[(name, stage)] = self.planned.get(name, 0)
            self.finished.add(name)
            if state == 'failed':
                self._write_log('[失败] ' + str(name) + ' : ' + str(item.get('error')))
            else:
                self._write_log('[' + state + '] ' + str(name))
            self.status.set(f'工况完成 {len(self.finished)}/{len(self.planned)}：{name}')
        elif event == 'preview_end':
            self.status.set(f'检查完成：{item.get("count", 0)} 个工况，共 {item.get("total",0):,} 帧')
        elif event == 'finished':
            self.status.set('全部完成：成功 {success}，跳过 {skipped}，失败 {failed}'.format(**item))
            self.bar['value'] = 100 if not item.get('failed') and not item.get('cancelled') else self.bar['value']

    def _done(self, exitcode):
        self.running = False
        self.begin_button.configure(state='normal')
        self.preview_button.configure(state='normal')
        self.stop_button.configure(state='disabled')
        if self.logfile:
            self._write_log(f'[EXIT] code={exitcode}')
            self.logfile.close()
            self.logfile = None
        if self.cancel:
            try:
                self.cancel.unlink(missing_ok=True)
            except OSError:
                pass
        if exitcode != 0:
            self.status.set('运行失败或已停止。请查看下方错误信息。')
            if not self.is_preview:
                messagebox.showwarning('运行未完成', '任务异常或已停止，查看日志即可定位原因；已完成的视频不会受影响。')
        elif self.is_preview:
            self.details.set(f'共识别 {len(self.planned)} 个工况、{self.n_total:,} 帧；未生成视频。')
        self.proc = None

    def _stop(self):
        if not self.running:
            return
        if not messagebox.askyesno('停止任务', '停止当前批处理？已成功保存的视频不受影响。'):
            return
        try:
            self.cancel.write_text('stop', encoding='ascii')
        except OSError as exc:
            self._write_log('[STOP ERROR] ' + str(exc))
        self.stop_button.configure(state='disabled')
        self.status.set('已请求安全停止；等待当前 PyMOL 帧结束...')

    def _open_video(self):
        folder = Path(self.target.get())
        if not folder.is_dir():
            messagebox.showinfo('尚未生成', '输出目录还不存在，请先生成视频。')
            return
        try:
            if os.name == 'nt':
                os.startfile(str(folder))
            else:
                messagebox.showinfo('视频目录', str(folder))
        except OSError as exc:
            messagebox.showerror('打开失败', str(exc))

    def _quit(self):
        if self.running:
            messagebox.showinfo('任务仍在运行', '请先点击「停止」，等待程序退出，再关闭窗口。')
            return
        self.win.destroy()


def main():
    root = tk.Tk()
    try:
        ttk.Style(root).theme_use('clam')
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
