"""Offline EPUB Simplified / Traditional Chinese converter."""
from __future__ import annotations

import copy
from io import BytesIO
import os
from pathlib import Path
import tempfile
import zipfile

from lxml import etree
from opencc import OpenCC

XML_EXTENSIONS = {'.xhtml', '.html', '.htm', '.opf', '.ncx', '.xml', '.svg'}
TEXT_ATTRIBUTES = {'title', 'alt', 'aria-label', 'aria-description', 'label', 'placeholder', 'file-as'}
MACHINE_ELEMENTS = {'script', 'style', 'identifier', 'date'}
META_TEXT_NAMES = {'description', 'keywords', 'author', 'title'}
SIMPLIFIED_LANGUAGES = {'zh', 'zh-cn', 'zh-hans', 'zh-hans-cn'}
TRADITIONAL_LANGUAGES = {
    'zh', 'zh-tw', 'zh-hk', 'zh-mo', 'zh-hant',
    'zh-hant-tw', 'zh-hant-hk', 'zh-hant-mo',
}
CONVERSION_LANGUAGES = {
    's2tw': ('zh-TW', SIMPLIFIED_LANGUAGES),
    's2t': ('zh-Hant', SIMPLIFIED_LANGUAGES),
    't2s': ('zh-Hans', TRADITIONAL_LANGUAGES),
}


def parse(data):
    return etree.parse(BytesIO(data), etree.XMLParser(resolve_entities=False, no_network=True))


def local_name(name):
    return name.rsplit('}', 1)[-1].lower()


def text_attribute(node, key):
    name = local_name(key)
    return name in TEXT_ATTRIBUTES or (
        local_name(node.tag) == 'meta' and name == 'content'
        and node.get('name', '').lower() in META_TEXT_NAMES
    )


def structure(data):
    """Validate tree topology and all IDs, paths, CSS, and other machine attributes."""
    def visit(node):
        if not isinstance(node.tag, str):
            return ('special', etree.tostring(node, with_tail=False))
        attributes = tuple(sorted((key, value) for key, value in node.attrib.items()
                                  if local_name(key) != 'lang' and not text_attribute(node, key)))
        return (node.tag, attributes, tuple(visit(child) for child in node))
    return visit(parse(data).getroot())


class Converter:
    def __init__(self, config='s2tw'):
        if config not in CONVERSION_LANGUAGES:
            raise ValueError('不支持的转换模式')
        self.opencc = OpenCC(config)
        self.language, self.source_languages = CONVERSION_LANGUAGES[config]

    def convert_xml(self, data):
        tree = parse(data)
        changes = 0

        def convert_text(value):
            nonlocal changes
            result = self.opencc.convert(value)
            changes += result != value
            return result

        def walk(node, blocked=False):
            nonlocal changes
            if not isinstance(node.tag, str):
                return
            name = local_name(node.tag)
            blocked = blocked or name in MACHINE_ELEMENTS
            if not blocked:
                if name == 'language' and node.text and node.text.strip().lower() in self.source_languages:
                    node.text = self.language
                    changes += 1
                elif node.text:
                    node.text = convert_text(node.text)
                for key, value in list(node.attrib.items()):
                    if text_attribute(node, key):
                        node.set(key, convert_text(value))
                    elif local_name(key) == 'lang' and value.strip().lower() in self.source_languages:
                        node.set(key, self.language)
                        changes += 1
            for child in node:
                walk(child, blocked)
                if not blocked and child.tail:
                    child.tail = convert_text(child.tail)

        walk(tree.getroot())
        if changes == 0:
            return data, 0
        result = etree.tostring(tree, encoding='utf-8', xml_declaration=True)
        if structure(data) != structure(result):
            raise ValueError('转换后的文档结构与原文不一致')
        return result, changes

    def convert_book(self, filename):
        book = Path(filename).resolve(strict=True)
        if book.suffix.lower() != '.epub' or not book.is_file():
            raise ValueError('请选择 EPUB 文件')
        original_stat = book.stat()
        stamp = (original_stat.st_size, original_stat.st_mtime_ns)
        temporary = None
        changed_files = changed_segments = 0
        try:
            with zipfile.ZipFile(book) as source:
                names = source.namelist()
                if len(names) != len(set(names)):
                    raise ValueError('EPUB 包内存在重名文件')
                if source.testzip() is not None:
                    raise ValueError('原 EPUB 的 ZIP 完整性检查失败')
                if source.read('mimetype') != b'application/epub+zip':
                    raise ValueError('文件不是有效的 EPUB 格式')
                if 'META-INF/container.xml' not in names:
                    raise ValueError('EPUB 缺少 META-INF/container.xml')
                fd, temporary_name = tempfile.mkstemp(prefix='.epub-convert-', suffix='.tmp', dir=book.parent)
                os.close(fd)
                temporary = Path(temporary_name)
                with zipfile.ZipFile(temporary, 'w') as output:
                    output.comment = source.comment
                    infos = sorted(source.infolist(), key=lambda info: info.filename != 'mimetype')
                    for info in infos:
                        data = source.read(info.filename)
                        if Path(info.filename).suffix.lower() in XML_EXTENSIONS:
                            try:
                                data, count = self.convert_xml(data)
                            except Exception as error:
                                raise ValueError(f'无法转换 {info.filename}：{error}') from error
                            changed_files += bool(count)
                            changed_segments += count
                        entry = copy.copy(info)
                        if entry.filename == 'mimetype':
                            entry.compress_type = zipfile.ZIP_STORED
                            entry.extra = b''
                        output.writestr(entry, data)
                with zipfile.ZipFile(temporary) as output:
                    if output.testzip() is not None or output.namelist() != [i.filename for i in infos]:
                        raise ValueError('生成的 EPUB 完整性检查失败')
                    first = output.infolist()[0]
                    if first.filename != 'mimetype' or first.compress_type != zipfile.ZIP_STORED:
                        raise ValueError('生成的 EPUB 封装格式不正确')
                    for info in source.infolist():
                        before, after = source.read(info.filename), output.read(info.filename)
                        if Path(info.filename).suffix.lower() in XML_EXTENSIONS:
                            if structure(before) != structure(after):
                                raise ValueError(f'链接或结构发生变化：{info.filename}')
                        elif before != after:
                            raise ValueError(f'非文本资源发生变化：{info.filename}')
            current = book.stat()
            if (current.st_size, current.st_mtime_ns) != stamp:
                raise ValueError('转换期间原文件被其他程序修改，未覆盖')
            if changed_files:
                os.replace(temporary, book)
            return {'file': str(book), 'changed_files': changed_files, 'changed_segments': changed_segments}
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()


def collect_books(paths, recursive=False):
    found = {}
    for value in paths:
        path = Path(value).expanduser().resolve(strict=True)
        if path.is_dir():
            candidates = path.rglob('*') if recursive else path.iterdir()
            for candidate in candidates:
                if candidate.is_file() and candidate.suffix.lower() == '.epub':
                    resolved = candidate.resolve()
                    found[os.path.normcase(str(resolved))] = resolved
        elif path.suffix.lower() == '.epub':
            found[os.path.normcase(str(path))] = path
        else:
            raise ValueError(f'不支持的文件：{path.name}')
    return sorted(found.values(), key=lambda path: str(path).casefold())
