# coding: utf-8

import importlib
import os
import sys
import re
import string
import time
import tempfile
import json
from .enchant_architecture import EnchantArchitecture
from cudatext import *

from cudax_lib import get_translation
_ = get_translation(__file__)  # I18N

def bool_to_str(v): return '1' if v else '0'
def str_to_bool(s): return s == '1'

filename_ini = os.path.join(app_path(APP_DIR_SETTINGS), 'cuda_spell_checker.ini')
filename_plugins = os.path.join(app_path(APP_DIR_SETTINGS), 'plugins.ini')
_mydir = os.path.dirname(__file__)
filename_install_inf = os.path.join(_mydir, 'install.inf')

op_underline_color = app_proc(PROC_THEME_UI_DICT_GET, '')['EdMicromapSpell']['color']

op_lang                      =             ini_read(filename_ini, 'op', 'lang'                      , 'en_US'          )
op_underline_style           =         int(ini_read(filename_ini, 'op', 'underline_style'           , '6'              ))
op_confirm_esc               = str_to_bool(ini_read(filename_ini, 'op', 'confirm_esc_key'           , '0'              ))
op_file_types                =             ini_read(filename_ini, 'op', 'file_extension_list'       , '*'              )
op_url_regex                 =             ini_read(filename_ini, 'op', 'url_regex'                 , r'\bhttps?://\S+')
op_cache_lifetime            =         int(ini_read(filename_ini, 'op', 'cache_lifetime'            , '60'             ))  # in minutes, 0=forever

_events_str = ini_read(filename_install_inf, 'item1', 'events', '')
install_inf_events = {ev.strip() for ev in _events_str.split(',') if ev.strip()}

re_url = re.compile(op_url_regex, 0)
word_re = re.compile(r"[\w']+")

_ench = EnchantArchitecture()

# Get temp directory for cached dictionary
TEMP_DICT_DIR = os.path.join(tempfile.gettempdir(), 'cuda_spell_checker')

# File paths for persistent storage
TIMESTAMPS_FILE = os.path.join(TEMP_DICT_DIR, 'dict_timestamps.json')
PERSISTENT_CACHE_PREFIX = 'persistent_cache_'  # Will be suffixed with lang code

# Global unified cache: contains dictionary words and Enchant responses
# Maps word -> True (correct) or False (misspelled)
spell_cache = {}
cache_loaded = False  # Track if dictionary has been pre-loaded into cache
cache_last_save_time = 0  # Track when cache was last loaded/created
cache_needs_save = False  # Track if cache needs to be saved to disk, this prevents unnecessary disk writes

# On Windows expand PATH environment variable so that Enchant can find its backend DLLs
if sys.platform == "win32":
    os.environ["PATH"] += ";" + os.path.join(_mydir, _ench, "data", "bin") + ";" + os.path.join(_mydir, _ench, "data", "lib", "enchant-2")

sys.path.append(_mydir)

try:
    enchant = importlib.import_module(_ench)
    #import enchant
    dict_obj = enchant.Dict(op_lang)
except Exception as ex:
    msg_box(str(ex), MB_OK+MB_ICONERROR)
    dict_obj = None

MARKTAG = 105 #unique int for all marker plugins

# Track newly opened files that haven't been checked yet
newly_opened_files = set()

def set_events_safely(events_to_add, lexer_list='', filter_str=''):
    """
    Set events while preserving those from install.inf. because PROC_SET_EVENTS resets all the events including those from install.inf (only events in plugins.ini are preserved).

    Args:
        events_to_add: Set or list of event names to add
        lexer_list: Comma-separated lexer names (optional)
        filter_str: Filter parameter for certain events (optional)
    """
    all_events = install_inf_events | set(events_to_add)
    event_list_str = ','.join(all_events)
    app_proc(PROC_SET_EVENTS, f"cuda_spell_checker;{event_list_str};{lexer_list};{filter_str}")

