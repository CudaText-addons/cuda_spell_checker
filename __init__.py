# coding: utf-8

import importlib
import os
import sys
import re
import string
from .enchant_architecture import EnchantArchitecture
from cudatext import *

from cudax_lib import get_translation
_ = get_translation(__file__)  # I18N

def bool_to_str(v): return '1' if v else '0'
def str_to_bool(s): return s == '1'

filename_ini = os.path.join(app_path(APP_DIR_SETTINGS), 'cuda_spell_checker.ini')
op_underline_color = app_proc(PROC_THEME_UI_DICT_GET, '')['EdMicromapSpell']['color']

op_lang            =             ini_read(filename_ini, 'op', 'lang'               , 'en_US'          )
op_underline_style =         int(ini_read(filename_ini, 'op', 'underline_style'    , '6'              ))
op_confirm_esc     = str_to_bool(ini_read(filename_ini, 'op', 'confirm_esc_key'    , '0'              ))
op_file_types      =             ini_read(filename_ini, 'op', 'file_extension_list', '*'              )
op_url_regex       =             ini_read(filename_ini, 'op', 'url_regex'          , r'\bhttps?://\S+')

re_url = re.compile(op_url_regex, 0)

_mydir = os.path.dirname(__file__)
_ench = EnchantArchitecture()

# On Windows expand PATH environment variable so that Enchant can find its backend DLLs
if os.name == "nt":
    os.environ["PATH"] += ";" + os.path.join(_mydir, _ench) + ";" + os.path.join(_mydir, _ench, "lib", "enchant")

sys.path.append(_mydir)

try:
    enchant = importlib.import_module(_ench)
    #import enchant
    dict_obj = enchant.Dict(op_lang)
except Exception as ex:
    msg_box(str(ex), MB_OK+MB_ICONERROR)

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

def caret_info():
    x, y, x2, y2 = ed.get_carets()[0]
    line = ed.get_text_line(y)
    if not line: return
    if not (0 <= x < len(line)) or not is_word_char(line[x]): return None

    n1 = x
    n2 = x + 1
    while n1 > 0 and is_word_char(line[n1 - 1])    : n1 -= 1
    while n2 < len(line) and is_word_char(line[n2]): n2 += 1
    x = n1

    return locals()

def get_current_word_under_caret():
    info = caret_info()
    if not info: return None
    return info['line'][info['n1']:info['n2']]

def replace_current_word_with_word(word, info):
    def inner():
        ed.replace(info['n1'], info['y'], info['n2'], info['y'], word)
    return inner

def context_menu(reset = False):
    if reset:
        visible = False
    else:
        info = caret_info()
        word = get_current_word_under_caret()
        if not word: return
        no_suggestions_found = _("No suggestions found")
        visible = not dict_obj.check(word) # only visible if incorrect word

    submenu_title = _("Spelling")
    spelling = None
    for key in menu_proc("text", MENU_ENUM):
        if key['cap'] == submenu_title:
            spelling = key['id']
            break
    if not spelling: spelling = menu_proc("text", MENU_ADD, caption = submenu_title, index = 0)

    menu_proc(spelling, MENU_CLEAR)
    menu_proc(spelling, MENU_SET_VISIBLE, command = visible)

    if not visible: return

    suggestions=dict_obj.suggest(word)
    for suggestion in dict_obj.suggest(word):
        menu_proc(spelling, MENU_ADD, command = replace_current_word_with_word(suggestion, info), caption = suggestion)

    if suggestions == []: menu_proc(spelling, MENU_ADD, caption = "("+no_suggestions_found+")")

def dlg_spell(sub):
    rep_list = dict_obj.suggest(sub)
    en_list = bool(rep_list)
    if not en_list: rep_list = []

    c1 = chr(1)
    RES_TEXT        = 3
    RES_WORDLIST    = 5
    RES_BTN_SKIP    = 6
    RES_BTN_REPLACE = 7
    RES_BTN_ADD     = 8
    RES_BTN_CANCEL  = 9

    res = dlg_custom(_('Misspelled word'), 426, 306, '\n'.join([]
        +[c1.join(['type=label'  , 'pos=6,8,100,0'     , 'cap=' + _('Not found:')])]
        +[c1.join(['type=edit'   , 'pos=106,6,300,0'   , 'cap=' + sub, 'ex0=1', 'ex1=0', 'ex2=1'])]
        +[c1.join(['type=label'  , 'pos=6,38,100,0'    , 'cap=' + _('C&ustom text:')])]
        +[c1.join(['type=edit'   , 'pos=106,36,300,0'  , 'val='])]
        +[c1.join(['type=label'  , 'pos=6,68,100,0'    , 'cap=' + _('Su&ggestions:')])]
        +[c1.join(['type=listbox', 'pos=106,66,300,300', 'items=' + '\t'.join(rep_list), 'val=' + ('0' if en_list else '-1')])]
        +[c1.join(['type=button' , 'pos=306,66,420,0'  , 'cap=' + _('&Ignore'), 'ex0=1'])]
        +[c1.join(['type=button' , 'pos=306,96,420,0'  , 'cap=' + _('&Change')])]
        +[c1.join(['type=button' , 'pos=306,126,420,0' , 'cap=' + _('&Add')])]
        +[c1.join(['type=button' , 'pos=306,186,420,0' , 'cap=' + _('Cancel')])]
        ), 3, get_dict = True)

    if res is None: return
    btn = res['clicked']

    if btn == RES_BTN_SKIP: return ''

    if btn == RES_BTN_ADD:
        dict_obj.add_to_pwl(sub)
        return ''

    if btn == RES_BTN_REPLACE:
        word = res[RES_TEXT]
        if word   : return word
        if en_list: return rep_list[int(res[RES_WORDLIST])]
        else      : return ''

