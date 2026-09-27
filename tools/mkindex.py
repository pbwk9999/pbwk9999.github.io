#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成越狱源索引：Packages / Packages.bz2 / Packages.gz / Release

用法（在仓库根目录执行）：
    python3 tools/mkindex.py

纯 Python 标准库实现，不需要 dpkg-* 工具，Windows / macOS / Linux 通用。
配置全部读自仓库根目录的 repo.conf。
"""

import bz2
import gzip
import hashlib
import io
import lzma
import os
import sys
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEBS_DIR = os.path.join(ROOT, 'debs')
DEPICTIONS_CONF = os.path.join(ROOT, 'depictions.conf')

QUOTE = chr(34)
APOSTROPHE = chr(39)
LF = chr(10)

# 这几个字段由脚本自动生成，deb 里如果自带就丢掉，避免出现两份
GENERATED_FIELDS = {'filename', 'size', 'md5sum', 'sha1', 'sha256'}


def read_conf(path):
    """读取 repo.conf（每行 KEY=VALUE，值两边可以有引号）"""
    conf = {}
    if not os.path.exists(path):
        return conf
    with open(path, 'r', encoding='utf-8-sig') as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, val = line.partition('=')
            val = val.strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in (QUOTE, APOSTROPHE):
                val = val[1:-1]
            conf[key.strip()] = val
    return conf


def absolute_url(value, base_url):
    """相对地址补上源根地址"""
    if value.startswith('http://') or value.startswith('https://'):
        return value
    if not base_url:
        return value
    return base_url.rstrip('/') + '/' + value.lstrip('/')


def read_depictions(path, base_url):
    """读取 depictions.conf，返回 {包名: [(字段名, 地址), ...]}

    每行一个包：包名 = Depiction 地址 | SileoDepiction 地址
    地址写相对路径就行，也允许只写其中一个，另一个留空。
    """
    mapping = {}
    if not os.path.exists(path):
        return mapping
    with open(path, 'r', encoding='utf-8-sig') as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _sep, val = line.partition('=')
            parts = [part.strip() for part in val.split('|')]
            fields = []
            if parts and parts[0]:
                fields.append(('Depiction', absolute_url(parts[0], base_url)))
            if len(parts) > 1 and parts[1]:
                fields.append(('SileoDepiction', absolute_url(parts[1], base_url)))
            if fields:
                mapping[key.strip()] = fields
    return mapping


def ar_members(blob):
    """拆开 ar 归档（deb 文件本身就是 ar 归档），返回 {成员名: 内容}"""
    if not blob.startswith(b'!<arch>\n'):
        raise ValueError('不是合法的 deb 文件：缺少 ar 头')
    members, pos = {}, 8
    while pos + 60 <= len(blob):
        header = blob[pos:pos + 60]
        name = header[0:16].decode('utf-8', 'replace').strip().rstrip('/')
        size_field = header[48:58].decode('ascii', 'replace').strip()
        if not size_field.isdigit():
            break
        size = int(size_field)
        start = pos + 60
        members[name] = blob[start:start + size]
        pos = start + size + (size % 2)
    return members


def decompress(data, kind):
    if kind == 'gz':
        return gzip.decompress(data)
    if kind == 'xz':
        return lzma.decompress(data)
    if kind == 'zst':
        try:
            import zstandard
        except ImportError:
            raise SystemExit('这个 deb 的 control 用了 zstd 压缩，请先执行 pip install zstandard')
        return zstandard.ZstdDecompressor().decompress(data)
    return data


def read_control(deb_path):
    """取出 deb 里的 control 文本"""
    with open(deb_path, 'rb') as fh:
        members = ar_members(fh.read())
    for name, kind in (('control.tar.gz', 'gz'), ('control.tar.xz', 'xz'),
                       ('control.tar.zst', 'zst'), ('control.tar', 'none')):
        if name not in members:
            continue
        blob = decompress(members[name], kind)
        with tarfile.open(fileobj=io.BytesIO(blob), mode='r:') as tar:
            for member in tar.getmembers():
                if os.path.basename(member.name) == 'control':
                    handle = tar.extractfile(member)
                    if handle is not None:
                        return handle.read().decode('utf-8', 'replace')
    raise ValueError('deb 里找不到 control 文件')


def split_fields(text):
    """把 control 拆成 [(字段名, 原文片段)]，保留字段顺序和多行续行"""
    fields, key, lines = [], None, []
    for line in text.splitlines():
        if line.startswith('#'):
            continue
        if line[:1] in (' ', '\t') and key is not None:
            lines.append(line.rstrip())
            continue
        if not line.strip() or ':' not in line:
            continue
        if key is not None:
            fields.append((key, lines))
        key, _, _rest = line.partition(':')
        lines = [line.rstrip()]
    if key is not None:
        fields.append((key, lines))
    result = []
    for key, lines in fields:
        result.append((key, LF.join(lines)))
    return result


def make_stanza(deb_path, rel_path, depictions=None):
    """把一个 deb 变成 Packages 里的一段"""
    with open(deb_path, 'rb') as fh:
        blob = fh.read()
    fields = split_fields(read_control(deb_path))

    normal, description, name, version = [], None, '', ''
    for key, block in fields:
        low = key.strip().lower()
        if low in GENERATED_FIELDS:
            continue
        if low == 'description':
            description = block
            continue
        if low == 'package':
            name = block.partition(':')[2].strip()
        elif low == 'version':
            version = block.partition(':')[2].strip()
        normal.append(block)

    # 详情页地址：depictions.conf 里配过的以配置为准，覆盖 deb 自带的
    extra = (depictions or {}).get(name, [])
    if extra:
        overridden = {key.lower() for key, _value in extra}
        normal = [block for block in normal
                  if block.partition(':')[0].strip().lower() not in overridden]
        for key, value in extra:
            normal.append('%s: %s' % (key, value))

    # 按 Debian 惯例：路径、大小、校验和放在 Description 之前
    normal.append('Filename: %s' % rel_path.replace(os.sep, '/'))
    normal.append('Size: %d' % len(blob))
    normal.append('MD5sum: %s' % hashlib.md5(blob).hexdigest())
    normal.append('SHA1: %s' % hashlib.sha1(blob).hexdigest())
    normal.append('SHA256: %s' % hashlib.sha256(blob).hexdigest())
    if description:
        normal.append(description)
    return name, version, LF.join(normal)


def write_text(path, text):
    """统一 LF 换行 + 无 BOM，客户端对这两点很敏感"""
    with open(path, 'wb') as fh:
        fh.write(text.encode('utf-8'))


def build_release(conf):
    name = conf.get('REPO_NAME', 'My Repo')
    return LF.join([
        'Origin: %s' % name,
        'Label: %s' % name,
        'Suite: stable',
        'Version: 1.0',
        'Codename: ios',
        'Architectures: iphoneos-arm iphoneos-arm64',
        'Components: main',
        'Description: %s' % conf.get('REPO_DESCRIPTION', ''),
        '',
    ])


def main():
    conf = read_conf(os.path.join(ROOT, 'repo.conf'))
    depictions = read_depictions(DEPICTIONS_CONF, conf.get('REPO_URL', ''))
    if not os.path.isdir(DEBS_DIR):
        os.makedirs(DEBS_DIR)

    stanzas, problems = [], []
    for entry in sorted(os.listdir(DEBS_DIR)):
        if not entry.lower().endswith('.deb'):
            continue
        deb_path = os.path.join(DEBS_DIR, entry)
        try:
            stanzas.append(make_stanza(deb_path, os.path.join('debs', entry), depictions))
        except Exception as err:  # 单个包有问题不该拖垮整个源
            problems.append('%s - %s' % (entry, err))

    stanzas.sort(key=lambda item: (item[0].lower(), item[1]))
    body = (LF + LF).join(item[2] for item in stanzas)
    if body:
        body += LF

    write_text(os.path.join(ROOT, 'Packages'), body)
    raw = body.encode('utf-8')
    with open(os.path.join(ROOT, 'Packages.gz'), 'wb') as fh:
        fh.write(gzip.compress(raw, 9, mtime=0))
    with open(os.path.join(ROOT, 'Packages.bz2'), 'wb') as fh:
        fh.write(bz2.compress(raw, 9))
    write_text(os.path.join(ROOT, 'Release'), build_release(conf))

    print('索引已重建：Packages / Packages.gz / Packages.bz2 / Release')
    print('  源名   ：%s' % conf.get('REPO_NAME', '?'))
    print('  根地址 ：%s' % conf.get('REPO_URL', '?'))
    print('  包数量 ：%d' % len(stanzas))
    for name, version, _ in stanzas:
        print('    - %s %s' % (name, version))
    for problem in problems:
        print('  [跳过] %s' % problem, file=sys.stderr)


if __name__ == '__main__':
    main()
