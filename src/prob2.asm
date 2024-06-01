.data:
    output: 2
    amount: 0
    second: 1
    first: 2
    divider: 2
    limit: 4000000

.code:
    mov r0 first; first element
    mov r1 second; second element
    mov r2 amount; amount

    loop:
        add r0 r1; r0 = r0 + r1
        mov r3 r0; r3 = r0

        mod r3 divider; r3 = r3 % 2
        test r3 r3
        jnz continue
        add r2 r0; r2 = r2 + r0

        continue:
            mov r1 r0; r1 = r0
            sub r0 r1; r0 = r1 - r0
            neg r0; r0 = -r0

            cmp r0 limit
            jge end
            jmp loop

    end:
        st output r2
        hlt
