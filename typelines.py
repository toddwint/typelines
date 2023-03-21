#!/usr/bin/env python3
#!python3
"""
Cross platform compatible application (Windows, Linux, and macOS).
Create a text list and type the text line by line using a hotkey.
Commands can be captured from a text file or from the system clipboard.
There is an import option that allows vars in the file to be replaced with 
values the user enters at a prompt.
The list will cycle back around to the top after the last command which 
makes it easy to type a bunch of commands on many devices.
"""

__progname__ = 'Type Lines'
__author__ = 'Todd Wintermute'
__version__ = '0.0.10'
__date__ = '2023-03-17'

import pathlib
import queue
import re
import shutil
import subprocess
import sys
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.ttk, tkinter.messagebox, tkinter.filedialog

# 3rd party module
import pyperclip

def on_press(key):
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
        pass # Nothing to do, Abe.

def on_release(key):
    pass 

def on_press_darwin(key):
    keysqueue.put(('press', key))

def on_release_darwin(key):
    keysqueue.put(('release', key))

def typeit_darwin():
    if not keysqueue.empty():
        action, key = keysqueue.get()
        if key == Key[keylist[forward.get()]]:
            if action == 'press':
                if reversenextbool.get():
                    typeline_gobackward()
                else:
                    typeline_goforward()
        elif key == Key[keylist[repeat.get()]]:
            if action == 'press':
                typeline()
        elif key == Key[keylist[selnext.get()]]:
            if action == 'press':
                if reversenextbool.get():
                    cyclebackward()
                else:
                    cycleforward()
        elif key == Key[keylist[selprev.get()]]:
            if action == 'press':
                if reversenextbool.get():
                    cycleforward()
                else:
                    cyclebackward()
        elif suppress:
            if action == 'press':
                controller.press(key)
            elif action == 'release':
                controller.release(key)
            else:
                print(action, key)
        else:
            pass # Nothing to do, Abe.
    root.after(15, typeit_darwin)

"""
<https://github.com/moses-palmer/pynput/issues/170>
Windows has an event filter to suppress/block specific keys
<https://docs.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes>
Mac OS does too
Linux is a bit difficult. Either suppress all keys and manage all events
 or don't. There is no filtering on individual keys.
 Also, the backends are xorg and uinput. Xorg requires an X11 system or
 an XWayland program. uinput requires root permissions.
 The terminal on Ubuntu 22.04 is Wayland. I want to use the terminal.
 The options are switch over to Xorg login or use a program that uses
 XWayland. I settled on XWayland via a terminal inside of firefox with the
 tool [ttyd](https://github.com/tsl0922/ttyd). Firefox is still XWayland.
 You can verify this using the program `xeyes` from the package `x11-apps`.
 I am currently not suppressing keys on linux. 
 For my use, it works without suppressing keys.
 When Wayland has the features needed and pynput is updated to include
 these features this program should be updated to use those instead.
"""

def win32_event_filter(msg, data):
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
    import Quartz
    length, chars = Quartz.CGEventKeyboardGetUnicodeString(
        event, 100, None, None)
    if length > 0 and (
        chars == '\x10' or # hack; value received is always \x10
        chars == keylist[forward.get()] or 
        chars == keylist[repeat.get()] or
        chars == keylist[selnext.get()] or
        chars == keylist[selprev.get()]
        ): # Suppress 
        return None
    else:  # nothing to do
        return event

def typeline():
    if l.curselection():
        try:
            curseltxt = l.selection_get()
        except:
            curseltxt = '' # can't select an empty string
        controller.type(curseltxt)
    else:
        print('Hey, no selection. Select a line first')

def typeline_goforward():
    typeline()
    cycleforward()

def typeline_gobackward():
    typeline()
    cyclebackward()

def updatetypenextkey():
    tmplist = list(l.get(0, "end"))
    if not tmplist: return
    l.selection_set(0)
    l.see(0)

def updaterepeatkey():
    tmplist = list(l.get(0, "end"))
    if not tmplist: return
    l.selection_set(0)
    l.see(0)

def hookclipboard():
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
    l.insert(pos+1, text)
    l.delete(pos)
    l.select_clear(pos)
    l.select_set(pos)

def submit_edit_item(child, text, pos):
    edititem(text, pos)
    childdismiss(child)

