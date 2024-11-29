# Koei Tecmo Sound File extractor and combiner for MUA3
# by ak2yny, DeathChaos, HealingBrew, 0Liam, Raytwo, Alex Barney, Hairo R. Carela, KT, SlowpokeVG, vgmstream team, aluigi, RobCat030


import glob, subprocess
from argparse import ArgumentParser
from dataclasses import astuple, dataclass, field, InitVar
from pathlib import Path
from struct import calcsize, pack, unpack_from

from lib.lib_gust import dirtyAlign
from MUA3_ZL import backup


ZERO_INT = bytes(4)
KTSL2STBIN_ID = b'KTSR\x02\x94\xDD\xFC'
KTSL2STBIN_ENTRY_ID = b'\x09\xD4\xF4\x15'
KTSL2ASBIN_ID = b'KTSRw{H\x1A'
# KTSL2ASBIN_HASH_ID = b'\xBD\x88\x8C\x36'
KTSL2ASBIN_ENTRY_ID = b'\xC5\xCC\xCB\x70'
KTSL2_HEAD_DATA = b'\x01\x00\x00\x04' # Flags (must be 1) + Console (Switch)
KTSL2_HEAD_DATA += b'\x75\x9D\xEB\x03' # GameID
KTSL2_HEAD_DATA += bytes(8)  # Padding
BLOCK_SIZE = 1024 # DSP channel block_size hardcoded, do DSP only
SECTION_PADDING = 32 # Some sounds might need the extra 00 bytes. Unknown why and how many, so it's hardcoded at this time.
VGAudio = './VGAudioCli.exe'


"""
**KTSL2ASBIN (LE)**
KTSL2ASBIN_ID + KTSL2_HEAD_DATA
*********Hash Info Sections***********
id
size
id/hash?
offset strings
00 + int32 10 or 4? + 00 + 00 (sounds); 00 + ffffffff + 00 + ffffffff (voices); unk * 4 (music)
getKtsl2asbinStrings (but additional int32 512? (voices); 00 (sounds/music))
*type1 (sounds+voices id 63 B9 FE 29)
 size + id/hash? + offset a
 (a) count? + offset b (size - 32) + int32 68882? + unk
 0x0000803F? + 00 + size or offset? + 00
 00 * 3 + 0x0000803F?
 0x00000041? * 2 + 00 + 0x00000040?
 00 * 2 + ffffffff * 2
 00 * 2 + 0x0000A041? + 0x0000A040?
 (b) offset c (= size) + 00 + int32 1? + 0xABAA2ABD? + 0xABAAAA3D? + 00 + ffffffff * 2
 *type1.1 (id 72 04 17 A5)
  size + id/hash + int16 0 + int16 1
  00 + unk + 00 * 2
  0x0000803F? * 3 + 00
 padding
*type2 (music no strings id ??)
 ...
*type3 (music with strings id 82 50 D2 51)
 offset size
 ...
 size
 padding
 *type3.1 (id 29 CA 82 62)
  size + id/hash + unk
  ...
*********Padding***********
*********File Info Sections***********
KTSL2ASBIN ENTRY
*************************************


def padIt(data: str, i: int) -> str:
    return data + bytes((i - len(data) % i) % i)

WINDOW_WIDTH = min(30, os.get_terminal_size().columns - 10)
def print_progression(current: int, factor: float):
    # factor = WINDOW_WIDTH/total
    i = current * factor
    print('\r', end='')
    print(f'[{'=' * int(i)}{' ' * (WINDOW_WIDTH - int(i))}] {i/WINDOW_WIDTH:.1%}', end='')
    if i == WINDOW_WIDTH: print()
"""

KTSL2ASBIN_EHEAD_STRUCT = '< 4s5I'
KTSL2STBIN_EHEAD_STRUCT = '< 4s4I44x' # 64 - 4 * 5 = 44 is hardcoded at this time
KTSL2STBIN_ESUBHEADKTSR_STRUCT = '< 4s13I2H2I2H'
KTSL2STBIN_ESUBHEADKTSS_STRUCT = '< 4s16I'
KTSS_HEAD_STRUCT = '< 4sI24xB3sI2B2x4I4x'
DSPADPCM_HEAD_STRUCT = '> 3I2H3I32x14x2H18x'

