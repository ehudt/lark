import re
import sys

from .utils import get_regexp_width, STRING_TYPE

Py36 = (sys.version_info[:2] >= (3, 6))


###{standalone
def is_terminal(sym):
    return sym.isupper()

class GrammarError(Exception):
    pass

class ParseError(Exception):
    pass

class UnexpectedToken(ParseError):
    def __init__(self, token, expected, seq, index, considered_rules=None, state=None):
        self.token = token
        self.expected = expected
        self.line = getattr(token, 'line', '?')
        self.column = getattr(token, 'column', '?')
        self.considered_rules = considered_rules
        self.state = state

        try:
            context = ' '.join(['%r(%s)' % (t.value, t.type) for t in seq[index:index+5]])
        except AttributeError:
            context = seq[index:index+5]
        except TypeError:
            context = "<no context>"
        message = ("Unexpected token %r at line %s, column %s.\n"
                   "Expected: %s\n"
                   "Context: %s" % (token, self.line, self.column, expected, context))

        super(UnexpectedToken, self).__init__(message)

    def match_examples(self, parse_fn, examples):
        """ Given a parser instance and a dictionary mapping some label with
            some malformed syntax examples, it'll return the label for the
            example that bests matches the current error.
        """
        assert self.state, "Not supported for this exception"

        candidate = None
        for label, example in examples.items():
            assert not isinstance(example, STRING_TYPE)

            for malformed in example:
                try:
                    parse_fn(malformed)
                except UnexpectedToken as ut:
                    if ut.state == self.state:
                        if ut.token == self.token:  # Try exact match first
                            return label
                        elif not candidate:
                            candidate = label

        return candidate

    def get_context(self, text, span=10):
        pos = self.token.pos_in_stream
        start = max(pos - span, 0)
        end = pos + span
        before = text[start:pos].rsplit('\n', 1)[-1]
        after = text[pos:end].split('\n', 1)[0]
        return before + after + '\n' + ' ' * len(before) + '^\n'
###}



class LexerConf:
    def __init__(self, tokens, ignore=(), postlex=None, callbacks=None):
        self.tokens = tokens
        self.ignore = ignore
        self.postlex = postlex
        self.callbacks = callbacks or {}

class ParserConf:
    def __init__(self, rules, callback, start):
        self.rules = rules
        self.callback = callback
        self.start = start



class Pattern(object):
    def __init__(self, value, flags=()):
        self.value = value
        self.flags = frozenset(flags)

    def __repr__(self):
        return repr(self.to_regexp())

    # Pattern Hashing assumes all subclasses have a different priority!
    def __hash__(self):
        return hash((type(self), self.value, self.flags))
    def __eq__(self, other):
        return type(self) == type(other) and self.value == other.value and self.flags == other.flags

    if Py36:
        # Python 3.6 changed syntax for flags in regular expression
        def _get_flags(self, value):
            for f in self.flags:
                value = ('(?%s:%s)' % (f, value))
            return value

    else:
        def _get_flags(self, value):
            for f in self.flags:
                value = ('(?%s)' % f) + value
            return value

class PatternStr(Pattern):
    def to_regexp(self):
        return self._get_flags(re.escape(self.value))

    @property
    def min_width(self):
        return len(self.value)
    max_width = min_width

class PatternRE(Pattern):
    def to_regexp(self):
        return self._get_flags(self.value)

    @property
    def min_width(self):
        return get_regexp_width(self.to_regexp())[0]
    @property
    def max_width(self):
        return get_regexp_width(self.to_regexp())[1]

class TokenDef(object):
    def __init__(self, name, pattern, priority=1):
        assert isinstance(pattern, Pattern), pattern
        self.name = name
        self.pattern = pattern
        self.priority = priority

    def __repr__(self):
        return '%s(%r, %r)' % (type(self).__name__, self.name, self.pattern)

