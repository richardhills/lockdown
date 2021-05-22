# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import argparse
import sys
import unittest

from lockdown.utils import set_debug, set_runtime_type_information, profile


parser = argparse.ArgumentParser()
parser.add_argument('-d', action='store_true', help='debug')
parser.add_argument('-t', action='store_false', help='rtti mode off')
parser.add_argument('-p', help='cProfile mode')
args, unknown_args = parser.parse_known_args()
sys.argv[1:] = unknown_args

set_debug(args.d)
set_runtime_type_information(args.t)

sys.setrecursionlimit(10000)

if __name__ == "__main__":
    from lockdown.executor import test as executor_tests
    from lockdown.executor.test import *
    from lockdown.parser import test as parser_tests
    from lockdown.parser.test import *
    from lockdown.type_system import test as type_system_tests
    from lockdown.type_system.test import *

    if args.p:
        with profile(args.p):
            unittest.main()
    else:
        unittest.main()
