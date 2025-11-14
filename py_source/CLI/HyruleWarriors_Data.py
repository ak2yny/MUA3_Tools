# Hyrule Warriors - Age of Calamity data extraction script (Data V2)

import glob
from argparse import ArgumentParser
from pathlib import Path
from struct import iter_unpack, pack, unpack_from

from .MUA3_ZL import backup, re_pack_v2, un_pack_v2


def extract_strings(output_file: Path, data: bytes, total_size: int = 0) -> bool:
    if total_size == 0: total_size = len(data)
    if total_size < 0x10: return False
    count, strings_size, check = unpack_from('<2IQ', data)
    # li = unpack_from(f'< {"4xI" * count}', data, 4)
    # assert(li.count(li[0]) != count) # file with identical sizes isn't strings?
    string_count = data[-strings_size:].count(b'\x00')
    if 0 in (count, strings_size) or check > 0 or string_count % count != 0:
        return False
    entries = (total_size - strings_size - 16) // (count * 4)
    instances = string_count // count
    try:
        offsets = unpack_from(f'<{count * entries}I', data, 16)
        #strings = f.read(strings_size).decode(chardet.detect(data[-strings_size:])['encoding']).split('\x00')
        with output_file.open(mode='w', encoding='utf-8') as f:
            for c in range(0, count * entries, entries):
                for i in range(entries):
                    o = (4 + c + i) * 4 + offsets[c + i]
                    f.write(f'[{i}] ' + 
                            (data[o:data.find(b'\x00', o)].decode('utf8', 'backslashreplace').replace('\n', '\\n')
                            if i < instances else f'[{offsets[c + i]}]')
                            + '\n')
        return True
    except:
        return False

def convert_strings(input_file: Path) -> bytes:
    #if total_size == 0: total_size = input_file.stat().st_size
    indexed_lines = tuple(sl for line in input_file.read_text(encoding='utf-8').split('\n') for sl in line.split(' ', 1))
    indices = tuple(int(l[1:-1]) for l in indexed_lines[::2] if l)
    entries = max(indices) + 1
    instances = entries - sum(1 for l in indexed_lines[1:entries*2:2] if len(l) > 2 and l[0] == '[' and l[1:-1].isdigit() and l[-1] == ']')
    total = len(indices)
    o = total * 4
    offsets = []
    strings = bytes(0)
    # sometimes, the ranges are inverted (entries first, total second)
    for c in range(0, total, entries):
        for i in range(entries):
            if i < instances:
                offsets.append(o + len(strings))
                strings += indexed_lines[(c + i) * 2 + 1].replace('\\n', '\n').encode('utf-8') + b'\x00'
            else:
                offsets.append(int(indexed_lines[(c + i) * 2 + 1][1:-1]))
            o -= 4
    return pack(f'<2I8x{total}I', total // entries, len(strings), *offsets) + strings

def _extract_strings(input_file: Path):
    #input_folder = Path('contain string')
    #input_files = [x for x in input_folder.iterdir() if x.suffix.casefold() == '.bin']
    #with input_file.open(mode='rb') as f:
    if not extract_strings(input_file.with_suffix('.txt'), input_file.read_bytes()):
        raise ValueError(f'{input_file.name} is not a valid strings file.')

def _convert_strings(input_file: Path):
    input_file.with_suffix('.bin').write_bytes(convert_strings(input_file))

def re_pack2(input_folder: Path):
    data_file = Path(f'{input_folder}.bin')
    info_file = data_file.with_stem(data_file.stem[:-5] + 'Info2')
    backup(data_file)
    backup(info_file)
    info = bytes(0)

    with data_file.open(mode='wb') as f:
        f.write(bytes(16))
        for input_file in input_folder.iterdir():
            offset = f.tell()
            cat, h, chunk_size = (int(x) for x in input_file.stem.split('_')[1:])
            c_bool = chunk_size != 0
            decompressed = convert_strings(input_file) if input_file.suffix.casefold() == '.txt' else input_file.read_bytes()
            dc_size = len(decompressed) # if is_sf else input_file.stat().st_size
            compressed = re_pack_v2(decompressed, chunk_size, dc_size) \
                         if c_bool else decompressed
            c_size = len(compressed) # if c_bool else dc_size
            f.write(compressed + bytes(-c_size % 0x10))
            info += pack('<4Q2I', offset, dc_size, c_size, int(c_bool), cat, h)
    info_file.write_bytes(info)

def _re_pack(input_folder: Path):
    re_pack_v2(input_folder)

DATA_LINK = {
    'info': 'data',
    'data': 'info'
}
KNOWN_IDS = (b'ALGB', b'DJBO', b'RGND')
info_file, data_file = 0, 0

def un_pack_2(info: bytes, data_file: Path, output_folder: Path):
    with data_file.open(mode='rb') as f:
        for i, (offset, dc_size, c_size, c_bool, cat, h) in enumerate(iter_unpack('<4Q2I', info)):
            # info: they're usually normal compressed files, but compressed size equals decompressed instead. They are count (20) * 3I, i.e. 256 byte files.
            ext = 'info' if dc_size == c_size and c_bool else 'bin'
            f.seek(offset)
            (decompressed, chunk_size, magic) = un_pack_v2(f) if c_bool else (f.read(c_size), 0, -1)
            if not c_bool: assert(c_size == dc_size)
            # else: assert(len(decompressed) == dc_size)
            write = True
            if (ID := decompressed[:4]) in KNOWN_IDS:
                ext = ID.decode()[:-4:-1].lower()
            output_file = output_folder / f'{i:08}_{cat}_{h}_{chunk_size}.{ext}'
            if not (cat == 0XBE097869 and
                extract_strings(output_file.with_suffix('.txt'),
                                decompressed, dc_size)):
                output_file.write_bytes(decompressed)
            #with (output_folder / f'{i:08}_{cat}_{h}_{chunk_size}.{ext}').open('wb') as of:

def _un_pack(input_file: Path):
    typ = input_file.stem[-5:-1].lower()
    if typ not in DATA_LINK:
        return
    globals()[f'{typ}_file'] = input_file
    globals()[f'{DATA_LINK[typ]}_file'] =  input_file.with_stem(input_file.stem[:-5] + DATA_LINK[typ] + '2')

    output_folder = data_file.with_suffix('')
    backup(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    info = info_file.read_bytes() # raises file not found exception if incompatible .bin
    un_pack_2(info, data_file, output_folder)

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
            _re_pack(input_file)
        elif input_file.suffix.casefold() == '.bin':
            _un_pack(input_file)

if __name__ == '__main__':
    main()