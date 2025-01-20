#!/usr/bin/env python3
"""Create or import a text list and type & copy the each line via a
keyboard hotkey.
Text can be inserted from a file or from the system clipboard.
The Import file option includes a feature to take a template file and
replace keywords with user provided values.
The list cycles back around to the top after the last command.
"""

__progname__ = 'Type Lines'
__version__ = '0.0.12'
__date__ = '2025-01-19'
__author__ = 'Todd Wintermute'

import argparse
import os
import pathlib
import re
import shutil
import sys
import tkinter as tk
import tkinter.filedialog
import tkinter.messagebox
import tkinter.ttk as ttk

# 3rd party module
import pyperclip

# 3rd party modules imported at a later time
# pynput

# 3rd party modules imported at a later time (Linux only):
# evdev


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
    if key == Key[keylist[forward.get()]]:
        if reversenextbool.get():
            typeline_gobackward()
        else:
            typeline_goforward()
    elif key == Key[keylist[repeat.get()]]:
        typeline()
    elif key == Key[keylist[selnext.get()]]:
        if reversenextbool.get():
            cyclebackward()
        else:
            cycleforward()
    elif key == Key[keylist[selprev.get()]]:
        if reversenextbool.get():
            cycleforward()
        else:
            cyclebackward()
    else:
        pass


def on_release(key):
    """Assigned to the keyboard listener on_release option."""
    if not is_keyboard_hooked:
        return True


def win32_event_filter(msg, data):
    """Windows specific function to suppress specific key presses."""
    global listener
    if (msg == 0x0100 or msg == 0x0101) and (
        data.vkCode == keydict[keylist[forward.get()]] or
        data.vkCode == keydict[keylist[repeat.get()]] or
        data.vkCode == keydict[keylist[selnext.get()]] or
        data.vkCode == keydict[keylist[selprev.get()]]
        ): # Key Down/Up & selected keys
        listener._suppress = True
    else:
        listener._suppress = False
        return True


def darwin_intercept(event_type, event):
    """macOS specific function to suppress specific key presses."""
    import Quartz
    length, chars = Quartz.CGEventKeyboardGetUnicodeString(
        event, 100, None, None)
    if length > 0 and any([
            #chars == '\x10',  # Not sure, but seemed to work
            chars == keylist[forward.get()],
            chars == keylist[repeat.get()],
            chars == keylist[selnext.get()],
            chars == keylist[selprev.get()],
            ]):
        # Suppress keyboard hotkeys
        return None
    else:
        return event


def typeline():
    """Type the current selected line and copy value to clipboard."""
    try:
        curseltxt = listbox.get(listbox.curselection())
        controller.type(curseltxt)
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


def updatetypenextkey():
    """Reset selection to first item when hotkey is changed."""
    tmplist = list(listbox.get(0, "end"))
    if not tmplist:
        return False
    listbox.selection_set(0)
    listbox.see(0)


def updaterepeatkey():
    """Reset selection to first item when hotkey is changed."""
    tmplist = list(listbox.get(0, "end"))
    if not tmplist:
        return False
    listbox.selection_set(0)
    listbox.see(0)


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
    listbox.insert(pos+1, text)
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
    title = "No selection"
    message = "No line selected. Select a line first."
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
    mychild.grid(column=0, row=0, sticky="NWES")
    lbl1 = ttk.Label(mychild)
    lbl1.config(text='Item:')
    lbl1.grid(column=1, row=1, sticky="S")
    ent1 = ttk.Entry(mychild, justify='center')
    str1 = tk.StringVar(value=curtext) #def first var
    ent1.config(textvariable=str1, width=66)
    ent1.icursor('end')
    ent1.grid(column=1, row=2, sticky="WE")
    btn1 = ttk.Button(mychild)
    btn1.config(text="Submit")
    btn1.config(command=(lambda: submit_edit_item(
        myedit, ent1.get(), curpos
        )))
    btn1.grid(column=1, row=3, sticky="EWNS")
    myedit.bind("<Escape>", lambda event: childdismiss(myedit))
    myedit.bind("<Return>", lambda event: submit_edit_item(
        myedit, ent1.get(), curpos
        ))
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
        listbox.insert("end", line)
    removeblanklines()


