import copy

from z3 import *
from collections import defaultdict, deque

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class ClassPropertyDescriptor:
    def __init__(self, fget, fset=None):
        self.fget = fget
        self.fset = fset

    def __get__(self, obj, klass=None):
        if klass is None:
            klass = type(obj)
        return self.fget.__get__(obj, klass)()

    def __set__(self, obj, value):
        if not self.fset:
            raise AttributeError
        type_ = type(obj)
        return self.fset.__get__(obj, type_)(value)

    def setter(self, func):
        if not isinstance(func, (classmethod, staticmethod)):
            func = classmethod(func)
        self.fset = func
        return self

def classproperty(func):
    if not isinstance(func, (classmethod, staticmethod)):
        func = classmethod(func)
    return ClassPropertyDescriptor(func)

class Graph:
    _func_to_bbs = {}
    _bb_to_instructions = {}
    _bbs_graph = defaultdict(dict) # nested dict
    _loop_maximum_rounds = 5
    _wasmVM = None
    manual_guide = False

    def __init__(self, funcs):
        self.entries = funcs
        self.final_states = {func: None for func in funcs}

    @classproperty
    def loop_maximum_rounds(cls):
        return cls._loop_maximum_rounds

    @classproperty
    def func_to_bbs(cls):
        return cls._func_to_bbs

    @classproperty
    def bbs_graph(cls):
        return cls._bbs_graph

    @classproperty
    def bb_to_instructions(cls):
        return cls._bb_to_instructions

    @classproperty
    def wasmVM(cls):
        return cls._wasmVM

    @wasmVM.setter
    def wasmVM(cls, val):
        cls.wasmVM = val

    @classmethod
    def extract_basic_blocks(cls):
        cfg = cls.wasmVM.cfg
        funcs = cfg.functions
        cls.func_to_bbs = dict()
        for func in funcs:
            func_name, func_bbs = func.name, func.basicblocks
            # get the name of bb in func_bbs 
            func_bbs = [bb.name for bb in func_bbs]
            cls.func_to_bbs[func_name] = func_bbs

        # adjacent graph for basic blocks, like:
        # {'block_3_0': ['block_3_6', 'block_3_9']}
        edges = cfg.edges
        for edge in edges:
            # there are four types of edges:
            # ['unconditional', 'fallthrough', 'conditional_true', 'conditional_false']
            node_from, node_to, edge_type = edge.node_from, edge.node_to, edge.type
            cls.bbs_graph[node_from][edge_type] = node_to

        # goal 1: append those single node into the bbs_graph
        # goal 2: initialize bb_to_instructions
        bbs = cfg.basicblocks
        for bb in bbs:
            # goal 1
            bb_name = bb.name
            if bb_name not in cls.bbs_graph:
                cls.bbs_graph[bb_name] = dict()
            # goal 2
            cls.bb_to_instructions[bb_name] = bb.instructions

    def traverse(self):
        for entry_func in self.entries:
            self.final_states[entry_func] = self.traverse_one(entry_func)

    @classmethod
    def traverse_one(cls, func, state=None, has_ret=None):
        param_str, return_str = cls.wasmVM.get_signature(func)
        if state is None:
            state, has_ret = cls.wasmVM.init_state(func, param_str, return_str, [])
        # store the caller func
        caller_func_name = state.current_func_name
        # set the callee func
        state.current_func_name = cls.wasmVM.cfg.get_function(func).name

        # retrieve all the relevant basic blocks
        entry_func_bbs = cls.func_to_bbs[func]
        # filter out the entry basic block and corresponding instructions
        entry_bb = list(filter(lambda bb: bb[-2:] == '_0', entry_func_bbs))[0]
        vis = defaultdict(int)
        circles = set()
        cls.pre(entry_bb, vis, circles)
        vis = defaultdict(int)

        final_states = cls.visit([state], has_ret, entry_bb, vis, circles, cls.manual_guide)
        # recover the caller func
        state.current_func_name = caller_func_name
        return final_states

    @classmethod
    def pre(cls, blk, vis, circles):
        if vis[blk] == 1 and len(cls.bbs_graph[blk]) == 2: # br_if and has visited
            circles.add(blk)
            return
        vis[blk] = 1
        for ty in cls.bbs_graph[blk]:
            cls.pre(cls.bbs_graph[blk][ty], vis, circles)

    @classmethod
    def visit(cls, states, has_ret, blk, vis, circles, guided, branches=None):
        if not guided and vis[blk] > 0:
            return states
        instructions = cls.bb_to_instructions[blk]
        halt, emul_states = cls.wasmVM.emulate_basic_block(states, has_ret, instructions)
        if halt or len(cls.bbs_graph[blk]) == 0:
            return emul_states
        vis[blk] += 1
        final_states = []
        if guided:
            # show how many possible states here, and ask the user to choose one
            print(
                f"\n[+] Currently, there are {bcolors.WARNING}{len(emul_states)}{bcolors.ENDC} possible state(s) here")
            print(f"[+] Please choose one to continue the following emulation (1 -- {len(emul_states)})")
            print(
                f"[+] Also, you can add an 'i' to illustrate information of the corresponding state (e.g., '1 i' to show the first state's information)")
            state_index = cls.ask_user_input(emul_states, isbr=False)  # 0 for state, is a flag
            state_item = emul_states[state_index]
            emul_states = [state_item]

        for state_item in emul_states:
            branches = cls.bbs_graph[blk] if branches is None else branches
            avail_br = []
            for type in branches:
                if type in ['conditional_true', 'conditional_false'] and isinstance(state_item, dict):
                    if type not in state_item:
                        continue
                    state = state_item[type]
                    solver = Solver()
                    solver.add(*state.constraints)
                    if sat != solver.check():
                        continue
                avail_br.append(type)
            if guided:
                print(
                    f"\n[+] Currently, there are {len(avail_br)} possible branch(es) here: {bcolors.WARNING}{avail_br}{bcolors.ENDC}")
                print(f"[+] Please choose one to continue the following emulation (T, F, f, u)")
                print(
                    f"[+] Also, you can add an 'i' to illustrate information of your choice (e.g., 'T i' to show the basic block if you choose to go to the true branch)")
                avail_br = [cls.ask_user_input(emul_states, isbr=True, branches=avail_br, state_item=state_item)]

            for type in avail_br:
                nxt_blk = cls.bbs_graph[blk][type]
                state = state_item[type] if isinstance(state_item, dict) else state_item
                if not guided:
                    if nxt_blk in circles:
                        enter_states = [state]
                        for i in range(cls.loop_maximum_rounds):
                            enter_states = cls.visit(enter_states, has_ret, nxt_blk, vis, circles, guided, ['conditional_false'])
                        enter_states = cls.visit(enter_states, has_ret, nxt_blk, vis, circles, guided, ['conditional_true'])
                        final_states.extend(enter_states)
                    else:
                        final_states.extend(cls.visit([state], has_ret, nxt_blk, vis, circles, guided))
                else:
                    final_states.extend(cls.visit([state], has_ret, nxt_blk, vis, circles, guided))
        vis[blk] -= 1
        return final_states if len(final_states) > 0 else states

    @classmethod
    def show_state_info(cls, state_index, states):
        state = states[state_index]
        state_infos = state.items() if isinstance(state, dict) else [('fallthrough', state)]
        for edge_type, info in state_infos:
            print(f'''
PC:\t\t{info.pc}
Current Func:\t{info.current_func_name}
Stack:\t\t{info.symbolic_stack}
Local Var:\t{info.local_var}
Global Var:\t{info.globals}
Memory:\t\t{info.symbolic_memory}
Constraints:\t{info.constraints[:-1]}\n''')

    @classmethod
    def show_branch_info(cls, branch, branches, state):
        bb_name = branches[branch]
        if branch in ['conditional_true', 'conditional_false']:
            print(f'[!] The constraint: "{state[branch].constraints[-1]}" will be appended')
        print(f'[!] You choose to go to basic block: {bb_name}')
        print(f'[!] Its instruction begins at offset {cls.bb_to_instructions[bb_name][0].offset}')
        print(f'[!] The leading instructions are showed as follows:')
        instructions = cls.bb_to_instructions[bb_name]
        for i, instr in enumerate(instructions):
            if i >= 10:
                break
            print(f'\t{instr.operand_interpretation}')

    @classmethod
    def ask_user_input(cls, emul_states, isbr, branches=None, state_item=None):
        # the flag can be 0 or 1,
        # 0 means state, 1 means branch
        # `concerned_variable` is state_index or branch, depends on the flag value
        branch_mapping = {
            'T': 'conditional_true',
            'F': 'conditional_false',
            'f': 'fallthrough',
            'u': 'unconditional',
        }

        while True:
            user_input = input("[!] Please input the command: ")
            try:
                ask_for_info = False
                if ' ' in user_input:
                    concerned_variable, ask_for_info = user_input.split(' ')
                    assert ask_for_info == 'i'
                    ask_for_info = True
                else:
                    concerned_variable = user_input

                concerned_variable = branch_mapping[user_input] if isbr else int(concerned_variable) - 1
                if not ask_for_info:
                    break
                if isbr:
                    cls.show_branch_info(concerned_variable, branches, state_item)
                else:
                    cls.show_state_info(concerned_variable, emul_states)
                print('')
            except:
                raise("[!] Valid input is needed")
        return concerned_variable
