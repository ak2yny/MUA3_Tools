# GameMsg file extractor and combiner for Romance Of The Three Kingdoms 8 Remake
# by ak2yny

# Note: The encoding seems to be utf-16-le, but that's unknown, so there's some funky code in here.

import glob
from argparse import ArgumentParser
from ast import literal_eval
from codecs import BOM_UTF16_LE
from itertools import accumulate, chain
from pathlib import Path
from struct import pack, unpack_from

from .Fire_Emblem_Warriors_BIN import extract_rec
from .MUA3_ZL import backup, re_pack_v2, un_pack_v2


NL_CHARS = {e: tuple(c.encode(e) for c in ('\n', '\\n', '\r', '\\r', ' ')) for e in ('utf-8', 'utf-16-le')}

def combine_strings(input_file: Path) -> bytes:
    new_data = input_file.read_bytes()
    if len(new_data) == 0: return bytes()
    old_data = input_file.with_suffix('.bin').read_bytes()
    enc = 'utf-16-le' if new_data[:2] == BOM_UTF16_LE else 'utf-8'
    count, fo = unpack_from('< 2I', old_data)
    startID = old_data[fo:fo + 3]                                #
    endID = old_data[fo + 3:fo + 6]                              # WIP: unconfirmed
    ine = 'utf-16-le' if startID == b'\x07\x07\x01' else 'utf-8' #
    assert(startID[-1] + 1 == endID[-1] and ine == enc)          #
    # startID = 0x010707; endID = startID | 1 << 0x10; startID.to_bytes(3, endian='little')
    delim = '[...]'.encode(enc)
    nl, nl_esc, cr, cr_esc, _ = NL_CHARS[enc]
    uc = len(nl)
    square_bracket = delim[-uc:]
    offsets = unpack_from(f'< {count - 1}I', old_data, 8)
    max_i = count - 2
    strings = (s.replace(cr_esc, cr).replace(nl_esc, nl).split(delim) for s in new_data[2 if enc == 'utf-16-le' else 0:-uc].split(nl)) # note: .rstrip(nl) strips extra 0x00 from other utf16 characters
    offset = fo + 9
    data = old_data[fo:offset]
    new_offsets = [count, fo]
    for o, e in zip(offsets, chain(offsets[1:], (None,))):
        string = b''.join(
            (b'' if fs == 0 else bytes(literal_eval(f'{fs.decode(enc)}]'))) +
            (startID + s + endID if s or fs == 0 else b'')
                for st in next(strings) for fs, s in (st.split(square_bracket)
                    if st and st[0] == 91 else [0, st],)) + b'\x05\x05\x05' \
            if startID in old_data[o:o + 12] else old_data[o:e]
        new_offsets.append(offset)
        offset += len(string)
        data += string
    return pack(f'< {count + 1}I', *new_offsets) + data

def combine(input_folder: Path) -> bytes:
    data_bin = bytes()
    szs = []
    sza = []
    for d in input_folder.iterdir():
        if d.suffix != '.txt' and d.with_suffix('.txt').exists(): continue
        data = combine(d) if d.is_dir() else combine_strings(d) if d.suffix == '.txt' else d.read_bytes()
        s = len(data)
        align = -s % 4
        szs.append(s)
        sza.append(s + align)
        data_bin += data + bytes(align)
    count_bin = len(szs)
    if count_bin == 0: return bytes()
    return pack(f'< {1 + count_bin * 2}I', count_bin,
                *chain.from_iterable(zip(accumulate(sza, initial=(1 + count_bin * 2) * 4), szs))
                ) + data_bin

def extract_strings(input_file: Path):
    data = input_file.read_bytes()
    size = len(data)
    count, fo = unpack_from('< 2I', data)
    offsets = unpack_from(f'< {count - 1}I', data, 8)
    so = offsets[0] if offsets else size
    startID = data[fo:fo + 3]                                    #
    endID = data[fo + 3:fo + 6]                                  # WIP: unconfirmed
    assert(so - fo == 9 and startID[-1] + 1 == endID[-1])        #
    enc = 'utf-16-le' if startID == b'\x07\x07\x01' else 'utf-8' #
    nl, nl_esc, cr, cr_esc, _ = NL_CHARS[enc]
    with input_file.with_suffix('.txt').open('wb') as f:
        if enc == 'utf-16-le': f.write(BOM_UTF16_LE)
        for o in offsets:
            if startID in data[o:o + 12]:
                # Not sure if the initial size (12) is big enough or ID is good enough
                end = data.index(b'\x05\x05\x05', o)
                so = data.index(startID, o) + 3
                if so != o + 3:
                    f.write(f'[...]{[b for b in data[o:so - 3]]}'.encode(enc))
                while so < end:
                    se = data.index(endID, so)
                    f.write(data[so:se].replace(cr, cr_esc).replace(nl, nl_esc))
                    so = data.find(startID, se) + 3
                    if so == 2: so = size + 3
                    fse = min(so - 3, end)
                    if fse < end or se + 3 < fse:
                        f.write(f'[...]{[b for b in data[se + 3:fse]]}'.encode(enc))
                f.write(nl)
            #else:
            #    pass

def _combine(input_folder: Path, output_file: Path):
    data = combine(input_folder)
    filename, *chunk_size = input_folder.name.rsplit('_', 1) + [0]
    chunk_size = chunk_size[0]
    if chunk_size and len(chunk_size) > 1 and chunk_size[-2] == '.':
        chunk_size, zp = chunk_size.split('.')
        output_file = output_file.with_stem(filename)
        data = re_pack_v2(data, int(chunk_size), zp=int(zp))
    backup(output_file)
    output_file.write_bytes(data)

def _extract(input_file: Path, output_folder: Path):
    with input_file.open('rb') as f:
        if f.read(4) == b'zp1\x00':
            f.seek(0)
            data, chunk_size, _magic = un_pack_v2(f)
            output_folder = input_file.parent / f'{input_file.stem}_{chunk_size}.1'
        else:
            data = input_file.read_bytes()
    backup(output_folder)
    extract_rec(data, output_folder)
    for f in output_folder.rglob('*.bin'):
        extract_strings(f)

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
        ext = input_file.suffix.casefold()

        if ext == '.txt':
            combine_strings(input_file)
            found_any = True
        elif input_file.is_dir():
            _combine(input_file, Path(f'{input_file}.bin'))
            found_any = True
        elif ext == '.bin':
            _extract(input_file, input_file.parent / input_file.stem)
            found_any = True

    if not found_any:
        raise ValueError('No files found')

if __name__ == '__main__':
    main()