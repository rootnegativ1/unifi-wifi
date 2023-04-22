"""Random password generation function."""

import logging
import secrets, string

from xkcdpass import xkcd_password as xp

WORD_FILE = '/config/custom_components/unifi_wifi/eff_large_wordlist.txt'

_LOGGER = logging.getLogger(__name__)


def create(method, min_word_length, max_word_length, word_count, char_count):
    # https://github.com/redacted/XKCD-password-generator#using-xkcdpass-as-an-imported-module
    if method == 'xkcd':
        #wordfile = xp.locate_wordfile() # defaults to a copy of eff_long contained in xkcdpass python module
        wordfile = WORD_FILE
        mywords = xp.generate_wordlist(wordfile=wordfile, min_length=min_word_length, max_length=max_word_length)
        x = xp.generate_xkcdpassword(mywords, numwords=word_count, delimiter=' ')

    # https://docs.python.org/3/library/secrets.html#recipes-and-best-practices
    # this is basically the same as xkcd method
    # but without extra specificity such as min and max lengths
    # On standard Linux systems, use a convenient dictionary file.
    # Other platforms may need to provide their own word-list.
    # https://www.eff.org/files/2016/07/18/eff_large_wordlist.txt
    elif method == 'word':
        with open(WORD_FILE) as f:
            words = [word.strip() for word in f]
            x = ' '.join(secrets.choice(words) for i in range(word_count))

    # https://docs.python.org/3/library/secrets.html#recipes-and-best-practices
    # 'char' method
    else:
        alphabet = string.ascii_letters + string.digits
        x = ''.join(secrets.choice(alphabet) for i in range(char_count))

    return x