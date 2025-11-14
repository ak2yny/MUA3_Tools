# File container/archive extractor and combiner for Koei Tecmo games
# by yretenai (creator of Cethleann), therathatter, ak2yny


import glob
from argparse import ArgumentParser
from io import BytesIO
from pathlib import Path
from struct import pack, unpack
from typing import BinaryIO

from .lib.lib_gust import getFileExtension
from .MUA3_ZL import backup, re_pack_v2, un_pack_v2


def chunk_size_from_name(name: str) -> tuple[int]:
    # WIP: Can chunk_size be negative? .isdigit() fails on negative
    chunk_size, zp = '00'
    file_info = name.rsplit('_', 1)
    #_, *chunk_size = input_file.stem.rsplit('_', 1) + [0]
    #chunk_size = chunk_size[0]
    if len(file_info) > 1:
        chunk_size = file_info[-1]
        if '.' in chunk_size:
            chunk_size, zp, *_ = chunk_size.split('.')
    #    if len(chunk_size) > 1 and chunk_size[-2] == '.':
    #        chunk_size, zp = chunk_size[-1].split('.')
    return (int(chunk_size) if chunk_size.isdigit() else 0,
            int(zp) if len(zp) == 1 and zp.isdigit() else 0)

def extract_rec(stream: BinaryIO, output_folder: Path, pos: int = 0) -> bool:
    """Scan file for offset and size header and unpack, then return True if such a file, otherwise return False."""
    # WIP: Can create bug (incorrect ID), including undeletable directories
    if pos > 0: stream.seek(pos)
    try:
        count, = unpack('< I', stream.read(4))
        of_n_sz = unpack(f'< {count * 2}I', stream.read(count * 8))
        calc_1st_of = 4 + count * 8
        align = -calc_1st_of % 0x10
        if 0 < count < 0xFFFF and (of_n_sz[0] == calc_1st_of or
            (stream.read(align) == bytes(align) and calc_1st_of + align == of_n_sz[0])):
            output_folder.mkdir()
            for i, (offset, size) in enumerate(zip(of_n_sz[::2], of_n_sz[1::2])):
                offset += pos
                stream.seek(offset)
                try:
                    # WIP: Only the first level?
                    data, chunk_size, magic = un_pack_v2(stream)
                    sub_stream = BytesIO(data)
                    offset = 0
                    name = f'{i:04d}_{chunk_size}.{1 if magic == 0x0031707A else 0}'
                except:
                    name = f'{i:04d}'
                    sub_stream = stream
                    data = None
                if not extract_rec(sub_stream, output_folder / name, offset):
                    data = data or stream.read(size)
                    (output_folder / f'{name}{getFileExtension(
                        data[:12].split(b'\x00')[0])}'
                    ).write_bytes(data)
            return True
        stream.seek(pos)
        return False
    except:
        stream.seek(pos)
        return False

def combine_rec(input_folder: Path) -> bytes:
    # Note: Can be memory intensive, not very efficient
    input_files = tuple(input_folder.iterdir())
    count = len(input_files)
    if count == 0: return bytes(0)
    offset = (1 + count * 2) * 4
    data = bytes()
    of_n_sz = []
    # Note: accepts mixed dir/file in container, might be incorrect
    for f in input_files:
        chunk_size, zp = chunk_size_from_name(f.name)
        d = combine_rec(f) if f.is_dir() else f.read_bytes()
        if chunk_size: # WIP: chunk_size_from_name can only return postive int at this time
            d = re_pack_v2(d, chunk_size, zp=zp)
        size = len(d)
        padding = -size % 4
        data += d + bytes(padding)
        of_n_sz += [offset, size]
        offset += size + padding
    return pack(f'< {1 + count * 2}I', count, *of_n_sz) + data

def _extract(input_file: Path, output_folder: Path):
    backup(output_folder)
    with input_file.open('rb') as f:
        _ = extract_rec(f, output_folder)

def _combine(input_folder: Path, output_file: Path):
    backup(output_file)
    output_file.write_bytes(combine_rec(input_folder))

def main():
    parser = ArgumentParser()
    parser.add_argument('input', help='input file (supports glob)')
    args = parser.parse_args()
    input_files = glob.glob(args.input.replace('[', '[[]'), recursive=True)

    if not input_files:
        raise ValueError('No files found')

    found_any = False
    for input_file in input_files:
        input_file = Path(input_file)

        if input_file.is_dir():
            _combine(input_file, Path(f'{input_file}.bin'))
            found_any = True
        elif input_file.suffix.casefold() == '.bin':
            _extract(input_file, input_file.parent / input_file.stem)
            found_any = True

    if not found_any:
        raise ValueError('No files found')

if __name__ == '__main__':
    main()