def insert_item_before_window():
    """Add a new item to the list before the selection."""
    insert_item_window(before_or_after='before')
    # windows puts curos at start of edit text???


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
    mychild.grid(column=0, row=0, sticky="NWES")
    lbl1 = ttk.Label(mychild)
    lbl1.config(text='Item:')
    lbl1.grid(column=1, row=1, sticky="S")
    ent1 = ttk.Entry(mychild, justify='center')
    str1 = tk.StringVar() #def first var
    ent1.config(textvariable=str1)
    ent1.config(width=66)
    ent1.grid(column=1, row=2, sticky="WE")
    btn1 = ttk.Button(mychild)
    btn1.config(text="Submit")
    btn1.config(command=(lambda: submit(myinsert, ent1.get())))
    btn1.grid(column=1, row=3)
    btn1.grid(sticky="EWNS")
    myinsert.bind("<Escape>", lambda event: childdismiss(myinsert))
    myinsert.bind("<Return>", lambda event: submit(myinsert, ent1.get()))
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
        # Remove multiple rows (not allowed to select multiple currently)
        if len(selected) > 1:
            for row in selected[::-1]:
                listbox.delete(row)
            return True
        curpos = listbox.curselection()[0]
        listbox.delete(listbox.curselection())
        if curpos < len(listbox.get(0, "end")):
            listbox.selection_set(curpos)
            listbox.see(curpos)
        elif curpos >= len(listbox.get(0, "end")):
            listbox.selection_set(len(listbox.get(0, "end"))-1)
            listbox.see(curpos)
        else:
            listbox.selection_set(0)
            listbox.see(0)
    else:
        return False
        warning_no_selection()
    if not len(listbox.get(0, 'end')):
        listbox.insert(0, "")
        listbox.selection_set(0)
        listbox.see(0)


