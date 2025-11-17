# coding: utf-8

import importlib
import os
import sys
import re
import string
import time
from .enchant_architecture import EnchantArchitecture
from cudatext import *

from cudax_lib import get_translation
_ = get_translation(__file__)  # I18N

def bool_to_str(v): return '1' if v else '0'
def str_to_bool(s): return s == '1'

filename_ini = os.path.join(app_path(APP_DIR_SETTINGS), 'cuda_spell_checker.ini')
filename_plugins = os.path.join(app_path(APP_DIR_SETTINGS), 'plugins.ini')
op_underline_color = app_proc(PROC_THEME_UI_DICT_GET, '')['EdMicromapSpell']['color']

op_lang                      =             ini_read(filename_ini, 'op', 'lang'                      , 'en_US'          )
op_underline_style           =         int(ini_read(filename_ini, 'op', 'underline_style'           , '6'              ))
op_confirm_esc               = str_to_bool(ini_read(filename_ini, 'op', 'confirm_esc_key'           , '0'              ))
op_file_types                =             ini_read(filename_ini, 'op', 'file_extension_list'       , '*'              )
op_url_regex                 =             ini_read(filename_ini, 'op', 'url_regex'                 , r'\bhttps?://\S+')
op_use_global_cache          = str_to_bool(ini_read(filename_ini, 'op', 'use_global_cache'          , '0'              ))
op_use_extended_dictionary   = str_to_bool(ini_read(filename_ini, 'op', 'use_extended_dictionary'   , '1'              ))

re_url = re.compile(op_url_regex, 0)
word_re = re.compile(r"[\w']+")

_mydir = os.path.dirname(__file__)
_ench = EnchantArchitecture()

# On Windows expand PATH environment variable so that Enchant can find its backend DLLs
if sys.platform == "win32":
    os.environ["PATH"] += ";" + os.path.join(_mydir, _ench, "data", "bin") + ";" + os.path.join(_mydir, _ench, "data", "lib", "enchant-2")

sys.path.append(_mydir)

# ============================================================================
# HUNSPELL DICTIONARY PARSING
# ============================================================================

def parse_hunspell_dic(lang_code):
    """
    Parse a Hunspell .dic file and extract all base words.
    Returns a set of words.
    
    Args:
        lang_code: Language code like 'en_US', 'de_DE', etc.
    """
    dic_file = os.path.join(_mydir, _ench, "data", "share", "enchant", "hunspell", f"{lang_code}.dic")
    
    if not os.path.exists(dic_file):
        msg_status(_("Spell Checker: Could not find Hunspell dictionary for {}").format(lang_code))
        return set()
    
    # Parsing Hunspell dictionary: {dic_file}
    words = set()
    try:
        with open(dic_file, 'r', encoding='utf-8', errors='ignore') as f:
            # Skip the first line (word count)
            next(f, None)
            
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                # Split on '/' to get base word (ignore affixes)
                # Format is usually: word/flags or just word
                word = line.split('/')[0].strip()
                
                # Add word as-is, preserving case and all characters from Hunspell
                if word:
                    words.add(word)
        
        msg_status(_("Spell Checker: Extracted {} words from Hunspell dictionary").format(len(words)))
        return words
    
    except Exception as e:
        msg_status(_("Spell Checker: Error parsing Hunspell dictionary: {}").format(e))
        print(_("Error: Spell Checker: Error parsing Hunspell dictionary: {}").format(e))
        return set()


def create_hunspell_wordlist(lang_code):
    """
    Create an extended dictionary word list from Hunspell dictionary.
    Saves it to ext_dict folder with the language code name.
    
    Args:
        lang_code: Language code like 'en_US', 'de_DE', etc.
    """
    ext_dict_dir = os.path.join(_mydir, 'ext_dict')
    os.makedirs(ext_dict_dir, exist_ok=True)
    
    output_file = os.path.join(ext_dict_dir, f"{lang_code}.txt")
    
    if os.path.exists(output_file):
        msg_status(_("Spell Checker: Hunspell word list already exists: {}").format(output_file))
        return True
    
    # Parse the Hunspell dictionary
    words = parse_hunspell_dic(lang_code)
    
    if not words:
        msg_status(_("Spell Checker: Failed to create word list for {}").format(lang_code))
        return False
    
    # Save to file, so next time we load the extended dict directly, 
    # TODO: maybe it is better to auto create the dict on the fly so if the user update his hunspell dict then he will get an updated extended dict also, automatically, (otherwise the user need to delete the extended dict manually to get a newly autocreated and updated one). lets leave it as is now because we need max speed spell checking and maybe change it in the future
    try:
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            for word in sorted(words):
                f.write(word + '\n')
        
        msg_status(_("Spell Checker: Created Hunspell word list: {} ({} words)").format(output_file, len(words)))
        return True
    
    except Exception as e:
        msg_status(_("Spell Checker: Error saving word list: {e}").format(e))
        return False


# ============================================================================
# LOAD EXTENDED DICTIONARY INTO A SET FOR FAST LOOKUP
# ============================================================================

