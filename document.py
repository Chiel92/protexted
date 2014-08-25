"""A document represents the state of an editing document."""
from .selection import Selection, Interval
from .operation import Operation
from .event import Event
from . import commands
from .userinterface import UserInterface
from .mode import ModeStack
from .selectors import selectall

import logging

documentlist = []
activedocument = None


class Document():

    """Contains all objects of one file editing document"""
    OnDocumentInit = Event()
    create_userinterface = None
    _text = ''
    saved = True

    expandtab = False
    tabwidth = 4
    autoindent = True

    locked_selection = None

    def __init__(self, filename=""):
        documentlist.append(self)
        self.OnTextChanged = Event()
        self.OnRead = Event()
        self.OnWrite = Event()
        self.OnQuit = Event()
        self.OnActivate = Event()

        self.filename = filename
        self.selection = Selection(Interval(0, 0))
        self.mode = ModeStack()
        self.selectmode = 'SELECT'

        if not self.create_userinterface:
            raise Exception('No function specified in Document.create_userinterface.')
        self.ui = self.create_userinterface(self)
        if not isinstance(self.ui, UserInterface):
            raise Exception('document.ui not an instance of UserInterface.')
        self.OnQuit.add(self.ui.quit)

        # Load the default key map
        from .keymap import default
        self.keymap = {}
        self.keymap.update(default)

        self.OnDocumentInit.fire(self)

        if filename:
            load(self)

    def quit(self):
        """Quit document."""
        logging.info('Quitting document ' + str(self))
        self.OnQuit.fire(self)
        global activedocument
        index = documentlist.index(self)

        # debug(str(documentlist))
        #debug("self: " + str(self.document))
        #debug("index: " + str(index))
        # self.getkey()

        if len(documentlist) == 1:
            activedocument = None
            return

        if index < len(documentlist) - 1:
            nextdocument = documentlist[index + 1]
        else:
            nextdocument = documentlist[index - 1]

        nextdocument.activate()
        documentlist.remove(self)

    def activate(self):
        """Activate this document."""
        global activedocument
        activedocument = self
        self.OnActivate.fire(self)

    @property
    def selection(self):
        return self._selection

    @selection.setter
    def selection(self, value):
        # Make sure only valid selections are applied
        assert isinstance(value, Selection)
        value.validate(self)
        self._selection = value

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        self._text = value

        # Make sure that the selection stays valid
        self.selection.validate(self)

        self.saved = False
        self.OnTextChanged.fire(self)


def save(document, filename=None):
    """Save document text to file."""
    filename = filename or document.filename

    if filename:
        try:
            with open(filename, 'w') as fd:
                fd.write(document.text)
            document.saved = True
            document.OnWrite.fire(document)
        except (FileNotFoundError, PermissionError) as e:
            logging.error(str(e))
    else:
        logging.error('No filename')
commands.save = save


def load(document, filename=None):
    """Load document text from file."""
    filename = filename or document.filename

    if filename:
        try:
            with open(filename, 'r') as fd:
                newtext = fd.read()
        except (FileNotFoundError, PermissionError) as e:
            logging.error(str(e))
        else:
            current_selection = document.selection
            selectall(document)
            operation = Operation(document, [newtext])
            operation(document)
            document.selection = current_selection.bound(0, len(document.text))
            document.saved = True
            document.OnRead.fire(document)
    else:
        logging.error('No filename')
commands.load = load


def open_document(document):
    """Open a new document."""
    filename = document.ui.prompt('Filename: ')
    Document(filename)
commands.open_document = open_document


def quit_document(document):
    """Close current document."""
    if not document.saved:
        while 1:
            answer = document.ui.prompt('Unsaved changes! Really quit? (y/n)')
            if answer == 'y':
                document.quit()
                break
            if answer == 'n':
                break
    else:
        document.quit()
commands.quit_document = quit_document


def quit_all(document):
    """Close all documents."""
    for document in documentlist:
        quit_document(document)


def force_quit(document):
    """Quit all documents without warning if unsaved changes."""
    for document in documentlist:
        document.quit()
commands.force_quit = force_quit


def next_document(document):
    """Go to the next document."""
    index = documentlist.index(document)
    ndocument = documentlist[(index + 1) % len(documentlist)]
    ndocument.activate()
commands.next_document = next_document


def previous_document(document):
    """Go to the previous document."""
    index = documentlist.index(document)
    ndocument = documentlist[(index - 1) % len(documentlist)]
    ndocument.activate()
commands.previous_document = previous_document


def goto_document(index):
    """Command constructor to go to the document at given index."""
    def wrapper(document):
        documentlist[index].ui.activate()
    return wrapper
