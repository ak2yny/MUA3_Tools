# zlib un/packer for Team Ninja/Koei Tecmo's .ZL_ compressed files, used in MUA3
# by ThatGamer aka Rhogar, ak2yny, Charsles


import glob
from argparse import ArgumentParser
from itertools import count
from pathlib import Path
from struct import pack, unpack
from zlib import compress, decompress


CHUNK_SIZE = 0x8000


def re_pack(decompressed: bytes) -> bytes:
    size = len(decompressed)
    compressed = pack('< I', size)
    for i in range(0, size, CHUNK_SIZE):
        chunk = compress(decompressed[i:i + CHUNK_SIZE], level=9)
        compressed += pack('< I', len(chunk)) + chunk
    compressed += bytes(4)
    return compressed

def un_pack(input_file: Path) -> bytes:
    decompressed = bytes(0)
    with input_file.open(mode='rb') as zFile:
        size_decompressed, = unpack('< I', zFile.read(4))
        while len(decompressed) < size_decompressed:
            size_compressed, = unpack('< I', zFile.read(4))
            decompressed += decompress(zFile.read(size_compressed))
    return decompressed

def re_pack_v2(decompressed: bytes, chunk_size: int = CHUNK_SIZE, size: int = 0) -> bytes:
    """Different version of the chunk compression, using a header with chunk count and sizes"""
    if size == 0: size = len(decompressed)
    if chunk_size < 0: # buggy file
        return pack('< 4I', -chunk_size, 1, size, size) + bytes(0x80 - 16) + decompressed + bytes(-size % 0x80)
    #elif decompressed.count(b'\x00') == size: # zero bytes file
    #    return pack('< 3I', chunk_size, 1, size) + bytes(0x80 * 2 - 12)
    else:
        count = -(-size // chunk_size)
        header = pack('< 3I', chunk_size, count, size)
        compressed = bytes()
        # -(-((3 + count) * 4) // 0x80) * 0x80 | -((3 + count) * 4) % 0x80 + 0x80
        for i in range(0, size, chunk_size):
            # if all(x == 0 for x in decompressed[i:i + chunk_size]):
            #     chunk = bytes(size - i)
            chunk = compress(decompressed[i:i + chunk_size], level=9)
            size_compressed = len(chunk)
            compressed += pack('< I', size_compressed) + chunk + bytes(-(size_compressed + 4) % 0x80)
            header += pack('< I', size_compressed + 4)
        return header + bytes(-((3 + count) * 4) % 0x80) + compressed

def un_pack_v2(zFile) -> tuple[bytes, int]:
    """Different version of the chunk compression, using a header with chunk count and sizes"""
    decompressed = bytes(0)
    chunk_size, count, size_decompressed = unpack('< 3I', zFile.read(12))
    c_sizes = unpack(f'< {count}I', zFile.read(count * 4))
    offset = (3 + count) * 4
    for i in range(count):
        zFile.seek(-offset % 0x80, 1)
        if (bug := size_decompressed == c_sizes[0]):
            # this seems to be a bug
            chunk_size = -chunk_size
            size_compressed = size_decompressed
        else:
            size_compressed, = unpack('< I', zFile.read(4))
            if (zero := size_compressed == 0): size_compressed = size_decompressed - len(decompressed)
        decompressed += zFile.read(size_compressed) if bug or zero else \
                        decompress(zFile.read(size_compressed))
        offset = 4 + size_compressed
    assert(len(decompressed) == size_decompressed)
    return decompressed, chunk_size

def backup(output_file: Path):
    if not output_file.exists(): return
    for i in count(0):
        backup_file = output_file.with_stem(f'{output_file.stem}.backup{i}')
        if not backup_file.exists(): break
    output_file.rename(backup_file)

def _re_pack(input_file: Path, output_file: Path):
    backup(output_file)
    output_file.write_bytes(re_pack(input_file.read_bytes()))

def _un_pack(input_file: Path, output_file: Path):
    backup(output_file)
    output_file.write_bytes(un_pack(input_file))

def main():
    parser = ArgumentParser()
    # parser.add_argument('-u', '--unpack', action='store_true', help='unpack input .ZL_ file to uncompressed file')
    #repack input file to .ZL_ file
    parser.add_argument('input', help='input file (supports glob)')
    args = parser.parse_args()
    input_files = glob.glob(args.input.replace('[', '[[]'), recursive=True)

    if not input_files:
        raise ValueError('No files found')

    for input_file in input_files:
        input_file = Path(input_file)

        if input_file.suffix.upper() == '.ZL_':
            output_file = input_file.parent / input_file.stem
            _un_pack(input_file, output_file)
        else:
            output_file = Path(f'{input_file}.ZL_')
            _re_pack(input_file, output_file)

if __name__ == '__main__':
    main()