cleaned_generic_dicts = set()
def load_extended_dict_temp():
    """
    Load the 'Extended Dictionary' words into a set for O(1) lookup.
    This is called only when spell-checking and the set is discarded after use.
    
    Behavior depends on op_use_extended_dictionary option:
    - If True: Load generic extended dictionary (e.g., en_generic.txt with 360k words)
      - If not found, fallback to Hunspell-compatible dictionary (e.g., en_US.txt with 70k words)
    - If False: Load or create Hunspell-compatible dictionary (e.g., en_US.txt with 70k words)
    
    Returns:
        set: Set of words for fast lookup, or empty set if unavailable
    """
    ext_dict_dir = os.path.join(_mydir, 'ext_dict')
    
    if op_use_extended_dictionary:
        # Try generic extended dictionary first
        lang_prefix = op_lang[:2] if len(op_lang) >= 2 else 'en'
        generic_txt_name = f'{lang_prefix}_generic.txt'
        generic_txt_path = os.path.join(ext_dict_dir, generic_txt_name)
        
        if os.path.exists(generic_txt_path):
            try:
                # {lang_prefix}_generic.txt should not start or end with white space, but if someone forget this then we should use {line.strip() for line in f}, but it is a litle bit slower than set(f.read().splitlines()), and this file will be loaded at every spell check so it should be the fastest posible, so lets clean it once per session to be safe
                if lang_prefix in cleaned_generic_dicts:
                    # Fast path: Assume clean, use splitlines
                    with open(generic_txt_path, 'r', encoding='utf-8') as f:
                        word_list = set(f.read().splitlines())
                else:
                    # Clean path: Load with strip, dedup preserving order, rewrite clean
                    with open(generic_txt_path, 'r', encoding='utf-8') as f:
                        words = [line.strip() for line in f if line.strip()]
                    # Dedup preserving order (using dict.fromkeys in Python 3.7+)
                    unique_words = list(dict.fromkeys(words))
                    word_list = set(unique_words)
                    
                    # Rewrite the file clean (no extra spaces, no blanks)
                    with open(generic_txt_path, 'w', encoding='utf-8', newline='') as fw:
                        for word in unique_words:
                            fw.write(word + '\n')
                    
                    cleaned_generic_dicts.add(lang_prefix)
                    msg_status(_("Spell Checker: Cleaned and loaded {} words from extended dictionary '{}'").format(len(word_list), generic_txt_name))
                    return word_list
                
                msg_status(_("Spell Checker: Loaded {} words from extended dictionary '{}'").format(len(word_list), generic_txt_name))
                return word_list
            except Exception as e:
                msg_status(_("Spell Checker: Error loading extended dictionary: {e}").format(e))
        
        # Fallback to Hunspell-compatible if generic not found or failed to load
        msg_status(_("Spell Checker: Extended dictionary not found: '{}'. Falling back to Hunspell-compatible.").format(generic_txt_name))
    
    # Hunspell-compatible dictionary (used directly if op_use_extended_dictionary=False, or as fallback)
    hunspell_txt_name = f'{op_lang}.txt'
    hunspell_txt_path = os.path.join(ext_dict_dir, hunspell_txt_name)
    
    # If it doesn't exist, try to create it from Hunspell dictionary
    if not os.path.exists(hunspell_txt_path):
        msg_status(_("Spell Checker: Hunspell word list not found. Creating from dictionary..."))
        if not create_hunspell_wordlist(op_lang):
            msg_status(_("Spell Checker: Could not create Hunspell word list. Using Enchant only."))
            return set()
    
    # Load the Hunspell word list (assume clean, use fast splitlines)
    try:
        with open(hunspell_txt_path, 'r', encoding='utf-8') as f:
            word_list = set(f.read().splitlines())
        msg_status(_("Spell Checker: Loaded {} words from Hunspell word list '{}'").format(len(word_list), hunspell_txt_name))
        return word_list
    except Exception as e:
        msg_status(_("Spell Checker: Error loading Hunspell word list: {e}").format(e))
        return set()
        
# ============================================================================
# ENCHANT INITIALIZATION
# ============================================================================
try:
    enchant = importlib.import_module(_ench)
    #import enchant
    dict_obj = enchant.Dict(op_lang)
except Exception as ex:
    msg_box(str(ex), MB_OK+MB_ICONERROR)
    dict_obj = None

spell_cache = {}

MARKTAG = 105 #unique int for all marker plugins

def is_word_char(c):
    return c.isalnum() or (c in "'_") # allow _ for later ignore words with _

def is_word_alpha(s):
    if not s: return False
    if s[0] in "'": return False #don't allow lead-quote

    #allow only alpha or '
    for c in s:
        if not (c.isalpha() or (c == "'")): return False

    return True