def get_hunspell_dict_path(lang_code):
    """
    Get the path to the Hunspell dictionary file for a language.

    Args:
        lang_code: Language code like 'en_US', 'de_DE', etc.
    """
    suffix = app_proc(PROC_GET_OS_SUFFIX, '')
    if suffix=='':
        dic_dir = os.path.join(_mydir, _ench, "data", "share", "enchant", "hunspell")
    elif suffix=='__linux':
        dic_dir = '/usr/share/hunspell'
    elif suffix=='__mac':
        dic_dir = '/Library/Spelling/'
    else:
        print('ERROR: Spell Checker cannot find Hunspell dicts, OS: '+suffix)
        return None

    return os.path.join(dic_dir, lang_code + '.dic')

def get_dict_info(lang_code):
    """Get the modification timestamp and file size of a Hunspell dictionary file."""
    dic_file = get_hunspell_dict_path(lang_code)
    if dic_file and os.path.exists(dic_file):
        stat = os.stat(dic_file)
        return {
            'timestamp': stat.st_mtime,
            'size': stat.st_size
        }
    return None

def load_timestamps():
    """Load dictionary timestamps and sizes from file."""
    if os.path.exists(TIMESTAMPS_FILE):
        try:
            with open(TIMESTAMPS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_timestamps(timestamps):
    """Save dictionary timestamps and sizes to file."""
    try:
        if not os.path.isdir(TEMP_DICT_DIR):
            os.makedirs(TEMP_DICT_DIR)
        with open(TIMESTAMPS_FILE, 'w', encoding='utf-8') as f:
            json.dump(timestamps, f)
    except Exception as e:
        print(f"Spell Checker: Error saving timestamps: {e}")

def is_dict_updated(lang_code):
    """Check if Hunspell dictionary has been updated since last check.
    First checks file size, then timestamp if size is the same."""
    current_info = get_dict_info(lang_code)
    if current_info is None:
        return False

    timestamps = load_timestamps()
    saved_info = timestamps.get(lang_code)

    # If no saved info, dictionary is "new"
    if saved_info is None:
        timestamps[lang_code] = current_info
        save_timestamps(timestamps)
        return True

    # Check file size first (more likely to change, user may use an old dictionary so checking size is more robust)
    if current_info['size'] != saved_info.get('size'):
        # Size changed, dictionary was updated
        timestamps[lang_code] = current_info
        save_timestamps(timestamps)
        return True

    # If size is the same, check timestamp
    if current_info['timestamp'] > saved_info.get('timestamp', 0):
        # Timestamp changed, dictionary was updated
        timestamps[lang_code] = current_info
        save_timestamps(timestamps)
        return True

    return False

def get_persistent_cache_path(lang_code):
    """Get the path to the persistent cache file for a language."""
    return os.path.join(TEMP_DICT_DIR, f'{PERSISTENT_CACHE_PREFIX}{lang_code}.json')

def parse_hunspell_dic(lang_code):
    """
    Parse a Hunspell .dic file and extract all base words.
    Returns a set of words.
    """
    dic_file = get_hunspell_dict_path(lang_code)

    if not dic_file or not os.path.exists(dic_file):
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
        print(_("ERROR: Spell Checker: Error parsing Hunspell dictionary: {}").format(e))
        return set()

def create_hunspell_wordlist(lang_code):
    """
    Create a cached Hunspell-compatible word list from Hunspell dictionary.
    Saves it to temp folder 'cuda_spell_checker' with the language code name.
    Only recreates if dictionary file size or timestamp changed.

    Args:
        lang_code: Language code like 'en_US', 'de_DE', etc.
    """
    # Ensure temp directory exists
    if not os.path.isdir(TEMP_DICT_DIR):
        try:
            os.makedirs(TEMP_DICT_DIR)
        except Exception as e:
            msg_status(_("Spell Checker: Error creating temp directory: {}").format(e))
            return False

    output_file = os.path.join(TEMP_DICT_DIR, f'{lang_code}.txt')

    # Check if dictionary was updated (size or timestamp changed)
    if is_dict_updated(lang_code) and os.path.exists(output_file):
        # Dictionary was updated, delete old wordlist and persistent cache
        try:
            os.remove(output_file)
            persistent_cache_file = get_persistent_cache_path(lang_code)
            if os.path.exists(persistent_cache_file):
                os.remove(persistent_cache_file)
                msg_status(_("Spell Checker: Dictionary updated, cleared caches"))
        except Exception as e:
            print(f"Spell Checker: Error removing old cache files: {e}")

    # If wordlist already exists and dict wasn't updated, skip creation
    if os.path.exists(output_file):
        return True

    # Parse the Hunspell dictionary
    words = parse_hunspell_dic(lang_code)

    if not words:
        msg_status(_("Spell Checker: Failed to create word list for {}").format(lang_code))
        return False

    # Save to file
    try:
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            for word in sorted(words):
                f.write(word + '\n')

        msg_status(_("Spell Checker: Created cached word list: {} ({} words)").format(output_file, len(words)))
        return True

    except Exception as e:
        msg_status(_("Spell Checker: Error saving word list: {}").format(e))
        return False

def load_persistent_cache(lang_code):
    """Load persistent cache from disk."""
    cache_file = get_persistent_cache_path(lang_code)

    if not os.path.exists(cache_file):
        return {}

    # Check if cache has expired
    if op_cache_lifetime > 0:
        cache_age_minutes = (time.time() - os.path.getmtime(cache_file)) / 60
        if cache_age_minutes > op_cache_lifetime:
            # Cache expired, delete it
            try:
                os.remove(cache_file)
                msg_status(_("Spell Checker: Persistent cache expired and deleted"))
            except:
                pass
            return {}

    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        msg_status(_("Spell Checker: Loaded {} entries from persistent cache").format(len(cache_data)))
        return cache_data
    except Exception as e:
        print(f"Spell Checker: Error loading persistent cache: {e}")
        return {}

def save_persistent_cache(lang_code, cache_data):
    """Save persistent cache to disk."""
    global cache_needs_save

    if not cache_needs_save:
        return

    cache_file = get_persistent_cache_path(lang_code)

    try:
        if not os.path.isdir(TEMP_DICT_DIR):
            os.makedirs(TEMP_DICT_DIR)

        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, separators=(',', ':'))  # Compact format for speed

        cache_needs_save = False
        # Don't show status message here to avoid spam
    except Exception as e:
        print(f"Spell Checker: Error saving persistent cache: {e}")

