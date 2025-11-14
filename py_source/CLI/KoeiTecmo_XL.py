# XL language file extractor and combiner for Fire Emblem Warriors (and other Koei Tecmo games)
# by ak2yny


import glob
from argparse import ArgumentParser
from ast import literal_eval
from codecs import BOM_UTF16_LE
from io import BytesIO
from pathlib import Path
from struct import calcsize, pack, unpack_from

from .KoeiTecmo_Arch import combine_rec, extract_rec
from .MUA3_ZL import backup, re_pack_v2, un_pack_v2


ENC = 'utf-8'
NL_CHARS = (b'\n', b'\\n', b'\r', b'\\r', b' ')
NL_CHARS_16_LE = tuple(c.encode('utf-16-le') for c in ('\n', '\\n', '\r', '\\r', ' '))

def combineXL(input_file: Path) -> bytes:
    data = input_file.read_bytes()
    enc = ENC
    if data[:2] == BOM_UTF16_LE:
        data = data[2:-1]
        enc = 'utf-16-le'
    sz = len(data)
    nl, nl_esc, cr, cr_esc, spc = NL_CHARS_16_LE if enc == 'utf-16-le' else NL_CHARS
    dtypes, *strings = ['[]',] if sz == 0 else data[:-1].split(nl) # note: .rstrip(nl) strips extra 0x00 from other utf16 characters
    dtypes = literal_eval(dtypes.decode(enc))
    dtype = ''.join('IIHBIHBI'[t] for t in dtypes)
    offsets = tuple(o for o, b in enumerate(dtypes) if b == 0)
    dt_sz = len(dtypes)
    count = len(strings) // dt_sz
    stride = calcsize(f'< {dtype}')
    table_size = count * stride
    padding = -dt_sz % 4
    string_delim = bytes(4 if enc == 'utf-16-le' else 1)
    uc = 2 if enc == 'utf-16-le' else 1
    dt_o = 20 if enc == 'utf-16-le' else 16 # WIP: Might be wrong
    table_offset = (1, dt_o + dt_sz + padding) if enc == 'utf-16-le' else (dt_o + dt_sz + padding,) # WIP: Might be wrong
    info = []
    data = bytes()
    for s in strings:
        i, s = s.split(spc, 1)
        i = int(i.decode(enc)[1:-1])# (i[1] - 48) * 10 + (i[2] - 48)
        if i in offsets:
            # IMPORTANT: Empty string sizes in org files are inconsistent. (string_delim)
            info.append(table_size + len(data))
            data += s.replace(cr_esc, cr).replace(nl_esc, nl) + string_delim
        else:
            info.append(int(s.decode(enc)[1:-1], 0x10))
    return pack(f'< 4s4H{uc}I{dt_sz}B{padding}s{count * dtype}', b'XL\x13\x00',
                sz and (dt_o + dt_sz + padding + table_size + len(data)) & 0xFFFF,
                dt_sz, count, stride, *table_offset,
                *dtypes, padding * b'\xFF', *info) + data

def extractXL(data: bytes, output_file: Path):
    # 2 uint: magic + id?
    _sz, dt_sz, count, stride, table_offset = unpack_from('< 4HI', data, 4)
    # 0xFF padding
    dtypes = unpack_from(f'< {dt_sz}B', data, 20 if table_offset == 1 else 16)
    if any(t > 7 for t in dtypes):
        raise ValueError('XL data types of more than 7 are unsupported')
    dtype = f"< {''.join('IIHBIHBI'[t] for t in dtypes)}"
    offsets = tuple(o for o, b in enumerate(dtypes) if b == 0)
    if table_offset == 1:
        table_offset, = unpack_from('< I', data, 16)
        # WIP: Might be wrong
        enc = 'utf-16-le'
        nl, nl_esc, cr, cr_esc, _ = NL_CHARS_16_LE
        char_size = 2
        string_delim = bytes(4)
    else:
        enc = ENC
        nl, nl_esc, cr, cr_esc, _ = NL_CHARS
        char_size = 1
        string_delim = bytes(1)
    backup(output_file)
    with output_file.open('wb') as f:
        if enc == 'utf-16-le': f.write(BOM_UTF16_LE)
        f.write(f'{dtypes}\n'.encode(enc))
        for o in range(table_offset, table_offset + count * stride, stride):
            for i, v in enumerate(unpack_from(dtype, data, o)):
                if i in offsets:
                    string_offset = table_offset + v
                    string_end = data.index(string_delim, string_offset)
                    f.write(f'[{i:02}] '.encode(enc) + 
                            data[string_offset:string_end + (
                                string_end - string_offset) % char_size]
                                .replace(cr, cr_esc).replace(nl, nl_esc) + nl)
                else:
                    f.write(f'[{i:02}] [0x{v:08X}]\n'.encode(enc))

def _combineXL(input_file: Path):
    output_file = input_file.with_suffix('.xl')
    backup(output_file)
    output_file.write_bytes(combineXL(input_file))

def _combine(input_folder: Path, output_file: Path):
    for input_file in input_folder.rglob('*.txt'):
        input_file.with_suffix('.xl').write_bytes(combineXL(input_file))
        input_file.unlink()
    data = combine_rec(input_folder)
    filename, *chunk_size = input_folder.name.rsplit('_', 1) + [0]
    chunk_size = chunk_size[0]
    if chunk_size and len(chunk_size) > 2 and chunk_size[-2] == '.':
        chunk_size, zp = chunk_size.split('.')
        output_file = output_file.with_stem(filename)
        data = re_pack_v2(data, int(chunk_size), zp=int(zp))
    backup(output_file)
    output_file.write_bytes(data)

def _extractXL(input_file: Path):
    extractXL(input_file.read_bytes(), input_file.with_suffix('.txt'))

def _extract(input_file: Path, output_folder: Path):
    with input_file.open('rb') as f:
        try:
            data, chunk_size, magic = un_pack_v2(f)
            output_folder = input_file.parent / f'{input_file.stem}_{chunk_size}.{1 if magic == 0x0031707A else 0}'
            f = BytesIO(data)
        except:
            f.seek(0)
        backup(output_folder)
        extract_rec(f, output_folder)
    for xl_file in output_folder.rglob('*.xl'):
        _extractXL(xl_file)

def set_xl_encoding(enc: str):
    if enc != 'utf-8':
        global ENC
        global NL_CHARS
        ENC = enc
        NL_CHARS = tuple(c.encode(enc) for c in ('\n', '\\n', '\r', '\\r', ' '))

def main():
    parser = ArgumentParser()
    parser.add_argument('input', help='input file (supports glob)')
    parser.add_argument('-e', '--encoding', type=str, default='utf-8', help='define a specific encoding (utf-8, if not defined)')
    args = parser.parse_args()
    input_files = glob.glob(args.input.replace('[', '[[]'), recursive=True)

    if not input_files:
        raise ValueError('No files found')

    set_xl_encoding(args.encoding)
    found_any = False
    for input_file in input_files:
        input_file = Path(input_file)
        ext = input_file.suffix.casefold()

        if ext == '.txt':
            _combineXL(input_file)
            found_any = True
        elif input_file.is_dir():
            _combine(input_file, Path(f'{input_file}.bin'))
            found_any = True
        elif ext == '.xl':
            _extractXL(input_file)
            found_any = True
        elif ext == '.bin':
            _extract(input_file, input_file.parent / input_file.stem)
            found_any = True

    if not found_any:
        raise ValueError('No files found')

if __name__ == '__main__':
    main()