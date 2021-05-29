# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import argparse
import sys
import unittest

from lockdown.utils import profile, environment


parser = argparse.ArgumentParser()
parser.add_argument('-t', action='store_false', help='rtti mode off')
parser.add_argument('-s', action='store_false', help='frame shortcut off')
parser.add_argument('-f', action='store_false', help='validate flow control off')
parser.add_argument('-o', action='store_false', help='opcode bindings off')
parser.add_argument('-p', action='store_false', help='consume python objects off')
parser.add_argument('-r', action='store_false', help='return value optimization off')
parser.add_argument('-T', action='store_true', help="transpile to python")
parser.add_argument('-P', help='cProfile mode')
args, unknown_args = parser.parse_known_args()
sys.argv[1:] = unknown_args

sys.setrecursionlimit(10000)

if __name__ == "__main__":
    from lockdown.executor import test as executor_tests
    from lockdown.executor.test import *
    from lockdown.parser import test as parser_tests
    from lockdown.parser.test import *
    from lockdown.type_system import test as type_system_tests
    from lockdown.type_system.test import *

    with environment(
        rtti=args.t,
        frame_shortcut=args.s,
        validate_flow_control=args.f,
        opcode_bindings=args.o,
        consume_python_objects=args.p,
        return_value_optimization=args.r,
        transpile=args.T,
        base=True
    ):
        if args.P:
            with profile(args.p):
                unittest.main()
        else:
            unittest.main()
