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

def re_pack_v2(decompressed: bytes, chunk_size: int = CHUNK_SIZE, size: int = 0, zp: int = 0) -> bytes:
    """Different version of the chunk compression, using a header with chunk count and sizes"""
    if size == 0: size = len(decompressed)
    count = -(-size // abs(chunk_size))
    bug = chunk_size < 0
    if bug:
        chunk_size = -chunk_size
        c_sizes = [chunk_size if i * chunk_size < 0x10 else
                   size % chunk_size for i in range(1, count + 1)]
        compressed = decompressed + bytes(-size % 0x80)
    #elif decompressed.count(b'\x00') == size: # zero bytes file
    #    return pack('< 3I', chunk_size, 1, size) + bytes(0x80 * 2 - 12)
    else:
        c_sizes = []
        compressed = bytes()
        for i in range(0, size, chunk_size):
            # if all(x == 0 for x in decompressed[i:i + chunk_size]):
            #     chunk = bytes(size - i)
            chunk = compress(decompressed[i:i + chunk_size], level=9)
            size_compressed = len(chunk)
            compressed += pack('< I', size_compressed) + chunk + bytes(-(size_compressed + 4) % 0x80)
            c_sizes.append(size_compressed + 4)
    # -(-sz_header // 0x80) * 0x80
    cnt = 1 if bug else count
    hec = 4 if zp else 3
    return pack(f'< {hec + count}I',
        *((0x0031707A, size, chunk_size, cnt) if zp else (chunk_size, cnt, size)),
        *c_sizes) + bytes(-((hec + count) * 4) % (0x800 if zp else 0x80)) + compressed

def un_pack_v2(zFile) -> tuple[bytes, int]:
    """Different version of the chunk compression, using a header with chunk count and sizes"""
    offset = 12
    magic, = unpack('< I', zFile.read(4))
    if magic == 0x0031707A: # zp1
        size_decompressed, chunk_size, count = unpack('< 3I', zFile.read(12))
        offset += 4
    else:
        chunk_size = magic
        count, size_decompressed = unpack('< 2I', zFile.read(8))
    # Is there a way to check for compressed files?
    #assert(chunk_size % 0x10000 == 0)
    c_sizes = unpack(f'< {count}I', zFile.read(count * 4))
    if magic == 0x0031707A:
        zFile.seek(0x800 - (16 + count * 4), 1)
    decompressed = bytes()
    offset += count * 4
    for i in range(count):
        zFile.seek(-offset % 0x80, 1)
        #print(hex(offset), hex(zFile.tell()))
        #if (bug := size_decompressed == sum(c_sizes)):
        #    # this seems to be a bug
        #    chunk_size = -chunk_size
        #    size_compressed = size_decompressed
        #else:
        size_compressed, = unpack('< I', zFile.read(4))
        if (tail := c_sizes[i] != size_compressed + 4):
            #WIP: Does this take care of the bug? Check commented code
            #size_compressed >> 0x18 != 0 doesn't seem to be right (i.e. it's uncompressed data)
            assert(i == count - 1)
            zFile.seek(-4, 1)
            size_compressed = c_sizes[i]
        if (zero := size_compressed == 0): size_compressed = size_decompressed - len(decompressed)
        decompressed += zFile.read(size_compressed) if tail or zero else \
                        decompress(zFile.read(size_compressed))
        #if bug or zero: break
        offset = 4 + size_compressed
    assert(len(decompressed) == size_decompressed)
    return decompressed, chunk_size, magic

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