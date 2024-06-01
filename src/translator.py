import sys
from typing import List, Dict, Tuple

from src.isa import Command, Opcode, write_code
from src.reg_file import Register


def get_meaningful_token(line: str) -> str:
    return line.split(";")[0].strip()


def process_data_section(program: str):
    needed_part = program.split(".code:")[0].strip(".data:").strip()
    memory = [None, None, None]
    labels = dict()

    for line in needed_part.splitlines():
        if line == '':
            continue

        token = get_meaningful_token(line)
        key, value = token.split(": ")
        labels[key] = len(memory)
        if '"' in value:
            str_to_append = value.strip('"')
            memory.append(len(str_to_append))

            for char in str_to_append:
                memory.append(char)
        elif 'buf ' in value:
            size = int(value.split("buf")[1])
            for i in range(size):
                memory.append(0)
        else:
            memory.append(int(value))

    return memory, labels


def first_stage(program: str):
    needed_part = program.split(".code:")[1].strip()
    code = list()
    labels = dict()

    for line in needed_part.splitlines():
        token = get_meaningful_token(line)
        if token == '':
            continue

        args = token.split(" ", 1)
        ind = len(code) + 1

        if ":" in token:
            label = token.strip(":")
            assert label not in labels, f"Переопределение метки {label}"
            labels[label] = ind
        else:
            opcode = args[0]
            terms = args[1].split(" ", 1) if len(args) > 1 else list()
            code.append(Command(ind, Opcode(opcode), terms))

    return code, labels


def place_labels_in_memory(memory: list, labels: dict[str, int]):
    constant = len(memory) + len(labels) - 1
    for key, value in labels.items():
        memory.append(value + constant)
        labels[key] = len(memory) - 1
    return memory, labels


def second_stage(code: List[Command], labels: Dict, memory) -> List:
    memory[0] = Command(0, Opcode.JMP, [len(memory)])
    for command in code:
        new_terms = list()
        for term in command.terms:
            if term in labels:
                new_terms.append(labels[term])
            elif term.upper() in Register.__members__:
                new_terms.append(Register(term))
            else:
                raise KeyError(f"Метка {term} не найдена в коде")
        command.terms = new_terms

        print(command)

        if command.opcode in {Opcode.JZ, Opcode.JMP, Opcode.JNZ, Opcode.JGE}:
            command.terms[0] = memory[command.terms[0]]

        if command.opcode == Opcode.LD:
            command.terms[1] = memory[command.terms[1]]

        if command.opcode == Opcode.ST:
            command.terms[0] = memory[command.terms[0]]

        if command.opcode == Opcode.MOV and str(new_terms[-1]).upper() not in Register.__members__:
            command.opcode = Opcode.LD

        memory.append(command)

    return memory


def translate(program: str) -> List[Command]:
    memory, labels = process_data_section(program)
    code, inner_labels = first_stage(program)
    memory, inner_labels = place_labels_in_memory(memory, inner_labels)
    labels = labels | inner_labels
    print(memory, labels)
    memory = second_stage(code, labels, memory)

    return memory


def main(source_filename: str, target_filename: str) -> None:
    with open(source_filename, 'r', encoding="utf8") as in_file:
        source = in_file.read()

    memory = translate(source)

    write_code(target_filename, memory)


if __name__ == '__main__':
    assert len(sys.argv) == 3, "usage translator.py <input_filename> <output_filename>"
    _, input_file, output_filename = sys.argv
    main(input_file, output_filename)
