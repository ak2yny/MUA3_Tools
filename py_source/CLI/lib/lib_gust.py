from dataclasses import dataclass


# =================================================================
# Gust headers
# =================================================================

III_STRUCT = '3I'

@dataclass
class GResourceHeader:
    magic: int|str
    chunkVersion: int
    chunkSize: int


# =================================================================
# Endian Functions
# =================================================================

E = '<' # ENDIAN_SYMBOL (little), Note: Conflicts with Tkinter's E from NSWE variables, but not using interface at this time

def e_to_big(isBigEndian: bool = True):
    global E
    E = '>' if isBigEndian else '<'

def force_little(sz:int, *le: int):
    return le if E == '<' else [int.from_bytes(x.to_bytes(sz, 'little'), 'big') for x in le]

# =================================================================
# Utility Functions
# =================================================================

def dirtyAlign(data: str, pos: int, sz: int) -> int:
    zb = bytes(sz)
    tsz = len(data)
    while pos < tsz and data[pos:pos + sz] == zb: pos += sz
    return pos