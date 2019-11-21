import sys


def EnchantArchitecture():
  return 'enchant_x64' if sys.maxsize > 2**32 else 'enchant_x86'