def edit_item_window():
    if not l.curselection():
        print('Nothing selected')
        return False
    curpos, *_ = l.curselection()
    curtext = l.get(curpos)
    myedit = tk.Toplevel(root)
    myedit.title('Edit item')
    mychild = ttk.Frame(myedit, padding=(2,2,2,2))
    mychild.grid(column=0, row=0, sticky="NWES")
    lbl1 = ttk.Label(mychild)
    lbl1.config(text='Item:')
    lbl1.grid(column=1, row=1, sticky="S")
    ent1 = ttk.Entry(mychild, justify='center')
    str1 = tk.StringVar(value=curtext) #def first var
    ent1.config(textvariable=str1)
    ent1.config(width=66)
    ent1.grid(column=1, row=2, sticky="WE")
    btn1 = ttk.Button(mychild)
    btn1.config(text="Submit")
    btn1.config(command=(lambda: submit_edit_item(
        myedit, ent1.get(), curpos
        )))
    btn1.grid(column=1, row=3)
    btn1.grid(sticky="EWNS") 
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
    for line in [line for line in element.splitlines()]:
        l.insert("end", line)
    removeblanklines()

def insertitem(text):
    if l.curselection():
        curpos, *_ = l.curselection()
        if reversenextbool.get():
            l.insert(curpos, text)
            l.select_clear(curpos+1)
            l.select_set(curpos)
        else:
            l.insert(curpos+1, text)
            l.select_clear(curpos)
            l.select_set(curpos+1)
    else:
        if l.index('end') == 0:
            l.insert(0, text)
            l.select_set(0)
        else:
            print('Hey, no selection. Select a line first')

def submit_insert_item(child, text):
    insertitem(text)
    childdismiss(child)

def insert_item_window():
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
    btn1.config(command=( lambda: submit_insert_item(
        myinsert, ent1.get()
        )))
    btn1.grid(column=1, row=3)
    btn1.grid(sticky="EWNS") 
    myinsert.bind("<Escape>", lambda event: childdismiss(myinsert))
    myinsert.bind("<Return>", lambda event: submit_insert_item(
        myinsert, ent1.get()
        ))
    for child in mychild.winfo_children(): 
        child.grid_configure(padx=2, pady=2)
    myinsert.update()
    myinsert.minsize(myinsert.winfo_width(), myinsert.winfo_height())
    myinsert.maxsize(myinsert.winfo_width(), myinsert.winfo_height())
    myinsert.grab_set()
    myinsert.focus()
    ent1.focus_set()
    myinsert.wait_window()

def removeitem():
    if l.curselection():
        curpos = l.curselection()[0]
        l.delete(l.curselection())
        if curpos < len(l.get(0, "end")):
            l.selection_set(curpos)
            l.see(curpos)
        elif curpos >= len(l.get(0, "end")):
            l.selection_set(len(l.get(0, "end"))-1)
            l.see(curpos)
        else:
            l.selection_set(0)
            l.see(0)
    else:
        print('No selection')

def moveitemup():
    curpos, *_ = l.curselection()
    if isinstance(curpos, int) and curpos > 0:
        curtext = l.get(curpos)
        uppos = curpos - 1
        uptext = l.get(uppos)
        l.delete(uppos)
        l.insert(uppos, curtext)
        l.delete(curpos)
        l.insert(curpos, uptext)
        l.select_set(uppos)
        l.see(uppos)

def moveitemdown():
    curpos, *_ = l.curselection()
    if isinstance(curpos, int) and curpos < (l.index('end') - 1):
        curtext = l.get(curpos)
        downpos = curpos + 1
        downtext = l.get(downpos)
        l.delete(downpos)
        l.insert(downpos, curtext)
        l.delete(curpos)
        l.insert(curpos, downtext)
        l.select_set(downpos)
        l.see(downpos)

def clearclipboard():
    l.delete(0, "end")

def childdismiss(child):
    child.grab_release()
    child.destroy()

def updatechildcombo(child, text, varsdict, myvarscmbs2):
    selectedvarsdict = {
        k: v.get() for k,v in zip(varsdict, myvarscmbs2)
        }
    fmttextlist = [
        x.format_map(selectedvarsdict) for x in text.splitlines() 
        if not re.match('^[#;][^ a-zA-Z0-9]', x)
        ]
    clipboardlist.set(fmttextlist)
    removeblanklines()
    print('Imported.')
    if l.curselection():
        l.selection_clear(l.curselection())
    l.selection_set(0)
    l.see(0)
    curline = l.get(l.curselection())
    if skipcommentlines.get() and re.match('^#', curline):
        if reversenextbool.get():
            cyclebackward()
        else:
            cycleforward()
    childdismiss(child)
    child.destroy()
    return True

