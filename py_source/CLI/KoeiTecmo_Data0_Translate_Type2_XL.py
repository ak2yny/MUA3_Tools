# Koei Tecmo V2 (XML) data extraction script

import glob
from argparse import ArgumentParser
from io import BytesIO
from itertools import count
from pathlib import Path
from struct import iter_unpack, pack, unpack, unpack_from
from typing import BinaryIO

#from .HyruleWarriors_Data import re_pack2, un_pack_2
from .KoeiTecmo_Arch import chunk_size_from_name
from .KoeiTecmo_Data0 import DATA_LINK, get_type
from .KoeiTecmo_XL import _extractXL, combineXL, set_xl_encoding
from .lib.lib_gust import getFileExtension
from .MUA3_ZL import backup, re_pack_v2, un_pack_v2


def re_pack_t2_rec(stream: BinaryIO, input_folder: Path, pos: int = 0) -> bytes:
    if pos > 0: stream.seek(pos)
    input_files = {int(f.stem.split('_', 1)[0]): f for f in input_folder.iterdir()}
    count, = unpack('< I', stream.read(4))
    of_n_sz = unpack(f'< {count * 2}I', stream.read(count * 8))
    offset = (1 + count * 2) * 4
    data = bytes()
    of_n_sz2 = []
    for i, (old_o, size) in enumerate(zip(of_n_sz[::2], of_n_sz[1::2])):
        old_o += pos
        stream.seek(old_o)
        if i in input_files:
            input_file = input_files[i]
            chunk_size, zp = chunk_size_from_name(input_file.stem)
            d = (re_pack_t2_rec(BytesIO(un_pack_v2(stream)[0]), input_file)
                if chunk_size else re_pack_t2_rec(stream, input_file, old_o)) \
                if input_file.is_dir() else input_file.read_bytes()
            if chunk_size: # WIP: negative...
                d = re_pack_v2(d, chunk_size, zp=zp)
            size = len(d)
        else:
            d = stream.read(size)
        padding = -size % 4
        data += d + bytes(padding)
        of_n_sz2 += [offset, size]
        offset += size + padding
    return pack(f'< {1 + count * 2}I', count, *of_n_sz2) + data

def re_pack_t2(input_folder: Path, data_file: Path, info_file: Path):
    # WIP: Slow performance
    if not (data_file.exists() and info_file.exists()):
        raise ValueError('Original files not found')
    old_info = info_file.read_bytes()
    backup(info_file)
    for i in count(0): # WIP: better solution?
        old_data = data_file.with_stem(f'{data_file.stem}.backup{i}')
        if not old_data.exists(): break
    data_file.rename(old_data)
    info = bytes()
    input_files = {(file_names[ID] if ID in file_names else int(ID)): f
        for f in input_folder.iterdir() if (ID := f.stem.split('_', 1)[0])}
    prev_item_number = -1
    with data_file.open(mode='wb') as f:
        with old_data.open(mode='rb') as of:
            for i, (old_o, dc_size, c_size, cat) in enumerate(iter_unpack('<4Q', old_info)):
                offset = f.tell()
                if i in input_files:
                    input_file = input_files[i]
                    chunk_size, zp = chunk_size_from_name(input_file.stem)
                    data = (re_pack_t2_rec(BytesIO(un_pack_v2(stream)[0]), input_file, 0)
                        if chunk_size else re_pack_t2_rec(of, input_file, old_o)) \
                        if input_file.is_dir() else input_file.read_bytes()
                    dc_size = len(data)
                    if chunk_size: # WIP: negative...
                        data = re_pack_v2(data, chunk_size, dc_size, zp)
                    c_size = len(data)
                    f.write(data)
                else:
                    of.seek(old_o)
                    f.write(of.read(c_size))
                f.seek(-c_size % 0x100, 1)
                info += pack('<4Q', offset, dc_size, c_size, cat)
        f.truncate()
    info_file.write_bytes(info)

def _re_pack(input_folder: Path):
    for input_file in input_folder.rglob('*.txt'):
        input_file.with_suffix('.xl').write_bytes(combineXL(input_file))
        input_file.unlink()
    data_file = Path(f'{input_folder}.BIN')
    info_file, _typ, v = get_type(data_file)
    assert(v != 2)
    #if v == 2:
    #    re_pack2(input_folder)
    #else:
    re_pack_t2(input_folder, data_file, info_file)

def is_text_xl(data: bytes, ext: str) -> bool:
    if ext == '.xl':
        _sz, dt_sz, *_, table_offset = unpack_from('< 4HI', data, 4)
        start = 20 if table_offset == 1 else 16
        if 0 in data[start:start + dt_sz]:
            return True
    return False

