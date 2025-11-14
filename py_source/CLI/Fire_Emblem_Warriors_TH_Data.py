# File extractor and combiner for Fire Emblem Warriors - Three Hopes
# by ak2yny


import glob
from argparse import ArgumentParser
from pathlib import Path
from struct import pack, unpack_from
from zlib import compress, decompress

from .lib.lib_gust import getFileExtension
from .MUA3_ZL import backup, re_pack


# WIP
def extract(data: bytes, output_folder: Path):
    output_folder.mkdir(parents=True, exist_ok=True)
    unk_magic, count, alignment, _ = unpack_from('< 4I', data)
    files_data = unpack_from(f'< {count * 4}I', data, 0x10)
    for i in range(count):
        offset, _, size_compressed, size_decompressed = files_data[i * 4:i * 4 + 4]
        offset *= alignment
        #assert(size_decompressed == unpack_from('< I', decrypted, offset)[0])
        pos = offset + 8
        decompressed = bytes()
        while len(decompressed) < size_decompressed:
            size_compressed, = unpack_from('< I', data, pos - 4)
            decompressed += decompress(data[pos:pos + size_compressed])
            pos += size_compressed + 4
        #ext = getFileExtension(decompressed[:12].split(b'\x00')[0])
        #if ext == '.bin':
        #assert(unpack_from('< 4I', decompressed) == (1, 0x10, 0, 0))
        string_count, unk = unpack_from('< 2I', decompressed, 0x10) # offset: unpack_from('< I', decompressed, 4)
        #assert(_ == 0)
        id_n_offsets = unpack_from(f'< {string_count * 2}I', decompressed, 0x18)
        (output_folder / f'{i:04d}_{unk}_{decompressed[0x18 + string_count * 8]}.txt').write_bytes(b'\n'.join(f'[{ID:08X}] '.encode() + s.replace(b'\n', b'\\n') for ID, s in zip(id_n_offsets[::2], (decompressed[o + 0x10:decompressed.index(b'\x00', o + 0x10)] for o in id_n_offsets[1::2]))))

alignment = 0x100 # hardcoded
def combine(input_folder: Path) -> bytes:
    input_files = tuple(input_folder.iterdir())
    count = len(input_files)
    if count == 0: return bytes()
    offset = (1 + count) * 0x10
    data = bytes()
    files_data = []
    for input_file in input_files:
        padding = -offset % alignment
        offset += padding
        data += bytes(padding)
        _, unk1, unk2 = input_file.stem.split('_')
        strings = input_file.read_bytes().split(b'\n')
        string_count = len(strings)
        sdata = b'\x00'.join(s[11:].replace(b'\\n', b'\n') for s in strings)
        strings_offset = 8 + string_count * 8 + 4
        size_strings = len(sdata) + 1
        padding = -(strings_offset + size_strings) % 0x10
        size_decompressed = 0x10 + strings_offset + size_strings + padding
        compressed = re_pack(pack(f'< {6 + string_count * 2 + 1}I',
            1, 0x10, 0, 0, string_count, int(unk1),
            *(x for io in zip((int(s[1:9], 0x10) for s in strings),
                [strings_offset] + [strings_offset + i + 1
                for i, b in enumerate(sdata) if b == 0]) for x in io),
            int(unk2)) + sdata + bytes(1 + padding))
        size_compressed = len(compressed)
        data += compressed
        files_data += [offset >> 8, 0, size_compressed, size_decompressed]
        offset += size_compressed
    return pack(f'< {(1 + count) * 4}I', 0x77DF9, count, alignment, 0, *files_data) + data + bytes(-size_compressed % alignment)

def _extract(input_file: Path, output_folder: Path):
    backup(output_folder)
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