def load_dictionary_into_cache():
    """
    Load the Hunspell dictionary words and persistent cache into spell_cache.
    Only loads base dictionary if persistent cache doesn't exist.
    """
    global spell_cache, cache_loaded, cache_last_save_time

    # If already loaded, return early
    if cache_loaded:
        return

    # Load persistent cache first
    persistent_cache = load_persistent_cache(op_lang)

    # If persistent cache exists and is not empty, use it
    # (it already contains base dictionary words marked as True)
    if persistent_cache:
        spell_cache.update(persistent_cache)
        cache_loaded = True
        cache_last_save_time = time.time()
        msg_status(_("Spell Checker: Loaded {} entries from persistent cache").format(len(persistent_cache)))
        return

    # Persistent cache doesn't exist or is empty, need to load base dictionary
    hunspell_txt_name = f'{op_lang}.txt'
    hunspell_txt_path = os.path.join(TEMP_DICT_DIR, hunspell_txt_name)

    # Check if dictionary was updated and regenerate if needed
    if is_dict_updated(op_lang) or not os.path.exists(hunspell_txt_path):
        if not create_hunspell_wordlist(op_lang):
            msg_status(_("Spell Checker: Could not create cached word list. Using Enchant only."))
            cache_loaded = True  # Mark as loaded even if failed, to avoid repeated attempts
            cache_last_save_time = time.time()
            return

    # Load base dictionary words
    try:
        with open(hunspell_txt_path, 'r', encoding='utf-8') as f:
            word_list = f.read().splitlines()

        # Add dictionary words to cache
        for word in word_list:
            spell_cache[word] = True

        cache_loaded = True
        cache_last_save_time = time.time()

        msg_status(_("Spell Checker: Loaded {} base dictionary words into cache").format(len(word_list)))

    except Exception as e:
        msg_status(_("Spell Checker: Error loading cached word list: {}").format(e))
        cache_loaded = True  # Mark as loaded to avoid repeated attempts
        cache_last_save_time = time.time()

