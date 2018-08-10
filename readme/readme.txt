Plugin for CudaText.
Gives spell-checking by using Enchant/PyEnchant libraries. 

- Windows 32-bit: supported, binary DLL files shipped with plugin
- Windows 64-bit: not supported yet (missed x64 DLLs)
- Unix: supported, but you must install Enchant binary files (using OS package manager)

Uses Hunspell dictionaries.
It's possible to install additional dictionaries:
https://github.com/titoBouzout/Dictionaries
Rename to short names: Russian.* to ru.* or ru_RU.*
Copy into folder:
    - on Windows: [plugin_dir]\enchant\share\enchant\myspell\
    - on Unix: ~/.enchant/myspell/

Misspelled words are highlighted with red underlines.
Use commands in "Plugins" menu:

    - "Show underlines on/off": Enables spell-checking after every change of text, after 2 second pause (pause after last change of text, so you must stop typing text and wait).
    - "Check text", "Check text, with suggestions": Run spell-checking, and with suggestion-dialog for misspelled words. Dialog will give suggestions from spell-check engine. 
    - "Check word", "Check word, with suggestions": Run spell-checking of only one word, under 1st caret.

Dialog buttons: 
    - Ignore: skip word
    - Change: replace word in editor, from dialog input box or selected listbox item
    - Add: skip word and add it to a user dictionary for future
    - Cancel: stop all work

Feature:
For lexers, not all text is checked, only words in "syntax comments" and "syntax strings". For none-lexer, entire text is checked. To set which lexer styles are "comments" and "strings", open Lexer Properties dialog in CudaText, and use "Commenting" tab of dialog to set these styles. E.g. in HTML/Markdown lexers, correct styles are set, so correct parts are checked. 

Plugin have several options in ini-file, call command "Options / Settings-plugins / Spell Checker / Config".
Options:
    - "lang": current language which user chose in "Select language" command
    - "underline_color": color of misspelled word underlines, in HTML form
    - "underline_style" (0..6): style of line below words
    - "confirm_esc_key" (0/1): allows to show confirmation when user presses Esc during long checking
    - "file_extension_list": 
        - "" (empty): disable on all files
        - "*": enable on all files
        - comma-separated list like "ext1,ext2,ext3": these extensions will be checked
         

Author: Alexey T (CudaText)
License: MIT