KTSL2STBIN_EHEAD_SIZE = calcsize(KTSL2STBIN_EHEAD_STRUCT)

@dataclass
class KTSL2ASBIN_EHead:
    ID: str
    size: int
    link_id: int
    audio_type: int # int32 0 = Voice; int32 2 = Sound; int16 0 + int16 1 = music
    string_count: int # unconfirmed, always 1?
    pos_offsets: int # = end of strings
    strings: dict = field(default_factory=dict)
    size_header: int = 28 # offset 1st file | hardcoded for KTSL2ASBIN entries at this time
    file_size: int = 0
    # padding
    def __post_init__(self):
        if self.ID == KTSL2STBIN_ENTRY_ID:
            self.size_header = self.audio_type
            self.file_size = self.string_count
        # self.size_header = unpack_from('< I', data, pos + self.pos_offsets)
    def get_strings(self, data: bytes, pos: int = 0, n: int = 0):
        pos += 24
        p = pos + self.pos_offsets
        for i in range(pos, pos + self.string_count * 4, 4):
            start, = unpack_from('< I', data, i)
            self.strings[data[start:self.pos_offsets].split(b'\x00', 1)[0].decode() if start > 0 else f'{n:04d}_{self.ID}'] = unpack_from('< I', data, p)[0]
            p += 4
            
@dataclass
class KTSL2ASBIN_ESubHead_Base:
    magic: str # might need to change depending on ktss, but need more info
    size: int # Not including ktss
    ID: int
    channel_count: int
    unk1: int # Transition Related (should be 4096); 0x76C539C8 with ktss
    unk2: int # ktss only: Transition Related (should be 4096)
    sample_rate: int
    duration: int # or loop end?
    zero: int # possibly file start/offset or something?
    loop_start: int # not confirmed
    channel_mask: int # not confirmed

@dataclass
class KTSL2ASBIN_ESubHead_Ktsr(KTSL2ASBIN_ESubHead_Base):
    unk2: int = field(init=False)
    dsp_header_pos: int
    dsp_header_size: int
    ks_infos_pos: int
    ks_sizes_pos: int
    # depends on dsp_header_pos, usually 4 x int32
    ks_unk1: int
    ks_unk2: int # ks_unk2 + ks_unk4 seem to be related
    zero1: int
    ks_header_end: int
    ks_unk3: int
    ks_unk4: int
    # or use self.__dict__ instead
    # def astuple(self):
    #     return (getattr(self, f.name) for f in fields(self) if f.init)

@dataclass
class KTSL2ASBIN_ESubHead_Ktss(KTSL2ASBIN_ESubHead_Base):
    zero1: int
    zero2: int
    ktss_pos: int
    ktss_size: int
    unk5: int # b'\x00\x02\x00\x00', 512?

@dataclass
class KTSS_Head:
    ID: str = b'KTSS'
    size: int = 0
    codec: int = 2 # 2 = DSPADPCM, 9 = Opus
    unk: str = b'\x00\x03\x03'
    h_size: int = 32 + 96
    layer_count: int = 1
    channel_count: int = 1
    sample_rate: int = 0
    sample_count: int = 0
    start: int = 0
    duration: int = 0
    def set_h_size(self):
        self.h_size = 32 + 96 * self.channel_count

@dataclass
class DSPADPCM_Head:
    sample_count: int
    nibble_count: int
    sample_rate: int
    loop_flag: int
    audio_format: int
    loop_start_offset: int # StartAddress?
    loop_end_offset: int # EndAddress?
    current_address: int # 0 or 2?
    # coefficients: list<int16>[16]
    # gain: int16
    # initial_predictor: int16 (scale) always matches first frame header??
    # initial_history1: int16 (sample)
    # initial_history2: int16 (sample)
    # loop_predictor: int16 (scale)
    # loop_history1: int16 Loop context sample history 1
    # loop_history2: int16 Loop context sample history 2
    channel_count: int
    interleave_size_frames: int # interleave_size / 8
    # Padding

def duration(v: int) -> int:
    return v - v // 8
    # round up: v - v // 8 - (v % 8 > 0)
    # round: v - (v + v % 8) // 8