def importwithoutvars(text):
    msg = "No variables found in file. That's ok."
    print(msg)
    #tkinter.messagebox.showinfo(title="No variables found", message=msg)
    # Then parse the text file normally
    textlist = text.splitlines()
    textlist = [
        x for x in textlist if not re.match('^#[^ a-zA-Z0-9]',x)
        ]
    clipboardlist.set(textlist)
    removeblanklines()
    print('Imported.')
    if l.curselection():
        l.selection_clear(l.curselection())
    l.selection_set(0)
    l.see(0)
    curline = l.get(l.curselection())
    if skipcommentlines.get() and re.match('^#', curline):
        if reversenextbool.get():
            cyclebackward()
        else:
            cycleforward()

def importwithvars(text, varsdict):
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

def importfromfile():
    initialdir = pathlib.Path()
    filename = tkinter.filedialog.askopenfilename(initialdir=initialdir)
    if not filename:
        print('No file selected')
        return False
    print(filename)
    #tkinter.messagebox.showinfo(
    #    message=filename, title='selected file', parent=mygui
    #    )
    importfile = pathlib.Path(filename)
    if importfile.exists():
        text = importfile.read_text()
    else:
        print(f"{importfile} does not exist")
        return False
    # Search for variables in the import file
    # It is valid to have only a variable name and no values 
    varsregex = re.compile('^## ?var:(?P<name>[^:=]+)[:=]?(?P<values>.*)?')
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
        print('I do not understand. How?')

def cycleforward():
    tmplist = list(l.get(0, "end"))
    if not tmplist: return
    if not l.curselection():
        return False
    curpos = l.curselection()[0]
    if curpos < len(tmplist) - 1:
        l.selection_clear(curpos)
        l.selection_set(curpos+1)
        l.see(curpos+1)
    if curpos == len(tmplist) - 1:
        l.select_clear(curpos)
        l.selection_set(0)
        l.see(0)
    curline = l.get(l.curselection())
    if skipcommentlines.get() and re.match('^#', curline):
        cycleforward()

def cyclebackward():
    tmplist = list(l.get(0, "end"))
    if not tmplist: return
    if not l.curselection():
        return False
    curpos = l.curselection()[0]
    if curpos > 0:
        l.selection_clear(curpos)
        l.selection_set(curpos-1)
        l.see(curpos-1)
    if curpos == 0:
        l.select_clear(curpos)
        l.selection_set(len(tmplist) - 1)
        l.see(len(tmplist) - 1)
    curline = l.get(l.curselection())
    if skipcommentlines.get() and re.match('^#', curline):
        cyclebackward()

def checkcb():
    global lastcbvalue
    global hookcbid
    if pyperclip.paste().strip() != lastcbvalue:
        lastcbvalue = pyperclip.paste().strip()
        additem(lastcbvalue)
        lastcbvalue = ''
        pyperclip.copy('')
        if l.curselection():
            l.selection_clear(l.curselection()[0])   
        l.select_set("end")
        l.see("end")
    hookcbid = root.after(10, checkcb)

def savelisttofile():
    filename = tkinter.filedialog.asksaveasfile(initialdir=".")
    if filename:
        print(filename.name)
        filename.write('\n'.join(l.get(0,"end")))
        filename.close()
        msg = f"File `{filename.name}` has been saved to disk."
        print(msg)
        #tkinter.messagebox.showinfo(title="File saved", message=msg)
    else:
        tkinter.messagebox.showinfo(
            title="No filename received", 
            message=f"I did not receive a filename. Save failed."
            )
        print('No filename received')

def about():
    tkinter.messagebox.showinfo(
        title="About", 
        message=f"""\
{__progname__}
Author: {__author__}
Version: {__version__} ({__date__})
"""
)

