"""
This module contains all kinds of commands and actors related to make selections.
We distinguish between functions that work selection-wise (global selectors)
and function that work interval-wise (local selectors).
Furthermore we have selectors that are based on regular expressions.

Selectors may return None, in which case the document should not be affected.
Selectors may also return a result which is identical to the previous selection.
The code that executes the command may want to check if this is the case, before applying.

Because it is often handy to use selectors as building blocks for other computations,
selectors return their result as a selection instead of executing them immediately.
Secondly, one can pass a selection which should be used as starting point
for the selector instead of the current selection of the document.
Because of this, it is a good habit to only decorate the function that is placed in
commands.
"""
import re
from functools import partial, wraps

from . import commands
from .selection import Selection, Interval


def escape(document):
    if document.selectmode != '':
        normalselectmode(document)
    else:
        commands.empty(document)
commands.escape = escape


def extendmode(document):
    document.selectmode = 'Extend'
commands.extendmode = extendmode


def reducemode(document):
    document.selectmode = 'Reduce'
commands.reducemode = reducemode


def normalselectmode(document):
    document.selectmode = ''
commands.normalselectmode = normalselectmode


def selector(function):
    """Decorator to make it more convenient to write selectors."""
    @wraps(function)
    def wrapper(document, selection=None, selectmode=None, preview=False):
        selection = selection or document.selection
        selectmode = selectmode or document.selectmode
        selection = function(document, selection, selectmode)
        if preview:
            return selection
        selection(document)
    return wrapper


def selectall(document, selection, selectmode):
    """Select the entire text."""
    return Selection(Interval(0, len(document.text)))
commands.selectall = selector(selectall)


def select_single_interval(document, selection, selectmode):
    """Reduce the selection to the single uppermost interval."""
    return Selection(selection[0])
commands.select_single_interval = selector(select_single_interval)


def empty(document, selection, selectmode):
    """Reduce the selection to a single uppermost empty interval."""
    beg = selection[0][0]
    return Selection(Interval(beg, beg))
commands.empty = selector(empty)


def join(document, selection, selectmode):
    """Join all intervals together."""
    return Selection(Interval(selection[0][0], selection[-1][1]))
commands.join = selector(join)


def complement(document, selection, selectmode):
    """Return the complement."""
    return Selection(selection.complement(document))
commands.complement = selector(complement)


def intervalselector(function):
    """Decorator to make it more convenient to write selectors acting on intervals."""
    @wraps(function)
    @selector
    def wrapper(document, selection, selectmode):
        new_intervals = []
        for interval in selection:
            new_interval = function(document, interval, selectmode)
            if new_interval == None:
                return
            new_intervals.append(new_interval)
        return Selection(new_intervals)
    return wrapper


def emptybefore(document, interval, selectmode):
    """Return the empty interval before each interval."""
    beg, _ = interval
    return Interval(beg, beg)
commands.emptybefore = intervalselector(emptybefore)


def emptyafter(document, interval, selectmode):
    """Return the empty interval after each interval."""
    _, end = interval
    return Interval(end, end)
commands.emptyafter = intervalselector(emptyafter)


@selector
def movedown(document, selection, selectmode):
    """Move each interval one line down. Preserve line selections."""
    intervals = []
    for interval in selection:
        beg, end = interval
        #currentline = document.text.rfind('\n'), document.text.find('\n', beg)
        #currentline[0] = currentline[0] if currentline[0] != -1 else 0
        #currentline[1] = currentline[1] if currentline[1] != -1 else len(document.text)
        #nextline = document.text.rfind('\n'), document.text.find('\n', beg)
        #nextline[0] = nextline[0] if nextline[0] != -1 else 0
        #nextline[1] = nextline[1] if nextline[1] != -1 else len(document.text)
        #currentline = 

        # TODO: make undecorated versions of nextline and nextfullline accesible and use
        # here

        intervals.append(Interval(end, end))
    return Selection(intervals)
commands.emptyafter = emptyafter


def findpattern(text, pattern, reverse=False, group=0):
    """Find intervals that match given pattern."""
    matches = re.finditer(pattern, text)
    if reverse:
        matches = reversed(list(matches))
    return [Interval(match.start(group), match.end(group))
            for match in matches]


