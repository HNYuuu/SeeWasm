from collections import namedtuple

from seewasm.arch.wasm.decode import decode_module
from seewasm.arch.wasm.instruction import WasmInstruction
from seewasm.arch.wasm.wasm import Wasm
from seewasm.core.function import Function
from seewasm.core.utils import bytecode_to_bytes
from seewasm.engine.disassembler import Disassembler

from wasm.compat import byte2int
from wasm.formatter import format_instruction
from wasm.modtypes import CodeSection
from wasm.opcodes import OPCODE_MAP

inst_namedtuple = namedtuple('Instruction', 'op imm len')


class WasmDisassembler(Disassembler):

    def __init__(self, bytecode=None):
        Disassembler.__init__(self, asm=Wasm(), bytecode=bytecode)

    def disassemble_opcode(self, bytecode=None, offset=0, nature_offset=0):
        '''
        based on decode_bytecode()
        https://github.com/athre0z/wasm/blob/master/wasm/decode.py

        '''

        bytecode_wnd = memoryview(bytecode)
        bytecode_idx = 0
        opcode_id = byte2int(bytecode_wnd[bytecode_idx])
        opcode_size = 1

        bytecode_idx += 1
        if opcode_id == 0xfc:
            opcode_id = (opcode_id << 8) | byte2int(bytecode_wnd[bytecode_idx])
            if opcode_id == 0xfc0a: # memory.copy
                opcode_size = 4
            elif opcode_id == 0xfc0b: # memory.fill
                opcode_size = 3
        # default value
        # opcode:(mnemonic/name, imm_struct, pops, pushes, description)
        invalid = ('INVALID', 0, 0, 0, 'Unknown opcode')
        name, imm_struct, pops, pushes, description = \
            self.asm.table.get(opcode_id, invalid)

        operand_size = 0
        operand = None
        operand_interpretation = None

        if imm_struct is not None:
            assert not isinstance(imm_struct, int), f"imm_struct is int, most likely encountered unsupported inst.\nname: {name}\nimm_struct: {imm_struct}\npops: {pops} pushes: {pushes}\ndesc: {description}\nopcode_id: {hex(opcode_id)}"
            operand_size, operand, _ = imm_struct.from_raw(
                None, bytecode_wnd[bytecode_idx:])
            insn = inst_namedtuple(
                OPCODE_MAP[opcode_id], operand, bytecode_idx + operand_size)
            operand_interpretation = format_instruction(insn)
        insn_byte = bytecode_wnd[:bytecode_idx + operand_size].tobytes()
        instruction = WasmInstruction(
            opcode_id, opcode_size, name, imm_struct, operand_size, insn_byte, pops, pushes,
            description, operand_interpretation=operand_interpretation,
            offset=offset, nature_offset=nature_offset)
        # print('%d %s' % (offset, str(instruction)))
        return instruction

    def disassemble(self, bytecode=None, offset=0, nature_offset=0,
                    r_format='list'):
        """Disassemble WASM bytecode

        :param bytecode: bytecode sequence
        :param offset: start offset
        :param r_format: output format ('list'/'text'/'reverse')
        :type bytecode: bytes, str
        :type offset: int
        :type r_format: list, str, dict
        :return: dissassembly result depending of r_format
        :rtype: list, str, dict
        """

        return super().disassemble(bytecode, offset, nature_offset, r_format)

    def extract_functions_code(self, module_bytecode):
        functions = list()
        mod_iter = iter(decode_module(module_bytecode))
        _, _ = next(mod_iter)
        sections = list(mod_iter)

        # iterate over all section
        # code_data = [cur_sec_data for cur_sec, cur_sec_data in sections if isinstance(cur_sec_data.get_decoder_meta()['types']['payload'], CodeSection)][0]
        for cur_sec, cur_sec_data in sections:
            sec = cur_sec_data.get_decoder_meta()['types']['payload']
            if isinstance(sec, CodeSection):
                code_data = cur_sec_data
                break
        if not code_data:
            raise ValueError('No functions/codes in the module')
        for idx, func in enumerate(code_data.payload.bodies):
            instructions = self.disassemble(func.code.tobytes())
            cur_function = Function(0, instructions[0])
            cur_function.instructions = instructions

            functions.append(cur_function)
        return functions

    def disassemble_module(
            self, module_bytecode=None, offset=0, r_format='list'):

        bytecode = bytecode_to_bytes(module_bytecode)

        functions = self.extract_functions_code(bytecode[offset:])
        self.instructions = [f.instructions for f in functions]

        # return instructions
        if r_format == 'list':
            return self.instructions
        elif r_format == 'text':
            text = ''
            for index, func in enumerate(functions):
                text += ('func %d\n' % index)
                text += ('\n'.join(map(str, func.instructions)))
                text += ('\n\n')
            return text
