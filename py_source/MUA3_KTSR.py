# Koei Tecmo Sound File extractor and combiner for MUA3
# by ak2yny, DeathChaos, HealingBrew, 0Liam, Raytwo, Alex Barney, Hairo R. Carela, KT, SlowpokeVG, vgmstream team, aluigi, RobCat030


import glob, subprocess
from argparse import ArgumentParser
from dataclasses import astuple, dataclass
from pathlib import Path
from struct import calcsize, pack, unpack

from MUA3_Formats import getFileExtension
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
KTSL2ASBIN_ENTRY_ID
size
link_id
int32 0 = Voice; int32 2 = Sound; int16 0 + int16 1 = music
getKtsl2asbinStrings
...
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

KTSL2STBIN_EHEAD_STRUCT = '< 4s4I44x' # 64 - 4 * 5 = 44 is hardcoded at this time
KTSS_HEAD_STRUCT = '< 4sI24xB3sI2B2x4I4x'
DSPADPCM_HEAD_STRUCT = '> 3I2H3I32x14x2H18x'

KTSL2STBIN_EHEAD_SIZE = calcsize(KTSL2STBIN_EHEAD_STRUCT)

@dataclass
class KTSL2STBIN_EHead:
    ID: str
    size: int
    link_id: int
    size_header: str
    file_size: int

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

def reverse_endianness(data: str, s: int) -> str:
    return b''.join([data[x:x + s][::-1] for x in range(0, len(data), s)])

def DSPADPCM_Head_Reverse(data: str, padding: int = 22) -> str:
    return reverse_endianness(data[:12], 4) + reverse_endianness(data[12:16], 2) + reverse_endianness(data[16:28], 4) + reverse_endianness(data[28:74], 2) + bytes(padding)

def parallelize_channels(channels: list, i: int) -> str:
    size = len(max(channels, key=len))
    size += (8 - size) % 8
    channels = [c + bytes(size - len(c)) for c in channels]
    return b''.join(c[p:p + i] for p in range(0, size, i) for c in channels)

def sequentialize_channels(data: str, i: int, channel_count: int) -> list:
    all_sz = len(data)
    ch_sz = all_sz // channel_count
    channels = [b'' for _ in range(channel_count)]
    for p in range(0, all_sz, i * channel_count):
        if i > ch_sz: i = ch_sz
        for c in range(channel_count):
            channels[c] += data[p + i * c:p + i * (c + 1)]
        ch_sz -= i
    return channels

def DSPADPCM_KTS_Convert(data: list, channel_count: int, in_i: int, out_i: int = -1) -> tuple:
    """
    Reverses endianness in header (data[0]) and changes interleave_size (except if -1).
    Returns channels (string if interleved, list otherwise or if unmodified) and headers (string) separately as tuple.
    """
    channel_count = max(channel_count, 1)
    pos = channel_count * 96
    if channel_count == 1 or out_i < 0 or out_i == in_i:
        new_data = data[1:]
        out_i = in_i
    elif in_i == 0:
        new_data = [parallelize_channels(data[1:], out_i * 8)]
    else:
        new_data = sequentialize_channels(data[1], in_i * 8, channel_count)
        if out_i > 0: new_data = [parallelize_channels(new_data, out_i * 8)]
    return (b''.join([DSPADPCM_Head_Reverse(data[0][i * 96:i * 96 + 74], 0) + pack('> 2H18x', 0 if channel_count == 1 else channel_count, 0 if channel_count == 1 else out_i) for i in range(channel_count)]), new_data)

def DSPADPCM_ToKtss(data: str) -> str:
    d = DSPADPCM_Head(*unpack(DSPADPCM_HEAD_STRUCT, data[:calcsize(DSPADPCM_HEAD_STRUCT)]))
    channel_count = min(2, max(d.channel_count, 1))
    if d.channel_count > 2:
        print('Maximum two channels are supported for this game and format (KTSS).')
    kd = DSPADPCM_KTS_Convert(
        [data[:channel_count * 96], data[max(d.channel_count, 1) * 96:]],
        channel_count,
        d.interleave_size_frames, 1) # layer_count = 1?
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
    KTSS = pack(KTSS_HEAD_STRUCT, *astuple(header)) + kd
    return KTSS

