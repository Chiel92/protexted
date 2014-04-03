"""This module defines the class Operation."""
from .selection import Selection, Interval
from .action import Undoable, Updateable
from .selectors import SelectIndent
from . import modes


class Operation(Undoable):
    """
    A container of modified content of a selection.
    Can be inverted such that the operation can be undone by applying the inverse.
    The members are `old_selection`, `old_content`, `new_content` and `new_selection`.
    """
    def __init__(self, session, selection=None, new_content=None):
        selection = selection or session.selection
        self.old_selection = selection
        self.old_content = selection.content(session)
        try:
            self.new_content = new_content or self.old_content[:]
        except AttributeError:
            # new_content has been overriden
            # TODO neater fix for this
            pass

    def __str__(self):
        attributes = [('old_selection', self.old_selection),
                      ('new_selection', self.new_selection),
                      ('old_content', self.old_content),
                      ('new_content', self.new_content)]
        return '\n'.join([k + ': ' + str(v) for k, v in attributes])

    @property
    def new_selection(self):
        """The selection containing the potential result of the operation."""
        beg = self.old_selection[0][0]
        end = beg + len(self.new_content[0])
        result = Selection(Interval(beg, end))
        for i in range(1, len(self.old_selection)):
            beg = end + self.old_selection[i][0] - self.old_selection[i - 1][1]
            end = beg + len(self.new_content[i])
            result.add(Interval(beg, end))
        return result

    def _call(self, session, inverse=False):
        """Apply self to the session."""
        if inverse:
            old_selection = self.new_selection
            new_selection = self.old_selection
            new_content = self.old_content
        else:
            new_selection = self.new_selection
            old_selection = self.old_selection
            new_content = self.new_content

        partition = old_selection.partition(session)
        partition_content = [(in_selection, session.text[beg:end])
                             for in_selection, (beg, end) in partition]
        count = 0
        result = []
        for in_selection, string in partition_content:
            if in_selection:
                result.append(new_content[count])
                count += 1
            else:
                result.append(string)

        session.text = ''.join(result)
        session.selection_mode = modes.SELECT_MODE
        session.selection = new_selection

    def _undo(self, session):
        """Undo operation."""
        self._call(session, inverse=True)


class InsertOperation(Operation, Updateable):
    """Abstract class for operations dealing with insertion of text."""
    def __init__(self, session, selection=None):
        selection = selection or session.selection
        Operation.__init__(self, session, selection)
        self.insertions = ['' for _ in selection]
        self.deletions = [0 for _ in selection]

    def insert(self, session, string):
        """
        Insert a string (typically a char) in the operation.
        By only autoindenting on a single \n, we potentially allow proper pasting.
        """
        indent = SelectIndent(session, self.new_selection)
        for i in range(len(self.new_selection)):
            if string == '\b':
                # remove string
                if self.insertions[i]:
                    self.insertions[i] = self.insertions[i][:-1]
                else:
                    self.deletions[i] += 1
            elif string == '\n':
                # add indent after \n
                self.insertions[i] += string + indent.content(session)[i]
            elif string == '\t' and session.expandtab:
                self.insertions[i] += ' ' * session.tabwidth
            else:
                # add string
                self.insertions[i] += string

        self.update(session)