def caret_info(ed, r_click=False):
    if r_click:
        x, y = app_proc(PROC_GET_MOUSE_POS, '')
        x, y = ed.convert(CONVERT_SCREEN_TO_LOCAL, x, y)
        x, y = ed.convert(CONVERT_PIXELS_TO_CARET, x, y)
        x2, y2 = -1, -1
    else:
        x, y, x2, y2 = ed.get_carets()[0]

    line = ed.get_text_line(y)
    if not line: return
    if not (0 <= x < len(line)) or not is_word_char(line[x]): return None

    n1 = x
    n2 = x + 1
    while n1 > 0 and is_word_char(line[n1 - 1]):
        n1 -= 1
    while n2 < len(line) and is_word_char(line[n2]):
        n2 += 1
    x = n1

    return locals()

def get_current_word_under_caret(ed, r_click=False):
    info = caret_info(ed, r_click)
    if info:
        return info['line'][info['n1']:info['n2']]

def replace_current_word_with_word(ed, word, info):
    def inner():
        ed.replace(info['n1'], info['y'], info['n2'], info['y'], word)
    return inner

def find_spell_submenu():
    submenu_title = _("Spelling")
    for key in menu_proc("text", MENU_ENUM):
        if key['cap'] == submenu_title:
            return key['id']

def context_menu(ed, reset):
    if dict_obj is None:
        return

    spelling = find_spell_submenu()
    if spelling:
        menu_proc(spelling, MENU_CLEAR)
        menu_proc(spelling, MENU_SET_VISIBLE, command = False)

    if reset:
        visible = False
    else:
        info = caret_info(ed, True)
        if not info: return
        word = info['line'][info['n1']:info['n2']]
        if not word: return
        no_suggestions_found = _("No suggestions found")
        visible = not dict_obj.check(word) # only visible if incorrect word

    if not spelling:
        submenu_title = _("Spelling")
        spelling = menu_proc("text", MENU_ADD, caption = submenu_title, index = 0)

    menu_proc(spelling, MENU_SET_VISIBLE, command = visible)

    if not visible: return

    suggestions=dict_obj.suggest(word)
    for suggestion in suggestions:
        menu_proc(spelling, MENU_ADD, command = replace_current_word_with_word(ed, suggestion, info), caption = suggestion)

    if suggestions == []:
        menu_proc(spelling, MENU_ADD, caption = "("+no_suggestions_found+")")

dialog_pos = None
dialog_visible = False

def dlg_create():
    h = dlg_proc(0, DLG_CREATE)
    dlg_proc(h, DLG_PROP_SET, prop={'cap': _('Misspelled word'), 'w': 430, 'h': 300})

    # restore dialog position
    global dialog_pos
    if dialog_pos:
        dlg_proc(h, DLG_PROP_SET, prop={'x': dialog_pos[0], 'y': dialog_pos[1]})

    n = dlg_proc(h, DLG_CTL_ADD, 'panel')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={'name': 'panel3', 'w': 130, 'h': 200, 'x': 330, 'y': 10, 'a_l': None, 'a_r': ('', ']'), 'a_b': ('', ']'), 'sp_a': 6})

    n = dlg_proc(h, DLG_CTL_ADD, 'panel')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={'name': 'panel1', 'w': 90, 'h': 200, 'x': 10, 'y': 10, 'a_b': ('', ']'), 'sp_a': 6})

    n = dlg_proc(h, DLG_CTL_ADD, 'panel')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={'name': 'panel2', 'h': 200, 'x': 170, 'y': 10,
    'a_l': ('panel1', ']'), 'a_r': ('panel3', '['), 'a_b': ('', ']'), 'sp_a': 6, 'tab_order': 0})

    n = dlg_proc(h, DLG_CTL_ADD, 'label')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={'name': 'lbl_not_found', 'cap': _('Not found:'), 'x': 0, 'y': 10, 'p': 'panel1'})

    n = dlg_proc(h, DLG_CTL_ADD, 'label')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={'name': 'lbl_custom_text', 'cap': _('C&ustom text:'), 'x': 0, 'y': 40, 'p': 'panel1'})

    n = dlg_proc(h, DLG_CTL_ADD, 'edit')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={'name': 'edit2', 'x': 0, 'y': 36, 'w': 150, 'h': 25, 'a_r': ('', ']'), 'p': 'panel2'})

    n = dlg_proc(h, DLG_CTL_ADD, 'label')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={'name': 'lbl_suggestions', 'cap': _('Su&ggestions:'), 'x': 0, 'y': 70, 'p': 'panel1'})

    n = dlg_proc(h, DLG_CTL_ADD, 'listbox')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={'name': 'list1', 'x': 0, 'y': 70, 'w': 150, 'h': 100, 'a_r': ('', ']'), 'a_b': ('', ']'), 'p': 'panel2'})

    n = dlg_proc(h, DLG_CTL_ADD, 'edit')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={'name': 'edit1', 'x': 0, 'y': 4, 'w': 150, 'h': 25, 'ex0': True, 'a_r': ('', ']'), 'p': 'panel2',
    'tab_stop': -1})

    n = dlg_proc(h, DLG_CTL_ADD, 'button')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={'name': 'btn_ignore', 'cap': _('&Ignore'), 'x': 0, 'y': 70, 'h': 25, 'p': 'panel3', 'a_r': ('',']'),
    'ex0': True})

    n = dlg_proc(h, DLG_CTL_ADD, 'button')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={'name': 'btn_change', 'cap': _('&Change'), 'x': 0, 'y': 100, 'h': 25, 'p': 'panel3', 'a_r': ('',']')})

    n = dlg_proc(h, DLG_CTL_ADD, 'button')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={'name': 'btn_add', 'cap': _('&Add'), 'x': 0, 'y': 130, 'h': 25, 'p': 'panel3', 'a_r': ('',']')})

    n = dlg_proc(h, DLG_CTL_ADD, 'button')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={'name': 'btn_cancel', 'cap': _('Cancel'), 'x': 0, 'y': 190, 'h': 25, 'p': 'panel3', 'a_r': ('',']')})

    return h

