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
filename_plugins = os.path.join(app_path(APP_DIR_SETTINGS), 'plugins.ini')
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
    for suggestion in dict_obj.suggest(word):
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
        return ''

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

def do_check_line(ed, nline, x_start, x_end, with_dialog, check_tokens):
    if dict_obj is None:
        return
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
        if n1 >= len(line):
            break
        if (x_end >= 0) and (n1 >= x_end):
            break
        if not is_word_char(line[n1]):
            continue
        n2 = n1 + 1
        while n2 < len(line) and is_word_char(line[n2]):
            n2 += 1

        #strip quote from begin of word
        while (n1 < len(line)) and line[n1] == "'":
            n1 += 1

        x_pos = n1    #start of actual word
        n1 = n2       #new start pos for next word

        #strip quote from end of word
        while line[n2 - 1] == "'":
            n2 -= 1

        sub = line[x_pos:n2]

        url_found, url_end = is_url(x_pos)
        if url_found:
            n1 = url_end                  #set start for next word after url
            continue

        if check_tokens:
            kind = ed.get_token(TOKEN_GET_KIND, x_pos, nline)
            if kind not in ('c', 's'):
                #print('check_line: not OK token kind:', kind, '; line', nline, '; x', x_pos)
                continue

        if not is_word_alpha(sub):
            #print('check_line: not is_word_alpha:', sub)
            continue
        if dict_obj.check(sub):
            #print('check_line: check off:', sub)
            continue

        count += 1
        if with_dialog:
            ed.set_caret(x_pos, nline, x_pos + len(sub), nline)
            rep = dlg_spell(sub)

            if rep is None:
                return   #stop all work
            if rep == '':
                continue #to next word

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
    percent = 0
    app_proc(PROC_SET_ESCAPE, False)
    check_tokens = need_check_tokens(editor)

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
    else:
        total_lines = editor.get_line_count()
        x1 = 0
        x2 = -1
        y1 = 0
        y2 = total_lines

    editor.attr(MARKERS_DELETE_BY_TAG, MARKTAG)   # delete all, otherwise inserting additional markers takes a long time

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

        res = do_check_line(editor, nline, x_start, x_end, with_dialog, check_tokens)
        if res is None:
            if with_dialog and (count_all > 0):
                reset_carets(editor, carets)
            return
        count_all     += res[0]
        count_replace += res[1]
        res_x         += res[2]
        res_y         += res[3]
        res_n         += res[4]

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
    msg_status(_('Spell check: {}, {}, {} mistake(s), {} replace(s)').format(op_lang, msg_sel, count_all, count_replace))

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
        if Command.active:
            do_work_if_name(ed, False)

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
