# EPUB 简繁转换工具

批量转换 EPUB 电子书中的简体与繁体中文。提供 Windows 图形界面、命令行和 Python 源码，支持简体转台湾繁体、简体转标准繁体，以及繁体转简体。

程序窗口已更名为“EPUB 简繁转换工具”，EXE 和文件夹沿用原名称，方便继续使用原有入口。

Windows 便携程序已包含运行环境和 OpenCC 字典，**免安装、无需 Python，转换过程无需联网**。

> **保存方式：直接覆盖原 EPUB，不创建备份，也不修改文件名。** 每本书先生成临时文件并完成检查，再替换原文件。需要保留原版本时，请在转换前自行复制。

## 下载与快速开始

1. [下载 EPUB简转繁.exe](./EPUB简转繁.exe?raw=true)，或点击仓库的 **Code → Download ZIP** 下载整个项目并解压。
2. 双击 `EPUB简转繁.exe`。
3. 点击 **添加 EPUB** 选择一本或多本书，或点击 **添加文件夹** 批量载入。
4. 在 **转换模式** 中选择 **繁体 → 简体**、**简体 → 台湾繁体（默认）** 或 **简体 → 标准繁体**。
5. 点击 **开始转换**，在窗口底部查看进度和处理结果。

便携程序面向 **Windows 10 / 11（64 位）**，已在 Windows 11 上验证运行。

也可以将 EPUB 文件或文件夹拖到文件管理器中的 `EPUB简转繁.exe` **程序图标**上，载入后再点击开始转换。程序窗口内部不支持拖放。

## 功能

- 批量处理文件或文件夹，支持中文路径和文件名。
- 可选扫描子文件夹；请先勾选 **包含子文件夹**，再添加文件夹。
- 重复添加的同一路径会自动去重。
- 转换正文、章节标题、目录、书籍信息，以及图片替代文字等文本属性。
- 保留图片、内嵌字体、CSS、JavaScript、包内文件名、链接地址和目录跳转目标。
- 检查 ZIP 完整性及 XML 文档结构，并核对非文本资源是否保持不变。
- 单本书失败时显示原因，保留其原文件，继续处理其他书籍。
- 支持 **完成当前文件后停止**；已经完成的书籍不会撤销。
- 无需更改的 EPUB 不会重新写入。

## 转换模式

| 界面选项 | OpenCC 配置 | 说明 |
| --- | --- | --- |
| 简体 → 台湾繁体（默认） | `s2tw` | 简体转繁体，并采用台湾常用字形；不启用台湾地区词汇替换。 |
| 简体 → 标准繁体 | `s2t` | 按 OpenCC 标准繁体规则转换。 |
| 繁体 → 简体 | `t2s` | 将繁体字转换为简体字；不启用地区词汇替换。 |

例如：简转繁 `头发与发展` → `頭髮與發展`；繁转简 `頭髮與發展，這裡還有文本。` → `头发与发展，这里还有文本。`。

简转繁时，适用的简体中文语言标记会随模式更新为 `zh-TW` 或 `zh-Hant`。繁转简时，`zh-TW`、`zh-HK`、`zh-MO`、`zh-Hant` 及其常见地区组合会更新为 `zh-Hans`；通用的 `zh` 标记也会随转换模式更新。其他语言标记保持不变。

## 命令行

在程序所在目录打开终端。添加 `--convert` 会直接执行转换，不打开主界面，保存方式同样是覆盖原文件、不备份。

以下为 PowerShell 示例：

```powershell
# 转换一本 EPUB，并把结果写入 JSON
.\EPUB简转繁.exe --convert "D:\电子书\示例.epub" --report "D:\结果.json"

# 转换多个文件
.\EPUB简转繁.exe --convert "D:\电子书\第一本.epub" "D:\电子书\第二本.epub" --report "D:\结果.json"

# 扫描文件夹及全部子文件夹，转换为台湾繁体
.\EPUB简转繁.exe --convert "D:\电子书" --recursive --report "D:\结果.json"

# 转换为标准繁体
.\EPUB简转繁.exe --convert "D:\电子书" --config s2t --report "D:\结果.json"

# 繁体转换为简体
.\EPUB简转繁.exe --convert "D:\电子书" --config t2s --report "D:\结果.json"
```

EXE 采用无控制台窗口打包，使用 `--report` 获取处理结果。报告的父文件夹需要已经存在；报告路径请使用独立的 `.json` 文件，已有同名报告会被覆盖。

| 参数 | 用途 |
| --- | --- |
| 一个或多个路径 | EPUB 文件或所在文件夹；不带 `--convert` 时载入图形界面。 |
| `--convert` | 不打开主界面，直接执行转换。 |
| `--recursive` | 命令行转换时扫描子文件夹，默认不扫描。 |
| `--config s2tw` | 简体转台湾繁体，默认值。 |
| `--config s2t` | 简体转标准繁体。 |
| `--config t2s` | 繁体转简体。 |
| `--report 路径` | 将命令行转换结果写入 UTF-8 JSON 文件。 |

