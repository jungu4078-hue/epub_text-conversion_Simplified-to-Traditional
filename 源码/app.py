from __future__ import annotations

import argparse
import json
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from epub_converter import Converter, collect_books

TITLE = 'EPUB 简繁转换工具'
CONVERSION_MODES = {
    's2tw': '简体 → 台湾繁体（默认）',
    's2t': '简体 → 标准繁体',
    't2s': '繁体 → 简体',
}


class App:
    def __init__(self, root, initial_paths=(), initial_config='s2tw'):
        self.root = root
        root.title(TITLE)
        root.geometry('850x660')
        root.minsize(720, 560)
        root.option_add('*Font', ('Microsoft YaHei UI', 10))
        self.paths = []
        self.busy = False
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.recursive = tk.BooleanVar(value=False)
        self.mode = tk.StringVar(value=CONVERSION_MODES[initial_config])
        self.status = tk.StringVar(value='请选择 EPUB 文件或所在文件夹')
        panel = ttk.Frame(root, padding=20)
        panel.pack(fill='both', expand=True)
        ttk.Label(panel, text=TITLE, font=('Microsoft YaHei UI', 20, 'bold')).pack(anchor='w')
        ttk.Label(panel, text='离线转换正文、目录和书籍信息，保留图片及排版资源。').pack(anchor='w', pady=(4, 12))
        toolbar = ttk.Frame(panel)
        toolbar.pack(fill='x')
        self.file_button = ttk.Button(toolbar, text='添加 EPUB', command=self.add_files)
        self.folder_button = ttk.Button(toolbar, text='添加文件夹', command=self.add_folder)
        self.clear_button = ttk.Button(toolbar, text='清空列表', command=self.clear)
        for button in (self.file_button, self.folder_button, self.clear_button):
            button.pack(side='left', padx=(0, 8))
        self.recursive_check = ttk.Checkbutton(toolbar, text='包含子文件夹', variable=self.recursive)
        self.recursive_check.pack(side='left')
        listing = ttk.Frame(panel)
        listing.pack(fill='both', expand=True, pady=10)
        self.listbox = tk.Listbox(listing, height=9, activestyle='none', borderwidth=1, relief='solid')
        self.listbox.grid(row=0, column=0, sticky='nsew')
        vertical = ttk.Scrollbar(listing, orient='vertical', command=self.listbox.yview)
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal = ttk.Scrollbar(listing, orient='horizontal', command=self.listbox.xview)
        horizontal.grid(row=1, column=0, sticky='ew')
        self.listbox.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        listing.columnconfigure(0, weight=1)
        listing.rowconfigure(0, weight=1)
        settings = ttk.Frame(panel)
        settings.pack(fill='x')
        ttk.Label(settings, text='转换模式：').pack(side='left')
        self.mode_box = ttk.Combobox(settings, textvariable=self.mode, values=list(CONVERSION_MODES.values()), state='readonly', width=28)
        self.mode_box.pack(side='left')
        ttk.Label(panel, text='保存方式：直接覆盖原文件，不创建备份。校验失败的文件保持原样。', foreground='#925200').pack(anchor='w', pady=(10, 4))
        ttk.Label(panel, text='也可将 EPUB 或文件夹拖到程序图标上；图片中的文字不会转换。', foreground='#555555').pack(anchor='w')
        actions = ttk.Frame(panel)
        actions.pack(fill='x', pady=12)
        self.start_button = ttk.Button(actions, text='开始转换', command=self.start)
        self.start_button.pack(side='left')
        self.stop_button = ttk.Button(actions, text='完成当前文件后停止', command=self.request_stop, state='disabled')
        self.stop_button.pack(side='left', padx=8)
        self.progress = ttk.Progressbar(panel, mode='determinate')
        self.progress.pack(fill='x')
        ttk.Label(panel, textvariable=self.status).pack(anchor='w', pady=(6, 4))
        self.log = tk.Text(panel, height=7, state='disabled', wrap='word', relief='solid', borderwidth=1)
        self.log.pack(fill='both', expand=True)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.poll)
        if initial_paths:
            root.after(150, lambda: self.add_paths(initial_paths))

    def add_paths(self, paths):
        try:
            new = collect_books(paths, self.recursive.get())
            self.paths = collect_books([*self.paths, *new])
            self.listbox.delete(0, 'end')
            for path in self.paths:
                self.listbox.insert('end', str(path))
            self.status.set(f'已选择 {len(self.paths)} 本 EPUB')
            if not new:
                messagebox.showinfo(TITLE, '没有找到 EPUB 文件。需要扫描子文件夹时，请先勾选“包含子文件夹”。', parent=self.root)
        except Exception as error:
            messagebox.showerror(TITLE, str(error), parent=self.root)

    def add_files(self):
        paths = filedialog.askopenfilenames(title='选择 EPUB 文件（可多选）', filetypes=[('EPUB 电子书', '*.epub'), ('所有文件', '*.*')])
        if paths:
            self.add_paths(paths)

    def add_folder(self):
        path = filedialog.askdirectory(title='选择 EPUB 所在文件夹')
        if path:
            self.add_paths([path])

    def clear(self):
        self.paths.clear()
        self.listbox.delete(0, 'end')
        self.status.set('请选择 EPUB 文件或所在文件夹')

    def append(self, message):
        self.log.configure(state='normal')
        self.log.insert('end', message + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def set_busy(self, value):
        self.busy = value
        for widget in (self.file_button, self.folder_button, self.clear_button, self.recursive_check, self.start_button):
            widget.configure(state='disabled' if value else 'normal')
        self.mode_box.configure(state='disabled' if value else 'readonly')
        self.stop_button.configure(state='normal' if value else 'disabled')

    def start(self):
        if self.busy:
            return
        if not self.paths:
            messagebox.showinfo(TITLE, '请先添加 EPUB 文件。', parent=self.root)
            return
        config = next(key for key, label in CONVERSION_MODES.items() if label == self.mode.get())
        self.set_busy(True)
        self.stop.clear()
        paths = list(self.paths)
        self.progress.configure(value=0, maximum=len(paths))
        self.append(f'开始转换 {len(paths)} 本书；{self.mode.get()}；直接覆盖，不备份。')
        threading.Thread(target=self.work, args=(paths, config), daemon=True).start()

    def work(self, paths, config):
        success = failure = unchanged = 0
        try:
            converter = Converter(config)
            for index, path in enumerate(paths):
                if self.stop.is_set():
                    break
                self.events.put(('status', f'正在处理 {index + 1}/{len(paths)}：{path.name}'))
                try:
                    result = converter.convert_book(path)
                    if result['changed_files']:
                        success += 1
                        text = f'完成：{path.name}（{result["changed_files"]} 个文本文件）'
                    else:
                        unchanged += 1
                        text = f'无需更改：{path.name}'
                except Exception as error:
                    failure += 1
                    text = f'失败，原文件保留：{path.name}\n  {error}'
                self.events.put(('log', text))
                self.events.put(('progress', index + 1))
        except Exception as error:
            self.events.put(('log', f'启动转换失败：{error}'))
        finally:
            pending = len(paths) - success - failure - unchanged
            self.events.put(('done', f'已转换 {success} 本，无需更改 {unchanged} 本，失败 {failure} 本，未处理 {pending} 本。'))

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'status':
                    self.status.set(value)
                elif kind == 'log':
                    self.append(value)
                elif kind == 'progress':
                    self.progress.configure(value=value)
                elif kind == 'done':
                    self.set_busy(False)
                    self.status.set(value)
                    self.append(value)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def request_stop(self):
        self.stop.set()
        self.stop_button.configure(state='disabled')
        self.append('将在当前文件处理完成后停止。')

    def close(self):
        if self.busy:
            self.request_stop()
            self.status.set('正在完成当前文件，请稍后关闭窗口。')
        else:
            self.root.destroy()


def save_report(path, report):
    if path:
        Path(path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument('paths', nargs='*')
    parser.add_argument('--convert', action='store_true', help='直接转换指定路径，不打开界面')
    parser.add_argument('--recursive', action='store_true')
    parser.add_argument('--config', choices=list(CONVERSION_MODES), default='s2tw',
                        help='转换模式：s2tw 台湾繁体（默认），s2t 标准繁体，t2s 繁体转简体')
    parser.add_argument('--report', help='将运行结果写入 JSON 文件')
    parser.add_argument('--self-test', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.convert:
        results, errors = [], []
        try:
            books = collect_books(args.paths, args.recursive)
            if not books:
                raise ValueError('没有找到 EPUB 文件')
            converter = Converter(args.config)
            for book in books:
                try:
                    results.append(converter.convert_book(book))
                except Exception as error:
                    errors.append({'file': str(book), 'error': str(error)})
        except Exception as error:
            errors.append({'error': str(error)})
        report = {'results': results, 'errors': errors}
        save_report(args.report, report)
        if sys.stdout:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if errors else 0
    root = tk.Tk()
    app = App(root, args.paths, args.config)
    if args.self_test:
        root.withdraw()
        def check():
            sample = '繁體中文轉換測試，頭髮發展。' if args.config == 't2s' else '简体中文转换测试，头发发展。'
            converted = Converter(args.config).opencc.convert(sample)
            save_report(args.report, {'gui': 'ok', 'opencc': converted, 'title': root.title(),
                                      'mode': app.mode.get(), 'modes': list(app.mode_box['values'])})
            root.destroy()
        root.after(400, check)
    root.mainloop()
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        messagebox.showerror(TITLE, f'程序运行失败：{error}')
        raise SystemExit(1)
