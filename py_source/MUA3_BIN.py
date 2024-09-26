# File extractor and combiner for MUA3
# by yretenai (creator of Cethleann), ak2yny, Hairo R. Carela (parts of ktsl2asbin)


import glob
from argparse import ArgumentParser
from pathlib import Path
from struct import pack, unpack, calcsize

from MUA3_Formats import ALL_FORMATS
from MUA3_ZL import backup, re_pack, un_pack, _re_pack, _un_pack


def getFileExtension(file_format: str) -> str:
    for f in [file_format, file_format[:4], file_format[:8]]:
        if f in ALL_FORMATS: return ALL_FORMATS[f]
    return '.bin'
    # b'\xf9\x7d\x07' -> LINKDATA found in AoT2
    # b'\xdf' -> ? found in model files
    # ?
    # b'LLOC' -> COLL
    # b'ONUN' -> NUNO
    # b'VNUN' -> NUNV
    # b'SNUN' -> NUNS
    # b'TFOS' -> SOFT
    # b'RIAH' -> HAIR
    # Don't know what the value would be in Python
    # b'\x00\x19  _  \x12\x16': '.struct', # 0x1612_1900 StructTable???
    # b'\x1A\x45  _  \xDF\xA3': '.webm', # 0xA3DF_451A WEBM???
    # b'\x00\x00  _  \x01\x00': '.gz', # 0x0001_0000 Compressed???
    # b'\x00\x00  _  \x02\x00': '.gz', # 0x0002_0000 CompressedChonky???


def extractKS(data: str, output_folder: Path):
    backup(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    file_start = 128 # KTSR header size, don't process header at this time
    i = 0
    while file_start < len(data):
        file_head = data[file_start:file_start + 8]
        file_end = file_start + unpack('< I', file_head[4:8])[0]
        output_file = output_folder / (str(i).zfill(4) + getFileExtension(file_head[:4]))
        output_file.write_bytes(data[file_start:file_end])
        i += 1
        # note for future sound editing: Each KTSS file has a section of 64 bytes before it starts. Not sure if it's part of the container. The magic seems to be '09 d4 f4 15'. The containers have varying lines of 00 bytes between each file (0, 16, 32).
        for m in [file_head[:4], b'KOVS', b'KTSS']:
            file_start = data.find(m, file_end + 64, file_end + 128)
            if file_start > 0: break
        else:
            break

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
    data = pack('< I', 0) * zero_bnum
    file_size = (file_count + 1 + zero_bnum) * 4
    for i in range(0, file_count):
        if i in input_numbers:
            input_file = next(x for x in input_files if int(x.stem) == i)
            head += pack('< I', file_size)
            data += input_file.read_bytes()
            file_size += input_file.stat().st_size
        else:
            head += pack('< I', 0)
    return re_pack(head + data)

def _extractKS(input_file: Path, output_folder: Path):
    data = input_file.read_bytes()
    if data[4:8] != b'w{H\x1a':
        extractKS(data, output_folder)
    # else: need a tool to convert b'w{H\x1a' and kvs/kns

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