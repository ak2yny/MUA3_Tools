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
    decompressed = b''
    with input_file.open(mode='rb') as zFile:
        size_decompressed, = unpack('< I', zFile.read(4))
        while len(decompressed) < size_decompressed:
            size_compressed, = unpack('< I', zFile.read(4))
            decompressed += decompress(zFile.read(size_compressed))
    return decompressed

def backup(output_file: Path):
    if not output_file.exists(): return
    for i in count(0):
        backup_file = output_file.parent / f'{output_file.stem}.backup{i}{output_file.suffix}'
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