def clear_spell_cache(tag='', info=''):
    """Clear the spell cache after cache_lifetime expires."""
    global spell_cache, cache_loaded, cache_last_save_time

    if op_cache_lifetime == 0:
        # Cache is persistent forever, don't clear
        return

    # Delete persistent cache file
    cache_file = get_persistent_cache_path(op_lang)
    if os.path.exists(cache_file):
        try:
            os.remove(cache_file)
        except:
            pass

    spell_cache.clear()
    cache_loaded = False
    cache_last_save_time = 0
    msg_status(_('Spell Checker: Cache cleared after {} minutes').format(op_cache_lifetime))

def start_cache_timer():
    """Start or restart the cache clear timer if cache_lifetime > 0."""
    if op_cache_lifetime == 0:
        # Cache is persistent forever, no timer needed
        return

    global cache_last_save_time

    # Only restart timer if cache was just loaded
    if cache_last_save_time == 0 or (time.time() - cache_last_save_time) < 60:
        callback = "module=cuda_spell_checker;func=clear_spell_cache;"
        timer_proc(TIMER_STOP, callback, interval=0)
        cache_lifetime_ms = op_cache_lifetime * 60 * 1000
        timer_proc(TIMER_START_ONE, callback, interval=cache_lifetime_ms)

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
    if lexer and not lexer.endswith('^'):
        props = lexer_proc(LEXER_GET_PROP, lexer)
        return props['st_c'] != '' or props['st_s'] != ''
    else:
        return False

def do_check_line(ed, nline, line, x_start, x_end, check_tokens, cache):
    """
    find misspelled words in a line, but ignore words with numbers (v1.0), words with underscore (my_var_name), UPPERCASE, camelCase, and MixedCase. and if lexer is active only comments/strings are checked.

    Uses unified spell_cache which contains pre-loaded dictionary words and runtime spell-check results.

    Returns list of misspelled word positions.
    """
    global cache_needs_save
    count = 0
    res_x, res_y, res_n = [], [], []

    # Early exit for empty lines
    if not line:
        return (0, res_x, res_y, res_n)

    is_ascii = line.isascii()

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

        # Check cache first (includes both pre-loaded dictionary and runtime results)
        if sub in cache:
            if cache[sub]:  # known correct
                continue
            # do not do this, it seems logic and faster (and it is faster), but it is wrong, ex: the first check will find http://good.com , if com was marked as bad somewhere else, here we will skip and mark this word as misspelled, but it is a link it should not be marked as bad, so it needs to pass the following filters before considering it bad
            # else:
                # known wrong from previous run
                # count += 1
                # res_x.append(m.start())
                # res_y.append(nline)
                # res_n.append(len(sub))
                # continue

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

        # Check cache again after stripping apostrophes
        if sub in cache:
            if cache[sub]:
                continue

        # Filter 1: Skip words with numbers or invalid chars, this ensure the word contains only letters and internal apostrophes. this filters out "my_var", "v1", etc... while correctly keeping "it's"
        if not sub.replace("'", "").isalpha():
            cache[sub] = True # add to cache as a "correct" (ignorable) word
            cache_needs_save = True
            continue

        # Filter 2: Ignore camelCase/MixedCase/ALL-CAPS. Logic: If it is not Lowercase AND not Titlecase, it is either UPPER, camelCase, or MixedCase. so skip and cache it.
        # We check islower first as it's the most common success case.
        if not sub.islower() and not sub.istitle():
            cache[sub] = True
            cache_needs_save = True
            continue

        # Filter 3: Skip URL
        if url_ranges:
            in_url = False
            for r_start, r_end in url_ranges:
                if r_start <= x_pos < r_end:
                    in_url = True
                    break
            if in_url:
                continue

        # Filter 4: Skip non-comment/string tokens (for files with a lexer)
        if check_tokens:
            kind = ed.get_token(TOKEN_GET_KIND, x_pos, nline)
            if kind not in ('c', 's'):
                continue

        if sub in cache:
            if cache[sub]:
                continue
            else:
                # known wrong from previous run
                count += 1

                if not is_ascii:
                    # fix for word after Emoji, wrong attr offset: encode to UTF-16 and count code units
                    utf16_str = line[:x_pos].encode('utf-16-le')
                    x_pos = len(utf16_str) // 2

                res_x.append(x_pos)
                res_y.append(nline)
                res_n.append(len(sub))
                continue
        else:
            # Check spelling and cache the result
            cache[sub] = dict_obj.check(sub)
            cache_needs_save = True

        # Skip correctly spelled words
        if cache[sub]:
            continue

        # --- We found a misspelled word ---
        count += 1

        if not is_ascii:
            # fix for word after Emoji, wrong attr offset: encode to UTF-16 and count code units
            utf16_str = line[:x_pos].encode('utf-16-le')
            x_pos = len(utf16_str) // 2

        res_x.append(x_pos)
        res_y.append(nline)
        res_n.append(len(sub))

    return (count, res_x, res_y, res_n)

