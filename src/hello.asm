.data:
    message: "hello, world!"
    length: 13
    input: 1
    output: 2
    zero: 0

.code:
    loop:
        mov r0 message
        mov r1 zero
        inc r0 ; пропускаем длину строки
        inc r1
        st output r0
        mov r2 zero
        cmp r1 r2
        jz end
        jmp loop
    end:
        hlt