def parallelize_channels(channels: list, i: int) -> bytes:
    size = len(max(channels, key=len))
    size += (8 - size) % 8
    return b''.join(c[p:p + i] for p in range(0, size, i) for c in (c + bytes(size - len(c)) for c in channels))

def sequentialize_channels(data: bytes, i: int, channel_count: int) -> list:
    all_sz = len(data)
    channels = [b''] * channel_count
    for p in range(0, all_sz, i * channel_count):
        for c in range(channel_count):
            channels[c] += data[p + i * c:p + i * (c + 1)]
    r = all_sz // channel_count % i
    if r > 0:
        for c in range(channel_count):
            channels[c] = channels[c][:all_sz // channel_count - r] + data[p + r * c:p + r * (c + 1)]
    return channels

def DSPADPCM_KTS_Convert(data: bytes, channels: list, channel_count: int, in_i: int, out_i: int = -1, pos:int = 0) -> tuple[bytes|list]:
    """
    Reverses endianness in header (data[0]) and changes interleave_size in data[1] (except if -1).
    Returns header (bytes) and channels (list) separately as tuple.
    """
    channel_count = max(channel_count, 1)
    if channel_count == 1 or out_i < 0 or out_i == in_i:
        new_data = channels
        out_i = in_i
    elif in_i == 0:
        new_data = [parallelize_channels(channels, out_i * 8)]
    else:
        new_data = sequentialize_channels(channels[1], in_i * 8, channel_count)
        if out_i > 0: new_data = [parallelize_channels(new_data, out_i * 8)]
    if channel_count == 1: out_i = ci = 0
    else: ci = channel_count
    return (b''.join(pack('< 3I2H3I16H7H2H18x', *unpack_from('> 3I2H3I16H7H', data, pos + i * 96), ci, out_i) for i in range(channel_count)), new_data)

def DSPADPCM_ToKtss(data: bytes) -> bytes:
    d = DSPADPCM_Head(*unpack_from(DSPADPCM_HEAD_STRUCT, data))
    channel_count = min(2, max(d.channel_count, 1))
    if d.channel_count > 2:
        print('Maximum two channels are supported for this game and format (.kns).')
    kd = DSPADPCM_KTS_Convert(
        data, [data[max(d.channel_count, 1) * 96:]],
        channel_count,
        d.interleave_size_frames, 1
    ) # layer_count = 1?
    kd = kd[0] + b''.join(kd[1]) + bytes((16 - len(kd[1])) % 16)
    start = duration(d.loop_start_offset) if d.loop_flag else 0
    header = KTSS_Head(
        size = calcsize(KTSS_HEAD_STRUCT) + len(kd),
        channel_count = min(2, channel_count),
        sample_rate = d.sample_rate,
        sample_count = d.sample_count,
        start = start,
        duration = min(duration(d.loop_end_offset), d.sample_count) - start if d.loop_flag else d.sample_count
        # must match d.current_address + loop info (lp, l1, l2, esp lp), but unknown how exactly
    )
    header.set_h_size()
    return pack(KTSS_HEAD_STRUCT, *astuple(header)) + kd

def splitKtsl2stbin(st_file: Path) -> list:
    s = st_file.read_bytes().split(KTSL2STBIN_ENTRY_ID) if st_file.exists() else []
    return [s[0]] + [KTSL2STBIN_ENTRY_ID + x for x in s[1:]] if s else [KTSL2STBIN_ID + KTSL2_HEAD_DATA + bytes(40)]


def extractNconvert(data: bytes, output_folder: Path, name: str, wav=False):
    output_file = output_folder / f'{name}.dsp'
    output_file.write_bytes(data)
    if wav: _convert2wav(output_file)

def extractKTSS(data: bytes, pos: int, output_folder: Path, name: str):
    h = KTSS_Head(*unpack_from(KTSS_HEAD_STRUCT, data, pos))
    kd = DSPADPCM_KTS_Convert(
        data, [data[pos + 64 + 96 * h.channel_count:pos + 64 + h.size]],
        h.channel_count,
        h.layer_count,
        pos=pos + 64
    )
    extractNconvert(kd[0] + b''.join(kd[1]), output_folder, name)

def extractKS(data: bytes, output_folder: Path, st_file: Path):
    if data[:8] != KTSL2STBIN_ID and data[:8] != KTSL2ASBIN_ID:
        raise ValueError('This is a KTSL2 container with unsupported format.')

    backup(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    st_data = splitKtsl2stbin(st_file)

    pos = dirtyAlign(data, 32, 16)
    i = 0
    while pos < len(data):
        kh = KTSL2ASBIN_EHead(*unpack_from(KTSL2ASBIN_EHEAD_STRUCT, data, pos))
        if kh.ID == KTSL2STBIN_ENTRY_ID:
            magic, file_size = unpack_from('< 4sI', data, pos + kh.size_header)
            # pos += kh.size_header
            if magic == b'KTSS':
                extractKTSS(data, pos, output_folder, f'{i:04d}_{kh.link_id}')
                i += 1
        elif kh.ID == KTSL2ASBIN_ENTRY_ID:
            kh.get_strings(data, pos, i)
            for file_string in kh.strings:
                if st_file.exists():
                    kdat = next((x for x in st_data if unpack_from('< I',x, 8)[0] == kh.link_id), None)
                    if kdat:
                        extractKTSS(kdat,
                            unpack_from('< I', kdat, 12)[0],
                            output_folder, file_string)
                        continue
                kdat = data[pos + kh.strings[file_string]:pos + file_size]
                channel_count, start_header, start_DSP, sizes_DSP = unpack_from('< I24xI4x2I', kdat, 12)
                d = sizes_DSP - start_DSP
                kd = DSPADPCM_KTS_Convert(
                    kdat, [kdat[unpack_from('< I', kdat, i)[0]:][:unpack_from('< I', kdat, i + d)[0]] for i in range(start_DSP, sizes_DSP, 4)],
                    channel_count, 0, BLOCK_SIZE, start_header) # ?
                extractNconvert(kd[0] + b''.join(kd[1]), output_folder, file_string)
            i += 1
        # else:
            # case x if x == KTSL2ASBIN_HASH_ID: don't process at this time
            # case b'\x61\x72\xDB\xA8': Padding
            # case b'\xA9\xD2\x3B\xF1': Unknown info sections
            # return unknown format or corrupted

        pos += kh.size

def dsp2kdata(file: Path, old: bytes, pos: int, link_id: int, ktss: bool) -> tuple:
    # The struct of the khead is still partially unknown. Copying the values from the old file.
    if ktss:
        ktd = DSPADPCM_ToKtss(file.read_bytes()) if file.suffix.casefold() == '.dsp' else convert2ktss(file)
        file_size = len(ktd)
        new = pack(KTSL2STBIN_EHEAD_STRUCT,
            KTSL2STBIN_ENTRY_ID,
            KTSL2STBIN_EHEAD_SIZE + file_size + SECTION_PADDING,
            link_id,
            KTSL2STBIN_EHEAD_SIZE,
            file_size
        ) + ktd + bytes(SECTION_PADDING)
        kh = KTSL2ASBIN_ESubHead_Ktss(*unpack_from(KTSL2STBIN_ESUBHEADKTSS_STRUCT, old, pos))
        kh.channel_count, kh.sample_rate, kh.duration, kh.loop_start = unpack_from('< B2x3I', ktd, 41)
        kh.channel_mask = 3 if kh.channel_count > 1 else 0
        kh.ktss_pos = 0 # write offset as 0, replace later
        kh.ktss_size = file_size
        # kh.unk5 = 512 # might need to set this, just to make sure
        khead = pack(KTSL2STBIN_ESUBHEADKTSS_STRUCT, *astuple(kh))
    else:
        dsp = file.read_bytes() if file.suffix.casefold() == '.dsp' else convert2dsp(file)
        kh = KTSL2ASBIN_ESubHead_Ktsr(*unpack_from(KTSL2STBIN_ESUBHEADKTSR_STRUCT, old, pos))
        kh.channel_count, interleave_size = unpack_from('> 2H', dsp, 74)
        kh.channel_count = max(kh.channel_count, 1)
        kd = DSPADPCM_KTS_Convert(
            dsp, [dsp[kh.channel_count * 96:]],
            kh.channel_count,
            interleave_size, 0,
        )
        if len(kd[1]) == 1 and 1 != kh.channel_count:
            ch_sz = len(kd[1][0]) // kh.channel_count
            kd[1] = (kd[1][0][ch_sz * i:ch_sz * (i + 1)] for i in range(kh.channel_count)) # WIP: might cause errors
        # elif len(kd[1]) != channel_count:
        #     raise ValueError(f'{file.name} channels seem to be corrupted.')
        kh.dsp_header_size = len(kd[0])
        kh.ks_infos_pos = kh.dsp_header_pos + kh.dsp_header_size
        kh.ks_sizes_pos = kh.ks_infos_pos + 4 * kh.channel_count
        kh.ks_header_end = kh.ks_infos_pos + 8 * kh.channel_count
        DSPh_padding = (16 - kh.ks_header_end) % 16 + 16 # padding seems to depend...
        info_DSP = sizes_DSP = []
        new = b''
        for ksd in kd[1]:
            size_DSP = len(ksd)
            info_DSP.append(kh.ks_header_end + DSPh_padding + len(new))
            sizes_DSP.append(size_DSP)
            new += ksd + bytes((16 - size_DSP) % 16 + 16) # padding seems to depend...
        kh.size = kh.ks_header_end + DSPh_padding + len(new)
        kh.duration, kh.sample_rate = unpack_from('< I4xI', kd[0])
        kh.loop_start = 0xFFFFFFFF if dsp[12:14] == b'\x00\x00' else 0 # need more info
        kh.channel_mask = 3 if kh.channel_count > 1 else 0
        khead = pack(KTSL2STBIN_ESUBHEADKTSR_STRUCT, *astuple(kh))[:kh.dsp_header_pos] + kd[0] + info_DSP + sizes_DSP + bytes(DSPh_padding)

    return (khead, new)

def combineKS(input_folder: Path, old_file: Path, ktss: bool) -> bytes:
    old_data = old_file.read_bytes() # Read info from old file at this time
    if old_data[:8] != KTSL2ASBIN_ID:
        raise ValueError('This is a KTSL2ASBIN container with unsupported format.')

    if ktss: st_data = splitKtsl2stbin(old_file.with_suffix('.ktsl2stbin'))
    input_files = {f.stem: (f.stem.rsplit('_', 1)[-1], f) for f in input_folder.iterdir()}

    pos = dirtyAlign(old_data, 32, 16)
    data = bytes(pos - 32)
    while pos < len(old_data):
        section_h = KTSL2ASBIN_EHead(*unpack_from(KTSL2ASBIN_EHEAD_STRUCT, old_data, pos))
        section_end = pos + section_h.size
        if section_end == pos: break
        section_data = old_data[pos:section_end]
        if section_h.ID == KTSL2ASBIN_ENTRY_ID:
            if ktss: si = next((i for i, x in enumerate(st_data) if unpack_from('< I', x, 8)[0] == section_h.link_id), 0)
            section_h.get_strings(section_data)
            file_id_matches = [i for i in input_files.items() if i[1][0].isdigit() and i[1][0] == section_h.link_id]
            file_st_matches = [i for i in input_files.items() if i[0] in section_h.strings]
            pos0 = next(x for x in section_h.strings.values())
            if file_id_matches or file_st_matches:
                new_section_data = section_data[8:section_h.pos_offsets]
                new_file_data = b''
                for i, file_string in enumerate(section_h.strings):
                    new_section_data += pack('< I', pos0 + len(new_file_data))
                    # don't use name, hash section is too complicated at this time
                    # st = file_id_matches[0][0].rsplit('_', 1)[0]
                    # st = b'' if st.isdigit() else padIt(st.encode('ascii'), 4)
                    posI = section_h.strings[file_string]
                    kd = dsp2kdata(file_id_matches[0][1][1], section_data, posI, section_h.link_id, ktss) if file_id_matches and i == 0 else \
                        dsp2kdata(next(x[1][1] for x in file_st_matches if x[0] == file_string), section_data, posI, section_h.link_id, ktss) if [x for x in file_st_matches if x[0] == file_string] else \
                        None
                    if not kd:
                        new_file_data = section_data[posI:posI + unpack_from('< I', section_data, posI + 4)[0]]
                    elif ktss and len(kd) > 1:
                        if si: st_data[si] = kd[1]
                        else: st_data.append(kd[1])
                        new_file_data += kd[0]
                    else:
                        new_file_data += b''.join(kd)
                new_section_data += bytes(pos0 - len(new_section_data) - 8) + new_file_data # error if len is bigger, i.e. file count increased
                new_section_data += bytes((16 - (len(new_section_data) + 8) % 16) % 16)
                section_data = KTSL2ASBIN_ENTRY_ID + pack('< I', 8 + len(new_section_data)) + new_section_data
            if ktss:
                ktss_offset = pack('< I', len(b''.join(st_data[:si])) + 64)
                posO = pos0 + unpack_from('< I', section_data, pos0 + 4)[0] - 12
                if ktss_offset != section_data[posO:posO + 4]: section_data = section_data[:posO] + ktss_offset + section_data[posO + 4:]
        data += section_data
        pos = section_end
    if ktss:
        kdat = b''.join(st_data[1:])
        backup(old_file.with_suffix('.ktsl2stbin'))
        old_file.with_suffix('.ktsl2stbin').write_bytes(st_data[0][:24] + (pack('< I', 64 + len(kdat)) * 2) + bytes(SECTION_PADDING) + kdat)
    return old_data[:24] + (pack('< I', 32 + len(data)) * 2) + data

def move2memory(input_file: Path) -> str:
    data = input_file.read_bytes()
    input_file.unlink()
    return data

def VGAudioConvert(input_file: Path, extension: str, arguments=[]) -> Path:
    output_file = input_file.with_suffix(extension)
    backup(output_file)
    subprocess.call([VGAudio, str(input_file), str(output_file)] + arguments, timeout=10)
    return output_file

def convert2dsp(input_file: Path) -> bytes:
    return move2memory(VGAudioConvert(input_file, '.dsp', ['--out-format', 'gcadpcm']))

def convert2ktss(input_file: Path) -> bytes:
    return DSPADPCM_ToKtss(convert2dsp(input_file))

def _extractKS(input_file: Path, output_folder: Path):
    as_file = input_file.with_suffix('.ktsl2asbin')
    if as_file.exists(): input_file = as_file
    extractKS(input_file.read_bytes(), output_folder, input_file.with_suffix('.ktsl2stbin'))

def _combineKS(input_folder: Path, output_file: Path, ktsl2stbin=False):
    data = combineKS(input_folder, output_file, ktsl2stbin)
    backup(output_file)
    output_file.write_bytes(data)

def _convert2wav(input_file: Path) -> Path:
    _ = VGAudioConvert(input_file, '.wav')

def _convert2kns(input_file: Path):
    output_file = input_file.with_suffix('.kns')
    backup(output_file)
    output_file.write_bytes(convert2dsp(input_file))
    # MUA3 uses DSPADPCM, not Opus
    # _ = VGAudioConvert(input_file, '.ktss' (or .kns?), ['--bitrate', '150000', '--CBR', '--opusheader', 'ktss'])

def main():
    parser = ArgumentParser()
    parser.add_argument('input', help='input file (supports glob)')
    parser.add_argument('-s', '--ktsl2stbin', action='store_true', help='combine sound data to separate ktsl2stbin')
    args = parser.parse_args()
    input_files = glob.glob(args.input.replace('[', '[[]'), recursive=True)

    if not input_files:
        raise ValueError('No files found')

    for input_file in input_files:
        input_file = Path(input_file)
        ext = input_file.suffix.casefold()

        if input_file.is_dir():
            _combineKS(input_file, Path(f'{input_file}.ktsl2asbin'), args.ktsl2stbin)
        elif ext == '.ktsl2stbin' or ext == '.ktsl2asbin':
            _extractKS(input_file, input_file.parent / input_file.stem)
        elif ext in ['.ktss', '.kns', '.kvs', '.dsp']:
            _convert2wav(input_file)
        else :
            _convert2kns(input_file)

if __name__ == '__main__':
    main()