def do_check_line_with_dialog(ed, nline, x_start, x_end, check_tokens, cache):
    """
    Find and interactively fix misspelled words in a line (dialog mode).
    Returns (count, replaced) or None if user cancels.

    Uses unified spell_cache.
    """
    global cache_needs_save
    count = 0
    replaced = 0
    checked_positions = set()  # Track positions we've already processed

    while True:
        # Get current line content (may have changed due to replacements)
        line = ed.get_text_line(nline)

        # Use do_check_line to find all misspelled words
        _, res_x, res_y, res_n = do_check_line(ed, nline, line, x_start, x_end, check_tokens, cache)

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
            sub = ed.get_text_substr(x_pos, nline, x_pos + word_len, nline)

            # Show dialog
            ed.set_caret(x_pos, nline, x_pos + word_len, nline)
            rep = dlg_spell(sub)

            if rep is None:
                return None  # User cancelled

            if rep == '':
                break  # Skip this word, continue to next
            elif rep == 'ADD':
                cache[sub] = True
                cache_needs_save = True
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

def lexer_parsed(ed_self):
    """Event handler for when lexer finishes parsing.
    Called after lexer has finished parsing (only if parsing took >=600ms)"""
    # Unsubscribe from on_lexer_parsed to avoid duplicate checks calls when the user change the lexer
    set_events_safely([])

    # Perform spell check now that lexer is ready
    msg_status(_("Spell Checker: Lexer has just finished its parsing. Checking again..."))
    do_work(ed_self, False, True, False, False)

def do_work(ed, with_dialog, allow_in_sel, allow_timer=False, on_lexer_parsed_subscription=False):
    # work only with remembered editor, until work is finished
    global cache_needs_save

    h_ed = ed.get_prop(PROP_HANDLE_SELF)
    editor = Editor(h_ed)

    count_all = 0
    count_replace = 0
    percent = -1
    app_proc(PROC_SET_ESCAPE, False)
    check_tokens = need_check_tokens(editor)

    if check_tokens and on_lexer_parsed_subscription and not with_dialog:
        # when we call check() on a big file that uses a lexer we will get wrong results because Cudatext takes some time to parse and set tokens (comments, strings..etc), so we need to subscribe to on_lexer_parsed. but this means that the file may be checked twice, one because we clicked check, and one if on_lexer_parsed fires, we cannot prevent this unless the API removes the 600ms limit
        # Subscribe to on_lexer_parsed event for files that take longer than 600ms to parse
        set_events_safely(['on_lexer_parsed'])

    # opening of Markdown file at startup gives not yet parsed file, so check fails
    if check_tokens and allow_timer:
        timer_editors.append(editor)
        timer_proc(TIMER_START_ONE, "module=cuda_spell_checker;func=timer_check;", interval=600) # no need to wait more than 600ms because we subscribe to on_lexer_parsed event which will fire if lexer parsing takes more than 600ms. the file will be checked twice if on_lexer_parsed fires, we can do nothing to prevent this unless the API removes the 600ms limit
        return

    # Always use unified cache and start/restart the 30-minute cache clear timer
    cache = spell_cache
    start_cache_timer()

    # Load dictionary into cache if not already loaded
    load_dictionary_into_cache()

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
            res = do_check_line(editor, nline, line, x_start, x_end, check_tokens, cache)
            count_all += res[0]
            res_x += res[1]
            res_y += res[2]
            res_n += res[3]
        else:
            res = do_check_line_with_dialog(editor, nline, x_start, x_end, check_tokens, cache)
            if res is None:
                if count_all > 0:
                    reset_carets(editor, carets)
                app_proc(PROC_PROGRESSBAR, -1)
                # Save cache before returning
                if cache_needs_save:
                    save_persistent_cache(op_lang, cache)
                return
            count_all += res[0]
            count_replace += res[1]

    app_proc(PROC_PROGRESSBAR, -1) # hide progressbar

    # Save persistent cache after checking file (not for word-only checks)
    if cache_needs_save:
        save_persistent_cache(op_lang, cache)

    if escape: return

    msg_sel = _('selection only') if is_selection else _('all text')

    time_str = ''
    if not with_dialog and allow_in_sel:
        duration = time.time() - start_time
        time_str = ', ' + _('time') + f' {duration:.2f}s'

    msg_status(_('Spell check: {}, {}, {} mistake(s), {} replace(s)').format(op_lang, msg_sel, count_all, count_replace) + time_str)

    if not with_dialog:
        # setting all markers at once is a bit faster than line by line
        editor.attr(
            MARKERS_ADD_MANY, MARKTAG,
            res_x, res_y, res_n,
            COLOR_NONE, COLOR_NONE, op_underline_color,
            0, 0, 0,
            0, 0, op_underline_style, 0,
            show_on_map = True)

    if with_dialog and (count_all > 0):
        reset_carets(editor, carets)


