import logging
import traceback
import sys
from dataclasses import dataclass
from enum import Enum, member
from typing import List, Callable, Dict

from src.isa import Command, Opcode, read_code
from src.reg_file import Register


class Signal(str, Enum):
    LATCH_LEFT_ALU = "latch left alu"
    LATCH_RIGHT_ALU = "latch right alu"

    LATCH_DATA_REGISTER = "latch data register"
    LATCH_ADDRESS_REGISTER = "latch address register"
    LATCH_REGISTER = "latch register"
    LATCH_LEFT_REGISTER_TERM = "latch left register term"
    LATCH_RIGHT_REGISTER_TERM = "latch right register term"
    LATCH_PROGRAM_COUNTER = "latch program counter"
    LATCH_MPC = "latch mpc"
    LATCH_PROGRAM = "latch program"

    SIGNAL_WRITE = "signal write"
    SIGNAL_READ = "signal read"

    EXECUTE_ALU_OPERATION = "execute alu operation"
    CHECK_ZERO_FLAG = "check zero flag"
    CHECK_NOT_ZERO_FLAG = "check not zero flag"
    CHECK_SIGN_FLAG = "check sign flag"

    HALT = "halt"


class Sel:
    class AddressRegister(str, Enum):
        PROGRAM_COUNTER = "sel_ar_pc"
        ALU = "sel_ar_alu"

    class DataRegister(str, Enum):
        ALU = "sel_dr_alu"
        MEMORY = "sel_dr_memory"

    class Register(str, Enum):
        CONTROL_UNIT = "sel_reg_cu"
        DATA_REGISTER = "sel_reg_dr"
        ALU = "sel_reg_alu"
        INPUT = "sel_reg_input"
        IMMEDIATE = "sel_reg_immediate"

    class LeftAlu(str, Enum):
        DATA_REGISTER = "sel_left_alu_dr"
        REGISTER = "sel_left_alu_reg"
        CONTROL_UNIT = "sel_left_alu_cu"

    class RightAlu(str, Enum):
        DATA_REGISTER = "sel_right_alu_dr"
        REGISTER = "sel_right_alu_reg"
        ZERO = "sel_right_alu_zero"
        PLUS_ONE = "sel_right_alu_plus_one"

    class PC(str, Enum):
        ZERO = "zero"
        MPROGRAM = "mprogram"
        PLUS_ONE = "plus_one"
        ADDRESS_REGISTER = "address_register"

    class MPC(str, Enum):
        ZERO = "zero"
        PLUS_ONE = "plus_one"
        MPC_ADDRESS = "mpc_address"


@dataclass()
class ALU:
    class ALUOperations(str, Enum):
        ADD = "add"
        SUB = "sub"
        MUL = "mul"
        DIV = "div"
        MOD = "mod"
        INC = "inc"
        DEC = "dec"
        NEG = "neg"
        CMP = "cmp"
        TEST = "test"

    result = None
    left_term = None
    right_term = None

    flags = {
        "Z": False,
        "N": False
    }

    def __init__(self):
        self.result = 0
        self.left_term = 0
        self.right_term = 0
        self.set_flags()

    def set_flags(self):
        self.flags["Z"] = self.result == 0
        self.flags["N"] = self.result < 0

    def signal_latch_left_alu(self, value):
        self.left_term = value

    def signal_latch_right_alu(self, value):
        self.right_term = value

    def compute(self, operation: ALUOperations):
        match operation:
            case ALU.ALUOperations.ADD:
                self.result = self.left_term + self.right_term
            case ALU.ALUOperations.SUB:
                self.result = self.left_term - self.right_term
            case ALU.ALUOperations.MUL:
                self.result = self.left_term * self.right_term
            case ALU.ALUOperations.DIV:
                self.result = self.left_term // self.right_term
            case ALU.ALUOperations.MOD:
                self.result = self.left_term % self.right_term
            case ALU.ALUOperations.INC:
                self.result = self.left_term + 1
            case ALU.ALUOperations.DEC:
                self.result = self.left_term - 1
            case ALU.ALUOperations.NEG:
                self.result = -self.left_term
            case ALU.ALUOperations.CMP:
                self.result = self.left_term - self.right_term
            case ALU.ALUOperations.TEST:
                self.result = self.left_term & self.right_term

        self.set_flags()


