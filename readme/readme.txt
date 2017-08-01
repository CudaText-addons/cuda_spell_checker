Plugin for CudaText.
Gives spell-checking by using Enchant/PyEnchant libraries. 
Uses Hunspell dictionaries. It's possible to install additional dicts: see more_dicts.txt. 

- Windows 32-bit: supported, binary DLL files shipped with plugin
- Windows 64-bit: not supported yet (missed x64 DLLs)
- Linux, macOS: supported, but you must install Enchant binary files (using OS package manager).

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


Author: Alexey T (CudaText)
License: MIT
