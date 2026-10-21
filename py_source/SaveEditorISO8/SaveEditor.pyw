from tkinter import *
#from tkinter.messagebox import showerror #, showinfo, showwarning # https://docs.python.org/3/library/tkinter.messagebox.html
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
    def set_int(self, value: int, is_float: bool = False):
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

    def clear(self):
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
        self.clear()
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
    def __init__(self, master, buff_icons: dict, **kwargs):
        # fg_color='transparent' makes the frame blend into the background
        super().__init__(master, **kwargs)
        self.widgets = []
        CTkLabel(self, text='').pack(side=LEFT, padx=5)
        self.specialbonuses = CTkOptionMenu(
            self,
            dynamic_resizing=False,
            command=self._change_bonus
        )
        self.specialbonuses.pack(side=RIGHT, padx=5, pady=5)
        CTkLabel(self, text='').pack(side=RIGHT, padx=5)
        self.buff_icons = buff_icons
        self.arguments = {'#arg1#': NumberStrVar(), '#arg2#': NumberStrVar()}

    def update_specialbonuses(self, specialbonuses: list):
        self.specialbonuses.configure(values=specialbonuses)

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
    offset_tail: int # only zeroes after that
    unknown1: int
    unknown2: int
    unknown3: int
    header_size: int # player 1?
    unknown4: int
    # 0x70 * B # flags?

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
    # 90   * CharacterAttributes (0x1c0 bytes = 0x9d80)
    # --0x009e30--
    # 1500 * ISO8 (838 used)
    # 31   * unknown iso8 struct (0x60 bytes = 0xba0), starting with hash, mostly all 0
    # --0x02dc50--
    # 600  * unknown struct (0x40 bytes = 0x9600), starting with I (?) / only 11 used
    # 400  * unknown struct (0x54 bytes = 0x8340), 80 * starting with I 0x1005 or 0; 104; 216 also starting with 0x3005
    # --0x03f590--
    # 10   * unknown struct (0x220 bytes = 0x1540) ?
    # --0x040ad0--
    # 0x1000*B # unknown (e.g. 0x80 * 0x20)
    # 0xd0 * B # unknown
    # 0x15c0*B # SHIELDDepotItemState
    # 0x2770*B # unknown (e.g. 631 * 0x10)
    # --0x0458d0--
    # hash?
    # 10   * 2I (all 0)
    # 37   * 2I (all 15, 0)
    # 3896 * 2I (all 0)
    # unknown 0xEA90 bytes (e.g. 1000 * 0x60 + padding), possibly multiple structs

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

    def SetState(self, check_state: ISO8State, state: bool):
        if state:
            self._state |= check_state
        else:
            self._state &= ~check_state

    def Is(self, check_state: ISO8State) -> bool:
        return self._state & check_state != 0

    def update(self, buff1: tuple, buff2: tuple, buff3: tuple, buff4: tuple):
        self.specialbonus1_index, self.specialbonus1_arg_1, self.specialbonus1_arg_2 = buff1
        self.specialbonus2_index, self.specialbonus2_arg_1, self.specialbonus2_arg_2 = buff2
        self.specialbonus3_index, self.specialbonus3_arg_1, self.specialbonus3_arg_2 = buff3
        self.specialbonus4_index, self.specialbonus4_arg_1, self.specialbonus4_arg_2 = buff4

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

