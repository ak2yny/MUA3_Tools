# File extractor and combiner for Dynasty Warriors Origin
# by ak2yny


import glob
from argparse import ArgumentParser
from pathlib import Path
from struct import pack, unpack_from
from zlib import compress, decompress

from Crypto.Cipher import AES
from .HyruleWarriors_Data import convert_strings, extract_strings
from .lib.lib_gust import getFileExtension
from .MUA3_ZL import backup, re_pack


XOR_LAST_BYTES = (
    b'\x30\xF9\x85\xBE\x44\x25\xA4\xD0\xA5\x21\x31\x86\x62\x52\xE7\x4D'
    b'\xDD\x10\x33\xF5\xB5\x00\x21\x41\xF5\x54\xAF\xA6\x15\x3B\x99\xCF'
    b'\x5D\x86\xD2\x36\xCE\x6D\x28\xC0\x53\x73\xE7\xD1\x3C\x00\x80\x50'
    b'\x9D\xB0\x4A\xCB\x10\x32\x7C\x08\x54\xBB\xF5\xD9\xD3\x9E\x5B\x65'
    b'\xA6\x4E\xD8\x66\x2B\x31\xF7\xB1\xCD\xEB\x05\x1F\x8C\x26\x40\x27'
    b'\x80\xC2\xE3\x20\x9E\x3A\xA5\xC4\x91\xB5\xCE\xB5\x8C\x08\x90\x94'
    b'\x48\xCA\x20\x1F\x9B\xE5\xE6\xCE\x6D\x30\xDA\xB7\x1D\x84\x58\xDA'
    b'\xBA\x2C\x3E\xF6\xFB\x4E\x3E\xB4\x27\x5F\xD0\x53\x0E\x1B\x96\xB1'
    b'\x59\x68\xD0\xC8\x52\x0F\xBF\x39\x10\xE1\x69\x03\x56\xFF\xDD\x27'
    b'\x0E\x11\x11\xAB\xC1\x2E\x00\xED\xCE\x05\x8F\x7C\x8E\xCD\x3B\x0B'
    b'\x47\x1D\x75\x76\x55\x2C\x65\x3C\x0D\x6C\x45\xF6\x5E\x79\x49\xE0'
    b'\xEE\x27\xDF\x4B\x89\x66\xD7\x21\xB1\x66\xAF\x92\x06\xF9\xE3\x0E'
    b'\x5B\xC1\x12\xDE\xEF\xEB\x10\x9E\xB9\xA2\x30\xD7\xE1\xE7\xF5\x49'
    b'\xC0\x4F\xC7\x72\x58\x28\x3D\xF3\x3C\x63\x1C\x72\xFF\xE9\x24\x27'
    b'\x1E\x29\xE2\x10\xD4\xBD\xB0\xBF\x2B\xB4\x5E\xF1\x39\xF8\x04\x9B'
    b'\xAE\x52\xB1\x77\x0A\xEC\x0C\x37\x66\xF4\x84\x73\xE9\xAA\x61\x4B'
    b'\x33\xE0\x3F\xC4\x46\x7E\x23\x75\x08\xBF\xB1\x19\x88\x30\xB1\x20'
    b'\x65\xC3\xD2\xCD\xF0\x97\x3E\x26\x8E\xDC\x65\x9A\x1C\xA9\x2B\xD3'
    b'\x79\x69\xAC\xA8\x38\x6C\xF9\x5B\x48\x97\xFE\x71\x95\xF0\xD5\x81'
)
KEY = b'UxxIYUYqbUDsorqpylPwzClZgvvPTZyi'
IV  = b'\xE1\xC1\xC4\x9F\x9A\x30\x19\x34\x1E\xA8\x20\xF9\x9F\xD0\x9A\x83'

def to_ecx(last_encrypted_byte: int):
    rdx = (last_encrypted_byte * 0xAF286BCB) >> 32
    #eax = ((last_encrypted_byte - rdx >> 1) + rdx >> 0x4) * 0x13
    #ecx = (last_encrypted_byte - eax) << 0x4
    return (last_encrypted_byte - ((last_encrypted_byte - rdx >> 1) + rdx >> 0x4) * 0x13) << 0x4

def encrypt(data: bytes, size: int = 0) -> bytes:
    if size == 0: size = len(data)
    if size < 0x10:
        return data

    size_aligned = size - size % 0x10
    cipher = AES.new(KEY, AES.MODE_CBC, iv=IV)
    out_data = cipher.encrypt(data[:size_aligned])
    if size != size_aligned:
        last_block_s = len(out_data) - 0x10
        last_enc_byte = out_data[-0x10]
        for i in range(size % 0x10):    
            last_enc_byte = out_data[last_block_s + i] ^ \
                            XOR_LAST_BYTES[to_ecx(last_enc_byte) + i] ^ \
                            data[size_aligned + i]
            out_data += last_enc_byte.to_bytes()
    return out_data

def decrypt(data: bytes, size: int = 0) -> bytes:
    if size == 0: size = len(data)
    if size < 0x10:
        return data

    cipher = AES.new(KEY, AES.MODE_CBC, iv=IV)
    size_aligned = size - size % 0x10
    if size == size_aligned:
        return cipher.decrypt(data)

    last_block_st = size_aligned - 0x10
    last_data = data[size_aligned:]
    return cipher.decrypt(data[:size_aligned]) + \
           bytes(XOR_LAST_BYTES[to_ecx(last_enc_byte) + i] ^ 
                 byte ^ data[last_block_st + i]
            for i, (last_enc_byte, byte) in enumerate(zip(
                (data[last_block_st:last_block_st+1] + last_data), last_data)))


def extract(data: bytes, output_folder: Path):
    output_folder.mkdir(parents=True, exist_ok=True)
    unk_size, count, alignment, _ = unpack_from('< 4I', data)
    files_data = unpack_from(f'< {count * 4}I', data, 0x10)
    for i in range(count):
        offset, _, size_compressed, size_decompressed = files_data[i * 4:i * 4 + 4]
        offset *= alignment
        # size_compressed = offset - files_data[i * 4 + 4] * alignment
        decrypted = decrypt(data[offset:offset + size_compressed])
        #assert(size_decompressed == unpack_from('< I', decrypted)[0])
        #if size_decompressed == 0:
        #    decompressed = decrypted
        #else:
        pos = 8
        decompressed = bytes()
        while len(decompressed) < size_decompressed:
            size_compressed, = unpack_from('< I', decrypted, pos - 4)
            decompressed += decompress(decrypted[pos:pos + size_compressed])
            pos += size_compressed + 4
        ext = getFileExtension(decompressed[:12].split(b'\x00')[0])
        if ext == '.bin':
            #try?
            extract_strings(output_folder / f'{i:08d}.txt', decompressed, size_decompressed)
        else:
            (output_folder / f'{i:08d}{ext}').write_bytes(decompressed)

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
        decompressed = convert_strings(input_file)
        size_decompressed = len(decompressed)
        # if size_decompressed < 0x101:
        #   decrypted = decompressed
        #else:
        decrypted = re_pack(decompressed)
        size_compressed = len(decrypted)
        data += encrypt(decrypted, size_compressed)
        files_data += [offset >> 8, 0, size_compressed, size_decompressed]
        #padding = -size_compressed % 0x10
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