def dlg_spell(sub):
    global dialog_visible
    if dialog_visible:
        return

    if dict_obj is None:
        msg_status(_('Spell Checker dictionary was not inited'))
        return

    rep_list = dict_obj.suggest(sub)
    en_list = bool(rep_list)
    if not en_list: rep_list = []

    RES_TEXT        = 3
    RES_WORDLIST    = 5
    RES_BTN_SKIP    = 6
    RES_BTN_REPLACE = 7
    RES_BTN_ADD     = 8
    RES_BTN_CANCEL  = 9

    h_dlg = dlg_create()
    dlg_proc(h_dlg, DLG_CTL_PROP_SET, name='edit1', prop={'val': sub})
    dlg_proc(h_dlg, DLG_CTL_PROP_SET, name='list1', prop={'items': '\t'.join(rep_list), 'val': ('0' if en_list else '-1')})

    btn = None
    def on_button(_btn):
        nonlocal btn
        btn = _btn
        dlg_proc(h_dlg, DLG_HIDE)

    dlg_proc(h_dlg, DLG_CTL_PROP_SET, name='btn_ignore', prop={'on_change': lambda *args, **kwargs: on_button(RES_BTN_SKIP)})
    dlg_proc(h_dlg, DLG_CTL_PROP_SET, name='btn_change', prop={'on_change': lambda *args, **kwargs: on_button(RES_BTN_REPLACE)})
    dlg_proc(h_dlg, DLG_CTL_PROP_SET, name='btn_add', prop={'on_change': lambda *args, **kwargs: on_button(RES_BTN_ADD)})
    dlg_proc(h_dlg, DLG_CTL_PROP_SET, name='btn_cancel', prop={'on_change': lambda *args, **kwargs: on_button(RES_BTN_CANCEL)})

    dlg_proc(h_dlg, DLG_SCALE)

    dialog_visible = True
    dlg_proc(h_dlg, DLG_SHOW_MODAL)
    dialog_visible = False

    # remember dialog position
    props = dlg_proc(h_dlg, DLG_PROP_GET)
    global dialog_pos
    dialog_pos = (props['x'],props['y'])

    if btn == RES_BTN_SKIP: return ''

    if btn == RES_BTN_ADD:
        dict_obj.add_to_pwl(sub)
        return 'ADD'

    if btn == RES_BTN_REPLACE:
        word = dlg_proc(h_dlg, DLG_CTL_PROP_GET, name='edit2')['val']
        list_index = dlg_proc(h_dlg, DLG_CTL_PROP_GET, name='list1')['val']
        if word   : return word
        if en_list: return rep_list[int(list_index)]
        else      : return ''

    dlg_proc(h_dlg, DLG_FREE)

def dlg_select_dict():
    items = sorted(enchant.list_languages())
    if op_lang in items:
        focused = items.index(op_lang)
    else:
        focused = -1
    res = dlg_menu(DMENU_LIST, items, focused, caption=_('Select dictionary'))
    if res is None: return
    return items[res]

def is_filetype_ok(fn):
    if op_file_types == '' : return False
    if op_file_types == '*': return True
    if fn == ''            : return True #allow in untitled tabs
    fn = os.path.basename(fn)
    n = fn.rfind('.')
    if n < 0: ext = '-'
    else    : ext = fn[n + 1:]
    return ',' + ext + ',' in ',' + op_file_types + ','

def need_check_tokens(ed):
    lexer = ed.get_prop(PROP_LEXER_FILE)
    if lexer:
        props = lexer_proc(LEXER_GET_PROP, lexer)
        return props['st_c'] != '' or props['st_s'] != ''
    else:
        return False

def fast_spell_check(word, extended_dict_set=None):
    """
    Fast spell check using extended dictionary + enchant fallback.
    Returns True if word is correct, False if misspelled.

    Args:
        word: The word to check (preserving original case)
        extended_dict_set: Optional extended dictionary set. If None, only enchant is used.
    """
    # If no extended dictionary available, use enchant only
    if extended_dict_set is None:
        return dict_obj.check(word) if dict_obj else True

    # First check: exact match in extended dictionary (very fast O(1) lookup)
    if word in extended_dict_set:
        return True

    # Second check: enchant (slower, but handles custom words added by user)
    if dict_obj:
        return dict_obj.check(word)

    # If no dict_obj, assume correct to avoid false positives
    return True