def getKtsl2asbinStrings(file_data: str, n=0) -> dict:
    strings = {}
    ID, count, end = unpack('< I4x2I', file_data[8:24])
    p = end
    for i in range(24, 24 + count * 4, 4):
        start = unpack('< I', file_data[i:i + 4])[0]
        strings[file_data[start:end].split(b'\x00', 1)[0].decode("utf-8") if start > 0 else f'{str(n).zfill(4)}_{ID}'] = unpack('< I', file_data[p:p + 4])[0]
        p += 4
    return strings

def splitKtsl2stbin(st_file: Path) -> list:
    s = st_file.read_bytes().split(KTSL2STBIN_ENTRY_ID) if st_file.exists() else []
    return [s[0]] + [KTSL2STBIN_ENTRY_ID + x for x in s[1:]] if s else [KTSL2STBIN_ID + KTSL2_HEAD_DATA + bytes(40)]


def extractNconvert(data: str, output_folder: Path, name: str, wav=False):
    output_file = output_folder / f'{name}.dsp'
    output_file.write_bytes(data)
    if wav: _convert2wav(output_file)

def extractKTSS(data: str, output_folder: Path, name: str):
    layer_count, channel_count = unpack('< 2B', data[40:42])
    kd = DSPADPCM_KTS_Convert(
        [data[64:64 + 96 * channel_count], data[64 + 96 * channel_count:]],
        channel_count,
        layer_count)
    extractNconvert(kd[0] + b''.join(kd[1]), output_folder, name)

def skipKTSRhead(data: str) -> int:
    pos = 32
    while pos < len(data) and data[pos] == 0: pos += 16
    return pos

