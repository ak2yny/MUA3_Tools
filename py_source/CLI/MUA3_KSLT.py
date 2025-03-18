# Based primarily off of:
#   - https://github.com/Joschuka/Project-G1M and its predecessor https://github.com/Joschuka/fmt_g1m (Python Noesis plugin)
#   - https://github.com/eArmada8/gust_stuff
#   - Research of thee GitHub/three-houses-research-team
#   - Research by Yretenai, DarkstarSword and others
# Many thanks to them, as well as https://github.com/eterniti/g1m_export (& vagonumero13).

# native
from argparse import ArgumentParser
from glob import glob
from pathlib import Path
from struct import unpack

# local
from .lib.lib_g1t import dds_to_kslt, kslt_to_dds
from .lib.lib_gust import E, setEndianMagic
from .MUA3_BIN import _extract as extractB

def kslt_extract(input_file: Path, output_folder: Path):
    kslt_to_dds(input_file.read_bytes(), output_folder)

def kslt_import(input_folder: Path):
    k_file = input_folder.parent / f'{input_folder.name}.kslt'
    KSLT_offset = 0
    if not k_file.exists():
        k_file = input_folder.parent / f'{input_folder.name}.kscl'
        if not k_file.exists():
            raise ValueError(f"Import source {k_file.with_suffix('.kslt')} not found.")
        with input_file.open('rb') as f:
            if setEndianMagic(f.read(4)) != '.kscl':
                raise ValueError(f'Import source {k_file} is not a valid KSCL file.')
            KSLT_offset = unpack(E+'4xI', f.read(8))[0] + 0x88
            if input_file.stat().st_size < KSLT_offset:
                raise ValueError(f"Import source {k_file.with_suffix('.kslt')} not found.")
    dds_to_kslt(k_file, input_folder, KSLT_offset)

def kscl_extract(input_file: Path, output_folder: Path):
    with input_file.open('rb') as f:
        if setEndianMagic(f.read(4)) != '.kscl':
            return
        KSLT_offset = unpack(E+'4xI', f.read(8))[0] + 0x88 # Might depend on game/version/file
        if input_file.stat().st_size < KSLT_offset:
            # External reference (can this be checked with a value?)
            kslt_to_dds(input_file.with_suffix('.kslt').read_bytes(), output_folder)
        else:
            f.seek(KSLT_offset)
            kslt_to_dds(f.read(), output_folder)

def main():
    parser = ArgumentParser()
    parser.add_argument('input', help='input file (supports glob)')
    # parser.add_argument('-f', '--flip_image', help="Flip images vertically", action="store_true")
    parser.add_argument('-e', '--extract', help="Extract the included files, if input is a directory. (Combines if this is not set, no effect if input is a file.)", action="store_true")
    parser.add_argument('-f', '--flat', help="Flat extraction. Don't extract to sub-folders with the name of each file, extract to the same folder instead.", action="store_true")
    args = parser.parse_args()
    input_files = glob(args.input.replace('[', '[[]'), recursive=True)

    if not input_files:
        raise ValueError('No files found')

    for input_file in input_files:
        input_file = Path(input_file)
        output_folder = input_file.parent if args.flat else input_file.with_suffix('')

        # WIP: needs kclt as well
        if input_file.is_dir():
            if args.extract:
                for k in input_file.glob('**/*.kslt'):
                    kslt_extract(k, input_file if args.flat else k.with_suffix(''))
                for k in input_file.glob('**/*.kscl'):
                    kscl_extract(k, input_file if args.flat else k.with_suffix(''))
            else:
                kslt_import(input_file)
        elif input_file.suffix.casefold() == '.bin':
            # WIP: could possibly scan the extracted folder for kslt files and extract them
            extractB(input_file, output_folder)
        elif input_file.suffix.casefold() == '.kslt':
            kslt_extract(input_file, output_folder)
        elif input_file.suffix.casefold() == '.kscl':
            kscl_extract(input_file, output_folder)

if __name__ == '__main__':
    main()