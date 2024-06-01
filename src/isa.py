import json
from dataclasses import dataclass
from enum import Enum
from typing import List

from src.reg_file import Register


class Opcode(str, Enum):
    MOV = "mov"
    ST = "st"
    LD = "ld"
    WORD = "word"

    ADD = "add"
    SUB = "sub"
    MUL = "mul"
    DIV = "div"
    INC = "inc"
    DEC = "dec"
    MOD = "mod"
    NEG = "neg"
    CMP = "cmp"

    TEST = "test"
    JMP = "jmp"
    JZ = "jz"
    JNZ = "jnz"
    JGE = "jge"

    HLT = "hlt"

    def __str__(self):
        return str(self.value)


@dataclass()
class Command:
    index: int
    opcode: Opcode
    terms: List

    def toDict(self):
        return {
            "index": self.index,
            "opcode": str(self.opcode),
            "terms": self.terms
        }


def write_code(filename: str, code: List[Command]) -> None:
    with open(filename, "w", encoding="utf8") as file:
        res = list()
        for command in code:
            res.append(command.toDict() if isinstance(command, Command) else command)
        file.write(json.dumps(res, indent=4))


def read_code(filename: str) -> List[Command]:
    with open(filename, "r", encoding="utf8") as file:
        in_json = json.loads(file.read())
        result = list()
        for command in in_json:
            if isinstance(command, dict):
                result.append(Command(command['index'], Opcode(command['opcode']), command['terms']))
            else:
                result.append(command)
        return result