def reset_carets(ed, carets):
    c = carets[0]
    ed.set_caret(*c)
    for c in carets[1:]:
        ed.set_caret(*c, CARET_ADD)

def do_work_if_name(ed_self, allow_in_sel, allow_timer=False, on_lexer_parsed_subscription=False):
    if is_filetype_ok(ed_self.get_filename()):
        do_work(ed_self, False, allow_in_sel, allow_timer, on_lexer_parsed_subscription)

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

    # Load dictionary into cache if not already loaded
    load_dictionary_into_cache()

    # Start cache timer
    start_cache_timer()

    if with_dialog:
        ed.set_caret(x, y, x + len(sub), y)
        rep = dlg_spell(sub)
        if rep is None: return
        if rep == 'ADD':
            ed.attr(MARKERS_DELETE_BY_POS, MARKTAG, x, y, len(sub))
            spell_cache[sub] = True
            return
        if rep == '': return
        ed.attr(MARKERS_DELETE_BY_POS, MARKTAG, x, y, len(sub))
        ed.delete(x, y, x + len(sub), y)
        ed.insert(x, y, rep)
    else:
        if dict_obj.check(sub):
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
    m = ed.attr(MARKERS_GET_DICT)
    if not m: return
    m = [(i['x'], i['y']) for i in m if i['tag'] == MARKTAG]
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
        msg_status(_('Cannot go to next/previous misspelled'))