def extractKS(data: str, output_folder: Path, st_file: Path):
    if data[:8] != KTSL2STBIN_ID and data[:8] != KTSL2ASBIN_ID:
        raise ValueError('This is a KTSL2 container with unsupported format.')

    backup(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    st_data = splitKtsl2stbin(st_file)

    pos = skipKTSRhead(data[:120])
    i = 0
    while pos < len(data):
        k = KTSL2STBIN_EHead(*unpack(KTSL2STBIN_EHEAD_STRUCT, data[pos:pos + KTSL2STBIN_EHEAD_SIZE]))
        section_end = pos + k.size
        if k.ID == KTSL2STBIN_ENTRY_ID: pos += k.size_header
        file_data = data[pos:pos + unpack('< I', data[pos + 4:pos + 8])[0]]
        if file_data[:4] == b'KTSS':
            extractKTSS(file_data, output_folder, f'{str(i).zfill(4)}_{str(k.link_id)}')
            i += 1
        elif file_data[:4] == KTSL2ASBIN_ENTRY_ID:
            file_strings = getKtsl2asbinStrings(file_data, i)
            for file_string in file_strings:
                if st_file.exists():
                    kdat = [x for x in st_data if x[8:12] == file_data[8:12]]
                    if kdat:
                        extractKTSS(kdat[0][unpack('< I', kdat[0][12:16])[0]:], output_folder, file_string)
                        continue
                kdat = file_data[file_strings[file_string]:]
                channel_count, start_header, start_DSP, sizes_DSP = unpack('< I24xI4x2I', kdat[12:56])
                d = sizes_DSP - start_DSP
                kd = DSPADPCM_KTS_Convert(
                    [kdat[start_header:start_header + 96 * channel_count]] + [kdat[unpack('< I', kdat[i:i + 4])[0]:][:unpack('< I', kdat[i + d:i + d + 4])[0]] for i in range(start_DSP, sizes_DSP, 4)],
                    channel_count, 0, BLOCK_SIZE) #  ?
                extractNconvert(kd[0] + b''.join(kd[1]), output_folder, file_string)
            i += 1
        # else:
            # case x if x == KTSL2ASBIN_HASH_ID: don't process at this time
            # case b'\x61\x72\xDB\xA8': Padding
            # case b'\xA9\xD2\x3B\xF1': Unknown info sections
            # return unknown format or corrupted

        pos = section_end

def dsp2kdata(file: Path, old: str, link_id:int, ktss) -> tuple:
    if ktss:
        ktd = DSPADPCM_ToKtss(file.read_bytes()) if file.suffix.casefold() == '.dsp' else convert2ktss(file)
        file_size = len(ktd)
        new = pack(KTSL2STBIN_EHEAD_STRUCT,
            KTSL2STBIN_ENTRY_ID,
            KTSL2STBIN_EHEAD_SIZE + file_size + SECTION_PADDING,
            link_id,
            KTSL2STBIN_EHEAD_SIZE,
            file_size
        )
        new += ktd + bytes(SECTION_PADDING)
        channel_count = unpack('< B', ktd[41:42])[0]
        size = old[4:8]
    else:
        dsp = file.read_bytes() if file.suffix.casefold() == '.dsp' else convert2dsp(file)
        channel_count, interleave_size = unpack('> 2H', dsp[74:78])
        channel_count = max(channel_count, 1)
        kd = DSPADPCM_KTS_Convert(
            [dsp[:channel_count * 96], dsp[channel_count * 96:]],
            channel_count,
            interleave_size, 0)

        if len(kd[1]) == channel_count:
            ksd = kd[1]
        elif len(kd[1]) == 1:
            ch_sz = len(kd[1][0]) // channel_count
            ksd = [kd[1][0][ch_sz * i:ch_sz * (i + 1)] for i in range(channel_count)]
        else:
            raise ValueError(f'{file.name} channels seem to be corrupted.')
        posDSPh = unpack('< I', old[40:44])[0]
        size_DSPh = len(kd[0])
        posDSPh_end = posDSPh + size_DSPh
        posDSPh_end2 = posDSPh_end + 8 * channel_count
        DSPh_padding = (16 - posDSPh_end2) % 16 + 16 # padding seems to depend...
        info_DSP = sizes_DSP = new = b''
        for i in range(channel_count):
            info_DSP += pack('< I', posDSPh_end2 + DSPh_padding + len(new))
            size_Dsp = len(ksd[i])
            sizes_DSP += pack('< I', size_Dsp)
            new += ksd[i] + bytes((16 - size_Dsp) % 16 + 16) # padding seems to depend...
        size = pack('< I', posDSPh_end2 + DSPh_padding + len(new))

    # The struct of the khead is still largely unknown. Copying the values from the old file.
    khead = old[:4] # might need to change depending on ktss, but need more info
    khead += size
    khead += old[8:12] # id
    khead += pack('< I', channel_count)
    khead += old[16:24] if ktss else old[16:20] # ktss 0x76C539C8; Transition Related, should be 4096
    khead += ktd[44:48] if ktss else kd[0][8:12] # sample_rate
    khead += ktd[48:52] if ktss else kd[0][:4] # duration or loop end ?
    khead += ZERO_INT
    khead += ktd[52:56] if ktss else b'\xff\xff\xff\xff' if dsp[12:14] == b'\x00\x00' else ZERO_INT # loop start, need more info for non ktss
    khead += pack('< I', 3) if channel_count > 1 else ZERO_INT # channel_mask (unknown what they are if more than 2)
    if ktss:
        khead += ZERO_INT * 3 # write offset as 0, replace later
        khead += pack('< I', file_size)
        khead += b'\x00\x02\x00\x00'
        # khead += pack('< 12x2I', file_size, 512) ?
    else:
        khead += old[40:44] # posDSPh
        khead += pack('< 3I', size_DSPh, posDSPh_end, posDSPh_end + 4 * channel_count)
        if posDSPh > 56: # This section, usually 4 x int32 is unknown
            khead += old[56:60]
            khead += pack('< 4xI', posDSPh_end2)
            khead += old[68:posDSPh]
        khead += kd[0] + info_DSP + sizes_DSP + bytes(DSPh_padding)

    return (khead, new)

def combineKS(input_folder: Path, old_file: Path, ktss: bool) -> str:
    old_data = old_file.read_bytes() # Read info from old file at this time
    if old_data[:8] != KTSL2ASBIN_ID:
        raise ValueError('This is a KTSL2ASBIN container with unsupported format.')

    if ktss: st_data = splitKtsl2stbin(old_file.with_suffix('.ktsl2stbin'))
    input_files = {f.stem: (f.stem.rsplit('_', 1)[-1], f) for f in input_folder.iterdir()}

    pos = skipKTSRhead(old_data[:120])
    data = bytes(pos - 32)
    while pos < len(old_data):
        section_end = pos + unpack('< I', old_data[pos + 4:pos + 8])[0]
        if section_end == pos: break
        section_data = old_data[pos:section_end]
        if section_data[:4] == KTSL2ASBIN_ENTRY_ID:
            if ktss: si = next((i for i, x in enumerate(st_data) if x[8:12] == section_data[8:12]), None)
            link_id = unpack('< I', section_data[8:12])[0]
            file_strings = getKtsl2asbinStrings(section_data)
            file_id_matches = [i for i in input_files.items() if i[1][0].isdigit() and i[1][0] == link_id]
            file_st_matches = [i for i in input_files.items() if i[0] in file_strings]
            pos0 = next(x for x in file_strings.values())
            if file_id_matches or file_st_matches:
                new_section_data = section_data[8:unpack('< I', section_data[20:24])[0]]
                new_file_data = b''
                for i, file_string in enumerate(file_strings):
                    new_section_data += pack('< I', pos0 + len(new_file_data))
                    # don't use name, hash section is too complicated at this time
                    # st = file_id_matches[0][0].rsplit('_', 1)[0]
                    # st = b'' if st.isdigit() else padIt(st.encode('ascii'), 4)
                    posI = file_strings[file_string]
                    kd = dsp2kdata(file_id_matches[0][1][1], section_data[posI:], link_id, ktss) if file_id_matches and i == 0 else dsp2kdata(next(x[1][1] for x in file_st_matches if x[0] == file_string), section_data[posI:], link_id, ktss) if [x for x in file_st_matches if x[0] == file_string] else [section_data[posI:posI + unpack('< I', section_data[posI + 4:posI + 8])[0]]]
                    if ktss and len(kd) > 1:
                        if si: st_data[si] = kd[1]
                        else: st_data += kd[1]
                        new_file_data += kd[0]
                    else:
                        new_file_data += b''.join(kd)
                new_section_data += bytes(pos0 - len(new_section_data) - 8) + new_file_data # error if len is bigger, i.e. file count increased
                new_section_data += bytes((16 - (len(new_section_data) + 8) % 16) % 16)
                section_data = KTSL2ASBIN_ENTRY_ID + pack('< I', 8 + len(new_section_data)) + new_section_data
            if ktss:
                ktss_offset = pack('< I', len(b''.join(st_data[:si])) + 64)
                posO = pos0 + unpack('< I', section_data[pos0 + 4:pos0 + 8])[0] - 12
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

def convert2dsp(input_file: Path) -> str:
    return move2memory(VGAudioConvert(input_file, '.dsp', ['--out-format', 'gcadpcm']))

def convert2ktss(input_file: Path) -> str:
    return DSPADPCM_ToKtss(convert2dsp(input_file))

def _extractKS(input_file: Path, output_folder: Path):
    as_file = input_file.with_suffix('.ktsl2asbin')
    if as_file.exists(): input_file = as_file
    extractKS(input_file.read_bytes(), output_folder, input_file.with_suffix('.ktsl2stbin'))

def _combineKSS(input_folder: Path, output_file: Path):
    backup(output_file)
    output_file.write_bytes(combineKSS(input_folder))

def _combineKSA(input_folder: Path, output_file: Path):
    data = combineKSA(input_folder, output_file)
    backup(output_file)
    output_file.write_bytes(data)

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
    # _ = VGAudioConvert(input_file, '.ktss', ['--bitrate', '150000', '--CBR', '--opusheader', 'ktss'])

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
        elif ext == '.ktss' or ext == '.kns' or ext == '.kvs' or ext == '.dsp':
            _convert2wav(input_file)
        else :
            _convert2kns(input_file)

if __name__ == '__main__':
    main()