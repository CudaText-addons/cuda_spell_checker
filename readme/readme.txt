plugin for CudaText.
gives spell-checking by using Enchant/PyEnchant libraries. it uses Hunspell dictionaries (didn't test other dictionaries). plugin has also binary DLL files for Windows (32-bit). it don't have binary files for Linux and OSX. so on Linux and OSX you must install Enchant binary files.

misspelled words hilited with red underlines.
to run spell-check use "Plugins" menu:

- call command "Show underlines on/off": this enables spell-check after each change of text, after a 2sec pause (pause after last change of text, so you must stop typing text and wait).
- call command "Check text": this runs one spell-check, and with replace-prompt-dialog. dialog will give suggestions from spell-check engine.


feature: not all text is checked, only words of "comments" and "strings".
to edit which lexer styles are "comments" and "strings", edit file "settings/user_lexers.json". this file - same format as file "settings_default/default_lexers.json" from CudaText distro. new lexers must have inf in user_lexers.json (if you want styles-aware spell-check).


author: Alexey T (Cudatext)
license: MIT
