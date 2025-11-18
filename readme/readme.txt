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
Rename files to short names, e.g. Russian.* to ru.* or ru_RU.* (the name must have at least 2 letters and no space)
Copy files to folder:

- on Windows:
  32-bit CudaText: CudaText\py\cuda_spell_checker\enchant_x86\data\share\enchant\hunspell\
  64-bit CudaText: CudaText\py\cuda_spell_checker\enchant_x64\data\share\enchant\hunspell\

- on Linux/Unix:
  ~/.enchant/myspell
  or
  ~/.config/enchant

On Linux/Unix, you need additionally to install the package:
  hunspell
  hunspell-<LANGUAGE>
For example, for Russian language and Debian OS:
  $ sudo apt-get install hunspell-ru


Extended dictionaries
=====================

Purpose: Hunspell dictionaries, while accurate because they respect language variants (like American English vs. British English), are often small (e.g., ~70k words for English). This leads to a high number of false positives (correct words marked as misspelled) for general use. The Extended Dictionaries provide much larger wordlists (e.g., ~370k+ words for English) and are generic—they do not respect language variants. This trade-off drastically reduces false positives for most users.

Users can choose between using the language-variant-respecting Hunspell dictionary or the larger, generic Extended Dictionary. This choice can be toggled via the menu command Options > Settings - plugins > Spell Checker > Toggle the Extended Dictionary. Read more about the behavioral difference in the `use_extended_dictionary` option description below.

Installation:
The plugin's Extended Dictionaries must be downloaded separately from:
https://github.com/CudaText-addons/cuda_spell_checker_extended_dictionaries

The downloaded dictionary files (e.g., `en_generic.txt` or specialized language lists) must be copied into the plugin's `ext_dict` folder:

