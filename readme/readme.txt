Plugin for CudaText.
Gives spell checking by using Enchant/PyEnchant libraries.
Misspelled words are highlighted with red underlines.

- Windows 32-bit and 64-bit: supported, binary DLL files shipped with plugin
- Unix: supported, but you must install Enchant binary files (using OS package manager)

Uses Hunspell dictionaries.
It's possible to install additional dictionaries:
https://github.com/titoBouzout/Dictionaries
Rename to short names: Russian.* to ru.* or ru_RU.*
Copy into folder:
    - on Windows (32 bit CudaText): [CudaText_dir]\py\cuda_spell_checker\enchant_x86\share\enchant\myspell\
                 (64 bit CudaText): [CudaText_dir]\py\cuda_spell_checker\enchant_x64\share\enchant\myspell\
    - on Unix: ~/.enchant/myspell/

------------------------------

Use commands in "Plugins" menu:

    - "Check text", "Check text, with suggestions": Run spell-checking, and with suggestion-dialog for misspelled words. Dialog will give suggestions from spell-check engine.
    - "Check word", "Check word, with suggestions": Run spell-checking of only one word, under 1st caret.
    - "Go to next/previous misspelled": Put caret to next (previous) misspelled word, if such words are already highlighted.

Use commands in "Options / Settings-plugins / Spell Checker" menu:

    - "Select language": Shows menu-dialog to choose one of installed spelling dictionaries.

    - "Enable/disable checking on opening file": This toggles auto-checking after file opening, on/off.
      This writes option to install.inf file, in "py" folder. So you must re-enable this option
      after each plugin update/installation.

    - "Enable/disable checking after text editing": Enable/disable checking after every change of text,
      after 2 second pause (pause after last change of text, so you must stop typing the text and wait).
      This pause can be changed in CudaText config user.json. See option "py_change_slow".

Spell checker confirmation dialog buttons:
    - Ignore: skip word
    - Change: replace word in editor, from dialog input box or selected listbox item
    - Add: skip word and add it to a user dictionary for future
    - Cancel: stop all work

------------------------------

Feature:
For lexers, not entire text is checked, but only words in "syntax comments" and "syntax strings". For none-lexer, entire text is checked. To set which lexer styles are "comments" and "strings", open Lexer Properties dialog in CudaText, and use "Commenting" tab of dialog to set these styles. E.g. in HTML/Markdown lexers, correct styles are set, so correct parts are checked.

Feature:
You can enable permanent checking after a) file opening, b) text editing.
a) For file opening. Use API event "on_open", write it to file "py/cuda_spell_checker/install.inf" like this:
[item1]
section=events
events=on_open
b) For text editing. Use API event "on_change_slow", write it to the same install.inf file like this:
[item1]
section=events
events=on_change_slow
c) If both API events are needed, write them comma-separated:
[item1]
section=events
events=on_open,on_change_slow

Note: file install.inf is overwritten on each plugin update/installation.

------------------------------

Plugin have several options in ini-file, call command "Options / Settings-plugins / Spell Checker / Config".
Options:
    - "lang": current language which user chose in "Select language" command
    - "underline_style" (0..6): style of line below words
    - "confirm_esc_key" (0/1): allows to show confirmation when user presses Esc during long checking
    - "file_extension_list": which files to check with option "Enable checking after text editing":
        - "" (empty): disable on all files
        - "*": enable on all files
        - comma-separated list like "ext1,ext2,ext3": these extensions will be checked


Author: Alexey Torgashin (CudaText)
License: MIT
