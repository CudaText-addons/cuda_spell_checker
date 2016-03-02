import os
import sys
import string
import json
from .jsoncomment import JsonComment
from cudatext import *

json_parser = JsonComment(json)

sys.path.append(os.path.dirname(__file__))
try:
    import enchant
    dict_obj = enchant.Dict('en_US')
except:
    msg_box('Cannot import Enchant spell-checker library.\nSeems cannot find binary Enchant files.', MB_OK+MB_ICONERROR)


COLOR_UNDER = 0xFF #red underline
BORDER_UNDER = 6 #wave underline
MARKTAG = 105 #uniq int for all marker plugins


def is_word_char(s):
    chars = string.ascii_letters+string.digits+"'_"
    return s in chars
    
def is_word_alpha(s):
    for ch in s:
        if ch in string.digits+'_': return False
    if s[0] in "'_": return False
    return True    

def dlg_spell(sub):
    rep_list = dict_obj.suggest(sub)
    if not rep_list: rep_list=['?']
    
    c1 = chr(1)
    id_edit = 3
    id_list = 5
    id_replace = 6
    id_skip = 7
    id_cancel = 8
    res = dlg_custom('Replace word?', 426, 306, '\n'.join([]
        +[c1.join(['type=label', 'pos=6,6,100,0', 'cap=Not found:'])]
        +[c1.join(['type=label', 'pos=106,6,400,0', 'cap='+sub])]
        +[c1.join(['type=label', 'pos=6,26,100,0', 'cap=&Custom replace:'])]
        +[c1.join(['type=edit', 'pos=106,26,300,0', 'val='])]
        +[c1.join(['type=label', 'pos=6,56,100,0', 'cap=Su&ggestions:'])]
        +[c1.join(['type=listbox', 'pos=106,56,300,300', 'items='+'\t'.join(rep_list), 'val=0'])]
        +[c1.join(['type=button', 'pos=306,56,420,0', 'cap=&Replace', 'props=1'])]
        +[c1.join(['type=button', 'pos=306,86,420,0', 'cap=&Skip'])]
        +[c1.join(['type=button', 'pos=306,136,420,0', 'cap=Cancel'])]
        ))
    if res is None: return
    res, text = res
    text = text.splitlines()
    if res==id_replace:
        word = text[id_edit]
        if word: return word 
        return rep_list[int(text[id_list])]
    if res==id_skip: return ''
        
#print(dlg_spell('tst'))        


def get_styles_from_file(fn, lexer):
    if not os.path.isfile(fn): return
    j = json_parser.loads(open(fn).read())
    return j.get('StringStyles', {}).get(lexer, []) \
         + j.get('CommentStyles', {}).get(lexer, [])


def get_styles_of_editor():
    lexer = ed.get_prop(PROP_LEXER_FILE)
    if not lexer: return
    fn_user = os.path.join(app_path(APP_DIR_SETTINGS), 'user_lexers.json')
    fn_def = os.path.join(os.path.dirname(app_path(APP_DIR_SETTINGS)), 'settings_default', 'default_lexers.json')
    s1 = get_styles_from_file(fn_user, lexer)
    s2 = get_styles_from_file(fn_def, lexer)
    res = []
    if s1: res+=s1
    if s2: res+=s2
    return res
    
#print(get_styles_of_editor()) #debug


def do_hilite(with_dialog=False):
    ed.attr(MARKERS_DELETE_BY_TAG, MARKTAG)
    COLOR_FORE = ed.get_prop(PROP_COLOR, 'EdTextFont')
    COLOR_BACK = ed.get_prop(PROP_COLOR, 'EdTextBg')
    styles = get_styles_of_editor()
    count_all = 0
    count_replace = 0
    
    for nline in range(ed.get_line_count()):
        line = ed.get_text_line(nline)
        n1 = -1
        n2 = -1
        while True:
            n1 += 1
            if n1>=len(line): break
            if not is_word_char(line[n1]): continue
            n2 = n1+1
            while n2<len(line) and is_word_char(line[n2]): n2+=1
            
            text_x = n1
            text_y = nline
            
            sub = line[n1:n2]
            n1 = n2
            
            token = ed.get_token(TOKEN_AT_POS, text_x, text_y)
            if token:
                ((start_x, start_y), (end_x, end_y), str_token, str_style) = token
                if not str_style in styles: continue
            
            if not is_word_alpha(sub): continue
            if dict_obj.check(sub): continue

            count_all += 1            
            if with_dialog:
                ed.set_caret(text_x, text_y, text_x+len(sub), text_y)
                rep = dlg_spell(sub)
                if rep is None: return
                if rep=='': continue
                count_replace += 1
                ed.delete(text_x, text_y, text_x+len(sub), text_y)
                ed.insert(text_x, text_y, rep)
                #replace
                line = ed.get_text_line(nline)
                n1 += len(rep)-len(sub)
            else:
                ed.attr(MARKERS_ADD, MARKTAG, text_x, text_y, len(sub),   
                  COLOR_FORE, COLOR_BACK, COLOR_UNDER, 
                  0, 0, 0, 0, 0, BORDER_UNDER)
    
    msg_status('Spell-checking done, %d mistakes, %d replaced' % (count_all, count_replace))

class Command:
    active = False

    def hilite(self):
        do_hilite()
        
    def check(self):
        do_hilite(True)

    def on_change_slow(self, ed_self):
        do_hilite()

    def on_open(self, ed_self):
        do_hilite()

    def toggle_hilite(self):
        self.active = not self.active
        if self.active:
            ev = 'on_change_slow'
            do_hilite() 
        else:
            ev = ''
            ed.attr(MARKERS_DELETE_BY_TAG, MARKTAG)
        app_proc(PROC_SET_EVENTS, 'cuda_spell_checker;'+ev+';;')
