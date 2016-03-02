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


def do_hilite():
    ed.attr(MARKERS_DELETE_BY_TAG, MARKTAG)
    COLOR_FORE = ed.get_prop(PROP_COLOR, 'EdTextFont')
    COLOR_BACK = ed.get_prop(PROP_COLOR, 'EdTextBg')
    
    for nline in range(ed.get_line_count()):
        s = ed.get_text_line(nline)
        n1 = -1
        n2 = -1
        while True:
            n1 += 1
            if n1>=len(s): break
            if not is_word_char(s[n1]): continue
            n2 = n1+1
            while n2<len(s) and is_word_char(s[n2]): n2+=1
            
            text_x = n1
            text_y = nline
            
            sub = s[n1:n2]
            n1 = n2
            if not is_word_alpha(sub): continue
            if dict_obj.check(sub): continue
            
            ed.attr(MARKERS_ADD, MARKTAG, text_x, text_y, len(sub),   
              COLOR_FORE, COLOR_BACK, COLOR_UNDER, 
              0, 0, 0, 0, 0, BORDER_UNDER)

class Command:
    active = False

    def hilite(self):
        do_hilite()

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
