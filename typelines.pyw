#!/usr/bin/env python3
"""Type & copy each line from a list via assignable keyboard macro key.
Import list from a file, copy from the clipboard, or enter manually.
The import option includes a feature to take a template file and
replace keywords with user provided values.
The list cycles back around to the top after the last line.
"""

__progname__ = 'Type Lines'
__version__ = '0.0.13'
__date__ = '2025-01-23'
__author__ = 'Todd Wintermute'

import argparse
import os
import pathlib
import queue
import re
import shutil
import sys
import threading
import time
import tkinter as tk
import tkinter.filedialog
import tkinter.messagebox
import tkinter.ttk as ttk

# 3rd party module
import pyperclip

# Built-in modules imported at a later time (Linux only using uinput)
# select

# 3rd party modules imported at a later time
# pynput

# 3rd party modules imported at a later time (Linux only):
# evdev

# 3rd party modules imported at a later time (macOS only):
# Quartz

def parse_arguments():
    """Create command line arguments. Returns a parser object."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog='Have a great day!',
        )
    parser.add_argument(
        '-v', '--version',
        help='show the version number and exit',
        action='version',
        version=f'Version: %(prog)s  {__version__}  ({__date__})',
        )
    parser.add_argument(
        '-b', '--backend',
        required=False,
        choices=['xorg', 'uinput'],
        help=(
            '(Linux only) Override backend assumption. '
            'By default, the script will try to determine the best option. '
            'Force the keyboard backend to be xorg or uinput.'
            ),
        )
    parser.add_argument(
        '-d', '--detect-keyboard',
        action='store_true',
        help=(
            '(Optional, Linux and uinput keyboard backend only).'
            'Launch a window to detect the keyboard by requiring the user '
            'press the ENTER key. Use this option if you have issues.'
            ),
        )
    parser.add_argument(
        'filename',
        nargs='?',
        type=pathlib.Path,
        help=(
            '(Optional) File to import at program start. '
            'Can be with or without variables'
            ),
        )
    return parser


def on_press(key):
    """Assigned to the keyboard listener on_press option."""
    if not is_keyboard_hooked:
        return True
    if key == keyforward:
        if reversenextbool.get():
            typeline_gobackward()
        else:
            typeline_goforward()
    elif key == keyrepeat:
        typeline()
    elif key == keyselprev:
        if reversenextbool.get():
            cycleforward()
        else:
            cyclebackward()
    elif key == keyselnext:
        if reversenextbool.get():
            cyclebackward()
        else:
            cycleforward()
    else:
        pass


def on_release(key):
    """Assigned to the keyboard listener on_release option."""
    if not is_keyboard_hooked:
        return True


def win32_event_filter(msg, data):
    """Windows specific function to suppress specific key presses."""
    global listener
    macro_keys = [keyforward, keyrepeat, keyselprev, keyselnext]
    vk_macro_keys = [k.value.vk for k in macro_keys]
    if not is_keyboard_hooked:
        listener._suppress = False
        return True
    elif all([msg in (0x0100, 0x0101), (data.vkCode in vk_macro_keys)]):
        # Key Down/Up on macro keys
        listener._suppress = True
    else:
        listener._suppress = False
        return True


def darwin_intercept(event_type, event):
    """macOS only. suppress specific function key presses."""
    key_events = (
        Quartz.kCGEventKeyDown,  # value = 10
        Quartz.kCGEventKeyUp,    # value = 11
        )
    kb_event_code = Quartz.kCGKeyboardEventKeycode  # value = 9
    event_keycode = Quartz.CGEventGetIntegerValueField(event, kb_event_code)
    macro_keys = [keyforward, keyrepeat, keyselprev, keyselnext]
    keycode_macro_keys = [k.value.vk for k in macro_keys]
    if not is_keyboard_hooked:
        return event
    elif event_type in key_events and event_keycode in keycode_macro_keys:
        # Suppress keyboard macro keys
        return None
    else:
        return event


def controller_worker():
    """Thread for the keyboard controller to type lines."""
    keyboard_controller = pynput.keyboard.Controller()
    while True:
        time.sleep(100/1000)
        if not keyboard_queue.empty():
            curseltxt = keyboard_queue.get()
            keyboard_controller.type(curseltxt)
            keyboard_queue.task_done()


def typeline():
    """Type the current selected line and copy value to clipboard."""
    try:
        curseltxt = listbox.get(listbox.curselection())
        keyboard_queue.put(curseltxt)
        copy_item()
    except:
        warning_no_selection()


def typeline_goforward():
    """Type & copy the selected line and move to next selection."""
    typeline()
    cycleforward()


def typeline_gobackward():
    """Type & copy the selected line and move to previous selection."""
    typeline()
    cyclebackward()


def update_macro_keys():
    """Reset selection and focus when macro keys are changed."""
    global keyforward
    global keyrepeat
    global keyselprev
    global keyselnext
    keyforward = Key[keydict[forward.get()]]
    keyrepeat = Key[keydict[repeat.get()]]
    keyselprev = Key[keydict[selprev.get()]]
    keyselnext = Key[keydict[selnext.get()]]
    curpos = listbox.curselection()[-1] or 0
    mygui.selection_clear()
    set_listbox_selection(curpos)


def hookclipboard():
    """Start lisenting to items added to the system clipboard."""
    global hookcbid
    global lastcbvalue
    if hookcb.get():
        lastcbvalue = ''
        pyperclip.copy('')
        checkcb()
    else:
        if hookcbid:
            root.after_cancel(hookcbid)
            hookcbid = ''


def edititem(text, pos):
    """Edit selected list item."""
    listbox.insert(pos+1, text)
    listbox.delete(pos)
    listbox.select_clear(pos)
    listbox.select_set(pos)


def submit_edit_item(child, text, pos):
    """Edit selected list item and close the edit window."""
    edititem(text, pos)
    childdismiss(child)


def copy_item():
    """Copy selected item to the system clipboard."""
    if listbox.curselection():
        pyperclip.copy(listbox.get(listbox.curselection()))
        return True
    else:
        warning_no_selection()


def copy_goforward():
    """Copy selected item and move to next selection."""
    copy_item()
    cycleforward()


def copy_gobackward():
    """Copy selected item and move to previous selection."""
    copy_item()
    cyclebackward()


def copy_gonext():
    """Copy selected item and move to next or previous via variable."""
    if reversenextbool.get():
        copy_gobackward()
    else:
        copy_goforward()


def warning_no_selection():
    """Warning when no item is selected, and an action is requested."""
    title = 'No selection'
    message = 'No line selected. Select a line first.'
    tk.messagebox.showwarning(title=title, message=message)


def edit_item_window():
    """Child window to modify a line."""
    if not listbox.curselection():
        warning_no_selection()
        return False
    curpos, *_ = listbox.curselection()
    curtext = listbox.get(curpos)
    myedit = tk.Toplevel(root)
    myedit.title('Edit item')
    mychild = ttk.Frame(myedit, padding=(2,2,2,2))
    mychild.grid(column=0, row=0, sticky='NWES')
    lbl1 = ttk.Label(mychild)
    lbl1.config(text='Item:')
    lbl1.grid(column=1, row=1, sticky='S')
    ent1 = ttk.Entry(mychild, justify='center')
    str1 = tk.StringVar(value=curtext)
    ent1.config(textvariable=str1, width=66)
    ent1.icursor('end')
    ent1.grid(column=1, row=2, sticky='WE')
    btn1 = ttk.Button(mychild)
    btn1.config(text='Submit')
    btn1.config(command=lambda: submit_edit_item(myedit, ent1.get(), curpos))
    btn1.grid(column=1, row=3, sticky='EWNS')
    myedit.bind('<Escape>', lambda event: childdismiss(myedit))
    myedit.bind(
        '<Return>',
        lambda event: submit_edit_item(myedit, ent1.get(), curpos)
        )
    for child in mychild.winfo_children():
        child.grid_configure(padx=2, pady=2)
    myedit.update()
    myedit.minsize(myedit.winfo_width(), myedit.winfo_height())
    myedit.maxsize(myedit.winfo_width(), myedit.winfo_height())
    myedit.grab_set()
    myedit.focus()
    ent1.focus_set()
    myedit.wait_window()


def additem(element):
    """Add a new item to the list."""
    for line in [line for line in element.splitlines()]:
        listbox.insert('end', line)
    removeblanklines()


def insert_item_before_window():
    """Add a new item to the list before the selection."""
    insert_item_window(before_or_after='before')


def insert_item_after_window():
    """Add a new item to the list after the selection."""
    insert_item_window(before_or_after='after')


def insert_item_window(before_or_after='after'):
    """Child window to insert a new line."""
    if before_or_after == 'before':
        submit = submit_insert_item_before
    elif before_or_after == 'after':
        submit = submit_insert_item_after
    else:
        return False
    myinsert = tk.Toplevel(root)
    myinsert.title('Insert item')
    mychild = ttk.Frame(myinsert, padding=(2,2,2,2))
    mychild.grid(column=0, row=0, sticky='NWES')
    lbl1 = ttk.Label(mychild)
    lbl1.config(text='Item:')
    lbl1.grid(column=1, row=1, sticky='S')
    ent1 = ttk.Entry(mychild, justify='center')
    str1 = tk.StringVar()
    ent1.config(textvariable=str1)
    ent1.config(width=66)
    ent1.grid(column=1, row=2, sticky='WE')
    btn1 = ttk.Button(mychild)
    btn1.config(text='Submit')
    btn1.config(command=lambda: submit(myinsert, ent1.get()))
    btn1.grid(column=1, row=3)
    btn1.grid(sticky='EWNS')
    myinsert.bind('<Escape>', lambda event: childdismiss(myinsert))
    myinsert.bind('<Return>', lambda event: submit(myinsert, ent1.get()))
    for child in mychild.winfo_children():
        child.grid_configure(padx=2, pady=2)
    myinsert.update()
    myinsert.minsize(myinsert.winfo_width(), myinsert.winfo_height())
    myinsert.maxsize(myinsert.winfo_width(), myinsert.winfo_height())
    myinsert.grab_set()
    myinsert.focus()
    ent1.focus_set()
    myinsert.wait_window()


def submit_insert_item_before(child, text):
    """Child window to insert a line before the selected line."""
    insert_item_before(text)
    childdismiss(child)


def submit_insert_item_after(child, text):
    """Child window to insert a line after the selected line."""
    insert_item_after(text)
    childdismiss(child)


def insert_item_before(text):
    """Insert an item before the selected line."""
    if listbox.curselection():
        curpos, *_ = listbox.curselection()
        if curpos == 0:
            newpos = 0
            curpos = 1
        else:
            newpos = curpos
            curpos = curpos + 1
    else:
        warning_no_selection()
        return False
    listbox.insert(newpos, text)
    listbox.select_clear(curpos)
    listbox.select_set(newpos)


def insert_item_after(text):
    """Insert an item after the selected line."""
    if listbox.curselection():
        curpos, *_ = listbox.curselection()
        newpos = curpos + 1
    else:
        warning_no_selection()
        return False
    listbox.insert(newpos, text)
    listbox.select_clear(curpos)
    listbox.select_set(newpos)


def removeitem():
    """Remove the selected line from the list."""
    if listbox.curselection():
        selected = listbox.curselection()
        # Remove multiple rows (currently select multiple not enabled)
        if len(selected) > 1:
            for row in selected[::-1]:
                listbox.delete(row)
            return True
        curpos = listbox.curselection()[0]
        old_end = listbox.size() - 1
        listbox.delete(listbox.curselection())
        new_end = listbox.size() - 1
        if curpos < new_end:
            set_listbox_selection(curpos)
        elif curpos >= new_end:
            set_listbox_selection(new_end)
        else:
            set_listbox_selection(0)
    else:
        warning_no_selection()
        return False
    if not listbox.size():
        listbox.insert(0, '')
        set_listbox_selection(0)


def clearclipboard():
    """Remove all lines from the list."""
    listbox.delete(0, 'end')
    listbox.insert(0, '')
    set_listbox_selection(0)


def moveitemup():
    """Move the selected line up one."""
    curpos, *_ = listbox.curselection()
    if isinstance(curpos, int) and curpos > 0:
        curtext = listbox.get(curpos)
        uppos = curpos - 1
        uptext = listbox.get(uppos)
        listbox.delete(uppos)
        listbox.insert(uppos, curtext)
        listbox.delete(curpos)
        listbox.insert(curpos, uptext)
        listbox.select_set(uppos)
        listbox.see(uppos)


def moveitemdown():
    """Move the selected line down one."""
    curpos, *_ = listbox.curselection()
    if isinstance(curpos, int) and curpos < (listbox.index('end') - 1):
        curtext = listbox.get(curpos)
        downpos = curpos + 1
        downtext = listbox.get(downpos)
        listbox.delete(downpos)
        listbox.insert(downpos, curtext)
        listbox.delete(curpos)
        listbox.insert(curpos, downtext)
        listbox.select_set(downpos)
        listbox.see(downpos)


def do_rightclickmenu(event):
    """Hook for right click in the list area."""
    rightclickmenu.post(event.x_root, event.y_root),


def childdismiss(child):
    """Close the insert and edit item child window."""
    child.grab_release()
    child.destroy()


def updatechildcombo(child, text, varsdict, myvarscmbs2):
    """Substitute the import template keywords from variables."""
    selectedvarsdict = {k: v.get() for k,v in zip(varsdict, myvarscmbs2)}
    fmttextlist = [
        x.format_map(selectedvarsdict) for x in text.splitlines()
        if not re.match(r'^[#;][^ a-zA-Z0-9]', x)
        ]
    listbox_text.set(fmttextlist)
    removeblanklines()
    set_listbox_selection(0)
    curline = listbox.get(listbox.curselection())
    if skipcommentlines.get() and re.match(r'^#', curline):
        if reversenextbool.get():
            cyclebackward()
        else:
            cycleforward()
    childdismiss(child)
    child.destroy()
    return True


def importwithoutvars(text):
    """Import a file and replace the list with its contents."""
    textlist = text.splitlines()
    textlist = [x for x in textlist if not re.match(r'^#[^ a-zA-Z0-9]',x)]
    listbox_text.set(textlist)
    removeblanklines()
    set_listbox_selection(0)
    curline = listbox.get(listbox.curselection())
    if skipcommentlines.get() and re.match(r'^#', curline):
        if reversenextbool.get():
            cyclebackward()
        else:
            cycleforward()


def importwithvars(text, varsdict):
    """Import a template and replace the list with its contents."""
    myvars = tk.Toplevel(root)
    myvars.title('Import list file with vars')
    mychild = ttk.Frame(myvars, padding=(2,2,2,2))
    mychild.grid(column=0, row=0, sticky='NWES')
    myvarslbls1 = []
    myvarslbls1.append(ttk.Label(mychild))
    myvarslbls1[-1].config(text='Variable')
    myvarslbls1[-1].grid(column=1, row=1, sticky='ES')
    myvarslbls1.append(ttk.Label(mychild))
    myvarslbls1[-1].config(text='Select from list')
    myvarslbls1[-1].grid(column=2, row=1, sticky='S')
    myvarslbls1.append(ttk.Label(mychild))
    myvarslbls1[-1].config(text='Manually specify')
    myvarslbls1[-1].grid(column=3, row=1, sticky='S')
    myvarslbls2 = []
    myvarscmbs2 = []
    myvarsstrs2 = []
    myvarsents2 = []
    for n, (keyss, values) in enumerate(varsdict.items(),2):
        myvarslbls2.append(ttk.Label(mychild))
        myvarslbls2[-1].config(text=f"{keyss}:")
        myvarslbls2[-1].grid(column=1, row=n, sticky='EN')
        myvarsstrs2.append(tk.StringVar(value=values[0]))
        myvarscmbs2.append(ttk.Combobox(mychild, justify='center'))
        myvarscmbs2[-1].config(textvariable=myvarsstrs2[-1])
        myvarscmbs2[-1].config(values=values)
        myvarscmbs2[-1].grid(column=2, row=n, sticky='WN')
        myvarsents2.append(ttk.Entry(mychild, justify='center'))
        myvarsents2[-1].config(textvariable=myvarsstrs2[-1])
        myvarsents2[-1].grid(column=3, row=n, sticky='WN')
    myvarsbtns1 = []
    myvarsbtns1.append(ttk.Button(mychild))
    myvarsbtns1[-1].config(text='Submit')
    myvarsbtns1[-1].config(
        command=lambda: updatechildcombo(myvars, text, varsdict, myvarscmbs2)
        )
    myvarsbtns1[-1].grid(column=1, columnspan=3, row=n+1, rowspan=3)
    myvarsbtns1[-1].grid(sticky='EWNS')
    myvars.bind('<Escape>', lambda event: childdismiss(myvars))
    myvars.bind('<Return>', lambda event: updatechildcombo(
        myvars, text, varsdict, myvarscmbs2
        ))
    for child in mychild.winfo_children():
        child.grid_configure(padx=2, pady=2)
    myvars.update()
    myvars.minsize(myvars.winfo_width(), myvars.winfo_height())
    myvars.maxsize(myvars.winfo_width(), myvars.winfo_height())
    myvars.grab_set()
    myvars.focus()
    myvars.wait_window()


def importfromfile(filename=''):
    """Import a file and replace the contents of the list."""
    if not filename:
        initialdir = pathlib.Path()
        filename = tkinter.filedialog.askopenfilename(
            #initialdir=initialdir,  # omit so last location is used
            defaultextension='.txt',
            filetypes=(('Text file', '.txt'), ('All files', '*.*'))
            )
    if not filename:
        return False
    importfile = pathlib.Path(filename)
    if importfile.exists():
        text = importfile.read_text()
    else:
        title = 'File does not exist'
        message = f"{importfile} does not exist"
        tk.messagebox.showwarning(title=title, message=message)
        return False
    # Search for variables in the import file
    # It is valid to have only a variable name and no values
    varsregex = re.compile(r'^## ?var:(?P<name>[^:=]+)[:=]?(?P<values>.*)?')
    varsmatch = [varsregex.match(t) for t in text.splitlines()]
    varsdict = {
        m['name'].strip(): m['values'].strip() if m['values'] else ''
        for m in varsmatch
        if m and m['name'] #and m['values']
        }
    varsdict = {
        k: [v.strip() or '' for v in v.split(',') ] #if v]
        for k,v in varsdict.items()
        }
    if varsdict:
        importwithvars(text, varsdict)
    elif not varsdict:
        importwithoutvars(text)
    else:
        return False


def set_listbox_selection(position):
    """Set the listbox selection and make it visible (scroll)"""
    listbox.selection_clear(0, 'end')
    listbox.selection_set(position)
    listbox.see(position)
    listbox.focus()
    listbox.activate(position)


def cycleforward():
    """Move the selection to the next item."""
    size = listbox.size()
    if not size:
        return False
    if not listbox.curselection():
        warning_no_selection()
        return False
    curpos = listbox.curselection()[0]
    end = size - 1
    if curpos < end:
        set_listbox_selection(curpos+1)
    if curpos == end:
        set_listbox_selection(0)
    curline = listbox.get(listbox.curselection())
    if skipcommentlines.get() and re.match(r'^#', curline):
        cycleforward()

def cyclebackward():
    """Move the selection to the previous item."""
    size = listbox.size()
    if not size:
        return False
    if not listbox.curselection():
        warning_no_selection()
        return False
    curpos = listbox.curselection()[0]
    if curpos > 0:
        set_listbox_selection(curpos-1)
    if curpos == 0:
        set_listbox_selection('end')
    curline = listbox.get(listbox.curselection())
    if skipcommentlines.get() and re.match(r'^#', curline):
        cyclebackward()


def checkcb():
    """Add items from the system clipboard to the list."""
    global lastcbvalue
    global hookcbid
    if pyperclip.paste().strip() != lastcbvalue:
        lastcbvalue = pyperclip.paste().strip()
        additem(lastcbvalue)
        lastcbvalue = ''
        pyperclip.copy('')
        if listbox.curselection():
            listbox.selection_clear(listbox.curselection()[0])
        listbox.select_set('end')
        listbox.see('end')
    hookcbid = root.after(10, checkcb)


def savelisttofile():
    """Save the current list to a file."""
    initialdir = pathlib.Path()
    filename = tkinter.filedialog.asksaveasfile(
        #initialdir=initialdir,  # omit so last location is used
        defaultextension='.txt',
        filetypes=(('Text file', '.txt'), ('All files', '*.*'))
        )
    if filename:
        filename.write('\n'.join(listbox.get(0, 'end')))
        filename.close()
    else:
        return False


def system_info():
    """Show system platform and keyboard backend used."""
    title = 'System Information'
    message = (
        f"Platform: {supported_platforms[userplatform]}\n"
        f"Keyboard backend: {bkend}\n")
    tkinter.messagebox.showinfo(title=title, message=message)


def about():
    """Show program name, version, and author."""
    title = 'About'
    message = (
        f"{__progname__}\n"
        f"Version: {__version__} ({__date__})\n"
        f"Author: {__author__}\n")
    tkinter.messagebox.showinfo(title=title, message=message)


def define_kybd_listener():
    """Create a keyboard listener. Return the listener object."""
    listener = pynput.keyboard.Listener(
        on_press=on_press,
        on_release=on_release,
        win32_event_filter=win32_event_filter,
        darwin_intercept=darwin_intercept,
        suppress=suppress,
        uinput_device_paths=uinput_device_paths,
        )
    return listener


def define_kybd_controller():
    """Create a keyboard controller. Return the controller object."""
    controller = threading.Thread(target=controller_worker, daemon=True)
    return controller


def start_keyboard_listener():
    """Start the keyboard listener on a separate thread."""
    if not listener.running:
        listener.start()


def start_keyboard_controller():
    """Start the keyboard controller on a separate thread."""
    if not controller.is_alive():
        controller.start()


def start_keyboard_threads():
    """Start the keyboard listener and controller."""
    global is_keyboard_hooked
    start_keyboard_listener()
    start_keyboard_controller()
    is_keyboard_hooked = True


def stop_keyboard_threads():
    """Stop the keyboard listener by setting a flag."""
    global is_keyboard_hooked
    is_keyboard_hooked = False


def toggle_keyboard_threads():
    """Toggle the state of the keyboard listener."""
    if is_keyboard_hooked:
        stop_keyboard_threads()
        togglekeyboard.set('Start keyboard listener')
    else:
        start_keyboard_threads()
        togglekeyboard.set('Stop keyboard listener')


def removeblanklines():
    """Remove blank lines from an imported file."""
    if allowblankline.get():
        # blank lines are allowed, nothing to do,
        # can't add back in blank lines
        pass
    else:
        tmpl = [x for x in listbox.get(0, 'end') if x]
        if tmpl == list(listbox.get(0, 'end')):
            # no need to remove blank lines or change my curpos
            pass
        else:
            listbox.delete(0, 'end')
            listbox.insert(0, *tmpl)
            set_listbox_selection(0)


def jumpovercommentlines():
    """Move the cursor while skipping over comment lines."""
    curline = listbox.get(listbox.curselection())
    if skipcommentlines.get() and re.match('^#', curline):
        if reversenextbool.get():
            cyclebackward()
        else:
            cycleforward()


def list_input_devices():
    """Return a list of all input devices on Linux."""
    import evdev
    return evdev.list_devices()


def detect_keyboard_window(timeout_seconds):
    """Window for detecting the user's keyboard on Linux."""
    main = tk.Tk()
    main.geometry('400x150')
    main.title('Detecting keyboard')
    text = (
        'Determining keyboard device id\n\n'
        f"Timeout set to {timeout_seconds} seconds\n\n"
        'Press ENTER')
    label = ttk.Label(main, justify='center', text=text)
    label.pack(pady=10)
    main.protocol('WM_DELETE_WINDOW', quit_detect_keyboard_window)
    main.update()
    main.minsize(main.winfo_width(), main.winfo_height())
    main.focus_force()
    return main


