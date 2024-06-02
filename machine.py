from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging
import sys

from isa import Command, Opcode, read_code
from reg_file import Register


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
    CHECK_NOT_SIGN_FLAG = "check not sign flag"

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
        LEFT = "left"

    result = None
    left_term = None
    right_term = None

    data_path = None

    flags = {"Z": False, "N": False}

    def __init__(self):
        self.result = 0
        self.left_term = 0
        self.right_term = 0
        self.set_flags()

    def set_flags(self):
        self.flags["Z"] = self.result == 0
        self.flags["N"] = self.result < 0

    def signal_latch_left_alu(self, sel):
        assert isinstance(sel, Sel.LeftAlu), "sel_left_alu is undefined"

        if sel == Sel.LeftAlu.REGISTER:
            self.left_term = self.data_path.registers[Register.LEFT_REGISTER_TERM]
        elif sel == Sel.LeftAlu.CONTROL_UNIT:
            self.left_term = (
                self.data_path.control_unit.program.terms[0]
                if str(self.data_path.control_unit.program.terms[0]).upper() not in Register.__members__
                else int(self.data_path.control_unit.program.terms[1])
            )
        elif sel == Sel.LeftAlu.DATA_REGISTER:
            self.left_term = self.data_path.data_register

    def signal_latch_right_alu(self, sel):
        assert isinstance(sel, Sel.RightAlu), "sel_right_alu is undefined"

        if sel == Sel.RightAlu.REGISTER:
            self.right_term = self.data_path.registers[Register.RIGHT_REGISTER_TERM]
        elif sel == Sel.RightAlu.ZERO:
            self.right_term = 0
        elif sel == Sel.RightAlu.PLUS_ONE:
            self.right_term = 1
        elif sel == Sel.RightAlu.DATA_REGISTER:
            self.right_term = self.data_path.data_register

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
            case ALU.ALUOperations.LEFT:
                self.result = self.left_term

        self.set_flags()