def dlg_select_dict():
    items = sorted(enchant.list_languages())
    if op_lang in items: focused = items.index(op_lang)
    else               : focused = -1
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

def do_check_line(ed, nline, x_start, x_end, with_dialog, check_tokens):
    count = 0
    replaced = 0
    res_x = []
    res_y = []
    res_n = []
    line = ed.get_text_line(nline)

    ranges = []
    urls = re_url.finditer(line)
    if urls:
        for i in urls:
            ranges.append(i.span())

    def is_url(x):
        for r in ranges:
            if r[0] <= x < r[1]:
                return True, r[1]
        return False, None

    n1 = x_start - 1
    while True:
        n1 += 1
        if n1 >= len(line)           : break
        if (x_end >= 0) and (n1 >= x_end): break
        if not is_word_char(line[n1]): continue
        n2 = n1 + 1
        while n2 < len(line) and is_word_char(line[n2]): n2 += 1

        if line[n1]     == "'": n1 += 1   #strip quote from begin of word
        x_pos = n1                        #start of actual word
        n1 = n2                           #new start pos for next word

        if line[n2 - 1] == "'": n2 -= 1   #strip quote from end of word
        sub = line[x_pos:n2]

        url_found, url_end = is_url(x_pos)
        if url_found:
            n1 = url_end                  #set start for next word after url
            continue

        if check_tokens:
            kind = ed.get_token(TOKEN_GET_KIND, x_pos, nline)
            if kind not in ('c', 's'): continue

        if not is_word_alpha(sub): continue
        if dict_obj.check(sub)   : continue

        count += 1
        if with_dialog:
            ed.set_caret(x_pos, nline, x_pos + len(sub), nline)
            rep = dlg_spell(sub)

            if rep is None: return   #stop all work
            if rep == ''  : continue #to next word

            #replace
            replaced += 1
            ed.delete(x_pos, nline, x_pos + len(sub), nline)
            ed.insert(x_pos, nline, rep)
            line = ed.get_text_line(nline)
            n1 += len(rep) - len(sub)     #adapt new word position regarding to replaced word len
        else:
            res_x.append(x_pos)
            res_y.append(nline)
            res_n.append(len(sub))

    return (count, replaced, res_x, res_y, res_n)

def do_work(with_dialog = False):
    count_all = 0
    count_replace = 0
    percent = 0
    app_proc(PROC_SET_ESCAPE, False)
    check_tokens = need_check_tokens(ed)

    carets = ed.get_carets()
    if not carets: return
    x1, y1, x2, y2 = carets[0]

    is_selection = y2 >= 0

    if is_selection:
        if (y1, x1) > (y2, x2):
            x1, y1, x2, y2 = x2, y2, x1, y1  # sort if neccessary
        y2 += 1                      # last line has to be included (range)
        total_lines = y2 - y1
    else:
        total_lines = ed.get_line_count()
        x1 = 0
        x2 = -1
        y1 = 0
        y2 = total_lines

    ed.attr(MARKERS_DELETE_BY_TAG, MARKTAG)   # delete all, otherwise inserting additional markers takes a long time

    res_x = []
    res_y = []
    res_n = []
    escape = False
    for nline in range(y1, y2):
        percent_new = (nline - y1) * 100 // total_lines
        if percent_new != percent:
            percent = percent_new
            msg_status(_('Spell-checking: %2d%%') % percent, True) # True = force msg
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

        res = do_check_line(ed, nline, x_start, x_end, with_dialog, check_tokens)
        if res is None:
            if with_dialog and (count_all > 0): reset_carets(carets)
            return
        count_all     += res[0]
        count_replace += res[1]
        res_x         += res[2]
        res_y         += res[3]
        res_n         += res[4]

    # setting all markers at once is a bit faster than line by line
    ed.attr(
        MARKERS_ADD_MANY, MARKTAG,
        res_x, res_y, res_n,
        COLOR_NONE, COLOR_NONE, op_underline_color,
        0, 0, 0,
        0, 0, op_underline_style, 0,
        show_on_map = True)
        
    if escape: return

    msg_sel = _('selection only') if is_selection else _('all text')
    msg_status(_('Spell check: {}, {}, {} mistake(s), {} replace(s)').format(op_lang, msg_sel, count_all, count_replace))

    if with_dialog and (count_all > 0): reset_carets(carets)