def do_check_line(ed, nline, line, x_start, x_end, check_tokens, cache, extended_dict_set=None):
    """
    find misspelled words in a line, but ignore words with numbers (v1.0) and words with underscore (my_var_name). and if lexer is active only comments/strings are checked.
    # TODO: ignore camel case vars (myVarName), like in javascript

    Args:
        extended_dict_set: Optional extended dictionary for fast lookups. If None, uses enchant only.

    Returns list of misspelled word positions.
    """
    count = 0
    res_x, res_y, res_n = [], [], []

    # Early exit for empty lines
    if not line:
        return (0, res_x, res_y, res_n)

    # Pre-check for URLs only if line contains ://
    has_urls = '://' in line
    url_ranges = None
    if has_urls:
        url_ranges = [m.span() for m in re_url.finditer(line)]
        if not url_ranges:
            has_urls = False

    end_pos = x_end if x_end >= 0 else len(line)
    # iteratively searches the given line of text, starting from x_start up to end_pos, and returns every continuous sequence of letters, numbers, underscores, and apostrophes that is found
    for m in word_re.finditer(line, x_start, end_pos):
        sub = m.group()

        # we repeat the cache check here despite we do it at the end, doing it here reduces a lot of consumed time because we bypass all the following checks
        if sub in cache:
            if cache[sub]:
                continue

        x_pos = m.start()
        if "'" in sub:
            # Strip all leading apostrophes
            while sub and sub[0] == "'":
                x_pos += 1
                sub = sub[1:]

            # Strip all trailing apostrophes
            while sub and sub[-1] == "'":
                sub = sub[:-1]

        if not sub:
            continue

        # so now sub is guaranteed to contain only characters from {letters, numbers, apostrophes (internal), underscores}

        # checking the cache here again is not bad, it reduces functions calls a litle bit and adds no overhead
        if sub in cache:
            if cache[sub]:
                continue

        # Filter 1: Skip words with numbers or invalid chars, this ensure the word contains only letters and internal apostrophes. this filters out "my_var", "v1", etc... while correctly keeping "it's"
        if not sub.replace("'", "").isalpha():
            cache[sub] = True # add to cache as a "correct" (ignorable) word. this have effect only if we check the cache in the begining
            continue


        # TODO: check speed again with filter 2 and 3 and optimize if needed
        # Filter 2: Ignore all-caps words (ex: CONSTANTS)
        if sub.isupper():
            cache[sub] = True
            continue

        # Filter 3: Ignore camelCase/MixedCase
        # This allows "word" (lower) and "Word" (title), but skips "myWord" or "MyWord" (usefull for javascript code).
        if not sub.islower() and not sub.istitle():
            cache[sub] = True
            continue

        # Filter 4: Skip URL
        if url_ranges:
            in_url = False
            for r_start, r_end in url_ranges:
                if r_start <= x_pos < r_end:
                    in_url = True
                    break
            if in_url:
                continue

        # Filter 5: Skip non-comment/string tokens (for files with a lexer)
        if check_tokens:
            kind = ed.get_token(TOKEN_GET_KIND, x_pos, nline)
            if kind not in ('c', 's'):
                continue

        # check spelling of the word and cache it
        # optimized spell check: Use word list first, then enchant
        if sub not in cache:
            cache[sub] = fast_spell_check(sub, extended_dict_set)
        
        # Skip correctly spelled words
        if cache[sub]:
            continue

        # --- We found a misspelled word ---
        count += 1
        res_x.append(x_pos)
        res_y.append(nline)
        res_n.append(len(sub))

    return (count, res_x, res_y, res_n)

def do_check_line_with_dialog(ed, nline, x_start, x_end, check_tokens, cache, extended_dict_set=None):
    """
    Find and interactively fix misspelled words in a line (dialog mode).
    Returns (count, replaced) or None if user cancels.

    Args:
        extended_dict_set: Optional extended dictionary for fast lookups.
    """
    count = 0
    replaced = 0
    checked_positions = set()  # Track positions we've already processed

    while True:
        # Get current line content (may have changed due to replacements)
        line = ed.get_text_line(nline)

        # Use do_check_line to find all misspelled words
        _, res_x, res_y, res_n = do_check_line(ed, nline, line, x_start, x_end, check_tokens, cache, extended_dict_set)

        # Find the first misspelled word we haven't checked yet
        word_found = False
        for i in range(len(res_x)):
            x_pos = res_x[i]
            word_len = res_n[i]

            if x_pos in checked_positions:
                continue

            # Mark this position as checked
            checked_positions.add(x_pos)
            word_found = True
            count += 1

            # Get the word
            sub = line[x_pos:x_pos + word_len]

            # Show dialog
            ed.set_caret(x_pos, nline, x_pos + word_len, nline)
            rep = dlg_spell(sub)

            if rep is None:
                return None  # User cancelled

            if rep == '':
                break  # Skip this word, continue to next
            elif rep == 'ADD':
                cache[sub] = True
                break  # Skip, but update cache

            # Replace the word
            replaced += 1
            ed.delete(x_pos, nline, x_pos + word_len, nline)
            ed.insert(x_pos, nline, rep)

            # Clear checked positions if replacement changes line length
            # This allows us to re-check positions that may have shifted
            if len(rep) != word_len:
                # Keep only positions before the replacement point
                checked_positions = {pos for pos in checked_positions if pos < x_pos}

            break  # Re-scan the line

        # If no new word was found, we're done with this line
        if not word_found:
            break

    return (count, replaced)