@dataclass()
class DataPath:
    memory: list[object] = None
    memory_size: int = None

    data_register = None
    address_register = None

    alu: ALU = None

    registers = {
        Register.R0: 0,
        Register.R1: 0,
        Register.R2: 0,
        Register.R3: 0,
        Register.R4: 0,
        Register.LEFT_REGISTER_TERM: 0,
        Register.RIGHT_REGISTER_TERM: 0,
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
        self.registers[Register.R4] = 0
        self.registers[Register.LEFT_REGISTER_TERM] = 0
        self.registers[Register.RIGHT_REGISTER_TERM] = 0

        self.input_buffer = input_buffer
        self.output_buffer = list()

        self.input_address = 1
        self.output_address = 2

        for i in range(len(code)):
            self.memory[i] = code[i]

        self.alu.data_path = self

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

    def signal_latch_register(self, sel, register):
        register = Register(register) if isinstance(register, str) else register
        assert isinstance(sel, Sel.Register), "sel_reg is undefined"
        assert isinstance(register, Register), "reg is undefined"

        if sel == Sel.Register.DATA_REGISTER:
            self.registers[register] = self.data_register
        elif sel == Sel.Register.ALU:
            self.registers[register] = self.alu.result

    def signal_latch_left_register_term(self, register):
        register = Register(register) if isinstance(register, str) else register
        assert isinstance(register, Register), "register is undefined"

        self.registers[Register.LEFT_REGISTER_TERM] = self.registers[register]

    def signal_latch_right_register_term(self, register: Register):
        register = Register(register) if isinstance(register, str) else register
        assert isinstance(register, Register), "register is undefined"

        self.registers[Register.RIGHT_REGISTER_TERM] = self.registers[register]

    def signal_write(self):
        assert self.address_register != self.input_address, "cannot write to input address"

        if self.address_register == self.output_address:
            self.output_buffer.append(self.data_register)
            logging.info(
                f"output: {[chr(i) if i < 128 else str(i) for i in self.output_buffer]} << {chr(self.data_register) if self.data_register < 128 else str(self.data_register)}"
            )
        else:
            self.memory[self.address_register] = self.data_register

    def signal_read(self):
        assert self.address_register != self.output_address, "cannot read from output address"

        if self.address_register == self.input_address:
            if len(self.input_buffer) == 0:
                raise EOFError("input buffer is empty")
            symbol = self.input_buffer.pop(0)
            logging.info(f"input: {self.input_buffer} >> {symbol}")
            symbol_code = ord(symbol)
            assert -128 < symbol_code <= 127, f"input token is out of bound: {self.data_register}"

            self.data_register = symbol_code
        else:
            self.data_register = self.memory[self.address_register]

    def execute_alu_operation(self, operation: ALU.ALUOperations):
        self.alu.compute(operation)

    def check_zero_flag(self):
        return self.alu.flags["Z"]

    def check_not_zero_flag(self):
        return not self.alu.flags["Z"]

    def check_sign_flag(self):
        return self.alu.flags["N"]

    def check_not_sign_flag(self):
        return not self.alu.flags["N"]


class HltErrorException(Exception):
    pass


class ControlUnit:
    program_counter: int = None
    program: Command = None
    mpc: int = None
    mpc_of_opcode: callable[[Opcode], int] = None
    mprogram: list = None
    data_path: DataPath = None
    model_tick: int = None
    signals: dict[Signal, callable] = None

    def __init__(self, data_path):
        self.program_counter = 0
        self.mpc = 0
        self.data_path = data_path
        self.model_tick = 0

        self.signals = {
            Signal.LATCH_LEFT_ALU: self.data_path.alu.signal_latch_left_alu,
            Signal.LATCH_RIGHT_ALU: self.data_path.alu.signal_latch_right_alu,
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
            Signal.CHECK_SIGN_FLAG: self.data_path.check_sign_flag,
            Signal.CHECK_NOT_SIGN_FLAG: self.data_path.check_not_sign_flag,
            Signal.LATCH_PROGRAM_COUNTER: self.signal_latch_pc,
            Signal.HALT: self.halt,
        }

        self.mpc_of_opcode = lambda opcode: {
            Opcode.MOV.value: 1,
            Opcode.MVA.value: 2,
            Opcode.ST.value: 3,
            Opcode.STA.value: 6,
            Opcode.LD.value: 9,
            Opcode.LDA.value: 12,
            Opcode.ADD.value: 15,
            Opcode.SUB.value: 16,
            Opcode.MUL.value: 17,
            Opcode.DIV.value: 18,
            Opcode.INC.value: 19,
            Opcode.DEC.value: 20,
            Opcode.MOD.value: 21,
            Opcode.NEG.value: 22,
            Opcode.CMP.value: 23,
            Opcode.TEST.value: 24,
            Opcode.JMP.value: 25,
            Opcode.JZ.value: 26,
            Opcode.JNZ.value: 27,
            Opcode.JGE.value: 28,
            Opcode.HLT.value: 29,
        }[opcode]

        self.mprogram = [
            # Instruction Fetch
            [
                (Signal.LATCH_ADDRESS_REGISTER, Sel.AddressRegister.PROGRAM_COUNTER),
                (Signal.SIGNAL_READ,),
                (Signal.LATCH_PROGRAM,),
                (Signal.LATCH_MPC, Sel.MPC.MPC_ADDRESS),
            ],
            # MOV
            [
                (Signal.LATCH_LEFT_REGISTER_TERM, None),
                (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER),
                (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.ZERO),
                (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.ADD),
                (Signal.LATCH_REGISTER, Sel.Register.ALU, None),
                (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE),
                (Signal.LATCH_MPC, Sel.MPC.ZERO),
            ],
            # MVA
            [
                (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.CONTROL_UNIT),
                (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.LEFT),
                (Signal.LATCH_REGISTER, Sel.Register.ALU, None),
                (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE),
                (Signal.LATCH_MPC, Sel.MPC.ZERO),
            ],
            # ST
            [
                (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.CONTROL_UNIT),
                (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.ZERO),
                (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.ADD),
                (Signal.LATCH_ADDRESS_REGISTER, Sel.AddressRegister.ALU),
                (Signal.LATCH_MPC, Sel.MPC.PLUS_ONE),
            ],
            [
                (Signal.LATCH_LEFT_REGISTER_TERM, None),
                (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER),
                (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.ZERO),
                (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.LEFT),
                (Signal.LATCH_DATA_REGISTER, Sel.DataRegister.ALU),
                (Signal.LATCH_MPC, Sel.MPC.PLUS_ONE),
            ],
            [(Signal.SIGNAL_WRITE,), (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE), (Signal.LATCH_MPC, Sel.MPC.ZERO)],
            # STA
            [
                (Signal.LATCH_LEFT_REGISTER_TERM, None),
                (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER),
                (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.LEFT),
                (Signal.LATCH_ADDRESS_REGISTER, Sel.AddressRegister.ALU),
                (Signal.LATCH_MPC, Sel.MPC.PLUS_ONE),
            ],
            [
                (Signal.LATCH_LEFT_REGISTER_TERM, None),
                (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER),
                (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.ZERO),
                (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.ADD),
                (Signal.LATCH_DATA_REGISTER, Sel.DataRegister.ALU),
                (Signal.LATCH_MPC, Sel.MPC.PLUS_ONE),
            ],
            [(Signal.SIGNAL_WRITE,), (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE), (Signal.LATCH_MPC, Sel.MPC.ZERO)],
            # LD
            [
                (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.CONTROL_UNIT),
                (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.ZERO),
                (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.ADD),
                (Signal.LATCH_ADDRESS_REGISTER, Sel.AddressRegister.ALU),
                (Signal.LATCH_MPC, Sel.MPC.PLUS_ONE),
            ],
            [(Signal.SIGNAL_READ,), (Signal.LATCH_MPC, Sel.MPC.PLUS_ONE)],
            [
                (Signal.LATCH_REGISTER, Sel.Register.DATA_REGISTER, None),
                (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE),
                (Signal.LATCH_MPC, Sel.MPC.ZERO),
            ],
            # LDA
            [
                (Signal.LATCH_LEFT_REGISTER_TERM, None),
                (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER),
                (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.ZERO),
                (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.LEFT),
                (Signal.LATCH_ADDRESS_REGISTER, Sel.AddressRegister.ALU),
                (Signal.LATCH_MPC, Sel.MPC.PLUS_ONE),
            ],
            [(Signal.SIGNAL_READ,), (Signal.LATCH_MPC, Sel.MPC.PLUS_ONE)],
            [
                (Signal.LATCH_REGISTER, Sel.Register.DATA_REGISTER, None),
                (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE),
                (Signal.LATCH_MPC, Sel.MPC.ZERO),
            ],
            # ADD
            [
                (Signal.LATCH_LEFT_REGISTER_TERM, None),
                (Signal.LATCH_RIGHT_REGISTER_TERM, None),
                (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER),
                (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.REGISTER),
                (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.ADD),
                (Signal.LATCH_REGISTER, Sel.Register.ALU, None),
                (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE),
                (Signal.LATCH_MPC, Sel.MPC.ZERO),
            ],
            # SUB
            [
                (Signal.LATCH_LEFT_REGISTER_TERM, None),
                (Signal.LATCH_RIGHT_REGISTER_TERM, None),
                (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER),
                (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.REGISTER),
                (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.SUB),
                (Signal.LATCH_REGISTER, Sel.Register.ALU, None),
                (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE),
                (Signal.LATCH_MPC, Sel.MPC.ZERO),
            ],
            # MUL
            [
                (Signal.LATCH_LEFT_REGISTER_TERM, None),
                (Signal.LATCH_RIGHT_REGISTER_TERM, None),
                (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER),
                (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.REGISTER),
                (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.MUL),
                (Signal.LATCH_REGISTER, Sel.Register.ALU, None),
                (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE),
                (Signal.LATCH_MPC, Sel.MPC.ZERO),
            ],
            # DIV
            [
                (Signal.LATCH_LEFT_REGISTER_TERM, None),
                (Signal.LATCH_RIGHT_REGISTER_TERM, None),
                (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER),
                (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.REGISTER),
                (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.DIV),
                (Signal.LATCH_REGISTER, Sel.Register.ALU, None),
                (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE),
                (Signal.LATCH_MPC, Sel.MPC.ZERO),
            ],
            # INC
            [
                (Signal.LATCH_LEFT_REGISTER_TERM, None),
                (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER),
                (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.PLUS_ONE),
                (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.ADD),
                (Signal.LATCH_REGISTER, Sel.Register.ALU, None),
                (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE),
                (Signal.LATCH_MPC, Sel.MPC.ZERO),
            ],
            # DEC
            [
                (Signal.LATCH_LEFT_REGISTER_TERM, None),
                (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER),
                (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.PLUS_ONE),
                (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.SUB),
                (Signal.LATCH_REGISTER, Sel.Register.ALU, None),
                (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE),
                (Signal.LATCH_MPC, Sel.MPC.ZERO),
            ],
            # MOD
            [
                (Signal.LATCH_LEFT_REGISTER_TERM, None),
                (Signal.LATCH_RIGHT_REGISTER_TERM, None),
                (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER),
                (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.REGISTER),
                (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.MOD),
                (Signal.LATCH_REGISTER, Sel.Register.ALU, None),
                (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE),
                (Signal.LATCH_MPC, Sel.MPC.ZERO),
            ],
            # NEG
            [
                (Signal.LATCH_LEFT_REGISTER_TERM, None),
                (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER),
                (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.ZERO),
                (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.NEG),
                (Signal.LATCH_REGISTER, Sel.Register.ALU, None),
                (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE),
                (Signal.LATCH_MPC, Sel.MPC.ZERO),
            ],
            # CMP
            [
                (Signal.LATCH_LEFT_REGISTER_TERM, None),
                (Signal.LATCH_RIGHT_REGISTER_TERM, None),
                (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER),
                (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.REGISTER),
                (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.CMP),
                (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE),
                (Signal.LATCH_MPC, Sel.MPC.ZERO),
            ],
            # TEST
            [
                (Signal.LATCH_LEFT_REGISTER_TERM, None),
                (Signal.LATCH_RIGHT_REGISTER_TERM, None),
                (Signal.LATCH_LEFT_ALU, Sel.LeftAlu.REGISTER),
                (Signal.LATCH_RIGHT_ALU, Sel.RightAlu.REGISTER),
                (Signal.EXECUTE_ALU_OPERATION, ALU.ALUOperations.TEST),
                (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.PLUS_ONE),
                (Signal.LATCH_MPC, Sel.MPC.ZERO),
            ],
            # JMP
            [(Signal.LATCH_PROGRAM_COUNTER, Sel.PC.MPROGRAM), (Signal.LATCH_MPC, Sel.MPC.ZERO)],
            # JZ
            [(Signal.LATCH_PROGRAM_COUNTER, Sel.PC.MPROGRAM, Signal.CHECK_ZERO_FLAG), (Signal.LATCH_MPC, Sel.MPC.ZERO)],
            # JNZ
            [
                (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.MPROGRAM, Signal.CHECK_NOT_ZERO_FLAG),
                (Signal.LATCH_MPC, Sel.MPC.ZERO),
            ],
            # JGE
            [
                (Signal.LATCH_PROGRAM_COUNTER, Sel.PC.MPROGRAM, Signal.CHECK_NOT_SIGN_FLAG),
                (Signal.LATCH_MPC, Sel.MPC.ZERO),
            ],
            # HLT
            [(Signal.HALT,)],
        ]

        self.data_path.control_unit = self

    def tick(self):
        self.model_tick += 1

    def signal_latch_pc(self, sel, check_signal=True):
        assert isinstance(sel, Sel.PC), "sel_pc is undefined"

        if sel == Sel.PC.ZERO:
            self.program_counter = 0
        elif sel == Sel.PC.MPROGRAM:
            self.program_counter = self.program.terms[0] if check_signal else self.program_counter + 1
        elif sel == Sel.PC.PLUS_ONE:
            self.program_counter += 1
        elif sel == Sel.PC.ADDRESS_REGISTER:
            self.program_counter = self.data_path.address_register

    def halt(self):
        raise HltErrorException("halt")

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
        if self.program is None or len(self.program.terms) == 0:
            terms = [None, None]
        elif len(self.program.terms) == 1:
            terms = [self.program.terms[0], self.program.terms[0]]
        else:
            terms = self.program.terms
        first_term = terms[0]
        second_term = terms[1]
        first_used = False

        if self.program is not None and self.program.opcode in {Opcode.ST, Opcode.MOV, Opcode.LDA}:
            first_term, second_term = second_term, first_term

        if (
            self.program is not None
            and self.program.opcode == Opcode.LDA
            and self.mprogram[self.mpc][0][0] == Signal.LATCH_REGISTER
        ):
            first_term, second_term = second_term, first_term

        if (
            self.program is not None
            and self.program.opcode == Opcode.STA
            and self.mpc == self.mpc_of_opcode(self.program.opcode) + 1
        ):
            first_term, second_term = second_term, first_term

        for signal in self.mprogram[self.mpc]:
            if None in signal:
                if not first_used:
                    reg_name = first_term
                    first_used = True
                else:
                    reg_name = second_term
                    second_term = first_term
                signal = (signal[0], signal[1], reg_name) if len(signal) == 3 else (signal[0], reg_name)
            if len(signal) == 3 and isinstance(signal[-1], Signal):
                signal = (signal[0], signal[1], self.signals[signal[2]]())
            self.signal_dispatch_data_path(*signal)

    def show_control_unit_debug(self):
        return (
            f"TICK: {self.model_tick}\t"
            f"PC: {self.program_counter}\t"
            f"AR: {self.data_path.address_register}\t"
            f"DR: {self.data_path.data_register}\t"
            f"R0: {self.data_path.registers[Register.R0]}\t"
            f"R1: {self.data_path.registers[Register.R1]}\t"
            f"R2: {self.data_path.registers[Register.R2]}\t"
            f"R3: {self.data_path.registers[Register.R3]}\t"
            f"R4: {self.data_path.registers[Register.R4]}"
        )

    def show_control_unit_microdebug(self):
        return (
            f"TICK: {self.model_tick}\t"
            f"PC: {self.program_counter}\t"
            f"AR: {self.data_path.address_register}\t"
            f"DR: {self.data_path.data_register}\t"
            f"R0: {self.data_path.registers[Register.R0]}\t"
            f"R1: {self.data_path.registers[Register.R1]}\t"
            f"R2: {self.data_path.registers[Register.R2]}\t"
            f"R3: {self.data_path.registers[Register.R3]}\t"
            f"R4: {self.data_path.registers[Register.R4]}\t"
            f"LEFT_REG: {self.data_path.registers[Register.LEFT_REGISTER_TERM]}\t"
            f"RIGHT_REG: {self.data_path.registers[Register.RIGHT_REGISTER_TERM]}\t"
            f"ALU: {self.data_path.alu.result}\t"
            f"MPC: {self.mpc}\t"
            f"PROGRAM: {self.program}\t"
            f"SIGNALS: {' | '.join([', '.join(str(i) if i is not None else '' for i in signal) for signal in self.mprogram[self.mpc]])}"
        )


def simulate(code, input_tokens, memory_size, limit, log_limit):
    data_path = DataPath(code, memory_size, input_tokens)
    control_unit = ControlUnit(data_path)
    try:
        while control_unit.model_tick < limit:
            if control_unit.model_tick < log_limit:
                logging.debug(control_unit.show_control_unit_microdebug())
            control_unit.decode_and_execute_micro_instruction()
            control_unit.tick()
    except Exception as e:
        logging.warning(e) if str(e) != "halt" else ...
        return (
            "".join([chr(i) if i < 128 else str(i) for i in data_path.output_buffer]),
            control_unit.program_counter,
            control_unit.model_tick,
        )


def main(code_file, input_file):
    memory = read_code(code_file)
    with open(input_file, encoding="utf-8") as file:
        input_text = file.read()
        input_token = []
        for char in input_text:
            input_token.append(char)

    output, program_counter, ticks = simulate(memory, input_token, 100000, 10000, 100000)
    print(f"output: {output}")
    print(f"program_counter: {program_counter}")
    print(f"ticks: {ticks}")


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    assert len(sys.argv) == 3, "Wrong arguments: machine.py <code_file> <input_file>"
    _, code_file, input_file = sys.argv
    main(code_file, input_file)