def reset_carets(carets):
    c = carets[0]
    ed.set_caret(*c)
    for c in carets[1:]:
        ed.set_caret(*c, CARET_ADD)

def do_work_if_name(ed_self):
    if is_filetype_ok(ed_self.get_filename()):
        do_work()

def do_work_word(with_dialog):
    info = caret_info()
    if not info:
        msg_status(_('Caret not on word-char'))
        return

    sub = get_current_word_under_caret()
    if not is_word_alpha(sub):
        msg_status(_('Not text-word under caret'))
        return

    x = info['x']
    y = info['y']

    if with_dialog:
        ed.set_caret(x, y, x + len(sub), y)
        rep = dlg_spell(sub)
        if rep is None: return
        if rep == '': return
        ed.delete(x, y, x + len(sub), y)
        ed.insert(x, y, rep)
    else:
        if dict_obj.check(sub):
            msg_status(_('Word ok: "%s"') % sub)
            marker = MARKERS_DELETE_BY_POS
        else:
            msg_status(_('Word misspelled: "%s"') % sub)
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
        do_work()

    def check_suggest(self):
        Command.active = True
        do_work(True)

    def check_word(self):
        Command.active = True
        do_work_word(False)

    def check_word_suggest(self):
        Command.active = True
        do_work_word(True)

    def on_open(self, ed_self):
        do_work_if_name(ed_self)

    def on_change_slow(self, ed_self):
        do_work_if_name(ed_self)

    def on_click(self,ed_self,state):
        context_menu()

    def select_dict(self):
        global op_lang
        global dict_obj

        res = dlg_select_dict()
        if res is None: return
        op_lang = res
        ini_write(filename_ini, 'op', 'lang', op_lang)
        dict_obj = enchant.Dict(op_lang)
        if Command.active: do_work_if_name(ed)

    def config(self):
        ini_write(filename_ini, 'op', 'lang'               , op_lang)
        ini_write(filename_ini, 'op', 'underline_style'    , str(op_underline_style))
        ini_write(filename_ini, 'op', 'confirm_esc_key'    , bool_to_str(op_confirm_esc))
        ini_write(filename_ini, 'op', 'file_extension_list', op_file_types)
        ini_write(filename_ini, 'op', 'url_regex'          , op_url_regex)
        if os.path.isfile(filename_ini): file_open(filename_ini)

    def goto_next(self):
        do_goto(True)

    def goto_prev(self):
        do_goto(False)

    def config_events(self):
        filename_inf = os.path.join(_mydir, 'install.inf')
        v = ini_read(filename_inf, 'item1', 'events', '')
        b_open   = ',on_open,'        in ',' + v + ','
        b_change = ',on_change_slow,' in ',' + v + ','

        WARN1 = _('To not slow down CudaText when events are off, plugin saves these settings to install.inf file.')
        WARN2 = _('So you need to re-configure these options each time you update Spell Checker plugin.')
        WARN3 = _('Settings will take effect after CudaText restart.')

        DLG_W = 680  # 626 is too small for translations
        DLG_H = 180
        BTN_W =  80
        c1 = chr(1)

        res = dlg_custom(_('Configure events'), DLG_W, DLG_H, '\n'.join([]
              + [c1.join(['type=check' , 'cap='+_('Handle event "on_open" (opening of a file)')             , 'pos=6,6,400,0' , 'val='+bool_to_str(b_open)])  ]
              + [c1.join(['type=check' , 'cap='+_('Handle event "on_change_slow" (editing of file + pause)'), 'pos=6,36,400,0', 'val='+bool_to_str(b_change)])]
              + [c1.join(['type=label' , 'cap='+WARN1      , 'pos=6,70,500,0' ])]
              + [c1.join(['type=label' , 'cap='+WARN2      , 'pos=6,90,500,0' ])]
              + [c1.join(['type=label' , 'cap='+WARN3      , 'pos=6,110,500,0'])]
              + [c1.join(['type=button', 'cap='+_('&OK')   , 'pos=%d,%d,%d,%d'%(DLG_W-BTN_W*2-12, DLG_H-30, DLG_W-BTN_W-12, 0)]), 'ex0=1']
              + [c1.join(['type=button', 'cap='+_('Cancel'), 'pos=%d,%d,%d,%d'%(DLG_W-BTN_W-6   , DLG_H-30, DLG_W-6       , 0)])         ]
              ),
              get_dict = True)
        if res is None: return

        b_open   = str_to_bool(res[0])
        b_change = str_to_bool(res[1])

        v = []
        if b_open  : v += ['on_open']
        if b_change: v += ['on_change_slow']

        ini_write(filename_inf, 'item1', 'events', ','.join(v))

    def del_marks(self):
        Command.active = False
        ed.attr(MARKERS_DELETE_BY_TAG, MARKTAG)
        context_menu(True) # reset context menu

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
