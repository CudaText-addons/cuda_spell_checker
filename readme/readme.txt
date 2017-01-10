plugin for CudaText.
gives spell-checking by using Enchant/PyEnchant libraries. it uses Hunspell dictionaries (didn't test other dictionaries). plugin has also binary DLL files for Windows (32-bit). it don't have binary files for Linux and OSX. so on Linux and OSX you must install Enchant binary files.

misspelled words hilited with red underlines.
to run spell-check, use "Plugins" menu:

- command "Show underlines on/off": this enables spell-check after each change of text, after a 2 sec pause (pause after last change of text, so you must stop typing text and wait).
- commands "Check text/word (with suggestions)": this runs spell-check, and with replace-prompt-dialog for misspelled words. dialog will give suggestions from spell-check engine.


feature: not all text is checked, only words in "comments" and "strings".
to edit which lexer styles are "comments" and "strings", open Lexer Properties dialog, and use "Commenting" tab of dialog to set these styles. 


author: Alexey T (CudaText)
license: MIT
