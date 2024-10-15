# File format identifiers for MUA3
# by yretenai (creator of Cethleann), ak2yny

# Gust is a Koei Tecmo developer
GUST_FORMATS = {
    b'_A1G': '.g1a', # Animation
    b'_A2G': '.g1a', # AnimationV2
    b'_H1G': '.g1h', # Morph
    b'_L1G': '.g1l', # Large
    b'_M1G': '.g1m', # Model
    b'_N1G': '.g1n', # Font2
    b'_OLS': '.sebin',
    b'_SPK': '.postfx',
    b'_S2G': '.g1s', # Shader
    b'GT1G': '.g1t', # TextureGroup
    b'OC1G': '.g1c', # Collision
    b'ME1G': '.g1em', # EffectManager
    b'SV1G': '.kslt', # VideoSource
    b'XF1G': '.g1fx', # Effect
    b'_DBW': '.wbd',
    b'_HBW': '.wbh',
    b'BPK0': '.bpk',
    b'Clip': '.clip',
    b'CONT': '.cont',
    b'DATD': '.datd',
    b'DCL0': '.lcd0',
    b'CRAE': '.elixir', # ElixirArchive
    b'GAPK': '.gapk',
    b'GEPK': '.gepk',
    b'GMPK': '.gmpk',
    b'RTPK': '.rtrpk',
    b'HDDB': '.hdb',
    b'LCSK': '.kscl', # ScreenLayout
    b'TLSK': '.kslt', # ScreenLayoutTexture
    b'LMPK': '.lmpk',
    b'MDLK': '.mdlk',
    b'PBSM': '.material', # PBSMaterial, PDBMat
    b'RIGB': '.rig',
    b'BGIR': '.rig', # RIGBL, RIGB little endian
    b'RTRE': '.ertr',
    b'RTXE': '.extra', # EXTR
    b'SARC': '.sarc', # S? archive
    b'SCEN': '.scene',
    b'3SPK': '.shaderpack',
    b'SPKG': '.spkg',
    b'SWGQ': '.swg', # SwingDefinition
    b'WHD1': '.sed', # video?
    b'XL\x13': '.xl', # XL19
    b'XL\x14': '.xlstruct', # XL20
    b'ecb': '.struct',
    b'MDLRESPK': '.mdlpack',
    b'MDLTEXPK': '.mdltexpack',
    b'EXAR': '.exarg', # EXARG000 or EXARG ???
    b'EFFRESPK': '.effectpack',
    b'G2A_PACK': '.g1apack',
    b'G1E_PACK': '.g1epack',
    b'G1M_PACK': '.g1mpack',
    b'PG1H_DAT': '.g1hpack',
    b'G1COPACK': '.g1copack',
    b'HEAD': '.exhead', # HEAD_PAK / HEADPACK ???
    b'COLRESPK': '.colpack',
    b'TDPA': '.tdpack', # TDPACK ???
    b'tdpa': '.tdpack', # tdpack / OldTDPack ???
    b'bodybase': '.bodybase',
    b'char_dat': '.chardata',
    b'pkgi': '.pkginfo' # pkginfo ???
    # g1m contents with ID, Version?, section length
    # b'SM1G' -> G1MS (Skeleton)
    # b'FM1G' -> G1MF (File?)
    # b'GM1G' -> G1MG (Graphics, texture)
    # b'MM1G' -> G1MM (Meshes?)
}

# Other Koei Tecmo formats
KOEI_TECMO_FORMATS = {
    b'KTSC': '.ktsl2asbin', # Koei Tecmo container for Nintendo DSP 4-bit ADPCM sound files (as .kns/kvs or otherwise)
    b'KTSRw{H\x1a': '.ktsl2asbin',
    b'KTSR': '.ktsl2stbin',
    b'KTSS': '.kns', # Koei Tecmo version? of Nintendo DSP 4-bit ADPCM sound files
    b'KOVS': '.kvs',
    b'LCSK': '.kscl', # ScreenLayout
    b'TLSK': '.kslt', # ScreenLayoutTexture
    b'TRRRESPK': '.ktfkpack'
}

# Other companies or Nintendo owned
NINTENDO_FORMATS = {
    b'SARC': '.sarc', # Nintendo (WiiU/3ds) archive https://mk8.tockdom.com/wiki/SARC_(File_Format)
    # Sega and/or Nintento? related formats
    b'_DRK': '.rdb',
    b'IDRK': '.rdb.bin', # RDBIndex
    b'PDRK': '.fdata', # RDBPackage
    b'_RNK': '.name', # NDB
    b'IRNK': '.name.bin', # NDBIndex
    b'_DOK': '.kidsobjdb', # OBJDB, compiled XML data files?
    b'IDOK': '.kidsobjdb.bin', # OBJDBIndex
    b'RDOK': '.kidsobjdb.bin' # OBJDBRecord
}

# Formats by unrelated companies
# https://web.archive.org/web/20221112073316/https://www.garykessler.net/library/file_sigs.html
COMMON_FORMATS = {
    b'DDS ': '.dds',
    b'OggS': '.ogg',
    b'RIVE': '.river', # Grafanga Labs configuration file?
    b'TMC': '.tmc', # ?
    b'RIFF': '.wav', # or another related file format
    b'\x30\x26\xB2\x75\x8E\x66\xCF\x11': '.wmv', # ASF, WMA, WMV
    b'\xA6\xD9\x00\xAA\x00\x62\xCE\x6C': '.wmv' # ASF, WMA, WMV
}

ALL_FORMATS = GUST_FORMATS | KOEI_TECMO_FORMATS | NINTENDO_FORMATS | COMMON_FORMATS


def getFileExtension(file_format: str) -> str:
    if file_format in ALL_FORMATS: return ALL_FORMATS[file_format]
    return '.bin'
    # b'\xf9\x7d\x07' -> LINKDATA found in AoT2
    # b'\xdf' -> ? found in model files
    # ?
    # b'LLOC' -> COLL
    # b'ONUN' -> NUNO
    # b'VNUN' -> NUNV
    # b'SNUN' -> NUNS
    # b'TFOS' -> SOFT
    # b'RIAH' -> HAIR
    # Don't know what the value would be in Python
    # b'\x00\x19  _  \x12\x16': '.struct', # 0x1612_1900 StructTable???
    # b'\x1A\x45  _  \xDF\xA3': '.webm', # 0xA3DF_451A WEBM???
    # b'\x00\x00  _  \x01\x00': '.gz', # 0x0001_0000 Compressed???
    # b'\x00\x00  _  \x02\x00': '.gz', # 0x0002_0000 CompressedChonky???