# Based on KoeiTecmo_Arch
def un_pack_t2_rec(stream: BinaryIO, output_folder: Path, pos: int = 0, depth: int = 0) -> bool:
    """Scan file for offset and size header and unpack, then return True if such a file, otherwise return False."""
    if depth > 10: return False
    if pos > 0: stream.seek(pos)
    try:
        count, = unpack('< I', stream.read(4))
        of_n_sz = unpack(f'< {count * 2}I', stream.read(count * 8))
        calc_1st_of = 4 + count * 8
        align = -calc_1st_of % 0x10
        if count > 0 and (of_n_sz[0] == calc_1st_of or
            (stream.read(align) == bytes(align) and calc_1st_of + align == of_n_sz[0])):
            for i, (offset, size) in enumerate(zip(of_n_sz[::2], of_n_sz[1::2])):
                offset += pos
                stream.seek(offset)
                name = f'{i:04d}'
                try:
                    # WIP: Only the first level?
                    data, chunk_size, magic = un_pack_v2(stream)
                    sub_stream = BytesIO(data)
                    offset = 0
                    name = f'{name}_{chunk_size}.{1 if magic == 0x0031707A else 0}'
                except:
                    sub_stream = stream
                    data = None
                if not un_pack_t2_rec(sub_stream, output_folder / name,
                                      offset, depth + 1):
                    data = data or stream.read(size)
                    ext = getFileExtension(data[:12].split(b'\x00', 1)[0])
                    if is_text_xl(data, ext):
                        output_folder.mkdir(parents=True, exist_ok=True)
                        (output_folder / f'{name}{ext}').write_bytes(data)
            return True
        stream.seek(pos)
        return False
    except:
        stream.seek(pos)
        return False

# Based on KoeiTecmo_Data0
def un_pack_t2(info: bytes, data_file: Path, output_folder: Path):
    with data_file.open(mode='rb') as f:
        for i, (offset, dc_size, c_size, cat) in enumerate(iter_unpack('<4Q', info)):
            if dc_size == 0 and c_size == 0 or dc_size < 8: # 0 byte files
                continue
            c_bool = dc_size > c_size or cat == 3 # cat is unconfirmed
            if not c_bool:
                if dc_size < c_size:
                    f.seek(offset)
                    chunk_size, = unpack_from('< I', f.read(4))
                    c_bool = chunk_size % 0x80 == 0 and chunk_size * 2 > c_size
                else:
                    assert(c_size == dc_size)
            f.seek(offset)
            #print(f'{offset:08X}', f'{i:08d}')
            name = file_ids.get(i, f'{i:08}')
            if c_bool:
                decompressed, chunk_size, magic = un_pack_v2(f)
                stream = BytesIO(decompressed)
                offset = 0
                name = f'{name}_{chunk_size}.{1 if magic == 0x0031707A else 0}'
            else:
                decompressed = f.read(12)
                f.seek(offset)
            ext = getFileExtension(decompressed[:12].split(b'\x00', 1)[0])
            if not (ext == '.bin' and
                un_pack_t2_rec(stream if c_bool else f,
                               output_folder / name, offset)):
                if (i in file_ids or ext == '.xl') and not c_bool:
                    decompressed = f.read(c_size)
                if i in file_ids or is_text_xl(decompressed, ext):
                    (output_folder / f'{name}{ext}').write_bytes(decompressed)
    #for d, _dirs, files in output_folder.walk(top_down=False):
    #    if not files:
    #        try: d.rmdir()
    #        except: pass # subdir is not removed/empty
            #for d2, *dirs_files in d.walk(top_down=False):
            #    if not any(dirs_files):
            #        d2.rmdir()
    for xl_file in output_folder.rglob('*.xl'):
        _extractXL(xl_file)

info_file, data_file = None, None
file_ids, file_names = {}, {}

def _un_pack(input_file: Path):
    other_file, typ, v = get_type(input_file)
    globals()[f'{typ}_file'] = input_file
    globals()[f'{DATA_LINK[typ]}_file'] = other_file

    output_folder = data_file.with_suffix('')
    backup(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    info = info_file.read_bytes() # raises file not found exception if incompatible .bin
    assert(v != 2)
    #if v == 2:
    #    un_pack_2(info, data_file, output_folder)
    #else:
    un_pack_t2(info, data_file, output_folder)

def main():
    parser = ArgumentParser()
    parser.add_argument('input', help='input file (supports glob)')
    parser.add_argument('additional_files', nargs='?', help='JSON file with additional file list and file IDs')
    parser.add_argument('-e', '--encoding', type=str, default='utf-8', help='define a specific encoding (utf-8, if not defined)')
    args = parser.parse_args()
    input_files = glob.glob(args.input.replace('[', '[[]'), recursive=True)

    if not input_files:
        raise ValueError('No files found')
    if args.additional_files:
        j = Path(args.additional_files if args.additional_files.casefold()[-5:] == '.json' else f'{args.additional_files}.json')
        if j.exists():
            import json
            global file_ids
            with j.open() as f:
                file_ids = {int(k): v for k, v in json.load(f).items()}
    set_xl_encoding(args.encoding)

    for input_file in input_files:
        input_file = Path(input_file)

        if input_file.is_dir():
            global file_names
            if not file_names:
                file_names = {v: k for k, v in file_ids.items()}
            _re_pack(input_file)
        elif input_file.suffix.casefold() == '.bin':
            _un_pack(input_file)

if __name__ == '__main__':
    main()