def selectpattern(pattern, document, selection=None, selectmode=None,
                  reverse=False, group=0):
    newselection = Selection()
    selection = selection or document.selection
    selectmode = selectmode or document.selectmode

    match_intervals = findpattern(document.text, pattern, reverse, group)

    # First select all occurences intersecting with selection,
    # and process according to mode
    new_intervals = [interval for interval in match_intervals
                     if selection.intersects(interval)]

    if new_intervals:
        new_selection = Selection(new_intervals)
        if selectmode == 'Extend':
            new_selection.add(new_intervals)
        elif selectmode == 'Reduce':
            new_selection.substract(new_intervals)

        if new_selection and selection != new_selection:
            newselection.add(new_selection)
            return newselection

    # If that doesnt change the selection,
    # start selecting one by one, and process according to mode
    new_intervals = []
    if reverse:
        beg, end = selection[-1]
    else:
        beg, end = selection[0]

    for mbeg, mend in match_intervals:
        new_selection = Selection(Interval(mbeg, mend))
        # If match is in the right direction
        if not reverse and mend > beg or reverse and mbeg < end:
            if selectmode == 'Extend':
                new_selection = selection.add(new_selection)
            elif selectmode == 'Reduce':
                new_selection = selection.substract(new_selection)

            if new_selection and selection != new_selection:
                newselection.add(new_selection)
                return newselection

    return newselection


def select_local_pattern(pattern, document, selection=None, selectmode=None, reverse=False,
                         group=0, only_within=False, allow_same_interval=False):
    newselection = Selection()
    selection = selection or document.selection
    selectmode = selectmode or document.selectmode

    match_intervals = findpattern(document.text, pattern, reverse, group)

    for interval in selection:
        beg, end = interval
        new_interval = None

        for mbeg, mend in match_intervals:
            # If only_within is True,
            # match must be within current interval
            if only_within and not (beg <= mbeg and mend <= end):
                continue

            # If allow_same_interval is True, allow same interval as original
            if allow_same_interval and (beg, end) == (mbeg, mend):
                new_interval = Interval(mbeg, mend)
                break

            # If match is valid, i.e. overlaps
            # or is beyond current interval in right direction
            # or is empty interval adjacent to current interval in right direction
            if (not reverse and mend > beg
                    or reverse and mbeg < end):
                if selectmode == 'Extend':
                    new_interval = Interval(min(beg, mbeg), max(end, mend))
                elif selectmode == 'Reduce':
                    if reverse:
                        mend = max(end, mend)
                    else:
                        mbeg = min(beg, mbeg)
                    new_interval = interval - Interval(mbeg, mend)
                else:
                    new_interval = Interval(mbeg, mend)

                if new_interval and new_interval != interval:
                    break

        # If no suitable result for this interval, return original selection
        if not new_interval:
            return selection

        newselection.add(new_interval)
    return newselection


selectindent = partial(select_local_pattern, r'(?m)^([ \t]*)', reverse=True, group=1,
                       allow_same_interval=True)
commands.selectindent = selectindent


selectline = partial(select_local_pattern, r'(?m)^[ \t]*([^\n]*)', group=1,
                     allow_same_interval=True)
commands.selectline = selectline


selectfullline = partial(select_local_pattern, r'[^\n]*\n?',
                         allow_same_interval=True)
commands.selectfullline = selectfullline


def patternpair(pattern, **kwargs):
    """
    Return two local pattern selectors for given pattern,
    one matching forward and one matching backward.
    """
    return (partial(select_local_pattern, pattern, **kwargs),
            partial(select_local_pattern, pattern, reverse=True, **kwargs))

nextchar, previouschar = patternpair(r'(?s).')
commands.nextchar = nextchar
commands.previouschar = previouschar
nextword, previousword = patternpair(r'\b\w+\b')
commands.nextword = nextword
commands.previousword = previousword
nextclass, previousclass = patternpair(r'\w+|[ \t]+|[^\w \t\n]+')
commands.nextclass = nextclass
commands.previousclass = previousclass
nextline, previousline = patternpair(r'(?m)^[ \t]*([^\n]*)', group=1)
commands.nextline = nextline
commands.previousline = previousline
nextfullline, previousfullline = patternpair(r'[^\n]*\n?')
commands.nextfullline = nextfullline
commands.previousfullline = previousfullline
nextparagraph, previousparagraph = patternpair(r'(?s)((?:[^\n][\n]?)+)')
commands.nextparagraph = nextparagraph
commands.previousparagraph = previousparagraph
nextwhitespace, previouswhitespace = patternpair(r'\s')
commands.nextwhitespace = nextwhitespace
commands.previouswhitespace = previouswhitespace


def lock(document):
    """Lock current selection."""
    if document.locked_selection == None:
        document.locked_selection = Selection()
    document.locked_selection += document.selection
    assert not document.locked_selection.isempty
commands.lock = lock


def unlock(document):
    """Remove current selection from locked selection."""
    locked = document.locked_selection
    if locked != None:
        nselection = locked - document.selection
        if not nselection.isempty:
            document.locked_selection = nselection
commands.unlock = unlock


def release(document):
    """Release locked selection."""
    if document.locked_selection != None:
        # The text length may be changed after the locked selection was first created
        # So we must bound it to the current text length
        newselection = document.locked_selection.bound(0, len(document.text))
        if not newselection.isempty:
            document.selection = newselection
        document.locked_selection = None
commands.release = release
