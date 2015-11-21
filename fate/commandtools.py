"""
This module contains several base classes and decorators for creating commands.
"""
from logging import debug
from collections import deque
from inspect import isclass
from .mode import Mode


class Undoable:

    """
    For some commands, we want to be able to undo them.
    Let us define the class Undoable for that.

    Note that, all commands can be made trivially undoable,
    by storing the document before and after applying the command.
    This is however not desirable for reasons of space.
    Therefore we leave the specific implementation
    of the undo method to the concrete subclasses.
    """

    def __call__(self, doc):
        """Add command to the undotree and execute it."""
        doc.undotree.add(self)
        self.do(doc)

    def undo(self, doc):
        """Undo command."""
        raise NotImplementedError("An abstract method is not callable.")

    def do(self, doc):
        """
        Execute command without it being added to the undotree again,
        e.g. for performing a redo.
        """
        raise NotImplementedError("An abstract method is not callable.")


# PROBLEM:
# Suppose we want to create a compound selection which involves a the mode
# of the document to change to extend mode at some point.
# Then extend mode must be executed at creation time,
# in order to create the intended selection.
# However, this violates the principle that the document must not be
# touched while only creating a command.
# The solution is that compositions don't return an command and thus
# cannot be inspected
# If this functionality is required nonetheless,
# the composition must be defined in a command body

# PROBLEM:
# how do you know whether to wait or to proceed after executing a mode
# solution: always wait, if you need a mode to change behaviour of further commands
# you should do it differently. Modes are meant to change the way that userinput is
# processed. If you need to switch between behaviours of certain commands (like head/tail
# selection) you should toggle a bool somewhere.

# TODO: Modes in nestesd compositions are not recognized as modes,
# so the toplevel Compound will just continue.
# Solution: make compounds take a callback function, and let it treat compounds
# in the same manner as modes.
def Compose(*subcommands, name='', docs=''):
    """
    In order to be able to conveniently chain commands, we provide a
    function that composes a sequence of commands into a single command.
    The undoable subcommands should be undoable as a whole.
    """
    # We need to define a new class for each composition
    class Compound:

        def __init__(self, doc):
            self.subcommands = subcommands

            self.todo = deque(self.subcommands[:])
            doc.undotree.start_sequence()
            self.proceed(doc)

        def proceed(self, doc):
            """
            This function gets called when a submode finishes,
            as it is passed as a callback function to submodes.
            """
            while self.todo:
                command = self.todo.popleft()
                while 1:
                    # Pass ourselves as callback when executing a mode
                    if isclass(command) and issubclass(command, Mode):
                        mode = command(doc) 
                        mode.start(doc, self.proceed)
                        return

                    result = command(doc)
                    if not callable(result):
                        break
                    command = result

            # Now we are completely finished
            doc.undotree.end_sequence()

    Compound.__name__ = name
    Compound.__docs__ = docs
    return Compound
