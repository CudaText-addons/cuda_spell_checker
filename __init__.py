# coding: utf8
import importlib
import os
import sys
import string
import json
from .enchant_architecture import EnchantArchitecture
from .jsoncomment import JsonComment
from cudatext import *

json_parser = JsonComment(json)

def bool_to_str(v): return '1' if v else '0'
def str_to_bool(s): return s=='1'


filename_ini = os.path.join(app_path(APP_DIR_SETTINGS), 'cuda_spell_checker.ini')
op_lang = ini_read(filename_ini, 'op', 'lang', 'en_US')
op_underline_color = app_proc(PROC_THEME_UI_DICT_GET, '')['EdMicromapSpell']['color']
op_underline_style = ini_read(filename_ini, 'op', 'underline_style', '6')
op_confirm_esc = str_to_bool(ini_read(filename_ini, 'op', 'confirm_esc_key', '0'))
op_file_types = ini_read(filename_ini, 'op', 'file_extension_list', '*')

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


MARKTAG = 105 #uniq int for all marker plugins

def is_word_char(s):
    return s.isalpha() or (s in "'_"+string.digits)

def is_word_alpha(s):
    if not s: return False
    #don't allow digit in word
    #don't allow lead-quote
    digits = string.digits+'_'
    for ch in s:
        if ch in digits: return False
    if s[0] in "'": return False
    return True

def dlg_spell(sub):
    rep_list = dict_obj.suggest(sub)
    en_list = bool(rep_list)
    if not en_list: rep_list=[]

    c1 = chr(1)
    RES_TEXT = 3
    RES_WORDLIST = 5
    RES_BTN_SKIP = 6
    RES_BTN_REPLACE = 7
    RES_BTN_ADD = 8
    RES_BTN_CANCEL = 9

    res = dlg_custom('Misspelled word', 426, 306, '\n'.join([]
        +[c1.join(['type=label', 'pos=6,8,100,0', 'cap=Not found:'])]
        +[c1.join(['type=edit', 'pos=106,6,300,0', 'cap='+sub, 'ex0=1', 'ex1=0', 'ex2=1'])]
        +[c1.join(['type=label', 'pos=6,38,100,0', 'cap=C&ustom text:'])]
        +[c1.join(['type=edit', 'pos=106,36,300,0', 'val='])]
        +[c1.join(['type=label', 'pos=6,68,100,0', 'cap=Su&ggestions:'])]
        +[c1.join(['type=listbox', 'pos=106,66,300,300', 'items='+'\t'.join(rep_list), 'val='+('0' if en_list else '-1')])]
        +[c1.join(['type=button', 'pos=306,66,420,0', 'cap=&Ignore', 'ex0=1'])]
        +[c1.join(['type=button', 'pos=306,96,420,0', 'cap=&Change'])]
        +[c1.join(['type=button', 'pos=306,126,420,0', 'cap=&Add'])]
        +[c1.join(['type=button', 'pos=306,186,420,0', 'cap=Cancel'])]
        ), 3, get_dict=True)

    if res is None: return
    btn = res['clicked']

    if btn==RES_BTN_SKIP:
        return ''

    if btn==RES_BTN_ADD:
        dict_obj.add_to_pwl(sub)
        return ''

    if btn==RES_BTN_REPLACE:
        word = res[RES_TEXT]
        if word:
            return word
        if en_list:
            return rep_list[int(res[RES_WORDLIST])]
        else:
            return ''


def dlg_select_dict():
    items = sorted(enchant.list_languages())
    global op_lang
    if op_lang in items:
        focused = items.index(op_lang)
    else:
        focused = -1
    res = dlg_menu(DMENU_LIST, items, focused, caption='Select dictionary')
    if res is None: return
    return items[res]


def is_filetype_ok(fn):
    global op_file_types
    if op_file_types=='': return False
    if op_file_types=='*': return True
    if fn=='': return True #allow in untitled tabs
    fn = os.path.basename(fn)
    n = fn.rfind('.')
    if n<0: return True #allow if no extension
    fn = fn[n+1:]
    return ','+fn+',' in ','+op_file_types+','


def need_check_tokens(ed):

    lexer = ed.get_prop(PROP_LEXER_FILE)
    if lexer:
        props = lexer_proc(LEXER_GET_PROP, lexer)
        return props['st_c']!='' or props['st_s']!=''
    else:
        return False


