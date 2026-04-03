from tkinter import *
from customtkinter import *
from dataclasses import dataclass
#from configparser import ConfigParser
#from os import startfile
from pathlib import Path
#from sys import executable
from struct import Struct

set_default_color_theme('green')


MAX_CHAR_INDEX = 2035
CHARACTER_NAMES = {
    int(''.join(l[:8].split(' ')[::-1]), 16): l[10:]
        for l in Path('DataCharacter.Bin IDs.txt').read_text().split('\n')
    }

CHARACTERDATA_STRUCT = Struct('<'
    'I'
    '4H'
    '9I'
    '2B'
    '2x'
)


class NumberStrVar(StringVar):
    '''An entry widget that only accepts digits (positive numbers) with an optional upper limit'''
    def __init__(self, upper_limit=0xFFFFFFFF, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.upper_limit = upper_limit
        self.trace_add('write', self.validate)
    def validate(self, *args):
        value = self.get()
        if value and not value.isdigit():
            self.set(0)
        elif value and int(value) > self.upper_limit:
            self.set(self.upper_limit)

@dataclass
class CharacterData:
    ID: int
    Number: int
    Unk_Enum1: int # 0-12; if SubsetNumber % 10 == 0: 0, 6, 8-12 (else 0-4, 6-7; except DLC has own pattern)
    Unk_Enum2: int # 0-4
    SubsetNumber: int #{Number}0-4
    Value5: int # 100 (1-400, often 55, esp chars @0xf970 & NPC)
    Value6: int # 100 (10-500+, seemingly same exceptions as 5)
    Value7: int # 100 (10-500, identical to 6 with few exceptions)
    Value8: int # 100 (+ 1 * 10)
    Value9: int # 100
    Value10: int# 100 (0-100)
    Value11: int# 200/500 (0-500, NPCs often 15)
    Value12: int# 100 (0-2500, 500 steps, few 50 st., seemingly same exceptions as 5)
    Value13: int# 10(/50/250) (0-250)
    Unk_Enum3: int # 0-9, 16 (0, some 1, few other)
    Unk: bool


class App(CTk):
    def __init__(self, title):
        super().__init__()
        self.title(title)
        self.iconbitmap(Path(__file__).parent.parent / 'MUA3_Mods.ico')
        #self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.input_file_name = StringVar()
        self.character_index = NumberStrVar(value=0, upper_limit=MAX_CHAR_INDEX)
        self.character_name = StringVar()
        #self.character_number = StringVar()
        self.temporary_number = StringVar()
        self.value2 = StringVar()
        self.value3 = StringVar()
        self.value4 = StringVar()
        self.value5 = StringVar()
        self.value6 = StringVar()
        self.value7 = StringVar()
        self.value8 = StringVar()
        self.value9 = StringVar()
        self.value10 = StringVar()
        self.value11 = StringVar()
        self.value12 = StringVar()
        self.value13 = StringVar()
        self.value14 = StringVar()
        self.value15 = BooleanVar()
        self.data = None
        self.temporary_number.trace_add('write', self.temporary_number_changed)

        top = CTkFrame(self, corner_radius=0)
        top.pack(fill=X)
        middle = CTkFrame(self, corner_radius=0)
        middle.pack(fill=X)
        bottom = CTkFrame(self, corner_radius=0)
        bottom.pack(fill=X)

        _ = CTkButton(
            top,
            text='Open CharData',
            command=self.pick_file
        ).pack(side=LEFT, padx=10, pady=10)
        _ = CTkLabel(
            top,
            text='Character index:'
        ).pack(side=LEFT, padx=(0, 10), pady=10)
        _ = CTkEntry(
            top,
            textvariable=self.character_index,
            width=48
        ).pack(side=LEFT, padx=0, pady=10)
        _ = CTkButton(
            top,
            text='Get data',
            command=self.character_index_changed
        ).pack(side=LEFT, padx=10, pady=10)

        #for i in range(4):
        #    self.grid_columnconfigure(i, weight=1)
        #self.grid_rowconfigure(1, weight=1)
        #self.grid_rowconfigure(2, weight=1)
        #self.grid_rowconfigure(3, weight=1)
        _ = CTkLabel(
            middle,
            font=('ROG Fonts', 18),
            textvariable=self.character_name
        ).grid(row=0, column=0, columnspan=4, padx=10, pady=10)
        _ = CTkEntry(
            middle,
            state=DISABLED,
            textvariable=self.value4,
            width=60
        ).grid(row=1, column=0, padx=10, pady=10)
        _ = CTkEntry(
            middle,
            textvariable=self.temporary_number,
            width=60
        ).grid(row=1, column=1, padx=0, pady=10)
        _ = CTkEntry(
            middle,
            textvariable=self.value3,
            width=60
        ).grid(row=1, column=2, padx=10, pady=10)
        _ = CTkEntry(
            middle,
            textvariable=self.value2,
            width=60
        ).grid(row=1, column=3, padx=(0, 10), pady=10)
        _ = CTkEntry(
            middle,
            textvariable=self.value5,
            width=60
        ).grid(row=2, column=0, padx=10, pady=10)
        _ = CTkEntry(
            middle,
            textvariable=self.value6,
            width=60
        ).grid(row=2, column=1, padx=0, pady=10)
        _ = CTkEntry(
            middle,
            textvariable=self.value7,
            width=60
        ).grid(row=2, column=2, padx=10, pady=10)
        _ = CTkEntry(
            middle,
            textvariable=self.value8,
            width=60
        ).grid(row=2, column=3, padx=(0, 10), pady=10)
        _ = CTkEntry(
            middle,
            textvariable=self.value9,
            width=60
        ).grid(row=3, column=0, padx=10, pady=10)
        _ = CTkEntry(
            middle,
            textvariable=self.value10,
            width=60
        ).grid(row=3, column=1, padx=0, pady=10)
        _ = CTkEntry(
            middle,
            textvariable=self.value11,
            width=60
        ).grid(row=3, column=2, padx=10, pady=10)
        _ = CTkEntry(
            middle,
            textvariable=self.value12,
            width=60
        ).grid(row=3, column=3, padx=(0, 10), pady=10)
        _ = CTkEntry(
            middle,
            textvariable=self.value12,
            width=60
        ).grid(row=4, column=0, padx=10, pady=10)
        _ = CTkEntry(
            middle,
            textvariable=self.value12,
            width=60
        ).grid(row=4, column=1, padx=0, pady=10)
        _ = CTkCheckBox(middle,
            text='',
            #command=checkbox_event,
            variable=self.value15,
            width=60
            #onvalue=True,
            #offvalue=False
        ).grid(row=4, column=2, padx=10, pady=10)

        _ = CTkOptionMenu(
            bottom,
            values=['System', 'Light', 'Dark'],
            #variable=self.current_theme,
            command=set_appearance_mode
        ).pack(side=RIGHT, padx=10, pady=10)
        _ = CTkLabel(
            bottom,
            text='Change theme:'
        ).pack(side=RIGHT, padx=10, pady=10)

        #self.character_index.trace_add('write', self.character_index_changed)
        #self.character_index.set('0')
        #self.current_theme.set(theme := CONFIG.get('THEME', 'System'))
        #if theme != 'System': set_appearance_mode(theme)

    def pick_file(self):
        self.data = Path(filedialog.askopenfilename()).read_bytes()

    def character_index_changed(self):
        if not self.data: return
        offset = int(self.character_index.get()) * 4 * 13
        cd = CharacterData(*CHARACTERDATA_STRUCT.unpack_from(self.data, offset))
        self.character_name.set(f'{CHARACTER_NAMES.get(cd.ID, f'Unknown 0x{cd.ID:X}')}  #{cd.Number:04}')
        #self.character_number.set(f'{}  #{cd.Number:04}')
        self.temporary_number.set(cd.SubsetNumber % 10)
        self.value2.set(cd.Unk_Enum1)
        self.value3.set(cd.Unk_Enum2)
        self.value4.set(cd.SubsetNumber)
        self.value5.set(cd.Value5)
        self.value6.set(cd.Value6)
        self.value7.set(cd.Value7)
        self.value8.set(cd.Value8)
        self.value9.set(cd.Value9)
        self.value10.set(cd.Value10)
        self.value11.set(cd.Value11)
        self.value12.set(cd.Value12)
        self.value13.set(cd.Value13)
        self.value14.set(cd.Unk_Enum3)
        self.value15.set(cd.Unk)

    def temporary_number_changed(self, *args):
        new = self.temporary_number.get()
        if not new: return
        new = int(new) if new.isdigit() else 0
        if new > 9: new = 9
        val = self.value4.get()
        val = int(val) if val else 0
        self.value4.set(val - ((val % 10) - new))
        self.temporary_number.set(new)

    #def on_closing(self):
    #    self.save_settings()
    #    self.destroy()

if __name__ == '__main__':
    app = App('MUA3 DataCharacter Editor')
    app.mainloop()