def quit_detect_keyboard_window():
    """If the user closes the keyboard detect window set a flag"""
    global exit_flag
    exit_flag = True


def detect_keyboard():
    """Detect the user's keyboard interactively on Linux."""
    import evdev
    import select
    global exit_flag
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    timeout_seconds = 10
    exit_flag = False
    main = detect_keyboard_window(timeout_seconds)
    time_timeout = time.time() + timeout_seconds
    while not exit_flag:
        main.update()
        if time.time() > time_timeout:
            print('Timed out.')
            return False
        rlist, wlist, xlist = select.select(devices, [], [], )
        for device in rlist:
            for key, code in device.active_keys(verbose=True):
                if key == 'KEY_ENTER':
                    print(device.name, device.path, sep='\n')
                    device_path = list()
                    device_path.append(device.path)
                    main.destroy()
                    return device_path


if __name__ == '__main__':
    # Start of main program
    parser = parse_arguments()
    args = parser.parse_args()
    supported_platforms = {
        'win32': 'Windows',
        'linux': 'Linux',
        'darwin': 'macOS'
        }
    userplatform = sys.platform
    if userplatform == 'win32':
        # Microsoft Windows platforms
        bkend = 'win32'
    elif userplatform == 'darwin':
        import Quartz
        # Apple macOS platforms
        bkend = 'darwin'
        rootuser = True if shutil.os.geteuid() == 0 else False
        if rootuser:
            print("Running with root user permissions")
    elif userplatform == 'linux':
        # Linux platforms
        # Keyboard backends determined by desktop environment
        # xorg backend for x11 DE
        # uinput for wayland DE or no DE
        rootuser = True if shutil.os.geteuid() == 0 else False
        if rootuser:
            print("Running with root user permissions")
        try:
            window_system = os.getenv('XDG_SESSION_TYPE')
        except:
            window_system = None
        if args.backend == 'xorg' or window_system == 'x11':
            bkend = 'xorg'
            os.environ['PYNPUT_BACKEND'] = 'xorg'
        elif args.backend == 'uinput' or window_system in ('wayland', None):
            bkend = 'uinput'
            #uinput_device_paths = ['/dev/event/input2']  # example device
            if args.detect_keyboard:
                uinput_device_paths = detect_keyboard()
            else:
                uinput_device_paths = list_input_devices()
            if not uinput_device_paths:
                sys.exit(1)
            os.environ['PYNPUT_BACKEND_KEYBOARD'] = 'uinput'
            os.environ['PYNPUT_BACKEND_MOUSE'] = 'dummy'
        else:
            title = 'Unsupported Window System'
            message = (
                'Window system could not be determined. '
                'Supported values are xorg and wayland.'
                )
            tk.messagebox.showwarning(title=title, message=message)
            sys.exit(1)
    else:
        title = 'Unsupported platform'
        message = (
            'Sorry, your platform is not supported: '
            f"`{supported_platforms[userplatform]}`.\n"
            'Supported platforms: '
            f"{', '.join(supported_platforms.values())}"
            )
        tk.messagebox.showwarning(title=title, message=message)

    # import 3rd party module pynput
    # after defining the keyboard backend using OS environmental variables
    import pynput

    Key = pynput.keyboard.Key
    # define the macro keys as F1 through F20
    keydict = {f'F{n+1}': f'f{n+1}' for n in range(20)}
    keylist = list(keydict.keys())
    lastcbvalue = ''
    hookcbid = ''
    test_listbox_text = [f'sample text {x+1:02d}' for x in range(25)]
    if not 'uinput_device_paths' in locals():
        uinput_device_paths = None
    suppress = False
    if userplatform == 'win32':
        suppress = True
    if userplatform == 'darwin':
        suppress = True

    # Start of tkinter GUI section
    root = tk.Tk()
    root.title(__progname__)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    mygui = ttk.Frame(root, padding=(2,2,2,2))
    mygui.grid(column=0, row=0, sticky='NSWE')
    mygui.columnconfigure(6, weight=1)
    mygui.rowconfigure(15, weight=1)
    ui_objs = list()

    # Main menu bar
    mainmenu = tk.Menu(root, tearoff=False)

    ## Main menu - File
    mainmenu_file = tk.Menu(mainmenu, tearoff=False)
    mainmenu_file_items = [
        ('Import template or file', importfromfile),
        ('Save list to file', savelisttofile),
        ]
    for label, command in mainmenu_file_items:
        mainmenu_file.add_command(label=label, command=command)
    mainmenu_file.add_separator()
    mainmenu_file.add_command(label='Exit', command=root.destroy)
    mainmenu.add_cascade(label='File', menu=mainmenu_file)

    ## Main menu - Actions
    mainmenu_actions = tk.Menu(mainmenu, tearoff=False)
    mainmenu_actions_items = [
        ('Copy selected', copy_item),
        ('Copy selected + Advance', copy_gonext),
        ('Edit selected', edit_item_window),
        ('Insert before selected', insert_item_before_window),
        ('Insert after selected', insert_item_after_window),
        ('Move selected up', moveitemup),
        ('Move selected down', moveitemdown),
        ('Delete selected', removeitem),
        ('Delete all items', clearclipboard),
        ]
    for label, command in mainmenu_actions_items:
        mainmenu_actions.add_command(label=label, command=command)
    mainmenu.add_cascade(label='Actions', menu=mainmenu_actions)

    ## Main menu - Options
    mainmenu_options = tk.Menu(mainmenu, tearoff=False)
    skipcommentlines = tk.BooleanVar(value=True)
    allowblankline = tk.BooleanVar(value=False)
    reversenextbool = tk.BooleanVar(value=False)
    mainmenu_options_items = [
        ('Skip over comment lines', skipcommentlines, jumpovercommentlines),
        ('Allow blank lines in import', allowblankline, removeblanklines),
        ('Reverse direction of advance', reversenextbool, None),
        ]
    for l, v, c in mainmenu_options_items:
        mainmenu_options.add_checkbutton(label=l, variable=v, command=c)
    mainmenu.add_cascade(label='Options', menu=mainmenu_options)

    ## Main menu - Help
    mainmenu_help = tk.Menu(mainmenu, tearoff=False)
    mainmenu_help_items = [('System Info', system_info), ('About', about)]
    for label, command in mainmenu_help_items:
        mainmenu_help.add_command(label=label, command=command)
    mainmenu.add_cascade(label='Help', menu=mainmenu_help)

    ## Main menu draw
    root.config(menu=mainmenu)

    # `Type & Advance` label and combobox
    forward = tk.StringVar(value='F3')
    ui_obj = ttk.Label(mygui)
    ui_obj.config(text='`Type & Advance` Key')
    ui_obj.grid(column=1, row=1, sticky='E')
    ui_objs.append(ui_obj)
    ui_obj = ttk.Combobox(mygui)
    ui_obj.config(textvariable=forward, values=keylist, width=5)
    ui_obj.config(state='readonly')
    ui_obj.grid(column=2, row=1, sticky='WE')
    ui_obj.bind('<<ComboboxSelected>>', lambda event: update_macro_keys())
    ui_objs.append(ui_obj)

    # `Type & Stay` label and combobox
    repeat = tk.StringVar(value='F4')
    ui_obj = ttk.Label(mygui)
    ui_obj.config(text='`Type & Stay` Key')
    ui_obj.grid(column=1, row=2, sticky='E')
    ui_objs.append(ui_obj)
    ui_obj = ttk.Combobox(mygui)
    ui_obj.config(textvariable=repeat, values=keylist, width=5)
    ui_obj.config(state='readonly')
    ui_obj.grid(column=2, row=2, sticky='WE')
    ui_obj.bind('<<ComboboxSelected>>', lambda event: update_macro_keys())
    ui_objs.append(ui_obj)

    # `Move to previous line` label and combobox
    selprev = tk.StringVar(value='F5')
    ui_obj = ttk.Label(mygui)
    ui_obj.config(text='Move to previous line')
    ui_obj.grid(column=3, row=1, sticky='E')
    ui_objs.append(ui_obj)
    ui_obj = ttk.Combobox(mygui)
    ui_obj.config(textvariable=selprev, values=keylist, width=5)
    ui_obj.config(state='readonly')
    ui_obj.grid(column=4, row=1, sticky='WE')
    ui_obj.bind('<<ComboboxSelected>>', lambda event: update_macro_keys())
    ui_objs.append(ui_obj)

    # `Move to next line` label and combobox
    selnext = tk.StringVar(value='F6')
    ui_obj = ttk.Label(mygui)
    ui_obj.config(text='Move to next line')
    ui_obj.grid(column=3, row=2, sticky='E')
    ui_objs.append(ui_obj)
    ui_obj = ttk.Combobox(mygui)
    ui_obj.config(textvariable=selnext, values=keylist, width=5)
    ui_obj.config(state='readonly')
    ui_obj.grid(column=4, row=2, sticky='WE')
    ui_obj.bind('<<ComboboxSelected>>', lambda event: update_macro_keys())
    ui_objs.append(ui_obj)

    # `Start/Stop keyboard listener` button
    if userplatform == 'darwin' and not sys.flags.interactive:
        is_keyboard_hooked = True
        # Must start with program or it will crash when starting listener
    else:
        is_keyboard_hooked = False
        # It is better security to let the user start the keyboard listener
    value = f"{'Stop' if is_keyboard_hooked else 'Start'} keyboard listener"
    togglekeyboard = tk.StringVar(value=value)
    ui_obj = ttk.Button(mygui)
    ui_obj.config(textvariable=togglekeyboard)
    ui_obj.config(command=toggle_keyboard_threads)
    ui_obj.grid(column=5, row=1, sticky='NSWE')
    ui_objs.append(ui_obj)
    keyboard_listener_button = ui_obj

    # Hook clipboard checkbox
    hookcb = tk.BooleanVar(value=False)
    ui_obj = ttk.Checkbutton(mygui)
    ui_obj.config(text='Hook Clipboard')
    ui_obj.config(variable=hookcb)
    ui_obj.config(command=hookclipboard)
    ui_obj.grid(column=5, row=2, sticky='WE')
    ui_objs.append(ui_obj)

    # Text List (The data to be typed)
    listbox_text = tk.StringVar(value=test_listbox_text)
    selectmode = (tk.BROWSE, tk.EXTENDED, tk.SINGLE, tk.MULTIPLE)[2]
    activestyle = (tk.UNDERLINE, tk.DOTBOX, tk.NONE)[2]
    ui_obj = tk.Listbox(mygui, selectmode=selectmode)
    ui_obj.config(listvariable=listbox_text, height=15)
    ui_obj.config(exportselection=False, activestyle=activestyle)
    ui_obj.grid(column=1, columnspan=6, row=3, rowspan=15, sticky='NSWE')
    ui_obj.bind('<Button-3>', do_rightclickmenu)
    ui_obj.bind('<Double-1>', lambda event: copy_item())
    ui_obj.bind('<Triple-1>', lambda event: edit_item_window())
    ui_obj.bind('<Up>', lambda event: cyclebackward())
    ui_obj.bind('<Down>', lambda event: cycleforward())
    ui_obj.bind('<Return>', lambda event: copy_gonext())
    ui_obj.bind('<Delete>', lambda event: removeitem())
    ui_obj.bind('<Control-Return>', lambda event: toggle_keyboard_threads())
    ui_obj.bind('<Control-e>', lambda event: edit_item_window())
    ui_obj.bind('<Control-i>', lambda event: insert_item_after_window())
    ui_obj.bind('<Control-o>', lambda event: importfromfile())
    ui_obj.bind('<Control-s>', lambda event: savelisttofile())
    ui_objs.append(ui_obj)
    listbox = ui_obj
    set_listbox_selection(0)

    # Right click menu for copy and select all
    rightclickmenu = tk.Menu(listbox, tearoff=False)
    rightclickmenu_items = mainmenu_actions_items
    for label, command in rightclickmenu_items:
        rightclickmenu.add_command(label=label, command=command)
    ui_objs.append(rightclickmenu)

    # Scroll bar for the Text List
    scrollbar = ttk.Scrollbar(mygui)
    scrollbar.config(orient=tk.VERTICAL, command=listbox.yview)
    scrollbar.grid(column=7, row=3, rowspan=20, sticky='NSWE')
    listbox['yscrollcommand'] = scrollbar.set
    ui_objs.append(scrollbar)

    # main text list box and scroll bar padding
    for child in mygui.winfo_children():
        child.grid_configure(padx=2, pady=2)
    listbox.grid_configure(padx=(2,0))
    scrollbar.grid_configure(padx=(0,2))

    root.update()
    root.minsize(root.winfo_width(), root.winfo_height())

    update_macro_keys()
    keyboard_queue = queue.Queue()
    listener = define_kybd_listener()
    controller = define_kybd_controller()

    if userplatform == 'darwin':
        print(f"{listener.IS_TRUSTED=}")

    if is_keyboard_hooked:
        start_keyboard_listener()
        start_keyboard_controller()

    if args.filename:
        importfromfile(args.filename)

    if not sys.flags.interactive:
        root.mainloop()
    else:
        print('Running in interactive mode.\nKeyboard listener is disabled.')
        keyboard_listener_button.config(state='disabled')
        listbox.unbind('<Control-Return>')