def do_check_line(ed, nline, line,
    with_dialog,
    check_tokens,
    count_all, count_replace,
    res_x, res_y, res_n):

    n1 = -1

    while True:
        n1 += 1
        if n1>=len(line): break
        if not is_word_char(line[n1]): continue
        n2 = n1+1
        while n2<len(line) and is_word_char(line[n2]): n2+=1

        #strip quote from begin of word
        if line[n1]=="'": n1 += 1
        #strip quote from end of word
        if line[n2-1]=="'": n2 -= 1

        text_x = n1
        text_y = nline

        sub = line[n1:n2]
        n1 = n2

        if check_tokens:
            kind = ed.get_token(TOKEN_GET_KIND, text_x, text_y)
            if kind not in ('c', 's'):
                continue

        if not is_word_alpha(sub): continue
        if dict_obj.check(sub): continue

        count_all += 1
        if with_dialog:
            ed.set_caret(text_x, text_y, text_x+len(sub), text_y)
            rep = dlg_spell(sub)

            if rep is None:
                return #stop all work
            if rep=='':
                continue #to next word

            count_replace += 1
            ed.delete(text_x, text_y, text_x+len(sub), text_y)
            ed.insert(text_x, text_y, rep)
            #replace
            line = ed.get_text_line(nline)
            n1 += len(rep)-len(sub)
        else:
            res_x.append(text_x)
            res_y.append(text_y)
            res_n.append(len(sub))

    return (count_all, count_replace)


def do_work(with_dialog=False):
    global op_underline_color
    global op_underline_style
    global op_confirm_esc
    global op_lang

    ed.attr(MARKERS_DELETE_BY_TAG, MARKTAG)
    res_x = []
    res_y = []
    res_n = []
    count_all = 0
    count_replace = 0
    total_lines = ed.get_line_count()
    percent = 0
    app_proc(PROC_SET_ESCAPE, False)

    carets = ed.get_carets()
    if not carets: return
    x1, y1, x2, y2 = carets[0]
    is_selection = y2>=0

    if not is_selection:
        y1 = 0
        y2 = total_lines-1
        lines = ed.get_text_all().split('\n')
    else:
        if y1>y2:
            y1, y2 = y2, y1
        lines = [ed.get_text_line(i) for i in range(y1, y2+1)]

    chk_tokens = need_check_tokens(ed)

    for nline in range(y1, y2+1):
        '''
        percent_new = nline * 100 // total_lines
        if percent_new!=percent:
            percent = percent_new
            msg_status('Spell-checking %d%%'% percent)
            if app_proc(PROC_GET_ESCAPE, ''):
                app_proc(PROC_SET_ESCAPE, False)
                if not op_confirm_esc or \
                  msg_box('Stop spell-checking?', MB_OKCANCEL+MB_ICONQUESTION)==ID_OK:
                    msg_status('Spell-check stopped')
                    return
        '''

        res = do_check_line(ed,
            nline,
            lines[nline-y1],
            with_dialog,
            chk_tokens,
            count_all, count_replace,
            res_x, res_y, res_n)
        if res is None: return
        count_all, count_replace = res

    ed.attr(MARKERS_ADD_MANY, MARKTAG,
        res_x, res_y, res_n,
        COLOR_NONE,
        COLOR_NONE,
        op_underline_color,
        0, 0, 0, 0, 0,
        int(op_underline_style),
        show_on_map=True)

    msg_sel = 'selection only' if is_selection else 'all text'
    msg_status('Spell check: %s, %s, %d mistake(s), %d replace(s)' % (op_lang, msg_sel, count_all, count_replace))

    if len(carets)==1:
        c = carets[0]
        ed.set_caret(*c)
    else:
        c = carets[0]
        ed.set_caret(*c)
        for c in carets[1:]:
            ed.set_caret(*c, CARET_ADD)


def do_work_if_name(ed_self):
    if is_filetype_ok(ed_self.get_filename()):
        do_work()


