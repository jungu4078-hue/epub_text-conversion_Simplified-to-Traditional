from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import time
import tkinter as tk
import unittest
import zipfile

from app import App, CONVERSION_MODES
from epub_converter import Converter, collect_books, parse, structure

CONTAINER = b'''<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'''
OPF = '''<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="book"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>头发与发展</dc:title><dc:identifier id="book">简体ID</dc:identifier><dc:language>zh-CN</dc:language></metadata><manifest><item id="chapter" href="Text/简体.xhtml" media-type="application/xhtml+xml"/><item id="toc" href="toc.ncx" media-type="application/x-dtbncx+xml"/></manifest><spine toc="toc"><itemref idref="chapter"/></spine></package>'''.encode()
CHAPTER = '''<?xml version="1.0"?><!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN"><head><title>第一章</title><style>.简体 { color: red; }</style><script>var name = "简体";</script></head><body><p id="简体">头发与发展，<em>简单测试</em>这里还有文本。</p><a href="简体.xhtml#简体" title="点击阅读">目录</a><img src="../Images/简体.jpg" alt="简体图片"/><!--保留简体注释--></body></html>'''.encode()
NCX = '''<?xml version="1.0"?><ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1"><docTitle><text>头发与发展</text></docTitle><navMap><navPoint id="简体" playOrder="1"><navLabel><text>第一章 简单测试</text></navLabel><content src="Text/简体.xhtml#简体"/></navPoint></navMap></ncx>'''.encode()
ASSETS = {'OEBPS/Images/简体.jpg': b'\xff\xd8opaque-image\x00\xff\xd9', 'OEBPS/style.css': '.简体 { color: red; }'.encode(), 'OEBPS/app.js': 'var name = "简体";'.encode()}
TRADITIONAL_OPF = '''<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="book"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>頭髮與發展</dc:title><dc:identifier id="book">繁體ID</dc:identifier><dc:language>zh-TW</dc:language></metadata><manifest><item id="chapter" href="Text/繁體.xhtml" media-type="application/xhtml+xml"/><item id="toc" href="toc.ncx" media-type="application/x-dtbncx+xml"/></manifest><spine toc="toc"><itemref idref="chapter"/></spine></package>'''.encode()
TRADITIONAL_CHAPTER = '''<?xml version="1.0"?><!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml" lang="zh-Hant" xml:lang="zh-TW"><head><title>第一章 測試</title><meta name="description" content="繁體簡介"/><style>.繁體 { color: red; }</style><script>var name = "繁體";</script></head><body><p id="繁體">頭髮與發展，<em>簡單測試</em>這裡還有文本。</p><a href="繁體.xhtml#繁體" title="點擊閱讀">目錄</a><img src="../Images/简体.jpg" alt="繁體圖片"/><!--保留繁體註釋--></body></html>'''.encode()
TRADITIONAL_NCX = '''<?xml version="1.0"?><ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1"><docTitle><text>頭髮與發展</text></docTitle><navMap><navPoint id="繁體" playOrder="1"><navLabel><text>第一章 簡單測試</text></navLabel><content src="Text/繁體.xhtml#繁體"/></navPoint></navMap></ncx>'''.encode()


def fixture(path, broken=False, traditional=False):
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.comment = b'keep archive comment'
        archive.writestr('mimetype', b'application/epub+zip')
        archive.writestr('META-INF/container.xml', CONTAINER)
        archive.writestr('OEBPS/content.opf', TRADITIONAL_OPF if traditional else OPF)
        chapter_name, chapter = ('繁體', TRADITIONAL_CHAPTER) if traditional else ('简体', CHAPTER)
        archive.writestr(f'OEBPS/Text/{chapter_name}.xhtml', b'<html><broken>' if broken else chapter)
        archive.writestr('OEBPS/toc.ncx', TRADITIONAL_NCX if traditional else NCX)
        for name, data in ASSETS.items():
            archive.writestr(name, data)


def check_result(case, path):
    with zipfile.ZipFile(path) as archive:
        case.assertIsNone(archive.testzip())
        case.assertEqual(archive.infolist()[0].filename, 'mimetype')
        case.assertEqual(archive.infolist()[0].compress_type, zipfile.ZIP_STORED)
        chapter = archive.read('OEBPS/Text/简体.xhtml').decode()
        case.assertIn('頭髮與發展', chapter)
        case.assertIn('簡單測試', chapter)
        case.assertIn('這裡還有文本。', chapter)
        case.assertIn('href="简体.xhtml#简体"', chapter)
        case.assertIn('id="简体"', chapter)
        case.assertIn('alt="簡體圖片"', chapter)
        case.assertIn('var name = "简体";', chapter)
        case.assertIn('.简体 { color: red; }', chapter)
        case.assertIn('zh-TW', chapter)
        case.assertIn('簡單測試', archive.read('OEBPS/toc.ncx').decode())
        case.assertIn('简体ID', archive.read('OEBPS/content.opf').decode())
        case.assertEqual(archive.comment, b'keep archive comment')
        for name, data in ASSETS.items():
            case.assertEqual(archive.read(name), data)


