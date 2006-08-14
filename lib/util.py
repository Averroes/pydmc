__all__ = ['is_string', 'has_length', 'is_sequence', 'colourise']

import sys

def is_string(s):
    """Test whether s is a string (byte or Unicode).
    """
    return isinstance(s, basestring)

def has_length(s):
    """Test whether s can have len() taken.
    All sequences (including strings) should succeed here.
    """
    try:
        len(s)
    except:
        return False
    else:
        return True

def is_sequence(s):
    """Test whether s is a sequence.

    For this purpose, strings are not sequences.
    """
    if is_string(s):
        return False
    return has_length(s)

_ansi_colour_keys = {
    # attributes
    'none' : '0',
    'bold' : '1',
    'underscore' : '4',
    'blink' : '5',
    'reverse' : '7',
    'concealed' : '8',
    # foreground
    'black' : '30',
    'red' : '31',
    'green' : '32',
    'yellow' : '33',
    'blue' : '34',
    'magenta' : '35',
    'cyan' : '36',
    'white' : '37',
    # background
    'bg_black' : '40',
    'bg_red' : '41',
    'bg_green' : '42',
    'bg_yellow' : '43',
    'bg_blue' : '44',
    'bg_magenta' : '45',
    'bg_cyan' : '46',
    'bg_white' : '47',
    # defaults for information
    'error' : '31', # red
    'warn' : '35',  # magenta
    'info' : '33',  # yellow
    }
def colourise(s, attributes=None, check_terminal=True, terminal=None):
    if attributes is None:
        return s
    if check_terminal:
        if terminal is None:
            terminal = sys.stdout
        if not terminal.isatty():
            return s
    if is_string(attributes):
        attributes = (attributes,)
    astr = ';'.join([_ansi_colour_keys[a] for a in attributes])
    return '\033[' + astr + 'm' + s + '\033[m'