@dataclass()
class DataPath:
    memory: List[object] = None
    memory_size: int = None

    data_register = None
    address_register = None

    alu: ALU = None

    registers = {
        Register.R0: 0,
        Register.R1: 0,
        Register.R2: 0,
        Register.R3: 0
    }

    input_buffer = None
    output_buffer = None

    input_address: int = None
    output_address: int = None

    control_unit = None

    def __init__(self, code, memory_size, input_buffer):
        assert memory_size > 0, "Memory size should be positive"
        assert len(code) <= memory_size, "The program does not fit within the specified memory limits"

        self.memory = [0] * memory_size
        self.memory_size = memory_size

        self.data_register = 0
        self.address_register = 0

        self.alu = ALU()

        self.registers[Register.R0] = 0
        self.registers[Register.R1] = 0
        self.registers[Register.R2] = 0
        self.registers[Register.R3] = 0

        self.input_buffer = input_buffer
        self.output_buffer = list()

        self.input_address = 1
        self.output_address = 2

        for i in range(len(code)):
            self.memory[i] = code[i]

    def signal_latch_data_register(self, sel):
        assert isinstance(sel, Sel.DataRegister), "sel_dr is undefined"
        if sel == Sel.DataRegister.MEMORY:
            self.data_register = self.memory[self.address_register]
        elif sel == Sel.DataRegister.ALU:
            self.data_register = self.alu.result

    def signal_latch_address_register(self, sel):
        assert isinstance(sel, Sel.AddressRegister), "sel_ar is undefined"

        if sel == Sel.AddressRegister.ALU:
            self.address_register = self.alu.result
        elif sel == Sel.AddressRegister.PROGRAM_COUNTER:
            self.address_register = self.control_unit.program_counter

        assert 0 <= self.address_register < self.memory_size, f"out of memory: {self.address_register}"

    def signal_latch_register(self, register: Register, sel, value_from_control_unit=None): # todo: maybe deleter value_from_control_unit??
        assert isinstance(sel, Sel.Register), "sel_reg is undefined"
        assert isinstance(register, Register), "reg is undefined"

        if sel == Sel.Register.CONTROL_UNIT:  # todo: 2 одинаковых sel
            self.registers[register] = value_from_control_unit
        elif sel == Sel.Register.DATA_REGISTER:
            self.registers[register] = self.data_register
        elif sel == Sel.Register.ALU:
            self.registers[register] = self.alu.result
        elif sel == Sel.Register.INPUT:
            if len(self.input_buffer) == 0:
                raise EOFError
            symbol = self.input_buffer.pop(0)
            symbol_code = ord(symbol)
            assert -128 < symbol_code <= 127, f"input token is out of bound: {self.data_register}"
        elif sel == Sel.Register.IMMEDIATE:
            self.registers[register] = value_from_control_unit

    def signal_latch_left_register_term(self, register: Register):
        assert isinstance(register, Register), "register is undefined"

        self.registers[Register.LEFT_REGISTER_TERM] = self.registers[register]

    def signal_latch_right_register_term(self, register: Register):
        assert isinstance(register, Register), "register is undefined"

        self.registers[Register.RIGHT_REGISTER_TERM] = self.registers[register]

    def signal_write(self):
        assert self.address_register != self.input_address, "cannot write to input address"

        if self.address_register == self.output_address:
            self.output_buffer.append(self.data_register)
        else:
            self.memory[self.address_register] = self.data_register

    def signal_read(self):
        assert self.address_register != self.output_address, "cannot read from output address"

        if self.address_register == self.input_address:
            if len(self.input_buffer) == 0:
                raise EOFError("input buffer is empty")
            self.data_register = self.input_buffer.pop(0)
        else:
            self.data_register = self.memory[self.address_register]

    def signal_sel_left_alu(self, sel):
        assert isinstance(sel, Sel.LeftAlu), "sel_left_alu is undefined"

        if sel == Sel.LeftAlu.REGISTER:
            self.alu.signal_latch_left_alu(self.registers[Register.LEFT_REGISTER_TERM])
        elif sel == Sel.LeftAlu.DATA_REGISTER:
            self.alu.signal_latch_left_alu(self.data_register)

    def signal_sel_right_alu(self, sel):
        assert isinstance(sel, Sel.RightAlu), "sel_right_alu is undefined"

        if sel == Sel.RightAlu.REGISTER:
            self.alu.signal_latch_right_alu(self.registers[Register.RIGHT_REGISTER_TERM])
        elif sel == Sel.RightAlu.DATA_REGISTER:
            self.alu.signal_latch_right_alu(self.data_register)

    def execute_alu_operation(self, operation: ALU.ALUOperations):
        self.alu.compute(operation)

    def check_zero_flag(self):
        return self.alu.flags["Z"]

    def check_not_zero_flag(self):
        return not self.alu.flags["Z"]

    def check_sign_flag(self):
        return self.alu.flags["N"]