@dataclass
class CharacterAttributes: # 0x30B  12I  8I  0x140B
    #UnknownValues: 19x 0-255 (0-70)
    # 29x unused0x00
    # 12x I, often all 0 (sometimes 9, 0x98, etc.)
    XP: int = 0
    Strength: int = 100
    Durability: int = 100
    Mastery: int = 100
    Resistence: int = 100
    Vitality: int = 3000
    Energy: int = 4000
    AP: int = 0x1000001
    # Flags:
    # 09x unused0x00 | 0x80
    UnlockedFlag: int = 0 # 0, 1 Unlocked, 2/4 Unused?, 8 Used when unl., 0x10 Used when unl.
    # 08x unused0x00
    #UnknownFLag: 1 | 8 (9)
    # 02x unused0x00
    #UnknownFLag: 1 | 8 (9)
    UnlockedFlagCostume02: int = 0
    UnlockedFlagCostume03: int = 0 #0, 1 Unlocked, 2 Unused, 4 c2 unl, 8 Unused, 0x10 c3+4 unl
    UnlockedFlagCostume04: int = 0 #^^, except DP: 1 | 2 | 4 | 8 = automatically unlocked
    UnlockedFlagCostume05: int = 0 #(same as 3+4)
    UnlockedFlagCostume06: int = 0 #(same as 3+4)
    UnlockedFlagCostume07: int = 0
    UnlockedFlagCostume08: int = 0
    UnlockedFlagCostume09: int = 0
    UnlockedFlagCostume10: int = 0
    UnlockedFlagCostume11: int = 0
    UnlockedFlagCostume12: int = 0
    UnlockedFlagCostume13: int = 0
    UnlockedFlagCostume14: int = 0
    UnlockedFlagCostume15: int = 0
    UnlockedFlagCostume16: int = 0
    # 16x unused0xFF | 0xA5
    # 03x unused0x00 | 0xB5
    Level: int = 0
    # 52x unused0x00 | 0xB9
    #Unknown0xF0: 12x 0-4 (or 9x + 3x 0x00)
    Skill4Level: int = 0 #
    Skill2Level: int = 0 # Level = value + 1
    Skill1Level: int = 0 #
    Skill3Level: int = 0 #
    # 16x unused0x00 | 0x100
    Skill4UnlockFlag: int = 0 #
    Skill2UnlockFlag: int = 0 # 1 = unlocked (flag or boolean)
    Skill1UnlockFlag: int = 1 #
    Skill3UnlockFlag: int = 0 #
    # 76x unused0x00 | 0x114
    # 12x unused0xFF | 0x160
    # 04x unused0x00 | 0x16C
    #UnknownFLag: 1 | 4 (5)
    # 79x unused0x00 | 0x171 - 0x1C0
    def GetAP(self) -> int:
        return self.AP & 0xFFFFFF
    def SetAP(self, value: int):
        self.AP = (self.AP & 0xFF000000) | value #& 0xFFFFFF
    def IsUnlocked(self, flag_value: int) -> bool:
        # or use post_init
        return TemporaryUnlockFlag.Unlocked in TemporaryUnlockFlag(flag_value)

class SHIELDDepotItemState(IntFlag): # 5: Unlocked | Common1; 0x14: Common1 | Common2
    No = 0
    Unlocked = auto()
    Unused1 = auto()
    Common1 = auto() # hidden in shop?
    Unused2 = auto()
    Common2 = auto() # shown in shield depot?

class TemporaryUnlockFlag(IntFlag):
    Locked = 0
    Unlocked = auto()

@dataclass
class SavedMaterials: # 28I
    UNKNOWN_0x2D700: int # 0xd2ed   53997
    UNUSED_0x2D704: int  # ?
    UNKNOWN_0x2D708: int # 0x285f   10335
    CREDITS: int
    UNUSED_0X2D710: int  # ?
    CHAR_ABILITY_ORBS: int
    UNUSED_0X2D718: int  # ?
    UNUSED_0X2D71C: int  # ?
    # ISO8 Shard upgrade materials
    ISO8_FRAGMENTS_PURPLE: int
    ISO8_FRAGMENTS_GREEN: int
    ISO8_FRAGMENTS_BLUE: int
    ISO8_FRAGMENTS_RED: int
    ISO8_FRAGMENTS_ORANGE: int
    ISO8_FRAGMENTS_YELLOW: int
    ISO8_FRAGMENTS_WHITE: int
    ISO8_FRAGMENTS_RAINBOW: int
    # Character upgrade materials                                             
    ENHANCEMENT_POINTS: int
    VOID_SPHERES: int
    SMALL_XP_CUBES: int
    SOLID_XP_CUBES: int
    ENHAN_XP_CUBES: int
    COSMICXP_CUBES: int
    ULTIM_XP_CUBES: int
    UNUSED_0x2D75C: int  # ?
    #Unknown if materials
    UNKNOWN_0x2D760: int # 0x000a   10
    UNKNOWN_0x2D764: int # 0x010000 65536
    UNUSED_0x2D768: int  # ?
    UNUSED_0x2D76C: int  # ?
    # ANOTHER ROW?

# --- MUA3 Save Constants ---

CD = Path(__file__).parent # executable, from sys import executable
# MAX_CHAR_INDEX = 2035

CHARACTERS_OFFSET = 0x20
MATERIALS_OFFSET = 0x2D700 # 0x89590
MATERIALS_STRUCT = Struct('< 28I')
SHIELD_TOKENS_OFFSET = 0x45840

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

DATACHARACTER_STRUCT = Struct('<'
    'I'
    '4H'
    '9I'
    '2B'
    '2x'
)
CHAR_DATA_STRUCT = Struct('<'
    '19x'
    '29x'
    '48x'
    '8I'
    '9x'
    'B'
    '6x'
    '6x'
    '15B'
    '16x'
    '3x'
    'I'
    '52x'
    '12x'
    '4B'
    '16x'
    '4B'
    '76x'
    '12x'
    '4x'
    '1x'
    '79x'
)
CHAR_DATA_OFFSET = 0x20
ISO8_DATA_OFFSET = 0x9DA0
with Path(CD / 'Data_ISO8.bin').open('rb') as f:
    ISO8_DATABASE = [ISO8DataBaseEntry(*d) for d in Struct('<23i').iter_unpack(f.read(1000 * 0x5C))]
