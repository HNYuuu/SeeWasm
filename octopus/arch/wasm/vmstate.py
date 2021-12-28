# This file defines the `state` that will be passed within Wasm-SE

from collections import defaultdict

from loky import wrap_non_picklable_objects
from octopus.engine.engine import VMstate
from z3 import *


class WasmVMstate(VMstate):
    def __init__(self):
        # data structure:
        @wrap_non_picklable_objects
        def local_default():
            return BitVecVal(0, 32)
        self.symbolic_stack = []
        self.symbolic_memory = {}
        self.local_var = defaultdict(local_default)
        self.globals = {}
        self.constraints = []
        # instruction
        self.instr = "end"
        # current function name
        self.current_func_name = 'none'
        # keep the operator and its speculated sign
        self.sign_mapping = defaultdict(bool)
        # TODO adapt C code
        # TODO we insert a `123` here, maybe we should insert a symbol
        # stdin buffer used by _fd_read, but scanf(modeled seperately) does not read from it
        self.stdin_buffer = [c for c in b'123\n'] # int array, use pop(0)

    def __str__(self):
        return f'''Current Func:\t{self.current_func_name}
Stack:\t\t{self.symbolic_stack}
Local Var:\t{self.local_var}
Global Var:\t{self.globals}
Memory:\t\t{self.symbolic_memory}
Constraints:\t{self.constraints}\n'''

    def details(self):
        raise NotImplementedError

    def __lt__(self, other):
        return False

    def __getstate__(self):
        return self.__dict__.copy()