- on Windows:
  `CudaText\py\cuda_spell_checker\ext_dict\`

- on Linux/Unix:
  `~/.config/cudatext/py/cuda_spell_checker/ext_dict/`

Naming Convention:
The plugin automatically attempts to match the Hunspell dictionary you are using with the corresponding Extended Dictionary file. It extracts the first two letters of your active Hunspell dictionary name (e.g., `en` from `en_US` or `de` from `de_DE`) and searches for a file named `[two-letter-code]_generic.txt` in the `ext_dict` folder (e.g., `en_generic.txt`).
Therefore, it is strongly recommended that you use the international two-letter naming convention (e.g., `en`, `es`, `fr`) when renaming your Hunspell dictionary files, as this aligns with the file names provided in the Extended Dictionaries GitHub repository. If you use a custom name for your Hunspell file (e.g., `myenglish.dic`), you must manually rename the corresponding Extended Dictionary file (e.g., `en_generic.txt` to `my_generic.txt`) for the feature to work.


Menu items
==========

Items in the "Plugins" menu:

- "Check text": Run spell-checking (of only selection, if selection is made).
- "Check text, with suggestions": Run spell-checking (of only selection, if selection is made), with the suggestion dialog for misspelled words. Dialog will give suggestions from the spell-checker dictionaries.
- "Check word", "Check word, with suggestions": Run spell-checking of only one word, under first caret. You don't need to select a word, only place caret on it.
- "Go to next/previous misspelled": Put caret to next/previous misspelled word, if such words are already found and underlined.
- "Create a list with all the misspelled words": Scans the entire document and opens a new tab containing a unique, sorted list of all misspelled words.

Items in the "Options / Settings-plugins / Spell Checker" menu:

- "Select language": Shows menu-dialog to choose one of installed spelling dictionaries.
- "Configure": Edit settings file (it has the INI format).
- "Configure events": Open dialog to configure events of plugin: on_open and on_change_slow.
  It writes to the file "settings/plugins.ini".
- "Toggle the Extended Dictionary": Switches the active dictionary between the larger, generic extended dictionary and the language-variant-specific Hunspell dictionary.


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

3)
High-Speed, High-Accuracy Checking: The plugin uses a modern, high-speed checking mechanism. It first checks words against a large, in-memory "Extended Dictionary" (`ext_dict/*.txt`) for an instant O(1) lookup. This is extremely fast (e.g., checking a 6MB file in ~1.5 seconds) and significantly reduces "false positives," as these wordlists are often much larger than the default Hunspell dictionaries. The plugin only falls back to the slower, external Enchant/Hunspell library for words not found in the fast list.

4)
Programmer-Specific Filters: To reduce false positives in source code, the plugin automatically skips checking words that are:
- In `ALL-CAPS` (e.g., `MYCONSTANT`)
- In `camelCase` or `MixedCase` (e.g., `myWord`, `MyWord`)
- Contain numbers (e.g., `v1.0`)
- Contain underscores (e.g., `my_var_name`)


Personal word list
==================

If you press "Add" button in the spell checker dialog, highlighted word will be added
to the personal word list. This word list is saved to this file which you can edit or delete. Location:

- Windows: C:\Users\username\AppData\Local\enchant\*.dic
- Linux: ~/.config/enchant/*.dic


Options
=======

Plugin has several options in the ini-file, call the menu item:
"Options / Settings-plugins / Spell Checker / Config".
Options are:

- "lang": Spell-checker language, e.g. "en_US". You cannot just change the value here without installing additional Enchant-library dictionaries. After you install them, use the "Select language" plugin's command to choose the language.

- "underline_style" (0..6): Style of lines below misspelled words.

- "confirm_esc_key" (0/1): Allows to show confirmation when user presses Esc-key during long spell-checking.

- "file_extension_list": Which files to check automatically, by events (on_change_slow, on_open).
  Possible values:
    - "" (empty value, without quotes): Disable for all files.
    - "*" (star character, without quotes): Enable for all files.
    - "txt,md,html": Enable only for listed file extensions, which are comma-separated, without dot-char.
      To specify files without extension here, add item "-" (minus sign).

- "url_regex": RegEx (regular expression) which finds URLs to skip them on checking. Avoid complex RegEx here, it's slower.

- "use_extended_dictionary" (0/1): This option controls which dictionary is used for the high-speed "Extended Dictionary" check.
    - Enabled (1): (Default) Uses a large, generic wordlist (e.g., 370k+ words). This significantly reduces "false positives" but does not respect language variants (e.g., it mixes American and British English). This is ideal for non-native speakers or anyone who prioritizes recognizing the most words.
    - Disabled (0): Uses a smaller, Hunspell-compatible wordlist (e.g., 70k+ words) generated from your specific language (e.g., `en_US` or `en_GB`). This strictly respects your chosen language variant but will result in more false positives for words not in that specific dictionary.

- "use_global_cache" (0/1): This option enables a global word cache to significantly speed up repeated spell-checking runs within the same session by storing the correctness status of every encountered word.
This option is most valuable if you are not using the "Extended Dictionaries" (stored in files "py/cuda_spell_checker/ext_dict/*.txt"), as normal checks are slower: without this option, a check on a 5 MB file might take ~4 seconds, but with this, the cache will reduce this to ~1 second on the second and successive runs.
However, if you are using the "Extended Dictionary" (which makes the first check very fast, ~1.5 seconds), the cache provides only a minimal further speed gain (~1 second) while consuming significant RAM (typically 40−60 MB for a 5 MB file).
Since the cache persists for the entire session and is only cleared upon application restart or dictionary change, it is generally not recommended to enable this option if you utilize the "Extended Dictionary".
Default: disabled (0).


About
=====

Authors:
- Alexey Torgashin (CudaText)
- Andreas Heim (https://github.com/dinkumoil) added the Enchant Windows DLL support
- CudaText forum member A:C made the big refactoring
- Badr Elmers (https://github.com/badrelmers) improved the speed a lot, made big refactoring

License: MIT
