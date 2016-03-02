import os
import sys
import string
from cudatext import *
from bisect import bisect_left

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
    if not rep_list: return
    
    c1 = chr(1)
    id_list = 1
    id_replace = 2
    id_skip = 3
    id_cancel = 4
    res = dlg_custom('Replace word?', 426, 306, '\n'.join([]
        +[c1.join(['type=label', 'pos=6,6,450,0', 'cap=Replace "%s":'%sub])]
        +[c1.join(['type=listbox', 'pos=6,26,300,300', 'items='+'\t'.join(rep_list), 'val=0'])]
        +[c1.join(['type=button', 'pos=306,26,420,0', 'cap=&Replace', 'props=1'])]
        +[c1.join(['type=button', 'pos=306,56,420,0', 'cap=&Skip'])]
        +[c1.join(['type=button', 'pos=306,106,420,0', 'cap=Cancel'])]
        ))
    if res is None: return
    res, text = res
    text = text.splitlines()
    if res==id_replace: return rep_list[int(text[id_list])]
    if res==id_skip: return ''
        
#print(dlg_spell('Test'))        


def do_hilite(with_dialog=False):
    ed.attr(MARKERS_DELETE_BY_TAG, MARKTAG)
    COLOR_FORE = ed.get_prop(PROP_COLOR, 'EdTextFont')
    COLOR_BACK = ed.get_prop(PROP_COLOR, 'EdTextBg')
    
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
            if not is_word_alpha(sub): continue
            if dict_obj.check(sub): continue
            
            if with_dialog:
                ed.set_caret(text_x, text_y, text_x+len(sub), text_y)
                rep = dlg_spell(sub)
                if rep is None: return
                if rep=='': continue
                ed.delete(text_x, text_y, text_x+len(sub), text_y)
                ed.insert(text_x, text_y, rep)
                #replace
                line = ed.get_text_line(nline)
                n1 += len(rep)-len(sub)
            else:
                ed.attr(MARKERS_ADD, MARKTAG, text_x, text_y, len(sub),   
                  COLOR_FORE, COLOR_BACK, COLOR_UNDER, 
                  0, 0, 0, 0, 0, BORDER_UNDER)
    
    msg_status('Spell-checking done')

class Command:
    active = False

    def hilite(self):
        do_hilite()
        
    def check(self):
        do_hilite(True)

    def on_change_slow(self, ed_self):
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