def clearclipboard():
    """Remove all lines from the list."""
    listbox.delete(0, "end")
    listbox.insert(0, "")
    listbox.selection_set(0)
    listbox.see(0)


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
    #if listbox.curselection():
    #    listbox.selection_clear(listbox.curselection())
    listbox.selection_clear(0, 'end')
    listbox.selection_set(0)
    listbox.see(0)
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
    #if listbox.curselection():
    #    listbox.selection_clear(listbox.curselection())
    listbox.selection_clear(0, 'end')
    listbox.selection_set(0)
    listbox.see(0)
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
    mychild.grid(column=0, row=0, sticky="NWES")
    myvarslbls1 = []
    myvarslbls1.append(ttk.Label(mychild))
    myvarslbls1[-1].config(text='Variable')
    myvarslbls1[-1].grid(column=1, row=1, sticky="ES")
    myvarslbls1.append(ttk.Label(mychild))
    myvarslbls1[-1].config(text='Select from list')
    myvarslbls1[-1].grid(column=2, row=1, sticky="S")
    myvarslbls1.append(ttk.Label(mychild))
    myvarslbls1[-1].config(text='Manually specify')
    myvarslbls1[-1].grid(column=3, row=1, sticky="S")
    myvarslbls2 = []
    myvarscmbs2 = []
    myvarsstrs2 = []
    myvarsents2 = []
    for n, (keyss, values) in enumerate(varsdict.items(),2):
        myvarslbls2.append(ttk.Label(mychild))
        myvarslbls2[-1].config(text=f"{keyss}:")
        myvarslbls2[-1].grid(column=1, row=n, sticky="EN")
        myvarsstrs2.append(tk.StringVar(value=values[0])) #def first var
        myvarscmbs2.append(ttk.Combobox(mychild, justify='center'))
        myvarscmbs2[-1].config(textvariable=myvarsstrs2[-1])
        myvarscmbs2[-1].config(values=values)
        myvarscmbs2[-1].grid(column=2, row=n, sticky="WN")
        myvarsents2.append(ttk.Entry(mychild, justify='center'))
        myvarsents2[-1].config(textvariable=myvarsstrs2[-1])
        myvarsents2[-1].grid(column=3, row=n, sticky="WN")
    myvarsbtns1 = []
    myvarsbtns1.append(ttk.Button(mychild))
    myvarsbtns1[-1].config(text="Submit")
    myvarsbtns1[-1].config(command=( lambda: updatechildcombo(
        myvars, text, varsdict, myvarscmbs2
        )))
    myvarsbtns1[-1].grid(column=1, columnspan=3, row=n+1, rowspan=3)
    myvarsbtns1[-1].grid(sticky="EWNS")
    myvars.bind("<Escape>", lambda event: childdismiss(myvars))
    myvars.bind("<Return>", lambda event: updatechildcombo(
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
        filename = tkinter.filedialog.askopenfilename(initialdir=initialdir)
    if not filename:
        return False
    importfile = pathlib.Path(filename)
    if importfile.exists():
        text = importfile.read_text()
    else:
        title = "File does not exist"
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


def cycleforward():
    """Move the selection to the next item."""
    tmplist = list(listbox.get(0, "end"))
    if not tmplist: return
    if not listbox.curselection():
        return False
    curpos = listbox.curselection()[0]
    if curpos < len(tmplist) - 1:
        listbox.selection_clear(curpos)
        listbox.selection_set(curpos+1)
        listbox.see(curpos+1)
    if curpos == len(tmplist) - 1:
        listbox.select_clear(curpos)
        listbox.selection_set(0)
        listbox.see(0)
    curline = listbox.get(listbox.curselection())
    if skipcommentlines.get() and re.match(r'^#', curline):
        cycleforward()


def cyclebackward():
    """Move the selection to the previous item."""
    tmplist = list(listbox.get(0, "end"))
    if not tmplist: return
    if not listbox.curselection():
        return False
    curpos = listbox.curselection()[0]
    if curpos > 0:
        listbox.selection_clear(curpos)
        listbox.selection_set(curpos-1)
        listbox.see(curpos-1)
    if curpos == 0:
        listbox.select_clear(curpos)
        listbox.selection_set(len(tmplist) - 1)
        listbox.see(len(tmplist) - 1)
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
        listbox.select_set("end")
        listbox.see("end")
    hookcbid = root.after(10, checkcb)


def savelisttofile():
    """Save the current list to a file."""
    filename = tkinter.filedialog.asksaveasfile(initialdir=".")
    if filename:
        filename.write('\n'.join(listbox.get(0,"end")))
        filename.close()
    else:
        return False


def system_info():
    """Show system platform and keyboard backend used."""
    title = "System Information"
    message = (
        f"Platform: {supported_platforms[userplatform]}\n"
        f"Keyboard backend: {bkend}\n")
    tkinter.messagebox.showinfo(title=title, message=message)


def about():
    """Show program name, version, and author."""
    title = "About"
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
        uinput_device_paths=uinput_device_paths)
    return listener


def startkeyboardlistener():
    """Start the keyboard listener."""
    global is_keyboard_hooked
    global listener
    if 'listener' in globals():
        if not listener.running:
            listener.start()  # start to listen on a separate thread
        is_keyboard_hooked = True
    else:
        listener = define_kybd_listener()
        startkeyboardlistener()


def stopkeyboardlistener():
    """Stop the keyboard listener."""
    global is_keyboard_hooked
    if 'listener' in globals():
        is_keyboard_hooked = False
    else:
        return False


def togglekeyboardlistener():
    """Toggle the state of the keyboard listener."""
    global listener
    if 'listener' in globals():
        if is_keyboard_hooked:
            stopkeyboardlistener()
            togglekeyboard.set("Start keyboard listener")
        else:
            startkeyboardlistener()
            togglekeyboard.set("Stop keyboard listener")
    else:
        listener = define_kybd_listener()
        togglekeyboardlistener()


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
            listbox.delete(0, "end")
            listbox.insert(0, *tmpl)
            listbox.selection_set(0)
            listbox.see(0)


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
    label = ttk.Label(main, justify="center", text=text)
    label.pack(pady=10)
    main.protocol("WM_DELETE_WINDOW", quit_detect_keyboard_window)
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
    import time
    global exit_flag
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    timeout_seconds = 10
    exit_flag = False
    main = detect_keyboard_window(timeout_seconds)
    time_timeout = time.time() + timeout_seconds
    #while True:
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


if __name__ == "__main__":
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
        # Apple macOS platforms
        bkend = 'darwin'
        rootuser = True if shutil.os.geteuid() == 0 else False
        if rootuser:
            print("I see you're running as root.")
        else:
            print("On macOS you should run as root: ", end='')
            print("`sudo -E python3 ./typelines.py`")
    elif userplatform == 'linux':
        # Linux platforms
        # Keyboard backends determined by desktop environment
        # xorg backend for x11 DE
        # uinput for wayland DE or no DE
        rootuser = True if shutil.os.geteuid() == 0 else False
        if rootuser:
            print("I see you're running as root.")
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
            title = "Unsupported Window System"
            message = (
                'Window system could not be determined. '
                'Supported values are xorg and wayland.'
                )
            tk.messagebox.showwarning(title=title, message=message)
            sys.exit(1)
    else:
        title = "Unsupported platform"
        message = (
            "Sorry, your platform is not supported: "
            f"`{supported_platforms[userplatform]}`.\n"
            "Supported platforms: "
            f"{', '.join(supported_platforms.values())}"
            )
        tk.messagebox.showwarning(title=title, message=message)

    # import 3rd party module pynput
    # after defining the keyboard backend using OS environmental variables
    import pynput

    Key = pynput.keyboard.Key
    # define the keylist as F1 through F20
    keylist = {f'f{n+1}': f'f{n+1}' for n in range(20)}
    keydict = {
        # keydict is only used in the win32_event_filter
        key.name: key.value.vk for key in pynput.keyboard.Key
        if key.name in keylist
        }
    keyforward = 'f3'
    keyrepeat = 'f4'
    keyselprev = 'f5'
    keyselnext = 'f6'
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
    mygui.grid(column=0, row=0, sticky="NSWE")
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
    mainmenu_file.add_command(label="Exit", command=root.destroy)
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
    forward = tk.StringVar(value=keyforward)
    ui_obj = ttk.Label(mygui)
    ui_obj.config(text="`Type & Advance` Key")
    ui_obj.grid(column=1, row=1, sticky="E")
    ui_objs.append(ui_obj)
    ui_obj = ttk.Combobox(mygui)
    ui_obj.config(textvariable=forward, values=list(keylist), width=5)
    ui_obj.grid(column=2, row=1, sticky="WE")
    ui_obj.bind('<<ComboboxSelected>>', lambda e: updatetypenextkey())
    ui_objs.append(ui_obj)

    # `Type & Stay` label and combobox
    repeat = tk.StringVar(value=keyrepeat)
    ui_obj = ttk.Label(mygui)
    ui_obj.config(text="`Type & Stay` Key")
    ui_obj.grid(column=1, row=2, sticky="E")
    ui_objs.append(ui_obj)
    ui_obj = ttk.Combobox(mygui)
    ui_obj.config(textvariable=repeat, values=list(keylist), width=5)
    ui_obj.grid(column=2, row=2, sticky="WE")
    ui_obj.bind('<<ComboboxSelected>>', lambda e: updaterepeatkey())
    ui_objs.append(ui_obj)

    # `Move to previous line` label and combobox
    selprev = tk.StringVar(value=keyselprev)
    ui_obj = ttk.Label(mygui)
    ui_obj.config(text="Move to previous line")
    ui_obj.grid(column=3, row=1, sticky="E")
    ui_objs.append(ui_obj)
    ui_obj = ttk.Combobox(mygui)
    ui_obj.config(textvariable=selprev, values=list(keylist), width=5)
    ui_obj.grid(column=4, row=1, sticky="WE")
    ui_obj.bind('<<ComboboxSelected>>', lambda e: cyclebackward())
    ui_objs.append(ui_obj)

    # `Move to next line` label and combobox
    selnext = tk.StringVar(value=keyselnext)
    ui_obj = ttk.Label(mygui)
    ui_obj.config(text="Move to next line")
    ui_obj.grid(column=3, row=2, sticky="E")
    ui_objs.append(ui_obj)
    ui_obj = ttk.Combobox(mygui)
    ui_obj.config(textvariable=selnext, values=list(keylist), width=5)
    ui_obj.grid(column=4, row=2, sticky="WE")
    ui_obj.bind('<<ComboboxSelected>>', lambda e: cycleforward())
    ui_objs.append(ui_obj)

    # `Start/Stop keyboard listener` button
    if userplatform == 'darwin':
        is_keyboard_hooked = True
        # Must start with program or it will crash when starting listener
    else:
        is_keyboard_hooked = False
        # It is better security to let the user start the keyboard listener
    value = f"{'Stop' if is_keyboard_hooked else 'Start'} keyboard listener"
    togglekeyboard = tk.StringVar(value=value)
    ui_obj = ttk.Button(mygui)
    ui_obj.config(textvariable=togglekeyboard)
    ui_obj.config(command=togglekeyboardlistener)
    ui_obj.grid(column=5, row=1, sticky="NSWE")
    ui_objs.append(ui_obj)

    # Hook clipboard checkbox
    hookcb = tk.BooleanVar(value=False)
    ui_obj = ttk.Checkbutton(mygui)
    ui_obj.config(text="Hook Clipboard")
    ui_obj.config(variable=hookcb)
    ui_obj.config(command=hookclipboard)
    ui_obj.grid(column=5, row=2, sticky="WE")
    ui_objs.append(ui_obj)

    # Text List (The data to be typed)
    listbox_text = tk.StringVar(value=test_listbox_text)
    selectmode = (tk.BROWSE, tk.EXTENDED, tk.SINGLE, tk.MULTIPLE)[2]
    listbox = tk.Listbox(mygui, selectmode=selectmode)
    listbox.config(listvariable=listbox_text, height=15)
    listbox.config(exportselection=False)
    listbox.grid(column=1, columnspan=6, row=3, rowspan=15, sticky="NSWE")
    listbox.selection_set(0)
    listbox.see(0)
    listbox.bind("<Double-1>", lambda event: copy_item())
    listbox.bind("<Triple-1>", lambda event: edit_item_window())
    listbox.bind("<Return>", lambda event: copy_gonext())
    listbox.bind("<Delete>", lambda event: removeitem())
    listbox.bind("<Button-3>", do_rightclickmenu)
    ui_objs.append(listbox)

    # Right click menu for copy and select all
    rightclickmenu = tk.Menu(listbox, tearoff=False)
    rightclickmenu_items = mainmenu_actions_items
    for label, command in rightclickmenu_items:
        rightclickmenu.add_command(label=label, command=command)
    ui_objs.append(rightclickmenu)

    # Scroll bar for the Text List
    scrollbar = ttk.Scrollbar(mygui)
    scrollbar.config(orient=tk.VERTICAL, command=listbox.yview)
    scrollbar.grid(column=7, row=3, rowspan=20, sticky="NSWE")
    listbox['yscrollcommand'] = scrollbar.set
    ui_objs.append(scrollbar)

    # main text list box and scroll bar padding
    for child in mygui.winfo_children():
        child.grid_configure(padx=2, pady=2)
    listbox.grid_configure(padx=(2,0))
    scrollbar.grid_configure(padx=(0,2))

    root.update()
    root.minsize(root.winfo_width(), root.winfo_height())

    controller = pynput.keyboard.Controller()
    listener = define_kybd_listener()

    if userplatform == 'darwin' and 'listener' in globals():
        print(f"{listener.IS_TRUSTED=}")

    if is_keyboard_hooked:
        startkeyboardlistener()

    if args.filename:
        importfromfile(args.filename)

    root.mainloop()