class ControlUnit:
    program_counter: int = None
    program = None
    mpc: int = None
    mpc_of_opcode: Callable[[Opcode], int] = None
    mprogram: List[str] = None
    data_path: DataPath = None
    model_tick: int = None
    signals: Dict[Signal, Callable] = None

    def __init__(self, data_path):
        self.program_counter = 0
        self.mpc = 0
        self.data_path = data_path
        self.model_tick = 0

        self.signals = {
            Signal.LATCH_LEFT_ALU: self.data_path.signal_sel_left_alu,
            Signal.LATCH_RIGHT_ALU: self.data_path.signal_sel_right_alu,
            Signal.LATCH_DATA_REGISTER: self.data_path.signal_latch_data_register,
            Signal.LATCH_ADDRESS_REGISTER: self.data_path.signal_latch_address_register,
            Signal.LATCH_REGISTER: self.data_path.signal_latch_register,
            Signal.LATCH_LEFT_REGISTER_TERM: self.data_path.signal_latch_left_register_term,
            Signal.LATCH_RIGHT_REGISTER_TERM: self.data_path.signal_latch_right_register_term,
            Signal.LATCH_MPC: self.signal_latch_mpc,
            Signal.LATCH_PROGRAM: self.signal_latch_program,
            Signal.SIGNAL_WRITE: self.data_path.signal_write,
            Signal.SIGNAL_READ: self.data_path.signal_read,
            Signal.EXECUTE_ALU_OPERATION: self.data_path.execute_alu_operation,
            Signal.CHECK_ZERO_FLAG: self.data_path.check_zero_flag,
            Signal.CHECK_NOT_ZERO_FLAG: self.data_path.check_not_zero_flag,
            Signal.LATCH_PROGRAM_COUNTER: self.signal_latch_pc,
            Signal.HALT: self.halt
        }

        self.mpc_of_opcode = lambda opcode: {
            Opcode.MOV.value: 1,
            Opcode.ST.value: 2,
            Opcode.LD.value: 5,
            Opcode.ADD.value: 8,
            Opcode.SUB.value: 9,
            Opcode.MUL.value: 10,
            Opcode.DIV.value: 11,
            Opcode.INC.value: 12,
            Opcode.DEC.value: 13,
            Opcode.MOD.value: 14,
            Opcode.NEG.value: 15,
            Opcode.CMP.value: 16,
            Opcode.TEST.value: 17,
            Opcode.JMP.value: 18,
            Opcode.JZ.value: 19,
            Opcode.JNZ.value: 20,
            Opcode.JGE.value: 21,
            Opcode.HLT.value: 22
        }[opcode]

        self.mprogram = [
            [(Signal.LATCH_ADDRESS_REGISTER, Sel.AddressRegister.PROGRAM_COUNTER), (Signal.SIGNAL_READ,), (Signal.LATCH_PROGRAM,), (Signal.LATCH_MPC, Sel.MPC.MPC_ADDRESS)],
            # MOV
            [(Signal.LATCH_LEFT_REGISTER_TERM, None), (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER), (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.ZERO), (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.ADD), (Signal.LATCH_REGISTER, Sel.Register.ALU, None), (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE), (Signal.LATCH_MPC, Sel.MPC.ZERO)],
            # ST
            [(Signal.LATCH_LEFT_ALU, Sel.LeftAlu.CONTROL_UNIT), (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.ZERO), (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.ADD), (Signal.LATCH_ADDRESS_REGISTER, Sel.AddressRegister.ALU), (Signal.LATCH_MPC, Sel.MPC.PLUS_ONE)],
            [(Signal.LATCH_LEFT_REGISTER_TERM, None), (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.ZERO), (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.ADD), (Signal.LATCH_DATA_REGISTER, Sel.DataRegister.ALU), (Signal.LATCH_MPC, Sel.MPC.PLUS_ONE)],
            [(Signal.SIGNAL_WRITE,), (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE), (Signal.LATCH_MPC, Sel.MPC.ZERO)],
            # LD
            [(Signal.LATCH_LEFT_ALU, Sel.LeftAlu.CONTROL_UNIT), (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.ZERO), (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.ADD), (Signal.LATCH_ADDRESS_REGISTER, Sel.AddressRegister.ALU), (Signal.LATCH_MPC, Sel.MPC.PLUS_ONE)],
            [(Signal.SIGNAL_READ,), (Signal.LATCH_MPC, Sel.MPC.PLUS_ONE)],
            [(Signal.LATCH_REGISTER, Sel.Register.DATA_REGISTER, None), (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE), (Signal.LATCH_MPC, Sel.MPC.ZERO)],
            # ADD
            [(Signal.LATCH_LEFT_REGISTER_TERM, None), (Signal.LATCH_RIGHT_REGISTER_TERM, None), (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER), (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.REGISTER), (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.ADD), (Signal.LATCH_REGISTER, Sel.Register.ALU, None), (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE), (Signal.LATCH_MPC, Sel.MPC.ZERO)],
            # SUB
            [(Signal.LATCH_LEFT_REGISTER_TERM, None), (Signal.LATCH_RIGHT_REGISTER_TERM, None), (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER), (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.REGISTER), (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.SUB), (Signal.LATCH_REGISTER, Sel.Register.ALU, None), (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE), (Signal.LATCH_MPC, Sel.MPC.ZERO)],
            # MUL
            [(Signal.LATCH_LEFT_REGISTER_TERM, None), (Signal.LATCH_RIGHT_REGISTER_TERM, None), (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER), (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.REGISTER), (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.MUL), (Signal.LATCH_REGISTER, Sel.Register.ALU, None), (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE), (Signal.LATCH_MPC, Sel.MPC.ZERO)],
            # DIV
            [(Signal.LATCH_LEFT_REGISTER_TERM, None), (Signal.LATCH_RIGHT_REGISTER_TERM, None), (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER), (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.REGISTER), (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.DIV), (Signal.LATCH_REGISTER, Sel.Register.ALU, None), (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE), (Signal.LATCH_MPC, Sel.MPC.ZERO)],
            # INC
            [(Signal.LATCH_LEFT_REGISTER_TERM, None), (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER), (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.PLUS_ONE), (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.ADD), (Signal.LATCH_REGISTER, Sel.Register.ALU, None), (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE), (Signal.LATCH_MPC, Sel.MPC.ZERO)],
            # DEC
            [(Signal.LATCH_LEFT_REGISTER_TERM, None), (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER), (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.PLUS_ONE), (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.SUB), (Signal.LATCH_REGISTER, Sel.Register.ALU, None), (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE), (Signal.LATCH_MPC, Sel.MPC.ZERO)],
            # MOD
            [(Signal.LATCH_LEFT_REGISTER_TERM, None), (Signal.LATCH_RIGHT_REGISTER_TERM, None), (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER), (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.REGISTER), (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.MOD), (Signal.LATCH_REGISTER, Sel.Register.ALU, None), (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE), (Signal.LATCH_MPC, Sel.MPC.ZERO)],
            # NEG
            [(Signal.LATCH_LEFT_REGISTER_TERM, None), (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER), (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.ZERO), (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.NEG), (Signal.LATCH_REGISTER, Sel.Register.ALU, None), (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE), (Signal.LATCH_MPC, Sel.MPC.ZERO)],
            # CMP
            [(Signal.LATCH_LEFT_REGISTER_TERM, None), (Signal.LATCH_RIGHT_REGISTER_TERM, None), (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER), (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.REGISTER), (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.CMP), (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE), (Signal.LATCH_MPC, Sel.MPC.ZERO)],
            # TEST
            [(Signal.LATCH_LEFT_REGISTER_TERM, None), (Signal.LATCH_RIGHT_REGISTER_TERM, None), (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER), (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.REGISTER), (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.TEST), (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE), (Signal.LATCH_MPC, Sel.MPC.ZERO)],
            # JMP
            [(Signal.LATCH_PROGRAM_COUNTER, Sel.PC.MPROGRAM), (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE), (Signal.LATCH_MPC, Sel.MPC.ZERO)],
            # JZ
            [(Signal.LATCH_PROGRAM_COUNTER, Sel.PC.MPROGRAM, Signal.CHECK_ZERO_FLAG), (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE), (Signal.LATCH_MPC, Sel.MPC.ZERO)],
            # JNZ
            [(Signal.LATCH_PROGRAM_COUNTER, Sel.PC.MPROGRAM, Signal.CHECK_NOT_ZERO_FLAG), (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE), (Signal.LATCH_MPC, Sel.MPC.ZERO)],
            # JGE
            [(Signal.LATCH_PROGRAM_COUNTER, Sel.PC.MPROGRAM, Signal.CHECK_SIGN_FLAG), (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE), (Signal.LATCH_MPC, Sel.MPC.ZERO)],
            # HLT
            [(Signal.HALT,)]
        ]

        self.data_path.control_unit = self

    def tick(self):
        self.model_tick += 1

    def signal_latch_pc(self, sel):
        assert isinstance(sel, Sel.PC), "sel_pc is undefined"

        if sel == Sel.PC.ZERO:
            self.program_counter = 0
        elif sel == Sel.PC.MPROGRAM:
            self.program_counter = self.program.terms[0]
        elif sel == Sel.PC.PLUS_ONE:
            self.program_counter += 1
        elif sel == Sel.PC.ADDRESS_REGISTER:
            self.program_counter = self.data_path.address_register

    def halt(self):
        raise SystemExit()

    def signal_latch_mpc(self, sel):
        assert isinstance(sel, Sel.MPC), "sel_mpc is undefined"

        if sel == Sel.MPC.ZERO:
            self.mpc = 0
        elif sel == Sel.MPC.PLUS_ONE:
            self.mpc += 1
        elif sel == Sel.MPC.MPC_ADDRESS:
            self.mpc = self.mpc_of_opcode(self.program.opcode)

    def signal_latch_program(self):
        self.program = self.data_path.data_register

    def signal_dispatch_data_path(self, signal, *args):
        fun = self.signals.get(signal, None)
        assert fun is not None, "signal not found"
        return fun(*args)

    def decode_and_execute_micro_instruction(self):
        for signal in self.mprogram[self.mpc]:
            self.signal_dispatch_data_path(*signal)

    def show_control_unit_debug(self):
        return (f"TICK: {self.tick()}\t"
                f"PC: {self.program_counter}\t"
                f"AR: {self.data_path.address_register}\t"
                f"DR: {self.data_path.data_register}"
                f"R0: {self.data_path.registers[Register.R0]}\t"
                f"R1: {self.data_path.registers[Register.R1]}\t"
                f"R2: {self.data_path.registers[Register.R2]}\t"
                f"R3: {self.data_path.registers[Register.R3]}")

    def show_control_unit_microdebug(self):
        return (f"TICK: {self.tick()}\t"
                f"PC: {self.program_counter}\t"
                f"AR: {self.data_path.address_register}\t"
                f"DR: {self.data_path.data_register}"
                f"R0: {self.data_path.registers[Register.R0]}\t"
                f"R1: {self.data_path.registers[Register.R1]}\t"
                f"R2: {self.data_path.registers[Register.R2]}\t"
                f"R3: {self.data_path.registers[Register.R3]}\t"
                f"MPC: {self.mpc}\t"
                f"SIGNALS: {' | '.join([', '.join(i) for i in map(str, self.mprogram[self.mpc])])}")


