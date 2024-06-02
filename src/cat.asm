.data:
    input: 1
    output: 2
    stop_char: 48

.code:
    loop:
        ld r0 input
        st output r0
        mov r1 stop_char
        cmp r0 r1
        jnz loop

    hlt
