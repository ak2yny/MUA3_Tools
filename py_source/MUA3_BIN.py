# File extractor and combiner for MUA3
# by yretenai (creator of Cethleann), therathatter, ak2yny


import glob
from argparse import ArgumentParser
from pathlib import Path
from struct import pack, unpack_from

from MUA3_Formats import getFileExtension
from MUA3_KTSR import _extractKS
from MUA3_ZL import backup, re_pack, un_pack, _re_pack, _un_pack


ZERO_INT = bytes(4)


def get_offsets(decompressed: bytes) -> tuple:
    """Read a .bin file and return all offsets in a tuple"""
    count_bin, = unpack_from('< I', decompressed)
    file_offsets = unpack_from(f'< {count_bin}I', decompressed, 4)
    return file_offsets

def extract(decompressed: bytes, output_folder: Path):
    backup(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    count_bin, = unpack_from('< I', decompressed)
    file_offsets = unpack_from(f'< {count_bin}I', decompressed, 4)
    for i, offset in enumerate(file_offsets):
        # Important note: The file name (number) differs from the original extractors, because the header may include empty spaces. This includes the (not extracted) empty spaces in the numbering, so the combiner remembers to add an empty space again and includes the correct file count.
        file_name = f'{i:04d}'
        if offset != 0 or i == count_bin - 1: # need to extract last file to know the total count
            file_data = decompressed[offset:next(filter(lambda x: x != 0, file_offsets[i + 1:]))] if i < count_bin - 1 else \
                        b'' if offset == 0 else \
                        decompressed[offset:]
            output_file = output_folder / (file_name + getFileExtension(file_data[:12].split(b'\x00')[0]))
            backup(output_file)
            output_file.write_bytes(file_data)

def combine(input_folder: Path) -> bytes:
    input_files = [x for x in input_folder.iterdir() if x.stem.isdigit()]
    file_count = int(input_files[-1].stem) + 1
    head_count = file_count + 1 + (4 - (file_count + 1) % 4)
    head_bin = [file_count] + [0] * (head_count - 1)
    offset = head_count * 4
    data = b''
    for input_file in input_files:
        head_bin[int(input_file.stem) + 1] = offset
        data += input_file.read_bytes()
        offset += input_file.stat().st_size
    return re_pack(pack(f'< {head_count}I', *head_bin) + data)

def _extractZ(input_file: Path, output_folder: Path):
    if output_folder.suffix.casefold() == '.bin':
        extract(un_pack(input_file), output_folder)
    else:
        _un_pack(input_file, output_folder)

def _extract(input_file: Path, output_folder: Path):
    extract(input_file.read_bytes(), output_folder)

def _combine(input_folder: Path, output_file: Path):
    backup(output_file)
    output_file.write_bytes(combine(input_folder))

def main():
    parser = ArgumentParser()
    parser.add_argument('input', help='input file (supports glob)')
    args = parser.parse_args()
    input_files = glob.glob(args.input.replace('[', '[[]'), recursive=True)

    if not input_files:
        raise ValueError('No files found')

    for input_file in input_files:
        input_file = Path(input_file)
        ext = input_file.suffix.casefold()

        if input_file.is_dir():
            ext = '.ZL_' if ext == '.bin' else '.bin.ZL_'
            output_file = Path(f'{input_file}{ext}')
            _combine(input_file, output_file)
        elif input_file.suffix.upper() == '.ZL_':
            output_folder = input_file.parent / input_file.stem
            _extractZ(input_file, output_folder)
        elif ext == '.bin':
            output_folder = input_file.parent / input_file.stem
            _extract(input_file, output_folder)
        elif ext == '.ktsl2stbin' or ext == '.ktsl2asbin':
            output_folder = input_file.parent / input_file.stem
            _extractKS(input_file, output_folder)
        else: # loose files to be compressed
            output_file = Path(f'{input_file}.ZL_')
            _re_pack(input_file, output_file)

if __name__ == '__main__':
    main()