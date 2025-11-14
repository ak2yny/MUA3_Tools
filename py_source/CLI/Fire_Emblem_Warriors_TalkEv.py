# Talk Events file extractor and combiner for Fire Emblem Warriors
# by ak2yny


import glob
from argparse import ArgumentParser
from pathlib import Path
from struct import pack, unpack_from

from .Fire_Emblem_Warriors_BIN import extract_rec
from .MUA3_ZL import backup, un_pack_v2


def extractTE(data: bytes, output_file: Path):
    if 4 < data[6:16].count(b'\x00') < 8: return
    # Note: size doesn't match bytes on some non-Latin languages. Encoding is unknown.
    size, = unpack_from('< H', data, 4)
    has_size = 6 - (size + 6 - data.index(b'\x00', 6)) in (4, 5)
    if has_size and size < 2: return
    info_size = 6 if has_size else 4
    max_size = len(data) - 6
    offset = 0
    with (output_file.parent / f'{output_file.stem}_{info_size}.txt').open('wb') as f:
        while offset < max_size:
            h1, h2, size = unpack_from('< 3H', data, offset)
            section = slice(offset + info_size, data.index(b'\x00', offset + info_size))
            if has_size: assert(section.stop < offset + info_size + size)
            f.write(f'[0x{h1:04X}] [0x{h2:04X}] '.encode('utf-8') + data[section].replace(b'\n', b'\\n') + b'\n')
            offset = section.stop + 1

def combineTE(input_file: Path) -> bytes:
    info_size = int(input_file.stem.rsplit('_', 1)[1])
    info_fmt = f'< {info_size // 2}H'
    data = bytes(0)
    strings = input_file.read_bytes().rstrip(b'\n').split(b'\n')
    for s in strings:
        *i, s = s.split(b'\x20', 2)
        i = [int(x[3:-1], 16) for x in i]
        sz_w_escape = len(s) + 1
        s = s.replace(b'\\n', b'\n') + bytes(1)
        # Note: size doesn't always match byte length (\n escape not confirmed)
        if info_size == 6: i.append(sz_w_escape if int(input_file.stem[3]) == 1 else len(s))
        data += pack(info_fmt, *i) + s
    return data

def _extractTE(input_file: Path, output_folder: Path):
    with input_file.open('rb') as f:
        if f.read(4) == b'zp1\x00':
            f.seek(0)
            data, chunk_size, _magic = un_pack_v2(f)
            output_folder = input_file.parent / f'{input_file.stem}_{chunk_size}.1'
        else:
            data = input_file.read_bytes()
    backup(output_folder)
    extract_rec(data, output_folder, False)
    for f in output_folder.iterdir():
        if f.stat().st_size > 6:
            extractTE(f.read_bytes(), f)

def _combineTE(input_folder: Path, output_file: Path):
    input_files = tuple(f for f in input_folder.iterdir()
        if f.suffix.casefold() == '.txt' or not any(input_folder.glob(f'{f.stem}*.txt'))
    )
    count_bin = len(input_files)
    if count_bin == 0: return bytes()
    offset = (1 + count_bin * 2) * 4
    data = bytes()
    of_n_sz = []
    for input_file in input_files:
        txt = input_file.suffix.casefold() == '.txt'
        te = combineTE(input_file) if txt else input_file.read_bytes()
        size = len(te) if txt else input_file.stat().st_size
        data += te + bytes(-size % 4)
        of_n_sz += [offset, size]
        offset += size + (-size % 4)
    backup(output_file)
    output_file.write_bytes(pack(f'< {1 + count_bin * 2}I', count_bin, *of_n_sz) + data + bytes(-len(data) % 4))

def main():
    parser = ArgumentParser()
    parser.add_argument('input', help='input file (supports glob)')
    args = parser.parse_args()
    input_files = glob.glob(args.input.replace('[', '[[]'), recursive=True)

    if not input_files:
        raise ValueError('No files found')

    for input_file in input_files:
        input_file = Path(input_file)

        if input_file.is_dir():
            output_file = Path(f'{input_file}.bin')
            _combineTE(input_file, output_file)
        else:
            _extractTE(input_file, input_file.parent / input_file.stem)

if __name__ == '__main__':
    main()