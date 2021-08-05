# define our own exceptions

# used in `type2z3.py`
# indicating that the variable type is not in ['i32', 'i64', 'f32', 'f64']
class UnsupportZ3TypeError(Exception):
    pass

# used in `emulator.py`
# indicating the local variable is not initialized before retriving
class UninitializedLocalVariableError(Exception):
    pass

# used in `emulator.py`
# indicating the unsupport global type encoutering global.get
class UnsupportGlobalTypeError(Exception):
    pass

# used in `emulator.py`
# indicating the unsupport instructions
class UnsupportInstructionError(Exception):
    pass

# indicateing the return value is bool but cannot be determined as True or False
class NotDeterminedRetValError(Exception):
    pass

# indicateing the state is not initialized before emulate_one_function
class UninitializedStateError(Exception):
    pass

# indicating the memory load error
class MemoryLoadError(Exception):
    pass