timer_editors = []
def timer_check(tag='', info=''):
    global timer_editors
    for ed in timer_editors:
        do_work(ed, False, False)
    timer_editors = []


def do_work(ed, with_dialog, allow_in_sel, allow_timer=False):
    # work only with remembered editor, until work is finished
    h_ed = ed.get_prop(PROP_HANDLE_SELF)
    editor = Editor(h_ed)

    count_all = 0
    count_replace = 0
    percent = -1
    app_proc(PROC_SET_ESCAPE, False)
    check_tokens = need_check_tokens(editor)
    cache = spell_cache if op_use_global_cache else {}  # Use global or local cache based on option

    # Load extended dictionary temporarily - will be garbage collected after function ends
    extended_dict_set = load_extended_dict_temp()

    # opening of Markdown file at startup gives not yet parsed file, so check fails
    if check_tokens and allow_timer:
        timer_editors.append(editor)
        timer_proc(TIMER_START_ONE, "module=cuda_spell_checker;func=timer_check;", interval=1000)
        return

    carets = editor.get_carets()
    if not carets: return
    x1, y1, x2, y2 = carets[0]

    is_selection = allow_in_sel and (y2 >= 0)

    if is_selection:
        if (y1, x1) > (y2, x2):
            x1, y1, x2, y2 = x2, y2, x1, y1  # sort if neccessary
        y2 += 1                      # last line has to be included (range)
        total_lines = y2 - y1
        lines = [editor.get_text_line(i) for i in range(y1, y2)]
    else:
        total_text = editor.get_text_all()
        lines = total_text.splitlines()
        total_lines = len(lines)
        x1 = 0
        x2 = -1
        y1 = 0
        y2 = total_lines

    if not with_dialog:
        editor.attr(MARKERS_DELETE_BY_TAG, MARKTAG)   # delete all, otherwise inserting additional markers takes a long time

    res_x = []
    res_y = []
    res_n = []
    escape = False

    if not with_dialog and allow_in_sel:
        start_time = time.time()

    msg_status(_('Spell-checking in progress...'), False)
    app_proc(PROC_PROGRESSBAR, 0)
    app_idle(False)

    for idx in range(total_lines):
        line = lines[idx]
        nline = y1 + idx
        percent_new = idx * 100 // total_lines
        if percent_new // 10 != percent // 10:  # update every 10% to reduce app_proc calls
            percent = percent_new
            app_proc(PROC_PROGRESSBAR, percent)
            app_idle(False)
            if app_proc(PROC_GET_ESCAPE, ''):
                app_proc(PROC_SET_ESCAPE, False)
                escape = True
                if op_confirm_esc:
                    escape = msg_box(_('Stop the spell-checking?'), MB_OKCANCEL + MB_ICONQUESTION) == ID_OK
                if escape:
                    msg_status(_('Spell-checking stopped'))
                    break

        x_start = x1 if nline == y1 else 0
        x_end = x2 if nline == y2 - 1 else -1

        if not with_dialog:
            res = do_check_line(editor, nline, line, x_start, x_end, check_tokens, cache, extended_dict_set)
            count_all += res[0]
            res_x += res[1]
            res_y += res[2]
            res_n += res[3]
        else:
            res = do_check_line_with_dialog(editor, nline, x_start, x_end, check_tokens, cache, extended_dict_set)
            if res is None:
                if count_all > 0:
                    reset_carets(editor, carets)
                app_proc(PROC_PROGRESSBAR, -1)
                return
            count_all += res[0]
            count_replace += res[1]

    # Word list will be garbage collected here when function exits
    app_proc(PROC_PROGRESSBAR, -1) # hide progressbar

    if not with_dialog:
        # setting all markers at once is a bit faster than line by line
        editor.attr(
            MARKERS_ADD_MANY, MARKTAG,
            res_x, res_y, res_n,
            COLOR_NONE, COLOR_NONE, op_underline_color,
            0, 0, 0,
            0, 0, op_underline_style, 0,
            show_on_map = True)

    if escape: return

    msg_sel = _('selection only') if is_selection else _('all text')

    time_str = ''
    if not with_dialog and allow_in_sel:
        duration = time.time() - start_time
        time_str = ', ' + _('time') + f' {duration:.2f}s'

    msg_status(_('Spell check: {}, {}, {} mistake(s), {} replace(s)').format(op_lang, msg_sel, count_all, count_replace) + time_str)

    if with_dialog and (count_all > 0):
        reset_carets(editor, carets)


