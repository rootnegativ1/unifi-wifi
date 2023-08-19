"""Random password generation function."""

import secrets, string

from xkcdpass import xkcd_password as xp

WORD_FILE = '/config/custom_components/unifi_wifi/eff_large_wordlist.txt'


def create(_method: str, _delimiter: str, _min_length: int, _max_length: int, _word_count: int, _char_count: int):
    # https://github.com/redacted/XKCD-password-generator#using-xkcdpass-as-an-imported-module
    if _method == 'xkcd':
        # xp.locate_wordfile() defaults to a looking for eff_long contained in xkcdpass python module
        # however this is not available to the function so we specify a local copy of eff_long
        # this file is located in the current working directory
        mywords = xp.generate_wordlist(wordfile=WORD_FILE, min_length=_min_length, max_length=_max_length)
        # x = xp.generate_xkcdpassword(mywords, numwords=_word_count, delimiter=' ')
        x = xp.generate_xkcdpassword(mywords, numwords=_word_count, delimiter=_delimiter)

    # https://docs.python.org/3/library/secrets.html#recipes-and-best-practices
    # this is basically the same as xkcd method
    # but without extra specificity such as min and max lengths
    # On standard Linux systems, use a convenient dictionary file.
    # Other platforms may need to provide their own word-list.
    # https://www.eff.org/files/2016/07/18/eff_large_wordlist.txt
    elif _method == 'word':
        with open(WORD_FILE) as f:
            words = [word.strip() for word in f]
            # x = ' '.join(secrets.choice(words) for i in range(_word_count))
            x = _delimiter.join(secrets.choice(words) for i in range(_word_count))

    # https://docs.python.org/3/library/secrets.html#recipes-and-best-practices
    # 'char' method
    elif _method =='char':
        alphabet = string.ascii_letters + string.digits
        x = ''.join(secrets.choice(alphabet) for i in range(_char_count))
    else:
        raise ValueError(f"Method {_method} is not a valid option.")
    return x