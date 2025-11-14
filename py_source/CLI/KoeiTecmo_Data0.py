# Koei Tecmo V0 (and 1?) data extraction script

import glob
from argparse import ArgumentParser
from io import BytesIO
from pathlib import Path
from struct import iter_unpack, pack, unpack_from

from .KoeiTecmo_Arch import chunk_size_from_name, extract_rec
from .KoeiTecmo_XL import _extractXL, combineXL
from .HyruleWarriors_Data import convert_strings, extract_strings, re_pack2, un_pack_2
from .lib.lib_gust import getFileExtension
from .MUA3_ZL import backup, re_pack_v2, un_pack_v2


def re_pack(input_file: Path):
    chunk_size, zp = chunk_size_from_name(input_file.stem)
    is_text = input_file.suffix.casefold() == '.txt'
    try:
        decompressed = combineXL(input_file) \
            if is_text and input_file.with_suffix('.xl').exists() else \
                       convert_strings(input_file) if is_text else \
                       input_file.read_bytes()
        c_bool = chunk_size != 0 # WIP: chunk_size_from_name can only return postive int at this time
        dc_size = len(decompressed)
        return (re_pack_v2(decompressed, chunk_size, dc_size, zp)
                if c_bool else decompressed), dc_size, c_bool
    except:
        print(input_file)
        raise

def re_pack_dir(input_folder: Path):
    chunk_size, zp = chunk_size_from_name(input_folder.name)
    input_files = tuple(i for i in input_folder.iterdir() if not (i.suffix.casefold() == '.xl' and any(i.parent.glob(f'{i.stem}*.txt'))))
    count_bin = len(input_files)
    if count_bin == 0: return bytes(0)
    offset = (1 + count_bin * 2) * 4
    data = bytes(0)
    of_n_sz = []
    dir_check = tuple(f.is_dir() for f in input_files)
    dir_dir = all(dir_check)
    if not dir_dir and any(dir_check):
        raise ValueError('The folder structure is incorrect. Expected folders and sub-folders that contain either files only or folders only.')
    for input_file in input_files:
        d, size, _c = re_pack_dir(input_file) if dir_dir else re_pack(input_file)
        padding = -size % 4
        data += d + bytes(padding)
        of_n_sz += [offset, size]
        offset += size + padding
    data = pack(f'< {1 + count_bin * 2}I', count_bin, *of_n_sz) + data + bytes(-len(data) % 4)
    c_bool = chunk_size > 0
    return re_pack_v2(data, chunk_size, zp=zp) if c_bool else data, len(data), c_bool

def re_pack0(input_folder: Path, data_file: Path, info_file: Path, isV1: bool):
    # WIP: Slow performance
    has_old_info = info_file.exists()
    old_info = info_file.read_bytes() if has_old_info else None
    backup(data_file)
    backup(info_file)
    info = bytes()
    with data_file.open(mode='wb') as f:
        prev_item_number = -1
        for input_file in input_folder.iterdir():
            if input_file.suffix.casefold() == '.xl' and any(input_file.parent.glob(f'{input_file.stem}*.txt')):
                continue
            offset = f.tell()
            item_number = int(input_file.stem.split('_', 1)[0])
            for i in range(prev_item_number + 1, item_number):
                info += pack('<4Q', offset, 0, 0, old_info[i*0x20+0x18] if has_old_info else 2) # cat 0-3
            prev_item_number = item_number
            cat = 1 if input_file.is_dir() else 2
            data, dc_size, c_bool = re_pack_dir(input_file) if cat == 1 else re_pack(input_file)
            if cat == 2 and c_bool: cat = 3
            c_size = len(data)
            f.write(data + bytes(-c_size % 0x100))
            #o = item_number * 0x20
            #if ((old_info[o+0x8:o+0x10] == old_info[o+0x10:o+0x18]) if has_old_info else (cat == 1)): dc_size = c_size
            info += pack('<4Q', offset, dc_size, c_size, old_info[item_number*0x20+0x18] if has_old_info else cat)
    if has_old_info and len(info) < len(old_info):
        info += old_info[len(info):]
    info_file.write_bytes(info)

