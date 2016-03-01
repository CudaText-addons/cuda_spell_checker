import os
import sys
import string
from cudatext import *
from bisect import bisect_left
sys.path.append(os.path.dirname(__file__))
import enchant


COLOR_UNDER = 0xFF #red underline
BORDER_UNDER = 6 #wave underline
MARKTAG = 105 #uniq int for all marker plugins

dict_obj = enchant.Dict('en_US')

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
    def hilite(self):
        do_hilite()
