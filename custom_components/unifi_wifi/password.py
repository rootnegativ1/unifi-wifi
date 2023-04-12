from xkcdpass import xkcd_password as xp
import secrets, string

def create(method):
    if method == 'xkcd': # https://github.com/redacted/XKCD-password-generator#using-xkcdpass-as-an-imported-module
        wordfile = xp.locate_wordfile() # defaults to eff_long
        mywords = xp.generate_wordlist(wordfile=wordfile, min_length=5, max_length=8)
        x = xp.generate_xkcdpassword(mywords, numwords=4, delimiter=" ")

    elif method == 'word': # https://docs.python.org/3/library/secrets.html#recipes-and-best-practices
        # this is basically the same as xkcd method
        # but without extra specificity such as min and max lengths
        # On standard Linux systems, use a convenient dictionary file.
        # Other platforms may need to provide their own word-list.
        # https://www.eff.org/files/2016/07/18/eff_large_wordlist.txt
        with open('/config/custom_components/unifi_wifi/eff_large_wordlist.txt') as f:
            words = [word.strip() for word in f]
            x = ' '.join(secrets.choice(words) for i in range(4))

    elif method == 'char': # https://docs.python.org/3/library/secrets.html#recipes-and-best-practices
        alphabet = string.ascii_letters + string.digits
        x = ''.join(secrets.choice(alphabet) for i in range(24))

    else:
        raise ValueError('invalid password method')

    return x