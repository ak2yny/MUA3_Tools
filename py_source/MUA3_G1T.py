# Based primarily off of:
#   - https://github.com/VitaSmith/gust_tools
#   - https://github.com/Joschuka/Project-G1M and its predecessor https://github.com/Joschuka/fmt_g1m (Python Noesis plugin)
#   - Research of thee GitHub/three-houses-research-team
#   - Research by Yretenai, DarkstarSword and others
# Many thanks to them, as well as eArmada8, https://github.com/eterniti/g1m_export (& vagonumero13).

# native
import json
from argparse import ArgumentParser
from glob import glob
from pathlib import Path

# local
from lib.lib_gust import * # incl. endian config
from lib.lib_g1t import dds_to_g1t, dds_to_g1t_json
from MUA3_G1_Helper import extractG, extractZ


def main():
    parser = ArgumentParser()
    parser.add_argument('input', help='input file (supports glob)')
    parser.add_argument('-f', '--flip_image', help="Flip images vertically", action="store_true")
    args = parser.parse_args()
    input_files = glob(args.input.replace('[', '[[]'), recursive=True)

    if not input_files:
        raise ValueError('No files found')

    for input_file in input_files:
        input_file = Path(input_file)
        ext = input_file.suffix.casefold()
        output_folder = input_file.with_suffix('')

        if input_file.is_dir():
            dds_to_g1t(input_file, args.flip_image)
        elif input_file.suffix.upper() == '.ZL_':
            extractZ(input_file, output_folder)
        elif ext == '.g1t':
            extractG(input_file, output_folder)
        elif input_file.name == 'g1t.json':
            with input_file.open('r') as f:
                json_data = json.load(f)
            dds_to_g1t_json(input_file.parent, json_data, args.flip_image)
        else: # check if Gust file
            extractG(input_file, output_folder)

if __name__ == '__main__':
    main()