.data:
    message: "hello, world!"
    length: 13
    input: 1
    output: 2
    zero: 0

.code:
    mva r0 message
    mov r1 zero
    loop:
        inc r0
        inc r1
        lda r2 r0
        st output r2
        mov r2 length
        cmp r1 r2
        jz end
        jmp loop
    end:
        hlt