def xmodmap():
    if not shutil.which('xmodmap'):
        msg = """\
I could not find `xmodmap` on your system.
Please install it first.
On Ubuntu you can use the command: `sudo apt install x11-xserver-utils`
"""
        tkinter.messagebox.showinfo(title='Remap Keys', message=msg)
        return False
    backup = pathlib.Path() / 'xmodmap_backup.txt'
    if not backup.exists():
        rval = subprocess.run(['xmodmap', '-pke'], capture_output=True)
        if not rval.returncode:
            bytesw = backup.write_bytes(rval.stdout)
            msg = f"""\
Backup of xmodmap data created: `{backup.absolute()}`
Please save this file. 
If you delete it, I cannot restore your original settings.
"""
            print(msg)
            tkinter.messagebox.showinfo(
                title='Backup Created',
                message=msg,
                parent=mygui
                )
        else:
            print('Something went wrong. Did not backup xmodmap info')
            return False
    xmminfo = xmodmap_read()
    fk = {
        k: 
        re.search(f'keycode\s+\\b{k}\\b\s+=\s+(F\d+).*', xmminfo).group(1) 
        for k in xmmkeycodes
        } # what happens if it is none?
    myxmod = tk.Toplevel(root)
    myxmod.title('Remap X11 F Keys using xmodmap')
    mychild = ttk.Frame(myxmod, padding=(2,2,2,2))
    mychild.grid(column=0, row=0, sticky="NSEW")
    myxmodhdrs1 = []
    myxmodhdrs1.append(ttk.Label(mychild))
    myxmodhdrs1[-1].config(text=f"F Key (keycode)")
    myxmodhdrs1[-1].grid(column=1, row=1, sticky="E")
    myxmodhdrs1.append(ttk.Label(mychild))
    myxmodhdrs1[-1].config(text=f"F Key remap")
    myxmodhdrs1[-1].grid(column=2, row=1)
    myxmodhdrs1.append(ttk.Label(mychild))
    myxmodhdrs1[-1].config(text=f"Current F key map")
    myxmodhdrs1[-1].grid(column=3, row=1)
    myxmodlbls1 = []
    myxmodcmbs1 = []
    myxmodstrs1 = []
    myxmodstrs2 = []
    myxmodents1 = []
    myxmodbtns1 = []
    for row, (kcode,fkey) in enumerate(xmmfkcodesdict.items(),2):
        myxmodlbls1.append(ttk.Label(mychild))
        myxmodlbls1[-1].config(text=f"{fkey} ({kcode}):")
        myxmodlbls1[-1].grid(column=1, row=row, sticky="E")
        myxmodstrs1.append(tk.StringVar(value=xmmfdefrmapdict[fkey])) 
        myxmodcmbs1.append(ttk.Combobox(mychild, justify='center'))
        myxmodcmbs1[-1].config(textvariable=myxmodstrs1[-1])
        myxmodcmbs1[-1].config(values=[k.upper() for k in keylist])
        myxmodcmbs1[-1].grid(column=2, row=row)
        myxmodstrs2.append(tk.StringVar(value=fk[kcode])) 
        myxmodents1.append(ttk.Entry(mychild, justify='center'))
        myxmodents1[-1].config(textvariable=myxmodstrs2[-1])
        myxmodents1[-1].grid(column=3, row=row)
        myxmodents1[-1].config(state='disabled')
    myxmodbtns1.append(ttk.Button(mychild))
    myxmodbtns1[-1].config(text='Restore')
    myxmodbtns1[-1].config(command=(lambda: xmodmap_restore(
        myxmod, backup, xmminfo,
        )))
    myxmodbtns1[-1].grid(column=1, columnspan=1, row=row+1)
    myxmodbtns1[-1].grid(sticky="NSEW")
    myxmodbtns1.append(ttk.Button(mychild))
    myxmodbtns1[-1].config(text='Save')
    myxmodbtns1[-1].config(command=(lambda: xmodmap_save(
        myxmod, myxmodcmbs1, xmminfo,
        )))
    myxmodbtns1[-1].grid(column=2, columnspan=1, row=row+1)
    myxmodbtns1[-1].grid(sticky="NSEW")
    myxmodbtns1.append(ttk.Button(mychild))
    myxmodbtns1[-1].config(text='Cancel')
    myxmodbtns1[-1].config(command=(lambda: myxmod.destroy()))
    myxmodbtns1[-1].grid(column=3, columnspan=1, row=row+1)
    myxmodbtns1[-1].grid(sticky="NSEW")
    for child in mychild.winfo_children(): 
        child.grid_configure(padx=2, pady=4)
    myxmod.update()
    myxmod.minsize(myxmod.winfo_width(), myxmod.winfo_height())
    myxmod.maxsize(myxmod.winfo_width(), myxmod.winfo_height())
    myxmod.grab_set()
    myxmod.focus()
    myxmod.wait_window()