def check_simplified_result(case, path):
    with zipfile.ZipFile(path) as archive:
        case.assertIsNone(archive.testzip())
        case.assertEqual(archive.infolist()[0].filename, 'mimetype')
        case.assertEqual(archive.infolist()[0].compress_type, zipfile.ZIP_STORED)
        chapter = archive.read('OEBPS/Text/繁體.xhtml')
        case.assertEqual(structure(TRADITIONAL_CHAPTER), structure(chapter))
        text = chapter.decode()
        for expected in ('头发与发展', '简单测试', '这里还有文本。', 'alt="繁体图片"',
                         'title="点击阅读"', 'content="繁体简介"', 'lang="zh-Hans"',
                         'xml:lang="zh-Hans"', 'href="繁體.xhtml#繁體"', 'id="繁體"',
                         'var name = "繁體";', '.繁體 { color: red; }', '<!--保留繁體註釋-->'):
            case.assertIn(expected, text)
        opf = archive.read('OEBPS/content.opf')
        case.assertEqual(structure(TRADITIONAL_OPF), structure(opf))
        for expected in ('头发与发展', '繁體ID', 'zh-Hans'):
            case.assertIn(expected, opf.decode())
        ncx = archive.read('OEBPS/toc.ncx')
        case.assertEqual(structure(TRADITIONAL_NCX), structure(ncx))
        case.assertIn('简单测试', ncx.decode())
        case.assertEqual(archive.comment, b'keep archive comment')
        for name, data in ASSETS.items():
            case.assertEqual(archive.read(name), data)