ISO8_SIZE_UINT32 = 24
ISO8_DATA_COUNT = ISO8_SIZE_UINT32 * 1500
ISO8_DATA_STRUCT = Struct(f'<{ISO8_DATA_COUNT}i')
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

SHIELD_DEPOT_ITEM_FLAGS_OFFSET = 0X41BA0 # SHIELDDepotItemState

SAVE_INDEX_TO_LOAD = 1
SAVE_ENTRY_SIZE = 0x5BE00 # Seems to be saved in SaveHeader, use from there?
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

        self.character_list = []
        self.character_attributes = {}
        #self.character_index = NumberStrVar(value=0, upper_limit=MAX_CHAR_INDEX)
        self.character_name = StringVar()
        #self.character_number = StringVar()
        self.value2 = StringVar()

        self.credit = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)
        self.ability_orbs = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)
        self.enhancement_points = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)
        self.void_spheres = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)
        self.small_xp_cubes = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)
        self.solid_xp_cubes = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)
        self.enhanced_xp_cubes = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)
        self.cosmic_xp_cubes = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)
        self.ultimate_xp_cubes = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)

        self.char_xp = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)
        self.char_strength = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)
        self.char_durability = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)
        self.char_mastery = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)
        self.char_resistence = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)
        self.char_vitality = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)
        self.char_energy = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)
        self.char_ap = NumberStrVar(value=0, upper_limit=0xFFFFFF)
        self.char_level = NumberStrVar(value=0, upper_limit=300)
        self.power1_level = NumberStrVar(value=0, upper_limit=5)
        self.power2_level = NumberStrVar(value=0, upper_limit=5)
        self.power3_level = NumberStrVar(value=0, upper_limit=5)
        self.power4_level = NumberStrVar(value=0, upper_limit=5)
        self.power1_unlocked = BooleanVar()
        self.power2_unlocked = BooleanVar()
        self.power3_unlocked = BooleanVar()
        self.power4_unlocked = BooleanVar()
        self.costume02_unlocked = BooleanVar()
        self.costume03_unlocked = BooleanVar()
        self.costume04_unlocked = BooleanVar()
        self.costume05_unlocked = BooleanVar()
        self.costume06_unlocked = BooleanVar()
        self.costume07_unlocked = BooleanVar()
        self.costume08_unlocked = BooleanVar()
        self.costume09_unlocked = BooleanVar()
        self.costume10_unlocked = BooleanVar()
        self.costume11_unlocked = BooleanVar()
        self.costume12_unlocked = BooleanVar()
        self.costume13_unlocked = BooleanVar()
        self.costume14_unlocked = BooleanVar()
        self.costume15_unlocked = BooleanVar()
        self.costume16_unlocked = BooleanVar()

        self.frag_purple = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)
        self.frag_green = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)
        self.frag_blue = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)
        self.frag_red = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)
        self.frag_orange = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)
        self.frag_yellow = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)
        self.frag_white = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)
        self.frag_rainbow = NumberStrVar(value=0, upper_limit=0xFFFFFFFF)
        self.iso8: ISO8 = None
        self.is_new = BooleanVar()
        self.is_locked = BooleanVar()
        self.is_equipped = BooleanVar()
        self.iso8_inventory = []
        self.specialbonus = []
        self.iso8_icons = [PhotoImage(file=i) for i in (CD / 'ISO8Icons').iterdir()]
        self.mod_icons = [PhotoImage(file=i) for i in (CD / '08_lab_ISO8_filter_parts').iterdir()]

        top = CTkFrame(self, corner_radius=0)
        top.pack(fill=X)
        middle = CTkFrame(self, corner_radius=0)
        middle.pack(fill=X)
        common = CTkFrame(self, corner_radius=0)
        common.pack(fill=X)
        bottom = CTkFrame(self, corner_radius=0)
        bottom.pack(fill=X)

        _ = CTkButton(
            top,
            text='Open Save',
            command=self.pick_file
        ).pack(side=LEFT, padx=10, pady=10)
        #_ = CTkButton(
        #    top,
        #    text='Get data',
        #    command=self.character_index_changed
        #).pack(side=LEFT, padx=10, pady=10)


        self.tabview = CTkTabview(middle, anchor=NW)
        self.tabview.pack(fill=BOTH)
        self.tabview.add('Characters')
        self.tabview.add('ISO-8')
        char_frame = CTkFrame(self.tabview.tab('Characters'), fg_color='transparent')
        char_frame.grid()
        iso8_frame = CTkFrame(self.tabview.tab('ISO-8'), fg_color='transparent')
        iso8_frame.grid()


        self.character_names = CTkOptionMenu(
            char_frame,
            command=self.character_changed
        )
        self.character_names.grid(row=0, column=0, columnspan=2, padx=10, pady=10) #.pack(padx=10, pady=10)
        #_ = CTkLabel(
        #    char_frame,
        #    font=('ROG Fonts', 18),
        #    textvariable=self.character_name
        #).grid(row=0, column=0, columnspan=2, padx=10, pady=10) #.pack(padx=10, pady=10)
        _ = CTkLabel(char_frame, text='Level:'
        ).grid(row=1, column=0, padx=10, pady=2, sticky=W)
        _ = CTkEntry(char_frame, justify=RIGHT, textvariable=self.char_level
        ).grid(row=1, column=1, padx=0,  pady=2)
        _ = CTkLabel(char_frame, text='XP:'
        ).grid(row=2, column=0, padx=10, pady=2, sticky=W)
        _ = CTkEntry(char_frame, justify=RIGHT, textvariable=self.char_xp
        ).grid(row=2, column=1, padx=0,  pady=2)
        #_ = CTkEntry(
        #    char_frame,
        #    textvariable=self.value3,
        #    width=60
        #).grid(row=1, column=2, padx=10, pady=10)
        #_ = CTkEntry(
        #    char_frame,
        #    textvariable=self.value2,
        #    width=60
        #).grid(row=1, column=3, padx=(0, 10), pady=10)
        _ = CTkLabel(char_frame, text='Vitality:'
        ).grid(row=3, column=0, padx=10, pady=2, sticky=W)
        _ = CTkEntry(char_frame, justify=RIGHT, textvariable=self.char_vitality
        ).grid(row=3, column=1, padx=0,  pady=2)
        #_ = CTkEntry(
        #    char_frame,
        #    textvariable=self.value7,
        #    width=60
        #).grid(row=2, column=2, padx=10, pady=10)
        #_ = CTkEntry(
        #    char_frame,
        #    textvariable=self.value8,
        #    width=60
        #).grid(row=2, column=3, padx=(0, 10), pady=10)
        _ = CTkLabel(char_frame, text='Energy:'
        ).grid(row=4, column=0, padx=10, pady=2, sticky=W)
        _ = CTkEntry(char_frame, justify=RIGHT, textvariable=self.char_energy
        ).grid(row=4, column=1, padx=0,  pady=2)
        #_ = CTkEntry(
        #    char_frame,
        #    textvariable=self.value11,
        #    width=60
        #).grid(row=3, column=2, padx=10, pady=10)
        #_ = CTkEntry(
        #    char_frame,
        #    textvariable=self.value12,
        #    width=60
        #).grid(row=3, column=3, padx=(0, 10), pady=10)
        _ = CTkLabel(char_frame, text='Strength:'
        ).grid(row=5, column=0, padx=10, pady=2, sticky=W)
        _ = CTkEntry(char_frame, justify=RIGHT, textvariable=self.char_strength
        ).grid(row=5, column=1, padx=0,  pady=2)
        _ = CTkLabel(char_frame, text='Durability:'
        ).grid(row=6, column=0, padx=10, pady=2, sticky=W)
        _ = CTkEntry(char_frame, justify=RIGHT, textvariable=self.char_durability
        ).grid(row=6, column=1, padx=0,  pady=2)
        _ = CTkLabel(char_frame, text='Mastery:'
        ).grid(row=7, column=0, padx=10, pady=2, sticky=W)
        _ = CTkEntry(char_frame, justify=RIGHT, textvariable=self.char_mastery
        ).grid(row=7, column=1, padx=0,  pady=2)
        _ = CTkLabel(char_frame, text='Resistence:'
        ).grid(row=8, column=0, padx=10, pady=2, sticky=W)
        _ = CTkEntry(char_frame, justify=RIGHT, textvariable=self.char_resistence
        ).grid(row=8, column=1, padx=0,  pady=2)
        _ = CTkLabel(char_frame, text='Ability Points:'
        ).grid(row=9, column=0, padx=10, pady=2, sticky=W)
        _ = CTkEntry(char_frame, justify=RIGHT, textvariable=self.char_ap
        ).grid(row=9, column=1, padx=0,  pady=2)
        #_ = CTkCheckBox(char_frame,
        #    text='',
        #    #command=checkbox_event,
        #    variable=self.value15,
        #    width=60
        #    #onvalue=True,
        #    #offvalue=False
        #).grid(row=4, column=2, padx=10, pady=10)

        mats = CTkFrame(char_frame, fg_color='transparent')
        mats.grid(row=9, column=0, columnspan=2, padx=10, pady=10)
        _ = CTkEntry(mats, justify=RIGHT, textvariable=self.ability_orbs, width=50).pack(side=LEFT)
        _ = CTkEntry(mats, justify=RIGHT, textvariable=self.enhancement_points, width=50).pack(side=LEFT)
        _ = CTkEntry(mats, justify=RIGHT, textvariable=self.void_spheres, width=50).pack(side=LEFT)
        _ = CTkEntry(mats, justify=RIGHT, textvariable=self.small_xp_cubes, width=50).pack(side=LEFT)
        _ = CTkEntry(mats, justify=RIGHT, textvariable=self.solid_xp_cubes, width=50).pack(side=LEFT)
        _ = CTkEntry(mats, justify=RIGHT, textvariable=self.enhanced_xp_cubes, width=50).pack(side=LEFT)
        _ = CTkEntry(mats, justify=RIGHT, textvariable=self.cosmic_xp_cubes, width=50).pack(side=LEFT)
        _ = CTkEntry(mats, justify=RIGHT, textvariable=self.ultimate_xp_cubes, width=50).pack(side=LEFT)


        filters = CTkFrame(iso8_frame, fg_color='transparent')
        filters.pack()
        _ = CTkLabel(
            filters,
            text='Filters:'
        ).pack(side=LEFT, padx=(0, 10), pady=10)
        _ = CTkOptionMenu(
            filters,
            values=CLASSES,
            command=self.filter_class
        ).pack(side=LEFT, padx=5, pady=10)
        _ = CTkOptionMenu(
            filters,
            values=ISO8COLOURS,
            command=self.filter_colour
        ).pack(side=LEFT, padx=5, pady=10)
        _ = CTkOptionMenu(
            filters,
            values=MODIFICATIONS,
            command=self.filter_modification
        ).pack(side=LEFT, padx=5, pady=10)
        _ = CTkButton(
            filters,
            text='Preserved',
            command=self.show_preserved
        ).pack(side=LEFT, padx=5, pady=10)
        _ = CTkButton(
            filters,
            text='Not Preserved',
            command=self.show_not_preserved
        ).pack(side=LEFT, padx=5, pady=10)
        #_ = CTkButton(
        #    iso8_frame,
        #    text='Equipped',
        #    command=self.show_equipped
        #).pack(side=LEFT, padx=5, pady=10)
        #_ = CTkButton(
        #    iso8_frame,
        #    text='Not Equipped',
        #    command=self.show_not_equipped
        #).pack(side=LEFT, padx=5, pady=10)
        _ = CTkButton(
            filters,
            text='Show All',
            command=self.show_all
        ).pack(side=LEFT, padx=5, pady=10)
        self.listbox = []
        self.iso8_selector = CTkOptionMenu(
            iso8_frame,
            values=self.listbox,
            command=self.iso8_changed
        )
        self.iso8_selector.pack(padx=10, pady=10)

        #self.listbox = CTkListbox(
        #    iso8_frame,
        #    command=self.iso8_changed,
        #    height=600,
        #    width=400,
        #    font=('ROG Fonts', 12),
        #)
        #self.listbox.pack(side=LEFT, padx=10, pady=10)

        details = CTkFrame(iso8_frame)
        details.pack(fill=BOTH) # side=LEFT
        #_ = CTkLabel(
        #    details,
        #    font=('ROG Fonts', 18),
        #    #textvariable=self.character_name
        #).pack(padx=10, pady=10) # WIP
        iso8_img = CTkFrame(details, fg_color='transparent')
        iso8_img.pack()
        self.shard = CTkLabel(iso8_img, text='')
        self.shard.grid(column=0, row=0)
        self.mod = CTkLabel(iso8_img, fg_color='transparent', text='')
        self.mod.grid(column=0, row=0, sticky='ne')
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
        self.buff1 = ISO8SpecialBonusEditor(details, buff_icons)
        self.buff1.pack(fill=BOTH, padx=10, pady=0)
        self.buff2 = ISO8SpecialBonusEditor(details, buff_icons)
        self.buff2.pack(fill=BOTH, padx=10, pady=10)
        # 3 rarely, and 4 never used?
        self.buff3 = ISO8SpecialBonusEditor(details, buff_icons)
        self.buff3.pack(fill=BOTH, padx=10, pady=0)
        self.buff4 = ISO8SpecialBonusEditor(details, buff_icons)
        self.buff4.pack(fill=BOTH, padx=10, pady=10)

        fi_path = CD / 'ISO8FragmentIconsScaled'
        fragments = CTkFrame(iso8_frame, fg_color='transparent')
        fragments.pack(fill=BOTH)
        _ = CTkLabel(fragments, image=PhotoImage(file=fi_path / '1.png'), text='').pack(side=LEFT, pady=5)
        _ = CTkEntry(fragments, justify=RIGHT, textvariable=self.frag_purple, width=50).pack(side=LEFT)
        _ = CTkLabel(fragments, image=PhotoImage(file=fi_path / '2.png'), text='').pack(side=LEFT)
        _ = CTkEntry(fragments, justify=RIGHT, textvariable=self.frag_red, width=50).pack(side=LEFT)
        _ = CTkLabel(fragments, image=PhotoImage(file=fi_path / '3.png'), text='').pack(side=LEFT)
        _ = CTkEntry(fragments, justify=RIGHT, textvariable=self.frag_orange, width=50).pack(side=LEFT)
        _ = CTkLabel(fragments, image=PhotoImage(file=fi_path / '4.png'), text='').pack(side=LEFT)
        _ = CTkEntry(fragments, justify=RIGHT, textvariable=self.frag_yellow, width=50).pack(side=LEFT)
        _ = CTkLabel(fragments, image=PhotoImage(file=fi_path / '5.png'), text='').pack(side=LEFT)
        _ = CTkEntry(fragments, justify=RIGHT, textvariable=self.frag_green, width=50).pack(side=LEFT)
        _ = CTkLabel(fragments, image=PhotoImage(file=fi_path / '6.png'), text='').pack(side=LEFT)
        _ = CTkEntry(fragments, justify=RIGHT, textvariable=self.frag_blue, width=50).pack(side=LEFT)
        _ = CTkLabel(fragments, image=PhotoImage(file=fi_path / '0.png'), text='').pack(side=LEFT)
        _ = CTkEntry(fragments, justify=RIGHT, textvariable=self.frag_white, width=50).pack(side=LEFT)
        _ = CTkLabel(fragments, image=PhotoImage(file=fi_path / '7.png'), text='').pack(side=LEFT)
        _ = CTkEntry(fragments, justify=RIGHT, textvariable=self.frag_rainbow, width=50).pack(side=LEFT)


        _ = CTkLabel(
            common,
            text='Credits:'
        ).pack(side=LEFT, padx=10, pady=10)
        _ = CTkEntry(
            common,
            justify=RIGHT,
            textvariable=self.credit
        ).pack(side=LEFT, padx=10, pady=10)

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

        self.change_language(LANGUAGES[0])
        #self.current_theme.set(theme := CONFIG.get('THEME', 'System'))
        #if theme != 'System': set_appearance_mode(theme)

    def pick_file(self):
        f = filedialog.askopenfile(parent=self, mode='rb')
        if f:
            h = SaveFileHeader(*SAVE_HEADER_STRUCT.unpack(f.read(4 * 8)))
            # WIP: Index selectable?, use size from the SaveHeader?
            if SAVE_INDEX_TO_LOAD < h.content_count:
                #offsets = [o for o in range(h.header_size, h.offset_tail, SAVE_ENTRY_SIZE)]
                offset_base = h.header_size + SAVE_ENTRY_SIZE * SAVE_INDEX_TO_LOAD
                f.seek(offset_base + ISO8_DATA_OFFSET)
                data = ISO8_DATA_STRUCT.unpack(f.read(ISO8_DATA_STRUCT.size))
                self.iso8_inventory = [ISO8(*data[i:i+ISO8_SIZE_UINT32]) for i in range(0, ISO8_DATA_COUNT, ISO8_SIZE_UINT32) if data[i] != -1]
                f.seek(offset_base + MATERIALS_OFFSET)
                self.materials = SavedMaterials(*MATERIALS_STRUCT.unpack(f.read(MATERIALS_STRUCT.size)))
                self.load_materials()
                f.seek(offset_base + CHARACTERS_OFFSET)
                self.character_attributes = {c: CharacterAttributes(*CHAR_DATA_STRUCT.unpack(f.read(CHAR_DATA_STRUCT.size))) for c in self.character_list}
                #self.show_all()
            f.close()

    def character_changed(self, value: str):
        #self.character_name.set(value)
        attributes = self.character_attributes.get(value)
        if not attributes: return
        self.char_xp.set(attributes.XP)
        self.char_strength.set(attributes.Strength)
        self.char_durability.set(attributes.Durability)
        self.char_mastery.set(attributes.Mastery)
        self.char_resistence.set(attributes.Resistence)
        self.char_vitality.set(attributes.Vitality)
        self.char_energy.set(attributes.Energy)
        self.char_ap.set(attributes.GetAP())
        self.char_level.set(attributes.Level + 1)
        self.costume02_unlocked.set(attributes.IsUnlocked(attributes.UnlockedFlagCostume02))
        self.costume03_unlocked.set(attributes.IsUnlocked(attributes.UnlockedFlagCostume03))
        self.costume04_unlocked.set(attributes.IsUnlocked(attributes.UnlockedFlagCostume04))
        self.costume05_unlocked.set(attributes.IsUnlocked(attributes.UnlockedFlagCostume05))
        self.costume06_unlocked.set(attributes.IsUnlocked(attributes.UnlockedFlagCostume06))
        self.costume07_unlocked.set(attributes.IsUnlocked(attributes.UnlockedFlagCostume07))
        self.costume08_unlocked.set(attributes.IsUnlocked(attributes.UnlockedFlagCostume08))
        self.costume09_unlocked.set(attributes.IsUnlocked(attributes.UnlockedFlagCostume09))
        self.costume10_unlocked.set(attributes.IsUnlocked(attributes.UnlockedFlagCostume10))
        self.costume11_unlocked.set(attributes.IsUnlocked(attributes.UnlockedFlagCostume11))
        self.costume12_unlocked.set(attributes.IsUnlocked(attributes.UnlockedFlagCostume12))
        self.costume13_unlocked.set(attributes.IsUnlocked(attributes.UnlockedFlagCostume13))
        self.costume14_unlocked.set(attributes.IsUnlocked(attributes.UnlockedFlagCostume14))
        self.costume15_unlocked.set(attributes.IsUnlocked(attributes.UnlockedFlagCostume15))
        self.costume16_unlocked.set(attributes.IsUnlocked(attributes.UnlockedFlagCostume16))
        self.power1_level.set(attributes.Skill1Level + 1)
        self.power2_level.set(attributes.Skill2Level + 1)
        self.power3_level.set(attributes.Skill3Level + 1)
        self.power4_level.set(attributes.Skill4Level + 1)
        self.power1_unlocked.set(attributes.IsUnlocked(attributes.Skill1UnlockFlag))
        self.power2_unlocked.set(attributes.IsUnlocked(attributes.Skill2UnlockFlag))
        self.power3_unlocked.set(attributes.IsUnlocked(attributes.Skill3UnlockFlag))
        self.power4_unlocked.set(attributes.IsUnlocked(attributes.Skill4UnlockFlag))

    def character_index_changed(self):
        if not self.data: return
        offset = int(self.character_index.get()) * 4 * 13
        #cd = CharacterData(*CHARACTERDATA_STRUCT.unpack_from(self.data, offset))
        self.character_name.set(f'{CHARACTER_NAMES.get(cd.ID, f'Unknown 0x{cd.ID:X}')}  #{cd.Number:04}')
        #self.character_number.set(f'{}  #{cd.Number:04}')

    def load_materials(self):
        self.credit.set_int(self.materials.CREDITS)
        self.ability_orbs.set_int(self.materials.CHAR_ABILITY_ORBS)
        self.enhancement_points.set_int(self.materials.ENHANCEMENT_POINTS)
        self.void_spheres.set_int(self.materials.VOID_SPHERES)
        self.small_xp_cubes.set_int(self.materials.SMALL_XP_CUBES)
        self.solid_xp_cubes.set_int(self.materials.SOLID_XP_CUBES)
        self.enhanced_xp_cubes.set_int(self.materials.ENHAN_XP_CUBES)
        self.cosmic_xp_cubes.set_int(self.materials.COSMICXP_CUBES)
        self.ultimate_xp_cubes.set_int(self.materials.ULTIM_XP_CUBES)
        self.frag_purple.set_int(self.materials.ISO8_FRAGMENTS_PURPLE)
        self.frag_green.set_int(self.materials.ISO8_FRAGMENTS_GREEN)
        self.frag_blue.set_int(self.materials.ISO8_FRAGMENTS_BLUE)
        self.frag_red.set_int(self.materials.ISO8_FRAGMENTS_RED)
        self.frag_orange.set_int(self.materials.ISO8_FRAGMENTS_ORANGE)
        self.frag_yellow.set_int(self.materials.ISO8_FRAGMENTS_YELLOW)
        self.frag_white.set_int(self.materials.ISO8_FRAGMENTS_WHITE)
        self.frag_rainbow.set_int(self.materials.ISO8_FRAGMENTS_RAINBOW)

    def get_specialbonus(self, index: int) -> str:
        try:
            return self.specialbonus[index]
        except:
            return ''

    def iso8_changed(self, name: str):
        self.iso8.update(self.buff1.get_values(), self.buff2.get_values(), self.buff3.get_values(), self.buff4.get_values())
        self.iso8.SetState(ISO8State.New, self.is_new)
        self.iso8.SetState(ISO8State.Preserved, self.is_locked)
        self.iso8 = self.iso8_inventory[int(name[:4])]
        #self.character_name.set(name[5:])
        try:
            iso8_base = ISO8_DATABASE[self.iso8.DbIndex]
            #iso8_base.ColorNumber
            self.shard.configure(image=self.iso8_icons[iso8_base.Sort // 10 * 5 + (iso8_base.Sort % 10)])
        except:
            self.shard.configure(image='')
        self.buff1.load(
            self.get_specialbonus(self.iso8.specialbonus1_index),
            self.iso8.specialbonus1_arg_1,
            self.iso8.specialbonus1_arg_2,
            self.iso8.specialbonus1_index)
        self.buff2.load(
            self.get_specialbonus(self.iso8.specialbonus2_index),
            self.iso8.specialbonus2_arg_1,
            self.iso8.specialbonus2_arg_2,
            self.iso8.specialbonus2_index)
        self.buff3.load(
            self.get_specialbonus(self.iso8.specialbonus3_index),
            self.iso8.specialbonus3_arg_1,
            self.iso8.specialbonus3_arg_2,
            self.iso8.specialbonus3_index)
        self.buff4.load(
            self.get_specialbonus(self.iso8.specialbonus4_index),
            self.iso8.specialbonus4_arg_1,
            self.iso8.specialbonus4_arg_2,
            self.iso8.specialbonus4_index)
        self.is_new.set(self.iso8.Is(ISO8State.New))
        self.is_locked.set(self.iso8.Is(ISO8State.Preserved))
        m = self.iso8.Modification - 1
        self.mod.configure(image=(self.mod_icons[m] if -1 < m < 5 else ''))
        #self.modification.set(f'+{self.iso8.Modification}' if self.iso8.Modification else '')

    def append_iso8(self, iso8: ISO8, i: int):
        try:
            iso8_base = ISO8_DATABASE[iso8.DbIndex]
            name = f'{i:04} {ISO8COLOURS[iso8_base.ColorNumber]} ISO-8 - Class {CLASSES[iso8_base.Tier]}'
        except:
            name = f'{i:04} Unused'
        self.listbox.append(name)

    def filter_list(self, state: ISO8State):
        self.listbox.clear()
        for i, iso8 in enumerate(self.iso8_inventory):
            if iso8.Is(state):
                self.append_iso8(iso8, i)

    def filter_colour(self, colour: str):
        self.listbox.clear()
        for i, iso8 in enumerate(self.iso8_inventory):
            try:
                iso8_base = ISO8_DATABASE[iso8.DbIndex]
                if ISO8COLOURS.index(colour) == iso8_base.ColorNumber:
                    self.listbox.append(f'{i:04} {ISO8COLOURS[iso8_base.ColorNumber]} ISO-8 - Class {CLASSES[iso8_base.Tier]}')
            except:
                pass

    def filter_class(self, cls: str):
        self.listbox.clear()
        for i, iso8 in enumerate(self.iso8_inventory):
            try:
                iso8_base = ISO8_DATABASE[iso8.DbIndex]
                if CLASSES.index(cls) == iso8_base.Tier:
                    self.listbox.append(f'{i:04} {ISO8COLOURS[iso8_base.ColorNumber]} ISO-8 - Class {CLASSES[iso8_base.Tier]}')
            except:
                pass

    def filter_modification(self, mod: str):
        self.listbox.clear()
        for i, iso8 in enumerate(self.iso8_inventory):
            if MODIFICATIONS.index(mod) == iso8.Modification:
                self.append_iso8(iso8, i)

    def show_preserved(self):
        self.filter_list(ISO8State.Preserved)

    def show_not_preserved(self):
        #self.filter_list(ISO8State.Unpreserved)
        pass

    def show_equipped(self):
        pass

    def show_not_equipped(self):
        pass

    def show_all(self):
        self.listbox.clear()
        for i, iso8 in enumerate(self.iso8_inventory):
            self.append_iso8(iso8, i)
        self.iso8_selector.configure(values=self.listbox)

    def change_language(self, lang: str):
        # WIP: Try/catch
        lc = lang[-4:-1]
        li = LANGUAGES.index(lang)
        self.specialbonus = get_strings_from_file(CD / f'mes_SpecialBonus_{lc}.bin', li)
        #self.iso8_names = get_table(CD / f'mes_ISO_8Name_{lc}.bin', li, '<2I4x')
        l = get_strings_from_file(CD / f'mes_Character_{lc}.bin', li)
        self.character_list = l[:40] + l[165:215] # is there another way to get playables only?
        self.character_names.configure(values=self.character_list) # WIP
        for w in (self.buff1, self.buff2, self.buff3, self.buff4):
            w.update_specialbonuses(self.specialbonus)

    #def on_closing(self):
    #    self.save_settings()
    #    self.destroy()

if __name__ == '__main__':
    app = App('MUA3 Save Editor')
    app.mainloop()