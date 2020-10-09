# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import argparse
import sys

from rdhlang5.utils import set_runtime_type_information, set_debug, profile


parser = argparse.ArgumentParser()
parser.add_argument('-d', action='store_true', help='debug')
parser.add_argument('-t', action='store_false', help='rtti mode off')
parser.add_argument('-p', help='cProfile mode')
args, unknown_args = parser.parse_known_args()
sys.argv[1:] = unknown_args


set_debug(args.d)
set_runtime_type_information(args.t)

if __name__ == "__main__":
    from rdhlang5.executor import test as executor_tests
    from rdhlang5.executor.test import *
    from rdhlang5.parser import test as parser_tests
    from rdhlang5.parser.test import *
    from rdhlang5.type_system import test as type_system_tests
    from rdhlang5.type_system.test import *

    if args.p:
        with profile(args.p):
            unittest.main()
    else:
        unittest.main()
