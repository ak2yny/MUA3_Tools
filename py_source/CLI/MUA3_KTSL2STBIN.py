# Koei Tecmo Sound File combiner for ktsl2stbin for MUA3
# by ak2yny


import glob
from argparse import ArgumentParser
from pathlib import Path

from .MUA3_KTSR import _combineKS

def main():
    parser = ArgumentParser()
    parser.add_argument('input', help='input file (supports glob)')
    args = parser.parse_args()
    input_files = glob.glob(args.input.replace('[', '[[]'), recursive=True)

    if not input_files:
        raise ValueError('No files found')

    for input_file in input_files:
        input_folder = Path(input_file)

        if input_folder.is_dir():
            output_file = Path(f'{input_folder}.ktsl2asbin')
            _combineKS(input_folder, output_file, True)

if __name__ == '__main__':
    main()