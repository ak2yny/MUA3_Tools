# File extractor and combiner for Fire Emblem Warriors (and other Koei Tecmo games)
# by yretenai (creator of Cethleann), therathatter, ak2yny


import glob
from argparse import ArgumentParser
from pathlib import Path
from struct import pack, unpack_from

from .lib.lib_gust import getFileExtension
from .MUA3_ZL import backup, un_pack_v2


def extract_rec(data: bytes, output_folder: Path, recursive: bool = True, pos: int = 0):
    output_folder.mkdir(parents=True, exist_ok=True) # WIP: parent + exist only in first level
    count_bin, = unpack_from('< I', data, pos)
    of_n_sz = unpack_from(f'< {count_bin * 2}I', data, pos + 4)
    for i, (offset, size) in enumerate(zip(of_n_sz[::2], of_n_sz[1::2])):
        offset += pos
        ext = getFileExtension(data[offset:offset + 12].split(b'\x00')[0])
        if recursive and ext == '.bin':
            count, first_offset = unpack_from('<2I', data, offset)
            if count > 0 and first_offset == 4 + count * 8:
                extract_rec(data, output_folder / f'{i:04d}', True, offset)
                continue
        (output_folder / (f'{i:04d}{ext}')).write_bytes(data[offset:offset + size])

def combine(input_folder: Path) -> bytes:
    input_files = tuple(input_folder.iterdir())
    count_bin = len(input_files)
    if count_bin == 0: return bytes(0)
    offset = (1 + count_bin * 2) * 4
    data = bytes(0)
    of_n_sz = []
    dir_check = tuple(f.is_dir() for f in input_files)
    if all(dir_check): # recurse into dir
        for input_folder in input_files:
            bin_data = combine(input_folder)
            size = len(bin_data)
            data += bin_data
            of_n_sz += [offset, size]
            offset += size
    elif any(dir_check):
        raise ValueError('The folder structure is incorrect. Expected folders and sub-folders that contain either files only or folders only.')
    else:
        for input_file in input_files:
            size = input_file.stat().st_size
            data += input_file.read_bytes()
            of_n_sz += [offset, size]
            offset += size
    return pack(f'< {1 + count_bin * 2}I', count_bin, *of_n_sz) + data + bytes(-len(data) % 4)

def _extract(input_file: Path, output_folder: Path, recursive: bool):
    backup(output_folder)
    with input_file.open('rb') as f:
        if f.read(4) == b'zp1\x00':
            f.seek(0)
            data, chunk_size, _magic = un_pack_v2(f)
            extract_rec(data, output_folder, recursive)
            return
    extract_rec(input_file.read_bytes(), output_folder, recursive)

def _combine(input_folder: Path, output_file: Path):
    backup(output_file)
    output_file.write_bytes(combine(input_folder))

def main():
    parser = ArgumentParser()
    parser.add_argument('input', help='input file (supports glob)')
    parser.add_argument('-r', '--recursive', help='Recursively unpack .bin (depth 1)', action='store_true')
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
            _extract(input_file, input_file.parent / input_file.stem, args.recursive)
            found_any = True

    if not found_any:
        raise ValueError('No files found')

if __name__ == '__main__':
    main()