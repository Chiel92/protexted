import sys

import argparse
import fate
from fate.test import cmdargs

parser = argparse.ArgumentParser()
parser.add_argument('-r', '--rerun', help='rerun the latest testcase',
                    action='store_true')
parser.add_argument('-s', '--seed', help='run a testcase with given seed',
                    action='store')
parser.add_argument('-l', '--long', help='start a long testing session',
                    action='store_true')
parser.add_argument('-n', '--no-randomized-tests',
                    help='don \'t run the randomized tests', action='store_true')
parser.add_argument('-v', '--verbose', help='run in verbose mode',
                    action='store_true')
parser.add_argument('-m', '--module', help='run single module',
                    action='store')
parser.add_argument('-p', '--print-logs', help='write log messages to stdout',
                    action='store_true')
args = parser.parse_args()
cmdargs.args = args
fate.log.LOG_TO_STDOUT = args.print_logs


from unittest import defaultTestLoader as loader, TextTestRunner

if args.module:
    module = 'fate.' + args.module
    print('Loading ' + module)
    suite = loader.loadTestsFromName(module)
else:
    suite = loader.discover('.')

runner = TextTestRunner()
test_result = runner.run(suite)
success = test_result.wasSuccessful()
if not success:
    sys.exit(1)
