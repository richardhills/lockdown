# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import argparse
import sys
import unittest

from lockdown.utils.utils import profile, environment
from sys import setrecursionlimit


parser = argparse.ArgumentParser()
parser.add_argument('-t', action='store_false', help='rtti mode off')
parser.add_argument('-s', action='store_true', help='enable frame optimization - avoid creating Frame objects when not needed, for speed')
parser.add_argument('-r', action='store_true', help='enable return-value optimization - avoids using Python Exception-flow control for simple values (enabled by default with -T)')
parser.add_argument('-f', action='store_false', help='disable validate run-time flow control - turns off interpreter checks for speed')
parser.add_argument('-o', action='store_false', help='disable opcode bindings - avoid checking if types bind at runtime, when we know that they must bind based on verification checks, for speed')
parser.add_argument('-p', action='store_false', help='disable consuming Python objects - leave enabled for Python interopability')
parser.add_argument('-T', action='store_true', help="transpile to Python - used to speed up execution")
parser.add_argument('-O', action='store_true', help="print transpiled Python")
parser.add_argument('-P', help='cProfile mode')
args, unknown_args = parser.parse_known_args()
sys.argv[1:] = unknown_args

sys.setrecursionlimit(10000)

if __name__ == "__main__":
    from lockdown.executor.test import *
    from lockdown.parser.test import *
    from lockdown.type_system.test import *
    from lockdown.utils.test import *

#    setrecursionlimit(8000)

    with environment(
        rtti=args.t,
        frame_shortcut=args.s,
        validate_flow_control=args.f,
        opcode_bindings=args.o,
        consume_python_objects=args.p,
        return_value_optimization=args.r or args.T,
        transpile=args.T,
        output_transpiled_code=args.O,
        base=True
    ):
        if args.P:
            with profile(args.P):
                unittest.main()
        else:
            unittest.main()
