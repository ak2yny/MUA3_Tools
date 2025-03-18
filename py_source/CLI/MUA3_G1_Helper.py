# Koei Tecmo's Gust files extractor and combiner for MUA3
# by eArmada8, Joschuka and three-houses-research-team, yretenai (creator of Cethleann), ..., ak2yny
# WIP: using byte stream instead of bytes could speed up the process: io.BytesIO(data) as f (f.read(4)), but bytearray should be the fastest

# native
from pathlib import Path

# local
from .MUA3_BIN import get_offsets
from .MUA3_ZL import backup, un_pack

from .lib.lib_gust import setEndianMagic, setEndianFile
from .lib.lib_g1t import g1t_to_dds


def extractG1T(input_file: Path, flip_image: bool = False):
    output_folder = input_file.with_suffix('')
    backup(output_folder)
    g1t_to_dds(input_file.read_bytes(), output_folder, flip_image)
    # subprocess.call([g1t_extract, str(input_file)])

def extractG1(data: bytes, output_file: Path, pos: int = 0, next_pos: int = 0):
    backup(output_file)
    # The helper mustn't have heavy imports, such as pyquaternion. Keep them to the main scripts
    match output_file.suffix:
        case '.g1t':
            g1t_to_dds(data, output_file.parent, False)
        case _:
            # add more...
            output_file.write_bytes(data[pos:next_pos]) # WIP

def _extractG(data: bytes, offsets: tuple, output_folder: Path):
    for i, pos in enumerate(offsets):
        e = setEndianMagic(data[pos:pos + 12].split(b'\x00')[0])
        if e: extractG1(data, output_folder / f'{i:04d}{e}', pos, offsets[i + 1] if i + 1 < len(offsets) else len(data))

def extractG(input_file: Path, output_folder: Path):
    e = setEndianFile(input_file)
    sz = input_file.stat().st_size
    if not e or sz < 12: return
    # WIP: Here comes the moment, where either all files are extracted (for g1m merge), or a Blender handling/dialogue is used
    if e == '.g1t':
        extractG1T(input_file)
    else:
        _extractG(input_file.read_bytes(), output_folder / (input_file.stem + e), sz)

def extractZ(input_file: Path, output_folder: Path):
    if output_folder.suffix.casefold() == '.bin':
        data = un_pack(input_file)
        _extractG(data, get_offsets(data), output_folder)
    else:
        _extractG(un_pack(input_file), (0,), output_folder.with_suffix(''))

def extractB(input_file: Path, output_folder: Path):
    data = input_file.read_bytes()
    _extractG(data, get_offsets(data), output_folder)
