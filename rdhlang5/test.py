# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import argparse
import sys

from rdhlang5.utils import set_bind_runtime_contexts, set_debug


parser = argparse.ArgumentParser()
parser.add_argument('-d', action='store_true', help='debug')
parser.add_argument('-p', action='store_true', help='python mode')
parser.add_argument('unittest_args', nargs='*')
args = parser.parse_args()
sys.argv[1:] = args.unittest_args


set_debug(args.d)
set_bind_runtime_contexts(args.p)

if __name__ == "__main__":
    from rdhlang5.executor import test as executor_tests
    from rdhlang5.executor.test import *
    from rdhlang5.parser import test as parser_tests
    from rdhlang5.parser.test import *
    from rdhlang5.type_system import test as type_system_tests
    from rdhlang5.type_system.test import *

    unittest.main()
