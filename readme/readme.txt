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
Rename files to short names, e.g. Russian.* to ru.* or ru_RU.* (the name must not have space)
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


Note: The provided initial link for downloading dictionaries has a limited and potentially outdated selection. As there is no single unified source for all available and up-to-date Hunspell dictionaries, you may need to use external sources to find a specific language or a more current version of a dictionary.
Alternative and Updated Sources:
http://app.aspell.net/create (Best for English)
https://github.com/wooorm/dictionaries
https://addons.mozilla.org/en-US/firefox/language-tools/
https://sourceforge.net/projects/wordlist/
https://extensions.libreoffice.org/
https://extensions.openoffice.org/


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
- "Configure events": Open dialog to configure events: 'Check spelling when opening files' and Check spelling while editing (after pause).
  It writes to the file "settings/plugins.ini".


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
You can enable permanent checking after:
  a) file opening (Check spelling when opening files)
  b) text editing (Check spelling while editing (after pause)).
See the topic above in this readme-file, about menu "Options / Settings-plugins / Spell Checker"

3)
High-Speed Checking and Persistent Caching:
The plugin uses a modern, high-speed checking mechanism backed by a persistent file cache.

- **Persistent Smart Cache**: The cache is saved to disk (JSON format in TEMP folder). This means spell checking data is preserved even if you restart CudaText, making subsequent checks instantaneous.
- **Configurable Lifetime**: You can control how long the cache persists via the `cache_lifetime` option (default: 60 minutes).
- **Smart Dictionary Updates**: The plugin automatically detects if your source Hunspell dictionary (`.dic` file) has been updated by monitoring the file size and timestamp. If an update is detected, the cache is automatically cleared and regenerated to ensure accuracy.

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

- "file_extension_list": Which files to check automatically, by events (Check spelling when opening files, Check spelling while editing (after pause)).
  Possible values:
    - "" (empty value, without quotes): Disable for all files.
    - "*" (star character, without quotes): Enable for all files.
    - "txt,md,html": Enable only for listed file extensions, which are comma-separated, without dot-char.
      To specify files without extension here, add item "-" (minus sign).

- "url_regex": RegEx (regular expression) which finds URLs to skip them on checking. Avoid complex RegEx here, it's slower.

- "cache_lifetime": Controls the duration (in minutes) of the persistent cache.
    - 0: Keep persistent cache forever (or until dictionary update).
    - >0: Reset the persistent cache file every X minutes.
    - Default: 60.

About
=====

Authors:
- Alexey Torgashin (CudaText)
- Andreas Heim (https://github.com/dinkumoil) added the Enchant Windows DLL support
- CudaText forum member A:C made the big refactoring
- Badr Elmers (https://github.com/badrelmers) improved the speed a lot, made big refactoring

License: MIT