def do_work_word(with_dialog):
    global op_underline_color
    global op_underline_style
    BORDER_UNDER = int(op_underline_style)

    x, y, x2, y2 = ed.get_carets()[0]
    line = ed.get_text_line(y)
    if not line: return

    if not (0 <= x < len(line)) or not is_word_char(line[x]):
        msg_status('Caret not on word-char')
        return

    n1 = x
    n2 = x
    while n1>0 and is_word_char(line[n1-1]): n1-=1
    while n2<len(line)-1 and is_word_char(line[n2+1]): n2+=1
    x = n1

    sub = line[n1:n2+1]
    if not is_word_alpha(sub):
        msg_status('Not text-word under caret')
        return

    if dict_obj.check(sub):
        msg_status('Word ok: "%s"' % sub)
        return

    msg_status('Word misspelled: "%s"' % sub)
    if with_dialog:
        ed.set_caret(x, y, x+len(sub), y)
        rep = dlg_spell(sub)
        if rep is None: return
        if rep=='': return
        ed.delete(x, y, x+len(sub), y)
        ed.insert(x, y, rep)
    else:
        ed.attr(MARKERS_ADD, MARKTAG, x, y, len(sub),
          COLOR_NONE,
          COLOR_NONE,
          op_underline_color,
          0, 0, 0, 0, 0, BORDER_UNDER,
          show_on_map=True)

    ed.set_caret(x, y)


def get_next_pos(x1, y1, is_next):
    m = ed.attr(MARKERS_GET)
    if not m: return
    m = [(x, y) for (tag, x, y, nlen, c1, c2, c3, f1, f2, f3, b1, b2, b3, b4, som, mo) in m if tag==MARKTAG]
    if not m: return

    if is_next:
        m = [(x, y) for (x, y) in m if (y>y1) or ((y==y1) and (x>x1))]
        if m: return m[0]
    else:
        m = [(x, y) for (x, y) in m if (y<y1) or ((y==y1) and (x<x1))]
        if m: return m[len(m)-1]


def do_goto(is_next):
    x1, y1, x2, y2 = ed.get_carets()[0]
    m = get_next_pos(x1, y1, is_next)
    if m:
        ed.set_caret(m[0], m[1])
        msg_status('Go to misspelled: %d:%d' % (m[1]+1, m[0]+1))
    else:
        msg_status('Cannot go to next/prev')



class Command:
    active = False

    def check(self):
        do_work()

    def check_suggest(self):
        do_work(True)

    def check_word(self):
        do_work_word(False)

    def check_word_suggest(self):
        do_work_word(True)

    def on_change_slow(self, ed_self):
        do_work_if_name(ed_self)

    def toggle_hilite(self):
        self.active = not self.active
        if self.active:
            ev = 'on_change_slow'
            do_work_if_name(ed)
        else:
            ev = ''
            ed.attr(MARKERS_DELETE_BY_TAG, MARKTAG)
        app_proc(PROC_SET_EVENTS, 'cuda_spell_checker;'+ev+';;')

        text = 'Underlines on' if self.active else 'Underlines off'
        msg_status(text)

    def select_dict(self):
        res = dlg_select_dict()
        if res is None: return
        global filename_ini
        global op_lang
        global dict_obj
        op_lang = res
        ini_write(filename_ini, 'op', 'lang', op_lang)
        dict_obj = enchant.Dict(op_lang)
        if self.active:
            do_work_if_name(ed)

    def config(self):
        global op_lang
        global op_underline_color
        global op_underline_style
        global op_confirm_esc
        global op_file_types
        global filename_ini
        ini_write(filename_ini, 'op', 'lang', op_lang)
        ini_write(filename_ini, 'op', 'underline_style', op_underline_style)
        ini_write(filename_ini, 'op', 'confirm_esc_key', bool_to_str(op_confirm_esc))
        ini_write(filename_ini, 'op', 'file_extension_list', op_file_types)
        if os.path.isfile(filename_ini):
            file_open(filename_ini)

    def goto_next(self):
        do_goto(True)

    def goto_prev(self):
        do_goto(False)

    def on_open(self, ed_self):
        do_work()

    def toggle_on_open(self):
        fn = os.path.join(_mydir, 'install.inf')
        v = ini_read(fn, 'item1', 'events', '')
        if not v:
            v = 'on_open'
        else:
            v = ''
        ini_write(fn, 'item1', 'events', v)
        msg_box('To not slow down CudaText when setting is Off, plugin saves this setting to install.inf file. '+
                'So you need to re-enable this setting each time you update Spell Checker plugin. '+
                'Setting will take effect after CudaText restart.',
                MB_OK+MB_ICONINFO)

    def del_marks(self):
        ed.attr(MARKERS_DELETE_BY_TAG, MARKTAG)
