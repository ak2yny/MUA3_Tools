from dataclasses import dataclass
#from configparser import ConfigParser
#from os import startfile
from pathlib import Path
#from sys import executable
from struct import Struct

from MUA3_Strings import split_strings



CD = Path(__file__).parent # executable, from sys import executable
HASH_TABLE_ISO_8NAME = CD / 'hash_table_ISO_8Name.bin'
MES_ISO_8NAME_ENG = CD / 'mes_ISO_8Name_eng.bin'
# MAX_CHAR_INDEX = 2035
# CHARACTER_NAMES = {
#     int(''.join(l[:8].split(' ')[::-1]), 16): l[10:]
#         for l in Path('DataCharacter.Bin IDs.txt').read_text().split('\n')
#     }


CHARACTERDATA_STRUCT = Struct('<'
    'I'
    '4H'
    '9I'
    '2B'
    '2x'
)

UINT32_STRUCT = Struct('<I')

def get_strings(file: Path) -> list:
    data = file.read_bytes()
    list_count, = UINT32_STRUCT.unpack_from(data)
    ISO8_string_offset, *_remaining_offsets = Struct(f'<{list_count}I').unpack_from(data, 4)
    count, o1 = Struct('<2I').unpack_from(data, ISO8_string_offset)
    o1 += ISO8_string_offset
    o2 = _remaining_offsets[0] if len(_remaining_offsets) != 0 else None
    return [s for s in split_strings(data[o1:o2].decode('utf-16le'), count)]

def get_iso8_hash_table(ISO_8Name: Path):
    data = ISO_8Name.read_bytes()
    # count, = UINT32_STRUCT.unpack_from(data, 4)
    for i, h in Struct('<I8s').iter_unpack(data[8:]):
        yield ''.join(f'{x:02x}' for x in h)

MES_SPECIALBONUS_ENG = get_strings(CD / 'mes_SpecialBonus_eng.bin')

print(MES_SPECIALBONUS_ENG)