def xmodmap_restore(mychild, backup, xmminfo):
    xmminfo = backup.read_text()
    fk = {
        k: re.search(f'keycode\s+\\b{k}\\b\s+=\s+(F\d+).*', xmminfo)
        for k in xmmkeycodes
        } # what happens if it is none?
    for k, remap in fk.items():
        maptext = remap.group(0)
        rval = subprocess.run(
            ['xmodmap', '-e', maptext], capture_output=True
            )
    keylist.update(xmodmap_curmap(xmodmap_read())) 
    msg = "Restored!\nPlease restart the program."
    print(msg)
    tkinter.messagebox.showinfo(
        title='Restored!', message=msg, parent=mychild
        )
    mychild.grab_release()
    mychild.destroy()

def xmodmap_save(mychild, myxmodcmbs1, xmminfo):
    fmaps = {k: cmb.get() for k,cmb in zip(xmmkeycodes, myxmodcmbs1)}
    fk = {
        k: re.search(f'keycode\s+\\b{k}\\b\s+=\s+(F\d+).*', xmminfo)
        for k in xmmkeycodes
        } # what happens if it is none?
    for k, remap in fmaps.items():
        maptext = re.sub(
            f'\\bF\d+\\b', 
            fmaps[k], 
            fk[k].group(0)
            )
        rval = subprocess.run(
            ['xmodmap', '-e', maptext], capture_output=True
            )
    xmminfonew = xmodmap_read()
    keylist.update(xmodmap_curmap(xmodmap_read())) 
    msg = "Saved!\nPlease restart the program."
    print(msg)
    tkinter.messagebox.showinfo(
        title='Saved!', message=msg, parent=mychild
        )
    mychild.grab_release()
    mychild.destroy()

def xmodmap_read():
    rval = subprocess.run(['xmodmap', '-pke'], capture_output=True)
    if not rval.returncode:
        xmminfo = rval.stdout.decode('utf-8')
    else:
        msg = "Something went wrong. Could not read xmodmap info"
        print(msg)
        tkinter.messagebox.showinfo(
            title='Error reading xmodmap', message=msg, parent=mychild
            )
        return False
    return xmminfo

def xmodmap_curmap(xmminfo):
    fk = {
        k:
        re.search(f'keycode\s+\\b{k}\\b\s+=\s+(F\d+).*', xmminfo).group(1) 
        for k in xmmkeycodes
        } # what happens if it is none?
    fkeyscur = {xmmfkcodesdict[k].lower(): c.lower() for k,c in fk.items()}
    return fkeyscur

def define_kybd_listener():
    listener = pynput.keyboard.Listener(
        on_press=on_press if not darwin else on_press_darwin,
        on_release=on_release if not darwin else on_release_darwin,
        win32_event_filter=win32_event_filter,
        darwin_intercept=darwin_intercept,
        suppress=suppress,
        uinput_device_paths=uinput_device_paths,
        )
    return listener

def startkeyboardlistener(listener):
    if 'listener' in globals() and not listener.running:
        listener.start()  # start to listen on a separate thread

def stopkeyboardlistener(listener):
    if 'listener' in globals() and listener.running:
        listener.stop()

def togglekeyboardlistener():
    global listener
    if listener.running:
        stopkeyboardlistener(listener)
        togglekeyboard.set("Start keyboard listener")
    else:
        listener = define_kybd_listener()
        startkeyboardlistener(listener)
        togglekeyboard.set("Stop keyboard listener")

def removeblanklines():    
    if allowblankline.get():
        # blank lines are allowed, nothing to do, 
        # can't add back in blank lines
        pass
    else:
        tmpl = [x for x in l.get(0, 'end') if x]
        if tmpl == list(l.get(0, 'end')):
            # no need to remove blank lines or change my curpos
            pass
        else:                        
            clearclipboard()
            l.insert(0, *tmpl)
            l.selection_set(0)
            l.see(0)

def jumpovercommentlines():
    curline = l.get(l.curselection())
    if skipcommentlines.get() and re.match('^#', curline):
        if reversenextbool.get():
            cyclebackward()
        else:
            cycleforward()