def _re_pack(input_folder: Path):
    data_file = Path(f'{input_folder}.BIN')
    info_file, _typ, v = get_type(data_file)
    if v == 2:
        re_pack2(input_folder)
    else:
        re_pack0(input_folder, data_file, info_file, v == 1)

DATA_LINK = {
    '.IDX': 'info',
    '.BIN': 'data',
    'IDX': 'info',
    'FILE': 'data',
    'info': 'data',
    'data': 'info'
}
info_file, data_file = None, None

def get_type(input_file: Path) -> tuple[Path, str, int]:
    typ = input_file.stem[-5:-1].lower()
    if typ in DATA_LINK: #v2
        other_file = input_file.with_stem(input_file.stem[:-5] + DATA_LINK[typ] + '2')
        return other_file, typ, 2
    ext  = input_file.suffix.upper()
    name = input_file.stem.upper()
    typ  = name[4:name.find('_')]
    if typ in DATA_LINK and name[:4] == 'LINK' and ext == '.BIN': #v1
        other_file = input_file.with_stem(name[:4] +
            ('FILE' if typ == 'IDX' else 'IDX') + name[-4:])
        return other_file, DATA_LINK[typ], 1
    if ext in DATA_LINK: #v0
        other_file = input_file.with_suffix('.IDX' if ext == '.BIN' else '.BIN')
        return other_file, DATA_LINK[ext], 0
    return ()

def un_pack_0(info: bytes, data_file: Path, output_folder: Path, specific_files: list[list]):
    with data_file.open(mode='rb') as f:
        lst_fls = [x[0] for x in specific_files]
        any_fls = any(specific_files)
        for i, (offset, dc_size, c_size, cat) in enumerate(iter_unpack('<4Q', info)):
            if any_fls and i not in lst_fls: continue
            if dc_size == 0 and c_size == 0: # 0 byte files, cats 2 = ?; 0 = ?; 3+?
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
            if c_bool:
                decompressed, chunk_size, magic = un_pack_v2(f)
                stream = BytesIO(decompressed)
                offset = 0
                name = f'{i:08}_{chunk_size}.{1 if magic == 0x0031707A else 0}'
            else:
                name = f'{i:08}'
                decompressed = f.read(12)
                f.seek(offset)
            ext = getFileExtension(decompressed[:12].split(b'\x00', 1)[0])
            #        and cat == 1: # cat doesn't seem to be relevant for rec files
            if not (ext == '.bin' and
                extract_rec(stream if c_bool else f, output_folder / name, offset)):
                if not c_bool: decompressed = f.read(c_size)
                if not (ext == '.bin' and
                    extract_strings(output_folder / f'{name}.txt',
                                    decompressed, dc_size)):
                    (output_folder / f'{name}{ext}').write_bytes(decompressed)

    for xl_file in output_folder.rglob('*.xl'):
        _extractXL(xl_file)

def _un_pack(input_file: Path, specific_files: list[list]):
    other_file, typ, v = get_type(input_file)
    globals()[f'{typ}_file'] = input_file
    globals()[f'{DATA_LINK[typ]}_file'] = other_file

    output_folder = data_file.with_suffix('')
    backup(output_folder)
    output_folder.mkdir()
    info = info_file.read_bytes() # raises file not found exception if incompatible .bin
    if v == 2:
        un_pack_2(info, data_file, output_folder)
    else: # v0
        un_pack_0(info, data_file, output_folder, specific_files)

def main():
    parser = ArgumentParser()
    parser.add_argument('input', help='input file (supports glob)')
    parser.add_argument('specific_files', nargs='*', help='define index numbers of specific files to be extracted (e.g. "00000523 100/0012.g1t"')
    args = parser.parse_args()
    input_files = glob.glob(args.input.replace('[', '[[]'), recursive=True)

    if not input_files:
        raise ValueError('No files found')
    specific_files = [[int(x[:next((i for i, c in enumerate(x) if not c.isdigit()), None)]) for x in f.split('/')] for f in args.specific_files]

    for input_file in input_files:
        input_file = Path(input_file)

        if input_file.is_dir():
            _re_pack(input_file)
        elif input_file.suffix.casefold() == '.bin':
            _un_pack(input_file, specific_files)

if __name__ == '__main__':
    main()