报告中的 `results` 列出成功处理的文件，`errors` 列出失败原因。`changed_files` 表示一本 EPUB 内发生变化的文本文件数量，`changed_segments` 表示变化的文本片段或语言标记数量，并非字符数。

不带 `--convert` 时，`--config` 也可设置打开图形界面时默认选中的转换模式。

进程退出码：`0` 表示全部成功，`1` 表示存在转换失败或没有找到 EPUB。自动化脚本应等待 EXE 进程结束后再读取报告或退出码；也可以使用下述 Python 命令行入口。

## 从源码运行

开发与打包环境使用 **64 位 Python 3.12**，需包含 Tkinter。首次安装依赖需要联网；完成安装后可以离线转换。

在仓库根目录运行以下 PowerShell 命令，无需激活虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\源码\requirements.txt
.\.venv\Scripts\python.exe .\源码\app.py
```

通过 Python 执行命令行转换时，结果还会输出到终端：

```powershell
.\.venv\Scripts\python.exe .\源码\app.py --convert "D:\电子书" --recursive --report "D:\结果.json"
```

依赖版本见 [`源码/requirements.txt`](./源码/requirements.txt)：OpenCC 提供简繁转换规则，lxml 用于 XML 解析与结构检查，PyInstaller 用于打包独立程序。

## 重新打包

安装好 64 位 Python 3.12，并确保 `python` 可在终端运行后，双击 [`源码/重新打包.bat`](./源码/重新打包.bat)。脚本会创建虚拟环境、安装依赖，并在上一级目录生成 `EPUB简转繁.exe`，替换已有的同名程序。

也可以使用前面创建的虚拟环境，在仓库根目录手动打包：

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name "EPUB简转繁" --collect-data opencc --distpath "." --workpath "build" --specpath "." .\源码\app.py
```

生成的 EXE 已包含运行环境、图形界面组件和 OpenCC 字典。分发整个项目时，请一并保留 [`许可证`](./许可证/) 中的第三方许可文件。

## 测试

在仓库根目录执行：

```powershell
# 转换逻辑测试；未指定 EXE 时会跳过独立程序测试
.\.venv\Scripts\python.exe .\源码\test_converter.py

# 包含独立 EXE 的转换与界面启动测试
$env:EPUB_TEST_EXE = (Resolve-Path ".\EPUB简转繁.exe").Path
.\.venv\Scripts\python.exe .\源码\test_converter.py
Remove-Item Env:EPUB_TEST_EXE
```

测试会在临时目录生成示例 EPUB，不需要真实电子书。当前测试覆盖双向文本转换、语言标记更新、链接及资源保留、损坏文件保护、重复转换、目录去重和子目录扫描、界面选择繁转简后的完整转换流程、三种命令行模式，以及独立 EXE 的运行。

## 处理过程与限制

每本书的处理顺序为：检查原文件 → 转换到同目录下的临时文件 → 检查输出 ZIP、XML 结构及资源 → 替换原文件。正常结束或捕获错误后会清理临时文件；强制结束进程或断电时可能留下 `.epub-convert-*.tmp` 文件。处理过程中需要有足够空间容纳当前一本书的临时副本。

- 仅处理可正常解析的 EPUB 文本；不解密 DRM，也不修复损坏的电子书。
- 支持转换 EPUB 内的 XML、XHTML、OPF、NCX、SVG 文本；HTML/HTM 内容也需要符合 XML 解析要求。
- 图片中的文字不会改变，因此封面、扫描页和插图文字仍会保留原字形。
- 内嵌字体保持原样，不会补全转换后的字形。若阅读器显示缺字，可尝试切换到支持相应简体或繁体字形的字体。
- 简繁转换基于词典规则，多义字、人名和被标签分隔的词语可能需要人工校对。
- 完整性和结构检查不等同于完整的 EPUB 标准验证，也不能保证所有阅读器中的显示效果。

## 项目结构

```text
.
├── README.md
├── EPUB简转繁.exe           # Windows 便携程序
├── 使用说明.txt             # 离线简明说明
├── 源码/
│   ├── app.py              # 图形界面及命令行入口
│   ├── epub_converter.py   # EPUB 转换与校验
│   ├── test_converter.py   # 自动化测试
│   ├── requirements.txt    # 依赖版本
│   └── 重新打包.bat         # Windows 打包脚本
└── 许可证/                 # 第三方组件许可与声明
```

## 第三方组件

本工具使用 OpenCC Python 实现及其字典、lxml、Python、Tcl/Tk 和 PyInstaller。相关版权声明及许可文本随项目保存在 [`许可证`](./许可证/) 目录中。
