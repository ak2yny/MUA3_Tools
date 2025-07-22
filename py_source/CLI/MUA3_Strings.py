# String converter (UTF-16 LE) for MUA3
# by ak2yny

import csv
import glob
from argparse import ArgumentParser
from pathlib import Path
from struct import iter_unpack, pack, unpack_from

from .MUA3_ZL import backup

def split_strings(strings: str, count: int):
    o = 0
    for _ in range(count):
        e = strings.find('\x00', o)
        yield strings[o:e].replace('\r\n', '\\r\\n')
        o = 8 - e % 8 + e

def extract_strings(input_file: Path, output_folder: Path):
    data = input_file.read_bytes()

    list_count, = unpack_from('<I', data)

    if list_count == 0: # assuming hash table
        output_file = input_file.with_suffix('.csv')
        backup(output_file)
        count, = unpack_from('<I', data, 4)
        with output_file.open('w', newline='') as cf:
            csvwriter = csv.writer(cf)
            _ = csvwriter.writerow(['Index', 'Hash'])
            for i, h in iter_unpack('<I8s', data[8:]):
                _ = csvwriter.writerow((i,''.join(f'{x:02x}' for x in h)))
    else:
        backup(output_folder)
        output_folder.mkdir(parents=True, exist_ok=True)
        list_offsets = unpack_from(f'<{list_count}I', data, 4)
        for i, o in enumerate(list_offsets):
            count, = unpack_from('<I', data, o)
            o1, = unpack_from('<I', data, o + 4)
            # Note: Python doesn't provide a more efficient way with offsets, that's why they're ignored
            #offsets = unpack_from(f'<{count}I', data, o + 4)
            strings = data[o + o1:(list_offsets[i+1] if i+1 < list_count else None)].decode('utf-16le')
            strings = *split_strings(strings, count),
            with (output_folder / f'{o:08}.txt').open('w', encoding='utf-16le') as f:
                f.write('\n'.join(strings))
               # for row in zip(offsets, strings):
               #     _ = csvwriter.writerow(row)
               
def combine_strings(input_folder: Path, output_file: Path):
    input_files = [x for x in input_folder.iterdir() if x.suffix.casefold() == '.txt']
    if len(input_files) > 0:
        backup(output_file)
        list_count = len(input_files)
        o = (-(list_count + 1) % 4 + list_count + 1) * 4
        list_offsets = []
        data = bytes(o)
        for input_file in input_files:
            list_offsets.append(len(data))
            # Note: Using plain text, instead of csv or numpy's genfromtext, and generate offsets anew
                #_ = next(csvreader)
                #(IDs, strings) = tuple(zip(*csvreader)) if input_file.stat().st_size > 24 else ([], [])
                #*map(int, IDs)
            # Note: Must be utf-16le anyway, so we can parse the data as bytes
            #with input_file.open(encoding='utf-16le') as f:
            #    strings = f.readlines()
            strings = input_file.read_bytes().split(b'\r\x00\n\x00') if input_file.stat().st_size > 0 else []
            count = len(strings)
            pad = (-(count + 1) % 4) * 4
            o1 = (count + 1) * 4 + pad
            sdata = bytes(0)
            data += pack('<I', count)
            for s in strings:
                data += pack('<I', o1 + len(sdata))
                s = s.replace(b'\\\x00r\x00\\\x00n\x00', b'\r\x00\n\x00') #.encode('utf-16le')
                sl = len(s)
                sdata += pack(f'{16 - sl % 16 + sl}s', s)
            data += bytes(pad) + sdata
        output_file.write_bytes(pack(f'<{1 + list_count}I', list_count, *list_offsets) +
                                data[4 + list_count * 4:])

def combine_hash_table(input_file: Path):
    with input_file.open(newline='') as cf:
        csvreader = csv.reader(cf)
        # skip header:
        _ = next(csvreader)
        hash_table = tuple(x for i, h in csvreader for x in (int(i), bytes.fromhex(h)))
    count = len(hash_table) // 2
    output_file = input_file.with_suffix('.bin')
    backup(output_file)
    output_file.write_bytes(pack(f'<2I{"I8s" * count}', 0, count, *hash_table))

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

        if input_file.is_dir():
            combine_strings(input_file, Path(f'{input_file}.bin'))
            found_any = True
        elif ext == '.bin':
            extract_strings(input_file, input_file.parent / input_file.stem)
            found_any = True
        elif ext == '.csv':
            combine_hash_table(input_file)
            found_any = True

    if not found_any:
        raise ValueError('No files found')

if __name__ == '__main__':
    main()