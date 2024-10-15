# File extractor and combiner for MUA3
# by yretenai (creator of Cethleann), therathatter, ak2yny


import glob
from argparse import ArgumentParser
from pathlib import Path
from struct import pack, unpack, calcsize

from MUA3_Formats import getFileExtension
from MUA3_KTSR import _extractKS
from MUA3_ZL import backup, re_pack, un_pack, _re_pack, _un_pack


ZERO_INT = bytes(4)


def extract(decompressed: str, output_folder: Path):
    backup(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    file_addresses = []
    size_bin = i = unpack('< I', decompressed[:calcsize('< I')])[0]
    while i > 0:
        current_address = (size_bin - i + 1) * 4
        file_addresses.append(unpack('< I', decompressed[current_address:current_address + calcsize('< I')])[0])
        i -= 1
    for file_address in file_addresses:
        file_name = str(i).zfill(4)
        i += 1
        if file_address != 0 or i == len(file_addresses):
            file_data = b'' if file_address == 0 else decompressed[file_address:next(filter(lambda x: x != 0, file_addresses[i:]))] if i < len(file_addresses) else decompressed[file_address:]
            output_file = output_folder / (file_name + getFileExtension(file_data[:12].split(b'\x00')[0]))
            backup(output_file)
            output_file.write_bytes(file_data)

def combine(input_folder: Path) -> str:
    input_files = [x for x in input_folder.iterdir() if x.stem.isdigit()]
    input_numbers = [int(x.stem) for x in input_files]
    file_count = input_numbers[-1] + 1
    head = pack('< I', file_count)
    zero_bnum = 4 - (file_count + 1) % 4
    data = ZERO_INT * zero_bnum
    file_size = (file_count + 1 + zero_bnum) * 4
    for i in range(0, file_count):
        if i in input_numbers:
            input_file = next(x for x in input_files if int(x.stem) == i)
            head += pack('< I', file_size)
            data += input_file.read_bytes()
            file_size += input_file.stat().st_size
        else:
            head += ZERO_INT
    return re_pack(head + data)

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