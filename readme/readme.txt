Plugin for CudaText.
Gives spell checking by using Enchant/PyEnchant libraries.
Misspelled words are highlighted with red underlines.

- Windows 32-bit and 64-bit are supported, binary DLL files are shipped with plugin.
- Linux and other Unixes are supported, but you must install Enchant binary files,
  using OS package manager.


Additional dictionaries
=======================

Plugin uses Hunspell dictionaries.
It's possible to install additional dictionaries:
https://github.com/titoBouzout/Dictionaries
Rename files to short names, e.g. Russian.* to ru.* or ru_RU.*
Copy files to folder:
- on Windows:
  32-bit CudaText: CudaText\py\cuda_spell_checker\enchant_x86\share\enchant\myspell\
  64-bit CudaText: CudaText\py\cuda_spell_checker\enchant_x64\share\enchant\myspell\
- on Unix: ~/.enchant/myspell/


Menu items
==========

Use commands in "Plugins" menu:

- "Check text", "Check text, with suggestions": Run spell-checking, and with
  suggestion-dialog for misspelled words. Dialog will give suggestions from spell-check engine.
- "Check word", "Check word, with suggestions": Run spell-checking of only one word, under 1st caret.
- "Go to next/previous misspelled": Put caret to next (previous) misspelled word,
  if such words are already highlighted.

Use commands in "Options / Settings-plugins / Spell Checker" menu:

- "Select language": Shows menu-dialog to choose one of installed spelling dictionaries.

- "Enable/disable checking on opening file": This toggles auto-checking after file opening, on/off.
  This writes option to install.inf file, in "py" folder. So you must re-enable this option
  after each plugin update/installation.

- "Enable/disable checking after text editing": Enable/disable checking after every change of text,
  after 2 second pause (pause after last change of text, so you must stop typing the text and wait).
  This pause can be changed in CudaText config user.json, it is the option "py_change_slow".


Confirmation dialog buttons
===========================

- "Ignore": Skip the word.
- "Change": Replace the word in editor, by suggestion in the dialog input box,
  or by selected listbox item.
- "Add": Skip the word + add it to a user dictionary for future, so the next time
  this word will be automatically skipped.
- "Cancel": Stop the checking process.


Features
========

1)
When lexer is active, not entire text is checked, but only words in "syntax comments"
and "syntax strings".
For none-lexer, entire text is checked.
To set which lexer styles are "comments" and "strings", you need to edit the lexer in SynWrite.
Activate the lexer in SynWrite, then open "Lexer Properties" dialog in SynWrite,
and use "Commenting" tab of the dialog to set these styles.
SynWrite will save this change to the file "data/lexlib/<lexer>.cuda-lexmap",
you need to copy/update this file to the CudaText folder "data/lexlib".

2)
You can enable permanent checking after a) file opening, b) text editing.
See the topic above in this readme-file, about menu "Options / Settings-plugins / Spell Checker",
you can do changes from that menu too, it is the same as editing file install.inf by hands.

2a) For file opening.
Use API event "on_open", write it to file "py/cuda_spell_checker/install.inf" like this:
[item1]
section=events
events=on_open

2b) For text editing.
Use API event "on_change_slow", write it to the same install.inf file like this:
[item1]
section=events
events=on_change_slow

2c) If both API events are needed, write them comma-separated:
[item1]
section=events
events=on_open,on_change_slow

Note: file install.inf is overwritten on each plugin update/installation,
so backup this file.


Personal word list
==================

If you press "Add" button in the spell checker dialog, highlighted word will be added
to the personal word list. This is text file which you can edit or delete. Location:

- Windows: C:\Users\username\AppData\Local\enchant\*.dic
- Linux: ~/.config/enchant/*.dic


Options
=======

Plugin has several options in ini-file, call command
"Options / Settings-plugins / Spell Checker / Config".
Options are:

- "lang": current language which user chose in "Select language" command
- "underline_style" (0..6): style of line below words
- "confirm_esc_key" (0/1): allows to show confirmation when user presses Esc during long checking
- "file_extension_list": which files to check with option "Enable checking after text editing":
    - "" (empty): disable on all files
    - "*": enable on all files
    - comma-separated list like "ext1,ext2,ext3": these extensions will be checked


About
=====

Author: Alexey Torgashin (CudaText)
License: MIT