# Start of program
if __name__ == "__main__":
    # Test if the user is running a supported platform and exit if not
    supported_platforms = {
        'win32': 'Windows',
        'linux': 'Linux',
        'darwin': 'macOS',
        }
    userplatform = sys.platform
    darwin = True if userplatform == 'darwin' else False
    linux = True if userplatform == 'linux' else False
    win32 = True if userplatform == 'win32' else False
    if userplatform not in supported_platforms:
        print(f"Sorry, your platform is not supported: `{userplatform}`.")
        print(f"Supported platforms: ", end='')
        print(f"{', '.join(supported_platforms.values())}")
        input('Press `ENTER` to exit')
        sys.exit()

    # Find if the user is running as root on Linux and macOS
    if linux or darwin:
        rootuser = True if shutil.os.geteuid() == 0 else False
        if rootuser:
            print("I see you're running as root.")
        if not rootuser and darwin:
            print("On macOS you should run as root: ", end='')
            print("`sudo -E python3 ./typelines.py`")

    """
    PYNPUT BACKENDS (OPTIONAL)
    Backends are selected automatically. But you can override them.
    Configure these if you wish to set the backend manually.
    Delete this section if you do not.
    """
    bkends_kybd = {
        'darwin': ['macOS'],
        'dummy': ['Windows', 'Linux', 'macOS'],
        'uinput': ['Linux'],
        'win32': ['Windows'],
        'xorg': ['Linux'],
    }
    bkends_mice = {
        'darwin': ['macOS'],
        'dummy': ['Windows', 'Linux', 'macOS'],
        'win32': ['Windows'],
        'xorg': ['Linux'],
    }

    """
    Use PYNPUT_BACKEND if using same backend for keyboard and mouse
    More specific takes precedence if set
    PYNPUT_BACKEND_KEYBOARD & PYNPUT_BACKEND_MOUSE > PYNPUT_BACKEND
    """
    #bkend = 'xorg'
    #os.environ['PYNPUT_BACKEND'] = bkend

    """
    PYNPUT_BACKEND_KEYBOARD and PYNPUT_BACKEND_MOUSE
    Select a specific backend per device
    More specific takes precedence if set
    PYNPUT_BACKEND_KEYBOARD & PYNPUT_BACKEND_MOUSE > PYNPUT_BACKEND
    """
    #bkend_kybd = 'uinput'
    #bkend_mous = 'dummy'
    #os.environ['PYNPUT_BACKEND_KEYBOARD'] = bkend_kybd
    #os.environ['PYNPUT_BACKEND_MOUSE'] = bkend_mous

    """
    `uinput` not working? It might not have found your keyboard device
    you can run this command to find your keyboard device
    `pip3 install evdev`
    `sudo -E python3 -m evdev.evtest`
    and then specify the device (example: /dev/input/event1)
    using the listener flag uinput_device_paths ['/dev/input/event0']
    """
    #uinput_device_paths = ['/dev/input/event1']

    # import pynput after defining the backend
    import pynput

    Key = pynput.keyboard.Key
    # define the keylist as F1 through F20
    keylist = {f'f{n+1}': f'f{n+1}' for n in range(20)}
    if darwin:
        keysqueue = queue.Queue()
    if userplatform == 'linux':
        # Define some default xmodmap values
        xmmfkeys = [f'F{x+1}' for x in range(12)]
        xmmkeycodes = list(range(67,77)) + [95, 96]
        xmmkeycodes2 = [f'XF86Switch_VT_{x+1}' for x in range(12)]
        xmmfkcodesdict = {k: v for k,v in zip(xmmkeycodes, xmmfkeys)}
        xmmfkeysdefremaps = [
            'F1', 'F2', 'F13', 'F14', 'F15', 'F16', 
            'F7', 'F8', 'F9', 'F10', 'F11', 'F12'
            ]
        xmmfdefrmapdict = {k:v for k,v in zip(xmmfkeys, xmmfkeysdefremaps)}
        # Update keylist to current xmodmap values
        keylist.update(xmodmap_curmap(xmodmap_read())) 
    # keydict is only used in the win32_event_filter
    keydict = {
        key.name: key.value.vk for key in pynput.keyboard.Key 
        if key.name in keylist
            }
    keyforward = 'f3'
    keyrepeat = 'f4'
    keyselprev = 'f5'
    keyselnext = 'f6'
    lastcbvalue = ''
    hookcbid = ''
    test_clipboard = [f'sample text {x+1:02d}' for x in range(25)]
    if not 'bkend_kybd' in locals():
        bkend_kybd = ''
    if not 'uinput_device_paths' in locals():
        uinput_device_paths = None
    suppress = True if bkend_kybd == 'uinput' else False

    # Start of tkinter GUI section
    root = tk.Tk()
    root.title(__progname__)

    mygui = ttk.Frame(root, padding=(2,2,2,2))
    mygui.grid(column=0, row=0, sticky="NSWE")

    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    mygui.columnconfigure(6, weight=1)
    mygui.rowconfigure(15, weight=1)

    myguibtns = []
    myguilbls = []
    myguicmbs = []
    myguistrs = []
    myguickbs = []
    myguilsbs = []
    myguiscbs = []

    # `Type & Advance` label and combobox
    myguilbls.append(ttk.Label(mygui))
    myguilbls[-1].config(text="`Type & Advance` Key")
    myguilbls[-1].grid(column=1, row=1, sticky="E")
    forward = tk.StringVar(value=keyforward)
    myguicmbs.append(ttk.Combobox(mygui))
    myguicmbs[-1].config(textvariable=forward)
    myguicmbs[-1].config(values=list(keylist))
    myguicmbs[-1].config(width=5)
    myguicmbs[-1].grid(column=2, row=1, sticky="WE")
    myguicmbs[-1].bind('<<ComboboxSelected>>', lambda e: 
        updatetypenextkey()
        )

    # `Type & Stay` label and combobox
    myguilbls.append(ttk.Label(mygui))
    myguilbls[-1].config(text="`Type & Stay` Key")
    myguilbls[-1].grid(column=1, row=2, sticky="E")
    repeat = tk.StringVar(value=keyrepeat)
    myguicmbs.append(ttk.Combobox(mygui))
    myguicmbs[-1].config(textvariable=repeat)
    myguicmbs[-1].config(values=list(keylist))
    myguicmbs[-1].config(width=5)
    myguicmbs[-1].grid(column=2, row=2, sticky="WE")
    myguicmbs[-1].bind('<<ComboboxSelected>>', lambda e: 
        updaterepeatkey()
        )

    # `Move to previous line` label and combobox
    myguilbls.append(ttk.Label(mygui))
    myguilbls[-1].config(text="Move to previous line")
    myguilbls[-1].grid(column=3, row=1, sticky="E")
    selprev = tk.StringVar(value=keyselprev)
    myguicmbs.append(ttk.Combobox(mygui))
    myguicmbs[-1].config(textvariable=selprev)
    myguicmbs[-1].config(values=list(keylist))
    myguicmbs[-1].config(width=5)
    myguicmbs[-1].grid(column=4, row=1, sticky="WE")
    myguicmbs[-1].bind('<<ComboboxSelected>>', lambda e: cyclebackward())

    # `Move to next line` label and combobox
    myguilbls.append(ttk.Label(mygui))
    myguilbls[-1].config(text="Move to next line")
    myguilbls[-1].grid(column=3, row=2, sticky="E")
    selnext = tk.StringVar(value=keyselnext)
    myguicmbs.append(ttk.Combobox(mygui))
    myguicmbs[-1].config(textvariable=selnext)
    myguicmbs[-1].config(values=list(keylist))
    myguicmbs[-1].config(width=5)
    myguicmbs[-1].grid(column=4, row=2, sticky="WE")
    myguicmbs[-1].bind('<<ComboboxSelected>>', lambda e: cycleforward())

    # `Stop keyboard listener` button
    togglekeyboard = tk.StringVar(value="Stop keyboard listener")
    myguibtns.append(ttk.Button(mygui))
    myguibtns[-1].config(textvariable=togglekeyboard)
    myguibtns[-1].grid(column=5, row=1, sticky="NSWE")
    myguibtns[-1].config(command=togglekeyboardlistener)

    # `Reverse direction` checkbox
    reversenextbool = tk.BooleanVar(value=False)
    myguickbs.append(ttk.Checkbutton(mygui))
    myguickbs[-1].config(text="Reverse direction")
    myguickbs[-1].config(variable=reversenextbool)
    myguickbs[-1].grid(column=5, row=2, sticky="WE")

    # Text List (The data to be typed)
    clipboardlist = tk.StringVar(value=test_clipboard)
    myguilsbs.append(tk.Listbox(mygui))
    myguilsbs[-1].config(height=15)
    myguilsbs[-1].config(listvariable=clipboardlist)
    myguilsbs[-1].grid(column=1, columnspan=6, row=3, rowspan=15)
    myguilsbs[-1].grid(sticky="NSWE")
    myguilsbs[-1].selection_set(0)
    myguilsbs[-1].see(0)
    l = myguilsbs[-1]
    # Edit item option (double click the item)
    myguilsbs[-1].bind("<Double-1>", lambda event: edit_item_window())

    # Scroll bar for the Text List
    myguiscbs.append(ttk.Scrollbar(mygui))
    myguiscbs[-1].config(orient=tk.VERTICAL)
    myguiscbs[-1].config(command=l.yview)
    myguiscbs[-1].grid(column=7, row=3, rowspan=20)
    myguiscbs[-1].grid(sticky="NSWE")
    s = myguiscbs[-1]
    l['yscrollcommand'] = s.set

    # Hook clipboard checkbox
    hookcb = tk.BooleanVar(value=False)
    myguickbs.append(ttk.Checkbutton(mygui))
    myguickbs[-1].config(text="Hook Clipboard")
    myguickbs[-1].config(variable=hookcb)
    myguickbs[-1].config(command=hookclipboard)
    myguickbs[-1].grid(column=10, row=1, sticky="WE")

    # Allow blank lines checkbox
    allowblankline = tk.BooleanVar(value=False)
    myguickbs.append(ttk.Checkbutton(mygui))
    myguickbs[-1].config(text="Allow blank lines")
    myguickbs[-1].config(variable=allowblankline)
    myguickbs[-1].config(command=removeblanklines)
    myguickbs[-1].grid(column=10, row=2, sticky="WE")

    # Allow comment lines checkbox
    skipcommentlines = tk.BooleanVar(value=True)
    myguickbs.append(ttk.Checkbutton(mygui))
    myguickbs[-1].config(text="Skip comment lines")
    myguickbs[-1].config(variable=skipcommentlines)
    myguickbs[-1].config(command=jumpovercommentlines)
    myguickbs[-1].grid(column=10, row=3, sticky="WE")

    # Add item
    myguibtns.append(ttk.Button(mygui))
    myguibtns[-1].config(text="Insert item")
    myguibtns[-1].config(command=insert_item_window)
    myguibtns[-1].grid(column=10, row=4, sticky="WE")

    # Remove item button
    myguibtns.append(ttk.Button(mygui))
    myguibtns[-1].config(text="Remove item")
    myguibtns[-1].config(command=removeitem)
    myguibtns[-1].grid(column=10, row=5, sticky="WE")

    # Move item up
    myguibtns.append(ttk.Button(mygui))
    myguibtns[-1].config(text="Move item up")
    myguibtns[-1].config(command=moveitemup)
    myguibtns[-1].grid(column=10, row=6, sticky="WE")

    # Move item down
    myguibtns.append(ttk.Button(mygui))
    myguibtns[-1].config(text="Move item down")
    myguibtns[-1].config(command=moveitemdown)
    myguibtns[-1].grid(column=10, row=7, sticky="WE")

    # Clear list button
    myguibtns.append(ttk.Button(mygui))
    myguibtns[-1].config(text="Clear list")
    myguibtns[-1].config(command=clearclipboard)
    myguibtns[-1].grid(column=10, row=8, sticky="WE")

    # Import list from file with vars button
    myguibtns.append(ttk.Button(mygui))
    myguibtns[-1].config(text="Import")
    myguibtns[-1].config(command=importfromfile)
    myguibtns[-1].grid(column=10, row=9, sticky="WE")

    # Save current list to file button
    myguibtns.append(ttk.Button(mygui))
    myguibtns[-1].config(text="Save")
    myguibtns[-1].config(command=savelisttofile)
    myguibtns[-1].grid(column=10, row=10, sticky="WE")

    # About button
    myguibtns.append(ttk.Button(mygui))
    myguibtns[-1].config(text="About")
    myguibtns[-1].config(command=about)
    myguibtns[-1].grid(column=10, row=11, sticky="WE")

    if userplatform == 'linux':
        # Remap X11 F Keys button
        myguibtns.append(ttk.Button(mygui))
        myguibtns[-1].config(text="Remap X11 F Keys")
        myguibtns[-1].config(command=xmodmap)
        myguibtns[-1].grid(column=10, row=12, sticky="WE")

    # main text list box and scroll bar padding
    for child in mygui.winfo_children(): 
        child.grid_configure(padx=2, pady=2)
    l.grid_configure(padx=(2,0))
    s.grid_configure(padx=(0,2))

    root.update()
    root.minsize(root.winfo_width(), root.winfo_height())

    controller = pynput.keyboard.Controller()
    listener = define_kybd_listener()

    if darwin:
        typeit_darwin()
        print(f"{listener.IS_TRUSTED=}")
    listener.start()  # start to listen on a separate thread
    root.mainloop()
    listener.stop()
