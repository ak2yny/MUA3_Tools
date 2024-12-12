# Koei Tecmo's Gust files extractor and combiner for MUA3
# by eArmada8, Joschuka and three-houses-research-team, yretenai (creator of Cethleann), ..., ak2yny
# WIP: using byte stream instead of bytes could speed up the process: io.BytesIO(data) as f (f.read(4)), but bytearray should be the fastest

# native
from pathlib import Path

# project
from MUA3_Formats import getFileExtension
from MUA3_BIN import get_offsets
from MUA3_ZL import backup, un_pack

from lib.lib_gust import E
from lib.lib_g1t import g1t_to_dds


def extractG1T(input_file: Path, flip_image: bool = False):
    output_folder = input_file.with_suffix('')
    backup(output_folder)
    g1t_to_dds(input_file.read_bytes(), output_folder, flip_image)
    # subprocess.call([g1t_extract, str(input_file)])

# WIP possibly put this into the gust lib, together with the formats
def setEndianMagic(magic: bytes):
    """
    Set the endian, depending on the magic.
    Returns file extension according to magic, if the endian was set, otherwise None if magic wasn't found.
    """
    global E
    e = getFileExtension(magic)
    if e != '.bin':
        E = '<'
        return e
    e = getFileExtension(magic, True)
    if e != '.bin':
        E = '>'
        return e
    return None

def setEndianFile(input_file: Path):
    with input_file.open('rb') as f: return setEndianMagic(f.read(4))

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
        if e:
            extractG1(data, output_folder / f'{i:04d}{e}', pos, offsets[i + 1] if i + 1 < len(offsets) else len(data))

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

def _readG(data: bytes, offsets: tuple) -> bytes:
    for i, pos in enumerate(offsets):
        e = setEndianMagic(data[pos:pos + 12].split(b'\x00')[0])
        if e:
            __extractG1(data / f'{i:04d}{e}', pos, offsets[i + 1] if i + 1 < len(offsets) else len(data))

def _readB(input_file: Path) -> bytes:
    data = input_file.read_bytes()
    _readG(data, get_offsets(data))

def _readZ(input_file: Path) -> bytes:
    if input_file.with_suffix('').suffix.casefold() == '.bin':
        data = un_pack(input_file)
        _readG(data, get_offsets(data))
    else:
        _readG(un_pack(input_file), (0,))

def read_any(input_file: Path):
    ext = input_file.suffix.casefold()
    # output_folder = input_file.with_suffix('')
    # output_folder.mkdir(parents=True, exist_ok=True)

    if input_file.is_dir():
        # WIP: Combine logic
        pass
    elif input_file.suffix.upper() == '.ZL_':
        _readZ(input_file)
    elif ext == '.bin':
        _readB(input_file)
    elif ext in ('.g1m', '.g1t', '.g1a', '.g2a'):
        _readG(input_file)
        # from g1m_export_meshes import parseG1M
        #parseG1M(f'{input_file.with_suffix('')}', overwrite=False, write_buffers=True, cull_vertices=False, transform_cloth=True, write_empty_buffers=False)
    elif ext in ['.g2a', '.g1a']:
        # _extractG(input_file, output_folder)
        pass # WIP
    elif ext == '.g1t': # Texture
        _extractG(input_file, output_folder)
    elif input_file.name == 'g1t.json':
        with input_file.open('r') as f:
            json_data = json.load(f)
        dds_to_g1t_json(input_file.parent, json_data, False)
    # Any other file formats? MUA3 doesn't seem to have OBJD (extension?), and lmpk don't seem to belong into this category
    # WIP: json files seem to contain numbers in hex format that might have to be converted to int(x, 16)
    elif input_file.name == 'elixir.json':
        with input_file.open(encoding='UTF-8') as f:
            elixir = json.load(f)
        _tryextractG1M([x for x in elixir['files'] if x[-4:] == '.g1m'], input_file.parent)
    elif input_file.name == 'gmpk.json':
        with input_file.open(encoding='UTF-8') as f:
            gmpk = json.load(f)
        _tryextractG1M([f'{x["name"]}.g1m' for x in gmpk['SDP']['NID']['names']], input_file.parent)
    else: # check if Gust file
        _extractG(input_file, output_folder)


