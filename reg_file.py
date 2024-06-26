from enum import Enum


class Register(str, Enum):
    R0 = "r0"
    R1 = "r1"
    R2 = "r2"
    R3 = "r3"
    R4 = "r4"
    R5 = "r5"
    R6 = "r6"
    R7 = "r7"

    LEFT_REGISTER_TERM = "left register term"
    RIGHT_REGISTER_TERM = "right register term"

    def __str__(self):
        return str(self.value)
