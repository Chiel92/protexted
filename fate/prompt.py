from .mode import Mode
from .document import Document
from logging import error, debug

class Prompt(Mode):
    def __init__(self, doc):
        Mode.__init__(self, doc)
        self.inputstring = ''

    def processinput(self, doc, userinput):
        if isinstance(userinput, str):
            key = userinput
            if key == doc.cancelkey:
                self.stop(doc)
            elif key == '\n':
                self.stop(doc)
            elif len(key) > 1:
                debug('Search key {} not supported.'.format(key))
            else:
                self.inputstring += key
        else:
            error('Prompt can not process non-string input')

    def start(self, doc, promptstring='>', callback=None):
        self.inputstring = ''
        self.promptstring = promptstring
        Mode.start(self, doc, callback)

    def stop(self, doc):
        Mode.stop(self, doc)
        debug('End prompt: ' + self.inputstring)

def init_prompt(doc):
    doc.modes.prompt = Prompt(doc)
Document.OnModeInit.add(init_prompt)