class ConversionTests(unittest.TestCase):
    def test_traditional_to_simplified_preserves_links_assets_and_code(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '繁體 中文.epub'
            fixture(path, traditional=True)
            converter = Converter('t2s')
            result = converter.convert_book(path)
            self.assertGreater(result['changed_segments'], 0)
            check_simplified_result(self, path)
            before = path.read_bytes()
            self.assertEqual(converter.convert_book(path)['changed_files'], 0)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(Path(folder).iterdir()), [path])

    def test_simplified_language_tags(self):
        converter = Converter('t2s')
        for language in ('zh', 'zh-TW', 'zh-HK', 'zh-MO', 'zh-Hant', 'zh-Hant-TW',
                         'zh-Hant-HK', 'zh-Hant-MO', 'ZH-hAnT', 'en', 'ja', 'zh-CN', 'zh-Hans'):
            with self.subTest(language=language):
                original = f'<book lang="{language}" xml:lang="{language}"><language>{language}</language><p>繁體</p></book>'.encode()
                converted, _ = converter.convert_xml(original)
                root = parse(converted).getroot()
                target = language if language in ('en', 'ja', 'zh-CN', 'zh-Hans') else 'zh-Hans'
                self.assertEqual(root.get('lang'), target)
                self.assertEqual(root.get('{http://www.w3.org/XML/1998/namespace}lang'), target)
                self.assertEqual(root.find('language').text, target)

    def test_gui_mode_selection_converts_book(self):
        root = tk.Tk()
        root.withdraw()
        try:
            app = App(root)
            self.assertEqual(app.mode.get(), CONVERSION_MODES['s2tw'])
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / '繁體.epub'
                fixture(path, traditional=True)
                app.add_paths([path])
                app.mode_box.current(list(CONVERSION_MODES).index('t2s'))
                app.start()
                self.assertTrue(app.busy)
                self.assertEqual(str(app.mode_box['state']), 'disabled')
                deadline = time.monotonic() + 30
                while app.busy and time.monotonic() < deadline:
                    root.update()
                    time.sleep(0.02)
                self.assertFalse(app.busy, 'GUI conversion timed out')
                self.assertIn('已转换 1 本', app.status.get())
                self.assertEqual(str(app.mode_box['state']), 'readonly')
                check_simplified_result(self, path)
        finally:
            root.destroy()

    def test_source_cli_conversion_modes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for config in CONVERSION_MODES:
                with self.subTest(config=config):
                    path, report = root / f'{config}.epub', root / 'report.json'
                    fixture(path, traditional=config == 't2s')
                    result = subprocess.run([sys.executable, str(Path(__file__).with_name('app.py')),
                                             '--convert', str(path), '--config', config, '--report', str(report)],
                                            capture_output=True, timeout=90)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(report.read_text(encoding='utf-8'))['errors'], [])
                    if config == 't2s':
                        check_simplified_result(self, path)
                    elif config == 's2tw':
                        check_result(self, path)
                    else:
                        with zipfile.ZipFile(path) as archive:
                            chapter = archive.read('OEBPS/Text/简体.xhtml').decode()
                            self.assertIn('頭髮與發展', chapter)
                            self.assertIn('zh-Hant', chapter)

    def test_conversion_preserves_links_assets_and_code(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '中文 空格.epub'
            fixture(path)
            result = Converter().convert_book(path)
            self.assertGreater(result['changed_segments'], 0)
            check_result(self, path)
            self.assertEqual(list(Path(folder).iterdir()), [path])

    def test_invalid_xml_preserves_original_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '损坏.epub'
            fixture(path, broken=True)
            before = path.read_bytes()
            for config in CONVERSION_MODES:
                with self.subTest(config=config):
                    with self.assertRaises(ValueError):
                        Converter(config).convert_book(path)
                    self.assertEqual(path.read_bytes(), before)
                    self.assertEqual(list(Path(folder).iterdir()), [path])

    def test_repeat_is_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'book.epub'
            fixture(path)
            converter = Converter()
            converter.convert_book(path)
            before = path.read_bytes()
            result = converter.convert_book(path)
            self.assertEqual(result['changed_files'], 0)
            self.assertEqual(before, path.read_bytes())

    def test_collect_deduplicates_and_honors_subfolders(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first = root / 'book.EPUB'
            first.touch()
            nested = root / '子目录'
            nested.mkdir()
            second = nested / 'book.epub'
            second.touch()
            self.assertEqual(collect_books([root, first]), [first])
            self.assertEqual(set(collect_books([root, first], recursive=True)), {first, second})

    @unittest.skipUnless(os.environ.get('EPUB_TEST_EXE'), 'Set EPUB_TEST_EXE to test the packaged executable')
    def test_standalone_exe_gui_and_conversion(self):
        executable = str(Path(os.environ['EPUB_TEST_EXE']).resolve())
        with tempfile.TemporaryDirectory(prefix='epub-便携测试-') as folder:
            root = Path(folder)
            good, bad = root / '正常 空格.epub', root / '损坏.epub'
            fixture(good)
            fixture(bad, broken=True)
            original_bad = bad.read_bytes()
            environment = {k: v for k, v in os.environ.items() if not k.startswith(('PYTHON', 'VIRTUAL_ENV'))}
            environment['PATH'] = str(Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32')
            report = root / '报告.json'
            result = subprocess.run([executable, '--convert', str(root), '--report', str(report)], cwd=root, env=environment, timeout=90)
            self.assertEqual(result.returncode, 1)
            summary = json.loads(report.read_text(encoding='utf-8'))
            self.assertEqual(len(summary['results']), 1)
            self.assertEqual(len(summary['errors']), 1)
            check_result(self, good)
            self.assertEqual(bad.read_bytes(), original_bad)
            result = subprocess.run([executable, '--convert', str(good), '--report', str(report)], cwd=root, env=environment, timeout=90)
            self.assertEqual(result.returncode, 0)
            summary = json.loads(report.read_text(encoding='utf-8'))
            self.assertEqual(summary['results'][0]['changed_files'], 0)
            gui_report = root / '界面.json'
            result = subprocess.run([executable, '--self-test', '--report', str(gui_report)], cwd=root, env=environment, timeout=90)
            self.assertEqual(result.returncode, 0)
            gui = json.loads(gui_report.read_text(encoding='utf-8'))
            self.assertEqual(gui['gui'], 'ok')
            self.assertIn('頭髮發展', gui['opencc'])
            self.assertEqual(gui['modes'], list(CONVERSION_MODES.values()))
            fixture(good, traditional=True)
            result = subprocess.run([executable, '--convert', str(good), '--config', 't2s',
                                     '--report', str(report)], cwd=root, env=environment, timeout=90)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(report.read_text(encoding='utf-8'))['errors'], [])
            check_simplified_result(self, good)
            result = subprocess.run([executable, '--self-test', '--config', 't2s', '--report', str(gui_report)],
                                    cwd=root, env=environment, timeout=90)
            self.assertEqual(result.returncode, 0)
            gui = json.loads(gui_report.read_text(encoding='utf-8'))
            self.assertEqual(gui['gui'], 'ok')
            self.assertEqual(gui['mode'], CONVERSION_MODES['t2s'])
            self.assertIn('繁体中文转换测试，头发发展。', gui['opencc'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
