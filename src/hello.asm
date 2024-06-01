message:
    word 13
    word "hello, world!"

pointer:
    word message
inc pointer

curr_length:
    word 0

input:
    word 1
output:
    word 2

loop:
    inc curr_length
    mov r0 curr_length
    sub r0 message
    test r0 r0
    jz end
    st output pointer
    inc pointer
    jmp loop

end:
    hlt
