from tkinter import *
from ast import literal_eval
from collections.abc import Callable
from customtkinter import *
from dataclasses import dataclass
from enum import auto, IntFlag
#from configparser import ConfigParser
#from os import startfile
from pathlib import Path
from re import compile as regex_compile
#from sys import executable
from struct import Struct

set_default_color_theme('green')


# --- widgets ---

class NumberStrVar(StringVar):
    '''An entry widget that only accepts floats with an optional upper limit.'''
    def __init__(self, upper_limit=0x7FFFFFFF, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.upper_limit = upper_limit
        self.is_float = False
        self.trace_add('write', self.validate)
    def validate(self, *args):
        value = self.get()
        try:
            if float(value) > self.upper_limit:
                self.set(self.upper_limit)
        except:
            self.set(0)
    def reset(self):
        self.set(0)
    def set_int(self, value: int, is_float: bool):
        self.is_float = is_float
        if is_float: value /= 10
        self.set(value)
    def get_int(self):
        try:
            return int(float(self.get()) * 10) if self.is_float else int(self.get())
        except:
            return 0

# https://github.com/Akascape/CTkListbox (with significant changes)
class CTkListboxOld(CTkScrollableFrame):
    def __init__(
        self,
        master: any,
        height: int = 100,
        width: int = 150,
        highlight_color: str = 'default',
        fg_color: str|tuple[str, str] = 'transparent',
        bg_color: str|tuple[str, str] = 'transparent',
        text_color: str|tuple[str, str]|None = None,
        hover_color: str|tuple[str, str]|None = None,
        button_color: str|tuple[str, str] = 'transparent',
        border_width: int = 3,
        font: tuple|None = None,
        multiple_selection: bool = False,
        listvariable: StringVar|None = None,
        hover: bool = True,
        command: Callable|None = None,
        wraplength: int = 0,
        justify: str = 'left',
        **kwargs,
        ):
        '''
        Usage with listvariable:
            items = [] < populated list
            var = StringVar()
            var.set(items)
            listbox = CtkListbox(..., listvariable=var)
            changed_items = ['other item1']
            var.set(changed_items)
        '''
        # possible improvements for this app: remove multiple selection, remove move, remove listvariable, remove bindings

        super().__init__(
            master,
            width=width,
            height=height,
            fg_color=fg_color,
            bg_color=bg_color,
            border_width=border_width,
            **kwargs,
        )
        self.buttons = {}
        self.bindings = {}
        self._scrollbar.grid_configure(padx=(0, border_width + 4))
        self._scrollbar.configure(width=12)
        self.select_color = (
            highlight_color or ThemeManager.theme['CTkButton']['fg_color']
        )
        self.text_color = (
            text_color or ThemeManager.theme['CTkLabel']['text_color']
        )
        self.hover_color = (
            hover_color or ThemeManager.theme['CTkButton']['hover_color']
        )
        self.font = (
            font
                if isinstance(font, CTkFont) else
            CTkFont(*font)
                if isinstance(font, tuple) else
            CTkFont(ThemeManager.theme['CTkFont']['family'], 13)
        )
        self.button_fg_color = button_color
        self.justify = (
            'w' if justify == 'left' else
            'e' if justify == 'right' else
            'c'
        )
        self.command = command
        self.multiple = multiple_selection
        self.selected = None
        self.hover = hover
        self.count = 0
        self.selections = [] # for multiple only
        self.selected_index = 0
        self.wraplength = wraplength
        self._scrollbar.configure(height=height)
        self.columnconfigure(0, weight=1)

        if listvariable:
            self.listvariable = listvariable
            self.listvariable.trace_add('write', lambda a, b, c: self.update_listvar())
            self.update_listvar()

    def update_listvar(self):
        values = list(literal_eval(self.listvariable.get()))
        self.delete_all()
        for v in values:
            self.append(v, False)
        self.update() # WIP: Does it work if only update at the end?

    #def select_all(self, index: int):
    #    '''select all options'''
    #    if self.multiple:
    #        for button in self.buttons.values():
    #            button.configure(fg_color=self.select_color, hover=False)
    #            if button not in self.selections:
    #                self.selections.append(button)

    def select(self, index: int):
        '''select the option'''
        selected_button = self.buttons[index] if index in self.buttons else list(self.buttons.values())[index] # WIP: change to list?

        if self.multiple:
            if selected_button in self.selections:
                self.selections.remove(selected_button)
                selected_button.configure(fg_color=self.button_fg_color, hover=False)
                self.after(100, lambda: selected_button.configure(hover=self.hover))
            else:
                self.selections.append(selected_button)
            for selected_button in self.selections:
                selected_button.configure(fg_color=self.select_color, hover=False)
                self.after(100, lambda button=selected_button: button.configure(hover=self.hover))
        else:
            if self.selected:
                self.selected.configure(fg_color=self.button_fg_color)
            self.selected = selected_button
            selected_button.configure(fg_color=self.select_color, hover=False)
            self.after(100, lambda: selected_button.configure(hover=self.hover))

        if self.command:
            self.command(self.get())

        self.event_generate('<<ListboxSelect>>')

    # WIP: Remove if possible
    #def activate(self, index):
    #    if str(index).lower() == 'all':
    #        if self.multiple:
    #            for i in self.buttons:
    #                self.select(i)
    #        return
    #
    #    if str(index).lower() == 'end':
    #        index = -1
    #
    #    self.select(list(self.buttons.keys())[index])

    @property
    def selected_indices(self) -> list:
        if self.multiple:
            index = 0
            indexes = []
            for i in self.buttons.values():
                if i in self.selections:
                    indexes.append(index)
                index += 1
            return indexes
        elif self.selected:
            for i, v in enumerate(self.buttons.values()):
                if v == self.selected:
                    return [i]
        return []

    def bind(self, key, func, add='+'):
        super().bind(key, lambda e: func(e), add=add)
        self._parent_frame.bind(key, lambda e: func(e), add=add)
        self._parent_canvas.bind(key, lambda e: func(e), add=add)
        for button in self.buttons.values():
            button.bind(key, lambda e: func(e), add=add)

        if key not in self.bindings:
            self.bindings[key] = []
        self.bindings[key].append((func, add))

    def unbind(self, key):
        super().unbind(key)
        self._parent_frame.unbind(key)
        self._parent_canvas.unbind(key)
        for button in self.buttons.values():
            button.unbind(key)

        if key in self.bindings:
            del self.bindings[key]

    def deselect_all(self): # WIP:
        if self.multiple:
            for i in self.buttons:
                self.deselect(i)
        elif self.selected:
            self.deselect(0)

    def deselect(self, index: int):
        if self.multiple:
            option = self.buttons.get(index)
            if option and option in self.selections:
                option.configure(fg_color=self.button_fg_color)
                self.selections.remove(option)
        elif self.selected:
            self.selected.configure(fg_color=self.button_fg_color)
            self.selected = None

    # WIP: Remove if possible
    #def deactivate(self, index):
    #    if str(index).lower() == 'all':
    #        if self.multiple:
    #            for i in self.buttons:
    #                self.deselect(i)
    #        elif self.selected:
    #            self.deselect(0)
    #        return
    #
    #    if str(index).lower() == 'end':
    #        index = -1
    #
    #    selected = list(self.buttons.keys())[index]
    #    self.deselect(selected)

    def append(self, option: str, update: bool = True):
        '''Append new option in the listbox.'''
        self.insert(-1, option, update)

    def insert(self, index: int, option: str, update: bool = True, **args):
        '''Add new option in the listbox at index. If index is negative or bigger than count, adds at the end.'''

        if index < 0 or index > self.count:
            index = self.count
            self.count += 1
        elif index in self.buttons:
            self.buttons[index].destroy()

        list_item = CTkButton(
            self,
            text=option,
            fg_color=self.button_fg_color,
            anchor=self.justify,
            text_color=self.text_color,
            font=self.font,
            hover_color=self.hover_color,
            **args,
        )
        list_item.configure(command=lambda num=index: self.select(num))
        list_item._text_label.config(anchor='w')
        if self.wraplength:
           list_item._text_label.config(wraplength=self.wraplength)

        list_item.grid(padx=0, pady=(0, 5), sticky='nsew', column=0, row=index)
        # WIP: if append? list_item.grid(padx=0, pady=(0, 5), sticky='nsew', column=0)
        self.buttons[index] = list_item

        if update:
            self.update()

        if self.multiple:
            list_item.bind(
                '<Shift-1>', lambda e: self.select_multiple(self.buttons[index])
            )

        # Apply stored bindings to the new button
        for key, funcs in self.bindings.items():
            for func, add in funcs:
                list_item.bind(key, lambda e, f=func: f(e), add=add)

        #return list_item

    def select_multiple(self, button):
        selections = list(self.buttons.values())
        if len(self.selections) > 0:
            last = selections.index(self.selections[-1])
            to = selections.index(button)

            if last < to:
                for i in range(last + 1, to + 1):
                    if list(self.buttons.values())[i] not in self.selections:
                        self.select(i)
            else:
                for i in range(to, last):
                    if list(self.buttons.values())[i] not in self.selections:
                        self.select(i)

    def destroy(self):
        for option in self.buttons.values():
            option.destroy()
        self._scrollbar.destroy()
        super().destroy()

        self._parent_frame.destroy()
        self._parent_canvas.destroy()

    def delete_all(self):
        '''delete all options from the listbox'''
        for option in self.buttons.values():
            option.destroy()
            self.update() # WIP: needed every time?
        self.buttons = {}
        self.selected = None
        self.selections.clear()
        self.count = 0

    def delete(self, index: int, to_index: int = 0):
        '''Delete option from the listbox, from index to to_index. If to_index is specified, it must be bigger than index.'''
        actual_count = self.size() # WIP
        if self.count == 0 or actual_count == 0 or index not in self.buttons: # WIP
            return
        # WIP:
        #if index >= actual_count:
        #    return
        if index == -1:
            self.count -= 1
            to_index = 0
        if not to_index:
            index = list(self.buttons.keys())[index]

        if to_index:
            if to_index == -1 or to_index > actual_count:
                to_index = actual_count
            else:
                to_index += 1
            indices = list(self.buttons.keys())   # WIP
            options = list(self.buttons.values()) # WIP
            for i in range(index, to_index):
                options[i].destroy()
                del self.buttons[indices[i]]
                self.update() # WIP: needed every time?
        else:
            self.buttons[index].destroy()
            if self.multiple:
                if self.buttons[index] in self.selections:
                    self.selections.remove(self.buttons[index])
            del self.buttons[index]
        
    def size(self): # WIP
        '''return total number of items in the listbox'''
        return len(self.buttons.keys())

    def see(self, index: int):
        '''Move the frame to the specific button position, placing it at the top.'''
        if index < -1:
            return
        elif index >= self.size():
            self._scrollbar._command('moveto', 1.0)
            return
        elif index in self.buttons: # WIP
            button = self.buttons[index]
        else:
            button = list(self.buttons.values())[index]

        button_y = button.winfo_y()
        scroll_region = self._parent_canvas.bbox('all')
        if scroll_region:
            scroll_height = scroll_region[3]
            self._parent_canvas.yview_moveto(button_y / scroll_height)

    def get_all(self) -> list:
        '''Get all values'''
        return [item.cget('text') for item in self.buttons.values()]

    def get(self, index: int|None = None) -> list:
        '''Get the selected value'''
        if index is None:
            return (
                [x.cget('text') for x in self.selections]
                    if self.multiple else
                [] if not self.selected else [self.selected.cget('text')]
            )
        else:
            index = list(self.buttons.keys())[index] # WIP
            return [self.buttons[index].cget('text')]

    def configure(self, **kwargs):
        '''configurable options of the listbox'''
        if 'command' in kwargs:
            self.command = kwargs.pop('command')
        if 'height' in kwargs:
            self._scrollbar.configure(height=kwargs['height'])
        if 'multiple_selection' in kwargs:
            self.multiple = kwargs.pop('multiple_selection')
        if 'highlight_color' in kwargs:
            self.select_color = kwargs.pop('highlight_color')
            if self.selected:
                self.selected.configure(fg_color=self.select_color)
            elif len(self.selections) > 0:
                for v in self.selections:
                    v.configure(fg_color=self.select_color)
        button_configs = {}
        if 'button_color' in kwargs:
            # WIP: Also changes fg of selected...
            self.button_fg_color = kwargs.pop('button_color')
            button_configs['fg_color': self.button_fg_color]
        if 'hover_color' in kwargs:
            self.hover_color = kwargs.pop('hover_color')
            button_configs['hover_color': self.hover_color]
        if 'text_color' in kwargs:
            self.text_color = kwargs.pop('text_color')
            button_configs['text_color': self.text_color]
        if 'font' in kwargs:
            self.font = kwargs.pop('font')
            button_configs['font': self.font]
        if 'hover' in kwargs:
            self.hover = kwargs.pop('hover')
            button_configs['hover': self.hover]
        if 'justify' in kwargs:
            justify = kwargs.pop('justify')
            self.justify = (
                'w' if justify == 'left' else
                'e' if justify == 'right' else
                'c'
            )
            button_configs['anchor': self.justify]
        if button_configs:
            for v in self.buttons.values():
                v.configure(**button_configs)
        if kwargs:
            super().configure(**kwargs)

    def cget(self, param):
        if param == 'hover_color':
            return self.hover_color
        if param == 'button_color':
            return self.button_fg_color
        if param == 'highlight_color':
            return self.select_color
        if param == 'text_color':
            return self.text_color
        if param == 'font':
            return self.font
        if param == 'hover':
            return self.hover
        if param == 'justify':
            return self.justify
        return super().cget(param)

    def move_up(self, index: int):
        '''Move the option one up in the listbox'''
        if index < 1: return
        self.swap_options(index, index - 1, -1)

    def move_down(self, index):
        '''Move the option one down in the listbox'''
        if index >= self.size() - 1: return
        self.swap_options(index, index + 1, 1)

    def swap_options(self, old_index: int, new_index: int, scroll_multplier: int = 0):
        '''Swap the option from old_index with the one from new_index'''
        # WIP
        index_to_key = list(self.buttons.keys())
        old_key = index_to_key[old_index]
        new_key = index_to_key[new_index]

        old_text = self.buttons[old_key].cget('text')
        self.buttons[old_key].configure(
            text=self.buttons[new_key].cget('text')
        )
        self.buttons[new_key].configure(text=old_text)

        self.deselect(old_key)
        self.select(new_key)

        # Update the scrollbar position
        if scroll_multplier and self._parent_canvas.yview() != (0.0, 1.0):
            self._parent_canvas.yview('scroll', 100 // 6 * scroll_multplier, 'units')

# https://github.com/Akascape/CTkListbox (with significant changes, still inefficient)
class CTkListbox(CTkScrollableFrame):
    def __init__(
        self,
        master: any,
        height: int = 100,
        width: int = 150,
        font: tuple|None = None,
        command: Callable|None = None,
        **kwargs,
        ):
        self.items = []
        self.bindings = {}

        # possible improvements for this app: remove multiple selection, remove move, remove listvariable, remove bindings
        super().__init__(
            master,
            width=width,
            height=height,
            border_width=3,
            **kwargs,
        )
        self._scrollbar.grid_configure(padx=(0, 7)) # scrollbar width = 4 (+border_width)
        self._scrollbar.configure(height=height, width=16)

        self.select_color = ThemeManager.theme['CTkButton']['fg_color']
        self.font = (
            font
                if isinstance(font, CTkFont) else
            CTkFont(*font)
                if isinstance(font, tuple) else
            CTkFont(ThemeManager.theme['CTkFont']['family'], 13)
        )
        self.command = command
        self.selected = None
        self.columnconfigure(0, weight=1)

    def select(self, index: int):
        '''select the option by index'''
        if index < -1 or self.count == 0: return
        self._select(self.items[min(index, self.count - 1)])

    def _select(self, selected_button: CTkButton):
        '''select the button'''
        if self.selected:
            self.selected.configure(fg_color='transparent')
        self.selected = selected_button
        selected_button.configure(fg_color=self.select_color, hover=False)
        self.after(100, lambda: selected_button.configure(hover=True))

        if self.command:
            self.command(self.get())

        self.event_generate('<<ListboxSelect>>')

    @property
    def count(self) -> int:
        return len(self.items)

    @property
    def selected_index(self) -> int:
        if self.selected:
            for i, list_item in enumerate(self.items):
                if list_item == self.selected:
                    return i
        return -1

    def bind(self, key, func, add='+'):
        super().bind(key, lambda e: func(e), add=add)
        self._parent_frame.bind(key, lambda e: func(e), add=add)
        self._parent_canvas.bind(key, lambda e: func(e), add=add)
        for list_item in self.items:
            list_item.bind(key, lambda e: func(e), add=add)

        if key not in self.bindings:
            self.bindings[key] = []
        self.bindings[key].append((func, add))

    def unbind(self, key):
        super().unbind(key)
        self._parent_frame.unbind(key)
        self._parent_canvas.unbind(key)
        for list_item in self.items:
            list_item.unbind(key)

        if key in self.bindings:
            del self.bindings[key]

    def deselect(self):
        if self.selected:
            self.selected.configure(fg_color='transparent')
            self.selected = None

    def append(self, option):
        '''Append new option in the listbox.'''
        self.insert(-1, option)

    def insert(self, index: int, option, **args):
        '''Add new option in the listbox at index. If index is negative or bigger than count, adds at the end.'''
        count = self.count
        if index < 0 or index > count:
            index = count

        list_item = CTkButton(
            self,
            text=str(option),
            fg_color='transparent',
            anchor='w',
            font=self.font,
            **args,
        )
        list_item._text_label.config(anchor='w')
        list_item.configure(command=lambda: self._select(list_item))

        # Apply stored bindings to the new button
        for key, funcs in self.bindings.items():
            for func, add in funcs:
                list_item.bind(key, lambda e, f=func: f(e), add=add)
        list_item.pack(fill = BOTH, expand = True, padx=0, pady=(0, 5))

        if index != count:
            for li in self.items[index:]:
                li.pack_forget()
                li.pack(fill = BOTH, expand = True, padx=0, pady=(0, 5))

        self.items.insert(index, list_item)
        #return list_item

    def _remove(self, list_item: CTkButton):
        if self.selected == list_item:
            self.selected = None
        self.items.remove(list_item)
        list_item.pack_forget()
        list_item.destroy()

    def delete_all(self):
        '''delete all options from the listbox'''
        for list_item in self.items:
            list_item.pack_forget()
            list_item.destroy()
        self.items.clear()
        self.selected = None

    def delete(self, index: int, to_index: int = 0):
        '''Delete options from the listbox, from index to to_index. If to_index is specified, it must be bigger than index (or -1).'''
        count = self.count
        if count == 0 or index < -1 or index >= count:
            return
        if index > -1 and to_index:
            if to_index == -1 or to_index > count:
                to_index = count
            else:
                to_index += 1
            for list_item in self.items[index:to_index]:
                self._remove(list_item)
        else:
            self._remove(self.items[index])

    def destroy(self):
        self.delete_all()
        super().destroy()
        self._scrollbar.destroy()
        self._parent_frame.destroy()
        self._parent_canvas.destroy()

    def see(self, index: int):
        '''Move the frame to the specific button position, placing it at the top.'''
        if index < -1:
            return
        elif index == -1 or index >= self.count:
            self._scrollbar._command('moveto', 1.0)
            return

        list_item = self.items[index]
        y = list_item.winfo_y()
        scroll_region = self._parent_canvas.bbox('all')
        if scroll_region:
            scroll_height = scroll_region[3]
            self._parent_canvas.yview_moveto(y / scroll_height)

    def get(self, index: int|None = None) -> str|None:
        '''Get the selected values'''
        if index is None:
            return self.selected.cget('text') if self.selected else None
        else:
            try:
                return self.items[index].cget('text')
            except:
                return None

class ISO8SpecialBonusEditor(CTkFrame):
    def __init__(self, master, specialbonuses: list, buff_icons: dict, **kwargs):
        # fg_color='transparent' makes the frame blend into the background
        super().__init__(master, **kwargs)
        self.widgets = []
        CTkLabel(self, text='').pack(side=LEFT, padx=5)
        _ = CTkOptionMenu(
            self,
            dynamic_resizing=False,
            values=specialbonuses,
            command=self._change_bonus
        ).pack(side=RIGHT, padx=5, pady=5)
        CTkLabel(self, text='').pack(side=RIGHT, padx=5)
        self.buff_icons = buff_icons
        self.arguments = {'#arg1#': NumberStrVar(), '#arg2#': NumberStrVar()}

    def _change_bonus(self, specialbonus: str):
        self.load(specialbonus, 0, 0, -1)

    def load(self, specialbonus: str, arg1: int, arg2: int, specialbonus_index: int):
        for w in self.widgets:
            w.pack_forget()
            w.destroy()
        self.widgets.clear()
        for a in self.arguments.values(): a.reset()
        self.specialbonus_index = specialbonus_index

        # Tokenize the string. 
        tokens = FORMAT_REGEX.split(specialbonus)
        token_count = len(tokens)

        current_colour = None
        current_text = [tokens[0]]
        arg_values = {'#arg1#': arg1, '#arg2#': arg2}

        for i in range(1, token_count, 2):
            tokn = tokens[i]
            text = tokens[i + 1]
            match tokn:
                case '%%':
                    current_text.append('%' + text)
                case '#arg1#' | '#arg2#':
                    self._add_label(''.join(current_text), current_colour)
                    self._add_entry(tokn, arg_values[tokn], tokens[i + 2] == '%%')
                    current_text = [text]
                case _:
                    typ = text[0]
                    tag, text = text[2:].split('~')
                    self._add_label(''.join(current_text), current_colour)
                    if typ in ('1', '2'):
                        current_colour = FORMAT_COLOURS[tag]
                    elif (icon := self.buff_icons.get(tag)):
                        label = CTkLabel(self, text='', image=icon)
                        label.pack(side=LEFT)
                        self.widgets.append(label)
                    else:
                        text = f'[{tag}]{text}'
                    current_text = [text]
        self._add_label(''.join(current_text), current_colour)

    def _add_label(self, text: str, color: tuple|None):
        if text:
            label = CTkLabel(self, text=text, text_color=color)
            label.pack(side=LEFT)
            self.widgets.append(label)

    def _add_entry(self, arg_tag: str, arg_val: int, is_percent: bool):
        arg_var = self.arguments[arg_tag]
        arg_var.set_int(arg_val, is_percent)
        arg = CTkEntry(self, justify=RIGHT, textvariable=arg_var, width=50)
        arg.pack(side=LEFT)
        self.widgets.append(arg)

    def get_values(self) -> tuple:
        if not self.widgets:
            return -1, 0, 0
        arg1 = self.arguments['#arg1#'].get_int()
        arg2 = self.arguments['#arg2#'].get_int()
        return self.specialbonus_index, arg1, arg2

    def get_values_new(self, specialbonuses: list) -> tuple:
        if not self.widgets:
            return -1, 0, 0
        arg1 = self.arguments['#arg1#'].get_int()
        arg2 = self.arguments['#arg2#'].get_int()
        return self.specialbonus_index, arg1, arg2


# --- MUA3 Save Classes ---

@dataclass
class SaveFileHeader: # 8I or 2I3Q
    magic: int #0
    content_count: int # 2
    size: int # size - 0xB90 (or offset to something that's 0xB90 long, but they're all zeroes)
    unknown1: int
    unknown2: int
    unknown3: int
    offset1: int # player 1?
    unknown4: int
    # 0x70 * B # flags?
    # content_count * SaveHeader

@dataclass
class SaveHeader: # 8I
    unknown0: int
    unknown1: int
    unknown2: int
    unknown3: int
    unknown4: int
    unknown_id: int # 1
    size: int # 0x5be00 bytes
    unknown7: int
    # 90   * unknown struct (0x1c0 bytes = 0x9d80)
    #   0x30 * B # unknown
    #   12   * I # unknown counts
    #   8    * I # unknown counts and/or sizes
    #   0x140* B # unknown
    # 0x9e30
    # 1500 * ISO8 (838 used)
    # 31   * unknown iso8 struct (0x60 bytes = 0xba0), starting with hash, mostly all 0
    # 0x2dc50
    # 600  * unknown struct (0x40 bytes = 0x9600), starting with I (?) / only 11 used
    # 400  * unknown struct (0x54 bytes = 0x8340), 80 * starting with I 0x1005 or 0; 104; 216 also starting with 0x3005
    # 0x3f590
    # 10   * unknown struct (0x220 bytes = 0x1540) ?
    # 0x40ad0
    # 0x4e00*B # unknown (e.g. 624 * 0x20)
    # 0x458d0
    # hash?
    # 10    * 2I (all 0)
    # 37    * 2I (all 15, 0)
    # 3896  * 2I (all 0)
    # unknown 0xea90 bytes (e.g. 1000 * 0x60 + padding), possibly multiple structs

class ISO8State(IntFlag):
    No = 0
    Unknown0x01 = auto()
    Unknown0x02 = auto()
    New = auto()
    Unknown0x08 = auto()
    Unknown0x10 = auto()
    Preserved = auto()
    Unknown0x40 = auto() # exclamation mark?
    # Equipped? # E icon
    # What's the no-deconstruct icon?

@dataclass
class ISO8: # 24I
    DbIndex: int
    _state: int
    Modification: int # level/grade 0 - 5
    _unk: int # padding?
    specialbonus1_index: int
    specialbonus1_arg_1: int
    specialbonus1_arg_2: int
    specialbonus1_unknown: int # padding?
    specialbonus2_index: int
    specialbonus2_arg_1: int
    specialbonus2_arg_2: int
    specialbonus2_unknown: int
    specialbonus3_index: int
    specialbonus3_arg_1: int
    specialbonus3_arg_2: int
    specialbonus3_unknown: int
    specialbonus4_index: int
    specialbonus4_arg_1: int
    specialbonus4_arg_2: int
    specialbonus4_unknown: int
    _specialbonus5_index: int
    _specialbonus5_arg_1: int
    _specialbonus5_arg_2: int
    _specialbonus5_unknown: int

    @property
    def State(self) -> ISO8State:
        return ISO8State(self._state)

    def Is(self, check_state: ISO8State) -> bool:
        return self._state & check_state != 0

@dataclass
class ISO8DataBaseEntry:
    ColorNumber: int
    Tier: int
    NoDeconstruct: bool # actually int (0, 1, 0xFF)
    Unused1: int # -1
    Deconstruct: bool # actually int (0, 1, 0x101), opposite of NoDeconstruct
    Unused2: int # 0
    Value1: int
    Value2: int
    Value3: int
    Value4: int
    Value5: int
    Value6: int
    Value7: int
    Value8: int
    Value9: int
    Value10Unused: int
    Value11Unused: int
    Value12Unused: int
    Value13Unused: int
    Value14Unused: int
    Value15Unused: int
    Sort: int # according to colour and tier
    Hash: int

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


# --- MUA3 Save Constants ---

CD = Path(__file__).parent # executable, from sys import executable
# MAX_CHAR_INDEX = 2035
# CHARACTER_NAMES = {
#     int(''.join(l[:8].split(' ')[::-1]), 16): l[10:]
#         for l in Path('DataCharacter.Bin IDs.txt').read_text().split('\n')
#     }

ISO8_OFFSETS = {
    'Purple': 0x895B0,
    'Green': 0x895B4,
    'Blue': 0x895B8,
    'Red': 0x895BC,
    'Orange': 0x895C0,
    'Yellow': 0x895C4,
    'White': 0x895C8,
    'Rainbow': 0x895CC,
}

LANGUAGES = ('English (eng)', 'Japanese (jpn)', 'French (fra)', 'Italian (ita)', 'German (ger)', 'Chinese (chn)', 'Chinese Simplified (smp)', 'Spanish (esp)', 'Korean (kor)')
CLASSES = ('D', 'C', 'B', 'A', 'AA') # Tier
ISO8COLOURS = ('Purple', 'Green', 'Blue', 'Red', 'Orange', 'Yellow', 'White', 'Rainbow')
MODIFICATIONS = ('NONE', '+1', '+2', '+3', '+4', '+5')
FORMAT_REGEX = regex_compile(r'\^0|(#arg[12]#|%%)')
FORMAT_COLOURS = {
    'PLUS': ('#CC8800', '#FFD700'),  # Yellow-ish
    'MINUS': ('#00008B', '#4169E1'), # Dark Blue / Royal Blue
    'WHITE': None
}

CHARACTERDATA_STRUCT = Struct('<'
    'I'
    '4H'
    '9I'
    '2B'
    '2x'
)
with Path(CD / 'Data_ISO8.bin').open('rb') as f:
    ISO8_DATABASE = [ISO8DataBaseEntry(*d) for d in Struct('<23i').iter_unpack(f.read(1000 * 0x5C))]
ISO8_SIZE_UINT32 = 24
ISO8_SIZE = 4 * ISO8_SIZE_UINT32
ISO8_INVENTORY_LIMIT = 1500
ISO8_DATA_COUNT = ISO8_SIZE_UINT32 * ISO8_INVENTORY_LIMIT
ISO8_DATA_OFFSET = 0x9DA0
ISO8_DATA_SIZE = ISO8_SIZE * ISO8_INVENTORY_LIMIT
ISO8_DATA_STRUCT = Struct(f'<{ISO8_SIZE_UINT32 * ISO8_INVENTORY_LIMIT}i')
ISO8_BUFF_TYPES = (
    'STATUS_ENE',
    'STATUS_HP',
    'STATUS_STR',
    'STATUS_DUR',
    'STATUS_MAS',
    'STATUS_RES',
    'MAIN_ATTR_FIGHT',
    'MAIN_ATTR_SLASH',
    'MAIN_ATTR_SHOT',
    'MAIN_ATTR_ENERGY',
    'MAIN_ATTR_MAGIC',
    'SUB_ATTR_HEAT',
    'SUB_ATTR_ICE',
    'SUB_ATTR_THUNDER',
    'SUB_ATTR_SPIDER_BIND',
    'unknown_eye',
    'GAUNTLET_DANGER_GIMMICK',
    'unknown_phoenix',
    'unknown_heart',
    'unknown_money',
    'FLYING'
)
SAVE_INDEX_TO_LOAD = 1
SAVE_ENTRY_SIZE = 0x5BE00 # Seems to be saved in file, use from there?
SAVE_HEADER_STRUCT = Struct('<8I')
UINT32_STRUCT = Struct('<I')

from MUA3_Strings import get_strings, get_table

def get_strings_from_file(input_file: Path, lang_i: int) -> list:
    data = input_file.read_bytes()
    list_count, = UINT32_STRUCT.unpack_from(data)
    list_offsets = Struct(f'<{list_count}I').unpack_from(data, 4)
    return get_strings(data, list_offsets[lang_i], lang_i + 1, list_count, list_offsets)


# --- App Window ---

class App(CTk):
    def __init__(self, title):
        super().__init__()
        self.title(title)
        self.iconbitmap(Path(__file__).parent.parent / 'MUA3_Mods.ico')
        #self.protocol('WM_DELETE_WINDOW', self.on_closing)

        #self.character_index = NumberStrVar(value=0, upper_limit=MAX_CHAR_INDEX)
        self.character_name = StringVar()
        #self.character_number = StringVar()
        self.value2 = StringVar()
        self.is_new = BooleanVar()
        self.is_locked = BooleanVar()
        self.is_equipped = BooleanVar()
        self.iso8_inventory = []
        self.specialbonus = []
        self.iso8_icons = [PhotoImage(file=i) for i in (CD / 'ISO8Icons').iterdir()]
        self.mod_icons = [PhotoImage(file=i) for i in (CD / '08_lab_ISO8_filter_parts').iterdir()]
        self.change_language(LANGUAGES[0])

        top = CTkFrame(self, corner_radius=0)
        top.pack(fill=X)
        middle = CTkFrame(self, corner_radius=0)
        middle.pack(fill=X)
        bottom = CTkFrame(self, corner_radius=0)
        bottom.pack(fill=X)

        _ = CTkButton(
            top,
            text='Open Save',
            command=self.pick_file
        ).pack(side=LEFT, padx=10, pady=10)
        _ = CTkLabel(
            top,
            text='Filters:'
        ).pack(side=LEFT, padx=(0, 10), pady=10)
        _ = CTkOptionMenu(
            top,
            values=CLASSES,
            command=self.filter_class
        ).pack(side=LEFT, padx=5, pady=10)
        _ = CTkOptionMenu(
            top,
            values=ISO8COLOURS,
            command=self.filter_colour
        ).pack(side=LEFT, padx=5, pady=10)
        _ = CTkOptionMenu(
            top,
            values=MODIFICATIONS,
            command=self.filter_modification
        ).pack(side=LEFT, padx=5, pady=10)
        _ = CTkButton(
            top,
            text='Preserved',
            command=self.show_preserved
        ).pack(side=LEFT, padx=5, pady=10)
        _ = CTkButton(
            top,
            text='Not Preserved',
            command=self.show_not_preserved
        ).pack(side=LEFT, padx=5, pady=10)
        #_ = CTkButton(
        #    top,
        #    text='Equipped',
        #    command=self.show_equipped
        #).pack(side=LEFT, padx=5, pady=10)
        #_ = CTkButton(
        #    top,
        #    text='Not Equipped',
        #    command=self.show_not_equipped
        #).pack(side=LEFT, padx=5, pady=10)
        _ = CTkButton(
            top,
            text='Show All',
            command=self.show_all
        ).pack(side=LEFT, padx=5, pady=10)

        #_ = CTkButton(
        #    top,
        #    text='Get data',
        #    command=self.character_index_changed
        #).pack(side=LEFT, padx=10, pady=10)

        #for i in range(4):
        #    self.grid_columnconfigure(i, weight=1)
        #self.grid_rowconfigure(1, weight=1)
        #self.grid_rowconfigure(2, weight=1)
        #self.grid_rowconfigure(3, weight=1)

        self.listbox = CTkListbox(
            middle,
            command=self.iso8_changed,
            height=600,
            width=400,
            font=('ROG Fonts', 12),
        )
        self.listbox.pack(side=LEFT, padx=10, pady=10)
        details = CTkFrame(middle)
        details.pack(side=LEFT)
        _ = CTkLabel(
            details,
            font=('ROG Fonts', 18),
            textvariable=self.character_name
        ).pack(padx=10, pady=10) # WIP
        iso8_img = CTkFrame(details, fg_color='transparent')
        iso8_img.pack()
        self.shard = CTkLabel(iso8_img, text='')
        self.shard.grid(column=0, row=0)
        self.mod = CTkLabel(iso8_img, fg_color='transparent', text='')
        self.mod.grid(column=0, row=0, sticky='ne')
        #_ = CTkEntry(
        #    middle,
        #    textvariable=self.value2,
        #    width=60
        #).grid(row=1, column=3, padx=(0, 10), pady=10)
        booleans = CTkFrame(details)
        booleans.pack(padx=10, pady=10)
        _ = CTkCheckBox(booleans,
            text='Preserved',
            #command=checkbox_event,
            variable=self.is_locked
        ).pack(side=LEFT, padx=10, pady=10)
        _ = CTkCheckBox(booleans,
            text='Equipped',
            #command=checkbox_event,
            variable=self.is_equipped
        ).pack(side=LEFT, padx=10, pady=10)
        _ = CTkCheckBox(booleans,
            text='New',
            #command=checkbox_event,
            variable=self.is_new
        ).pack(side=LEFT, padx=10, pady=10)

        # scalable only with PIL:
        #from PIL import Image
        #CTkImage(light_image=Image.open(p), size=(32, 32))
        buff_icons = {ISO8_BUFF_TYPES[i]: PhotoImage(file=p) for i, p in enumerate((CD / 'BuffsIcons').iterdir()) if i < len(ISO8_BUFF_TYPES)}
        self.buff1 = ISO8SpecialBonusEditor(details, self.specialbonus, buff_icons)
        self.buff1.pack(padx=10, pady=0)
        self.buff2 = ISO8SpecialBonusEditor(details, self.specialbonus, buff_icons)
        self.buff2.pack(padx=10, pady=10)
        # 3 rarely, and 4 never used?
        self.buff3 = ISO8SpecialBonusEditor(details, self.specialbonus, buff_icons)
        self.buff3.pack(padx=10, pady=0)
        self.buff4 = ISO8SpecialBonusEditor(details, self.specialbonus, buff_icons)
        self.buff4.pack(padx=10, pady=10)

        _ = CTkLabel(
            bottom,
            text='Change language:'
        ).pack(side=LEFT, padx=10, pady=10)
        _ = CTkOptionMenu(
            bottom,
            values=LANGUAGES,
            command=self.change_language
        ).pack(side=LEFT, padx=10, pady=10)

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

        #self.current_theme.set(theme := CONFIG.get('THEME', 'System'))
        #if theme != 'System': set_appearance_mode(theme)

    def pick_file(self):
        f = filedialog.askopenfile(mode='rb')
        if f:
            h = SaveFileHeader(*SAVE_HEADER_STRUCT.unpack(f.read(4 * 8)))
            # WIP: Index selectable?, use size from the SaveHeader?
            if SAVE_INDEX_TO_LOAD < h.content_count:
                offsets = [o for o in range(h.offset1, h.size, SAVE_ENTRY_SIZE)]
                f.seek(offsets[SAVE_INDEX_TO_LOAD] + ISO8_DATA_OFFSET)
                data = ISO8_DATA_STRUCT.unpack(f.read(ISO8_DATA_SIZE))
                self.iso8_inventory = [ISO8(*data[i:i+ISO8_SIZE_UINT32]) for i in range(0, ISO8_DATA_COUNT, ISO8_SIZE_UINT32) if data[i] != -1]
                self.show_all()

    def character_index_changed(self):
        if not self.data: return
        offset = int(self.character_index.get()) * 4 * 13
        #cd = CharacterData(*CHARACTERDATA_STRUCT.unpack_from(self.data, offset))
        self.character_name.set(f'{CHARACTER_NAMES.get(cd.ID, f'Unknown 0x{cd.ID:X}')}  #{cd.Number:04}')
        #self.character_number.set(f'{}  #{cd.Number:04}')

    def get_specialbonus(self, index: int) -> str:
        try:
            return self.specialbonus[index]
        except:
            return ''

    def iso8_changed(self, name: str):
        iso8 = self.iso8_inventory[int(name[:4])]
        self.character_name.set(name[5:])
        try:
            iso8_base = ISO8_DATABASE[iso8.DbIndex]
            #iso8_base.ColorNumber
            self.shard.configure(image=self.iso8_icons[iso8_base.Sort // 10 * 5 + (iso8_base.Sort % 10)])
        except:
            self.shard.configure(image=None)
        self.buff1.load(
            self.get_specialbonus(iso8.specialbonus1_index),
            iso8.specialbonus1_arg_1,
            iso8.specialbonus1_arg_2,
            iso8.specialbonus1_index)
        self.buff2.load(
            self.get_specialbonus(iso8.specialbonus2_index),
            iso8.specialbonus2_arg_1,
            iso8.specialbonus2_arg_2,
            iso8.specialbonus2_index)
        self.buff3.load(
            self.get_specialbonus(iso8.specialbonus3_index),
            iso8.specialbonus3_arg_1,
            iso8.specialbonus3_arg_2,
            iso8.specialbonus3_index)
        self.buff4.load(
            self.get_specialbonus(iso8.specialbonus4_index),
            iso8.specialbonus4_arg_1,
            iso8.specialbonus4_arg_2,
            iso8.specialbonus4_index)
        self.is_new.set(iso8.Is(ISO8State.New))
        self.is_locked.set(iso8.Is(ISO8State.Preserved))
        m = iso8.Modification - 1
        self.mod.configure(image=(self.mod_icons[m] if -1 < m < 5 else None))
        self.modification.set(f'+{iso8.Modification}' if iso8.Modification else '')

    def append_iso8(self, iso8: ISO8, i: int):
        try:
            iso8_base = ISO8_DATABASE[iso8.DbIndex]
            name = f'{i:04} {ISO8COLOURS[iso8_base.ColorNumber]} ISO-8 - Class {CLASSES[iso8_base.Tier]}'
        except:
            name = f'{i:04} Unused'
        self.listbox.append(name)

    def filter_list(self, state: ISO8State):
        self.listbox.delete_all()
        for i, iso8 in enumerate(self.iso8_inventory):
            if iso8.Is(state):
                self.append_iso8(iso8, i)

    def filter_colour(self, colour: str):
        self.listbox.delete_all()
        for i, iso8 in enumerate(self.iso8_inventory):
            try:
                iso8_base = ISO8_DATABASE[iso8.DbIndex]
                if ISO8COLOURS.index(colour) == iso8_base.ColorNumber:
                    self.listbox.append(f'{i:04} {ISO8COLOURS[iso8_base.ColorNumber]} ISO-8 - Class {CLASSES[iso8_base.Tier]}')
            except:
                pass

    def filter_class(self, cls: str):
        self.listbox.delete_all()
        for i, iso8 in enumerate(self.iso8_inventory):
            try:
                iso8_base = ISO8_DATABASE[iso8.DbIndex]
                if CLASSES.index(cls) == iso8_base.Tier:
                    self.listbox.append(f'{i:04} {ISO8COLOURS[iso8_base.ColorNumber]} ISO-8 - Class {CLASSES[iso8_base.Tier]}')
            except:
                pass

    def filter_modification(self, mod: str):
        self.listbox.delete_all()
        for i, iso8 in enumerate(self.iso8_inventory):
            if MODIFICATIONS.index(mod) == iso8.Modification:
                self.append_iso8(iso8, i)

    def show_preserved(self):
        self.filter_list(ISO8State.Preserved)

    def show_not_preserved(self):
        pass
        #self.filter_list(ISO8State.Unpreserved)

    def show_equipped(self):
        pass

    def show_not_equipped(self):
        pass

    def show_all(self):
        self.listbox.delete_all()
        for i, iso8 in enumerate(self.iso8_inventory):
            self.append_iso8(iso8, i)

    def change_language(self, lang: str):
        # WIP: Try/catch
        lc = lang[-4:-1]
        li = LANGUAGES.index(lang)
        self.specialbonus = get_strings_from_file(CD / f'mes_SpecialBonus_{lc}.bin', li)
        #self.iso8_names = get_table(CD / f'mes_ISO_8Name_{lc}.bin', li, '<2I4x')

    #def on_closing(self):
    #    self.save_settings()
    #    self.destroy()

if __name__ == '__main__':
    app = App('MUA3 Save Editor - ISO8 Edition')
    app.mainloop()