class Command:
    active = False

    def __init__(self):
        try:
            create_hunspell_wordlist(op_lang)
        except Exception as e:
            print(f"Spell Checker: Error creating cached dictionary: {e}")

    def check(self):
        Command.active = True
        do_work(ed, False, True, False, True)

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
        """Mark file as newly opened. If it's already focused, check it immediately."""
        h_ed = ed_self.get_prop(PROP_HANDLE_SELF)
        newly_opened_files.add(h_ed)

        # Check if this editor is currently focused
        # If yes, check immediately (because on_focus won't fire)
        is_focused = ed_self.get_prop(PROP_FOCUSED)
        if is_focused:
            # File is already focused, check it now
            newly_opened_files.discard(h_ed)
            do_work_if_name(ed_self, False, True, True)

    def on_focus(self, ed_self):
        """Check file only if it's newly opened AND now focused"""
        h_ed = ed_self.get_prop(PROP_HANDLE_SELF)

        # Only check if this file was just opened (is in newly_opened_files)
        if h_ed in newly_opened_files:
            newly_opened_files.discard(h_ed)  # Remove from set after checking
            do_work_if_name(ed_self, False, True, True)

    def on_change_slow(self, ed_self):
        do_work_if_name(ed_self, False)

    def on_click_right(self, ed_self, state):
        context_menu(ed_self, False)

    def on_lexer_parsed(self, ed_self):
        """Event handler for when lexer finishes parsing"""
        lexer_parsed(ed_self)

    def select_dict(self):
        global op_lang
        global dict_obj

        res = dlg_select_dict()
        if res is None: return
        op_lang = res
        ini_write(filename_ini, 'op', 'lang', op_lang)
        dict_obj = enchant.Dict(op_lang)

        # Clear cache when user changes dictionary
        spell_cache.clear()
        global cache_loaded
        cache_loaded = False

        # Regenerate cached dictionary for new language
        try:
            create_hunspell_wordlist(op_lang)
        except Exception as e:
            print(f"Spell Checker: Error creating cached dictionary: {e}")

        if Command.active:
            do_work_if_name(ed, False)

    def config(self):
        ini_write(filename_ini, 'op', 'lang'                    , op_lang)
        ini_write(filename_ini, 'op', 'underline_style'         , str(op_underline_style))
        ini_write(filename_ini, 'op', 'confirm_esc_key'         , bool_to_str(op_confirm_esc))
        ini_write(filename_ini, 'op', 'file_extension_list'     , op_file_types)
        ini_write(filename_ini, 'op', 'url_regex'               , op_url_regex)
        ini_write(filename_ini, 'op', 'cache_lifetime'          , str(op_cache_lifetime))
        if os.path.isfile(filename_ini): file_open(filename_ini)

    def goto_next(self):
        do_goto(True)

    def goto_prev(self):
        do_goto(False)

    def config_events(self):
        v = ini_read(filename_plugins, 'events', 'cuda_spell_checker', '')
        b_open   = ',on_open,'        in ',' + v + ','
        b_focus  = ',on_focus,'       in ',' + v + ','
        b_change = ',on_change_slow,' in ',' + v + ','

        # Combine on_open and on_focus into single option for user
        b_check_on_open = b_open and b_focus

        DLG_W = 630
        DLG_H = 130
        BTN_W = 100
        c1 = chr(1)

        res = dlg_custom(_('Configure events'), DLG_W, DLG_H, '\n'.join([]
              + [c1.join(['type=check' , 'cap='+_('Check spelling when opening files')             , 'pos=6,6,400,0' , 'val='+bool_to_str(b_check_on_open)])  ]
              + [c1.join(['type=check' , 'cap='+_('Check spelling while editing (after pause)'), 'pos=6,36,400,0', 'val='+bool_to_str(b_change)])]
              + [c1.join(['type=button', 'cap='+_('&OK')   , 'pos=%d,%d,%d,%d'%(DLG_W-BTN_W*2-12, DLG_H-30, DLG_W-BTN_W-12, 0)]), 'ex0=1']
              + [c1.join(['type=button', 'cap='+_('Cancel'), 'pos=%d,%d,%d,%d'%(DLG_W-BTN_W-6   , DLG_H-30, DLG_W-6       , 0)])         ]
              ),
              get_dict = True)
        if res is None: return

        b_check_on_open = str_to_bool(res[0])
        b_change = str_to_bool(res[1])

        v = []
        if b_check_on_open:
            v += ['on_open', 'on_focus']  # Both events needed for this feature
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

        # Always use unified cache and start timer
        cache = spell_cache
        start_cache_timer()

        # Load dictionary into cache if not already loaded
        load_dictionary_into_cache()

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
            res = do_check_line(ed, nline, line, 0, -1, check_tokens, cache)
            count_all += res[0]
            for i in range(res[0]):
                x_pos = res[1][i]
                sub_len = res[3][i]
                sub = ed.get_text_substr(x_pos, nline, x_pos + sub_len, nline)
                misspelled.add(sub)

        app_proc(PROC_PROGRESSBAR, -1)

        # Save cache after this operation
        global cache_needs_save
        if cache_needs_save:
            save_persistent_cache(op_lang, cache)

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
