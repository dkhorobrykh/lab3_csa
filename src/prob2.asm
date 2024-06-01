.data:
    output: 2
    amount: 2
    second: 1
    first: 2
    divider: 2
    limit: 4000000
    zero: 0

.code:
    mov r0 first; first element
    mov r1 second; second element
    mov r2 amount; amount

    loop:
        add r0 r1; r0 = r0 + r1
        mov r3 r0; r3 = r0

        mov r4 divider
        mod r3 r4; r3 = r3 % 2
        mov r4 zero
        cmp r3 r4
        jnz continue
        add r2 r0; r2 = r2 + r0

        continue:
            mov r3 r1
            mov r1 r0; r1 = r0
            sub r1 r3; r0 = r1 - r0

            mov r4 limit
            cmp r0 r4
            jge end
            jmp loop

    end:
        st output r2
        hlt
