from .basetestcase import BaseTestCase
from tempfile import gettempdir
from os import urandom
import random
from .randomized_userinterface import RandomizedUserSimulator
from .cmdargs import args


class RandomizedCommandTest(BaseTestCase):

    def setUp(self):
        self.create_userinterface = RandomizedUserSimulator
        BaseTestCase.setUp(self)

    def test_random_commands(self):
        if args.no_randomized_tests:
            print('Skipping randomized tests')
            return

        # Hack to allow setUp to be called properly
        self.tearDown()

        commands_per_run = 1000
        runs = 500
        if args.long:
            runs = 5000
        if args.rerun or args.seed:
            runs = 1

        self.successes = 0
        for run in range(runs):
            self.setUp()
            seed = self.getseed()
            print('Run {} (seed={})'.format(run + 1, seed))
            self.saveseed(seed)

            random.seed(seed)
            self.run_test(seed, commands_per_run)
            self.tearDown()

        # Want to know for sure all tests are really executed
        assert self.successes == runs
        print("SUCCESS...")

        # Hack to allow tearDown to be called properly
        self.setUp()

    def getseed(self):
        if args.seed != None:
            return int(args.seed)
        elif args.rerun:
            try:
                with open(gettempdir() + '/last_test_seed_fate.tmp') as f:
                    return int(f.read())
            except IOError:
                raise Exception('Can\'t rerun testcase: no previous testcase exists.')
        else:
            return int.from_bytes(urandom(10), byteorder='big')

    def saveseed(self, seed):
        """Save seed into temp file."""
        savefile = gettempdir() + '/last_test_seed_fate.tmp'
        if args.verbose:
            print('Saving run into ' + savefile)
        with open(savefile, 'w') as f:
            f.write(str(seed))

    def run_test(self, seed, commands_per_run):
        """Run the test based on given seed."""
        if args.verbose:
            print('Sample text:\n' + str(self.doc.text))
            print('Starting selection: ' + str(self.doc.selection))

        for i in range(commands_per_run):
            userinput = self.doc.ui.getinput()

            if args.verbose:
                try:
                    name = userinput.__name__
                except AttributeError:
                    name = str(userinput)
                print('{}: Input = {}, Mode = {}'.format(i + 1, name, self.doc.mode))

            try:
                self.doc.mode.processinput(self.doc, userinput)
            except:
                print('Current text:\n{}'.format(self.doc.text))
                print('Current selection: {}'.format(self.doc.selection))
                print('Current pattern: {}'.format(self.doc.search_pattern))
                raise

        self.successes += 1