def reset_carets(ed, carets):
    c = carets[0]
    ed.set_caret(*c)
    for c in carets[1:]:
        ed.set_caret(*c, CARET_ADD)

def do_work_if_name(ed_self, allow_in_sel, allow_timer=False):
    if is_filetype_ok(ed_self.get_filename()):
        do_work(ed_self, False, allow_in_sel, allow_timer)

def do_work_word(ed, with_dialog):
    if dict_obj is None:
        msg_status(_('Spell Checker dictionary was not inited'))
        return
    info = caret_info(ed)
    if not info:
        msg_status(_('Caret not on word-char'))
        return

    sub = get_current_word_under_caret(ed)
    if not is_word_alpha(sub):
        msg_status(_('Not text-word under caret'))
        return

    x = info['x']
    y = info['y']

    # Load word list temporarily for single word check
    extended_dict_set = load_extended_dict_temp()

    if with_dialog:
        ed.set_caret(x, y, x + len(sub), y)
        rep = dlg_spell(sub)
        if rep is None: return
        if rep == 'ADD':
            ed.attr(MARKERS_DELETE_BY_POS, MARKTAG, x, y, len(sub))
            if op_use_global_cache:
                spell_cache[sub] = True
            return
        if rep == '': return
        ed.attr(MARKERS_DELETE_BY_POS, MARKTAG, x, y, len(sub))
        ed.delete(x, y, x + len(sub), y)
        ed.insert(x, y, rep)
    else:
        if fast_spell_check(sub, extended_dict_set):
            msg_status(_('Word is Ok: "%s"') % sub)
            marker = MARKERS_DELETE_BY_POS
        else:
            msg_status(_('Word is misspelled: "%s"') % sub)
            marker = MARKERS_ADD

        ed.attr(
          marker, MARKTAG,
          x, y, len(sub),
          COLOR_NONE,
          COLOR_NONE,
          op_underline_color,
          0, 0, 0, 0, 0,
          op_underline_style,
          show_on_map = True)

def get_next_pos(x1, y1, is_next):
    m = ed.attr(MARKERS_GET)
    if not m: return
    m = [(x, y) for (tag, x, y, nlen, c1, c2, c3, f1, f2, f3, b1, b2, b3, b4, som, mo) in m if tag == MARKTAG]
    if not m: return

    if is_next:
        m = [(x, y) for (x, y) in m if (y > y1) or ((y == y1) and (x > x1))]
        if m: return m[0]
    else:
        m = [(x, y) for (x, y) in m if (y < y1) or ((y == y1) and (x < x1))]
        if m: return m[len(m) - 1]

def do_goto(is_next):
    x1, y1, x2, y2 = ed.get_carets()[0]
    m = get_next_pos(x1, y1, is_next)
    if m:
        ed.set_caret(m[0], m[1])
        msg_status(_('Go to misspelled: {}:{}').format(m[1] + 1, m[0] + 1))
    else:
        msg_status(_('Cannot go to next/prev'))