def simulate(code, input_tokens, memory_size, limit, log_limit):
    data_path = DataPath(code, memory_size, input_tokens)
    control_unit = ControlUnit(data_path)
    try:
        while control_unit.model_tick < limit:
            if control_unit.model_tick < log_limit:
                if control_unit.mpc == 0:
                    logging.info(control_unit.show_control_unit_debug())
                logging.info(control_unit.show_control_unit_microdebug())
            control_unit.decode_and_execute_micro_instruction()
            control_unit.tick()
    except Exception as e:
        print(traceback.format_exc())
        return "".join(control_unit.data_path.output_buffer), control_unit.program_counter, control_unit.model_tick


def main(code_file, input_file):
    memory = read_code(code_file)
    with open(input_file, encoding="utf-8") as file:
        input_text = file.read()
        input_token = []
        for char in input_text:
            input_token.append(char)

    output, program_counter, ticks = simulate(memory, input_token, 100000, 100000, 100000)
    print()
    print("PROGRAM IS ENDING!")
    print(f"output: {output}")
    print(f"program_counter: {program_counter}")
    print(f"ticks: {ticks}")


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    assert len(sys.argv) == 3, "Wrong arguments: machine.py <code_file> <input_file>"
    _, code_file, input_file = sys.argv
    main(code_file, input_file)