class Command:
    active = False

    def check(self):
        Command.active = True
        do_work(ed, False, True)

    def check_suggest(self):
        Command.active = True
        do_work(ed, True, True)

    def check_word(self):
        Command.active = True
        do_work_word(ed, False)

    def check_word_suggest(self):
        Command.active = True
        do_work_word(ed, True)

    def on_open(self, ed_self):
        do_work_if_name(ed_self, False, True)

    def on_change_slow(self, ed_self):
        do_work_if_name(ed_self, False)

    def on_click_right(self, ed_self, state):
        context_menu(ed_self, False)

    def select_dict(self):
        global op_lang
        global dict_obj

        res = dlg_select_dict()
        if res is None: return
        op_lang = res
        ini_write(filename_ini, 'op', 'lang', op_lang)
        dict_obj = enchant.Dict(op_lang)
        if op_use_global_cache:
            spell_cache.clear() # we clear the cache when user change the dictionary
        if Command.active:
            do_work_if_name(ed, False)

    def config(self):
        ini_write(filename_ini, 'op', 'lang'                    , op_lang)
        ini_write(filename_ini, 'op', 'underline_style'         , str(op_underline_style))
        ini_write(filename_ini, 'op', 'confirm_esc_key'         , bool_to_str(op_confirm_esc))
        ini_write(filename_ini, 'op', 'file_extension_list'     , op_file_types)
        ini_write(filename_ini, 'op', 'url_regex'               , op_url_regex)
        ini_write(filename_ini, 'op', 'use_global_cache'        , bool_to_str(op_use_global_cache))
        ini_write(filename_ini, 'op', 'use_extended_dictionary' , bool_to_str(op_use_extended_dictionary))
        if os.path.isfile(filename_ini): file_open(filename_ini)

    def goto_next(self):
        do_goto(True)

    def goto_prev(self):
        do_goto(False)

    def config_events(self):
        v = ini_read(filename_plugins, 'events', 'cuda_spell_checker', '')
        b_open   = ',on_open,'        in ',' + v + ','
        b_change = ',on_change_slow,' in ',' + v + ','

        DLG_W = 630
        DLG_H = 130
        BTN_W = 100
        c1 = chr(1)

        res = dlg_custom(_('Configure events'), DLG_W, DLG_H, '\n'.join([]
              + [c1.join(['type=check' , 'cap='+_('Handle event "on_open" (opening of a file)')             , 'pos=6,6,400,0' , 'val='+bool_to_str(b_open)])  ]
              + [c1.join(['type=check' , 'cap='+_('Handle event "on_change_slow" (editing of file + pause)'), 'pos=6,36,400,0', 'val='+bool_to_str(b_change)])]
              + [c1.join(['type=button', 'cap='+_('&OK')   , 'pos=%d,%d,%d,%d'%(DLG_W-BTN_W*2-12, DLG_H-30, DLG_W-BTN_W-12, 0)]), 'ex0=1']
              + [c1.join(['type=button', 'cap='+_('Cancel'), 'pos=%d,%d,%d,%d'%(DLG_W-BTN_W-6   , DLG_H-30, DLG_W-6       , 0)])         ]
              ),
              get_dict = True)
        if res is None: return

        b_open   = str_to_bool(res[0])
        b_change = str_to_bool(res[1])

        v = []
        if b_open:
            v += ['on_open']
        if b_change:
            v += ['on_change_slow']

        ini_write(filename_plugins, 'events', 'cuda_spell_checker', ','.join(v))

    def del_marks(self):
        Command.active = False
        ed.attr(MARKERS_DELETE_BY_TAG, MARKTAG)
        context_menu(ed, True) # reset context menu

    def get_all_misspelled_words(self):
        if dict_obj is None:
            msg_status(_('Spell Checker dictionary was not inited'))
            return
        check_tokens = need_check_tokens(ed)
        cache = spell_cache if op_use_global_cache else {}

        # Load word list temporarily
        extended_dict_set = load_extended_dict_temp()

        total_text = ed.get_text_all()
        lines = total_text.splitlines()
        total_lines = len(lines)
        misspelled = set()
        count_all = 0
        percent = -1
        app_proc(PROC_SET_ESCAPE, False)
        escape = False
        start_time = time.time()

        msg_status(_('Spell-checking in progress...'))
        app_proc(PROC_PROGRESSBAR, 0)
        app_idle(False)

        for idx in range(total_lines):
            percent_new = idx * 100 // total_lines
            if percent_new // 10 != percent // 10:  # update every 10% to reduce msg_status calls
                percent = percent_new
                app_proc(PROC_PROGRESSBAR, percent)
                app_idle(False)
                if app_proc(PROC_GET_ESCAPE, ''):
                    app_proc(PROC_SET_ESCAPE, False)
                    escape = True
                    if op_confirm_esc:
                        escape = msg_box(_('Stop the spell-checking?'), MB_OKCANCEL + MB_ICONQUESTION) == ID_OK
                    if escape:
                        msg_status(_('Spell-checking stopped'))
                        break
            line = lines[idx]
            nline = idx
            res = do_check_line(ed, nline, line, 0, -1, check_tokens, cache, extended_dict_set)
            count_all += res[0]
            for i in range(res[0]):
                x_pos = res[1][i]
                sub_len = res[3][i]
                sub = line[x_pos:x_pos + sub_len]
                misspelled.add(sub)

        app_proc(PROC_PROGRESSBAR, -1)
        duration = time.time() - start_time
        if escape:
            msg_status(_('Spell-checking stopped'))
            return
        sorted_misspelled = sorted(misspelled)
        if sorted_misspelled:
            msg_status(_('Found {} misspelled words, {} unique, time {:.2f}s').format(count_all, len(misspelled), duration))
            file_open('')
            ed.set_text_all('\n'.join(sorted_misspelled))
            ed.set_prop(PROP_TAB_TITLE, _("Misspelled words"))
        else:
            msg_status(_('No misspelled words found, time {:.2f}s').format(duration))

    def toggle_extended_dictionary(self):
        """Toggle between extended and Hunspell-compatible dictionaries"""
        global op_use_extended_dictionary
        
        op_use_extended_dictionary = not op_use_extended_dictionary
        ini_write(filename_ini, 'op', 'use_extended_dictionary', bool_to_str(op_use_extended_dictionary))
        
        if op_use_extended_dictionary:
            msg_status(_('Switched to extended dictionary (more words, generic language)'))
        else:
            msg_status(_('Switched to Hunspell dictionary (language variant specific)'))
        
        # Clear cache and re-check if active
        if op_use_global_cache:
            spell_cache.clear()
        
        if Command.active:
            do_work_if_name(ed, False)
            
    '''
    def toggle_hilite(self):
        self.active = not self.active
        if self.active:
            ev = 'on_change_slow'
            do_work_if_name(ed)
        else:
            ev = ''
            ed.attr(MARKERS_DELETE_BY_TAG, MARKTAG)
        app_proc(PROC_SET_EVENTS, 'cuda_spell_checker;'+ev+';;')

        text = _('Underlines on') if self.active else _('Underlines off')
        msg_status(text)
    '''
