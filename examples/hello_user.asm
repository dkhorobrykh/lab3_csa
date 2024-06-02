.data:
    message_name: "What is your name? (at the end enter 0)"
    length_msg_name: 39
    name: buf 30
    message_hello_fp: " Hello, "
    length_msg_hello_fp: 8
    message_hello_sp: "!"
    length_msg_hello_sp: 1
    check_char: 48
    input: 1
    output: 2
    zero: 0

.code:
    mva r0 message_name
    mov r1 zero
    loop:
        inc r0
        inc r1
        lda r2 r0
        st output r2
        mov r2 length_msg_name
        cmp r1 r2
        jz end_first_msg
        jmp loop

    end_first_msg:
        mva r0 name
        mov r4 zero
        loop_read_name:
            ld r2 input
            mov r3 check_char
            cmp r2 r3
            jz print_msg_2
            inc r4
            sta r0 r2
            inc r0
            jmp loop_read_name

    print_msg_2:
        mva r0 message_hello_fp
        mov r1 zero
        loop_msg_2:
            inc r0
            inc r1
            lda r2 r0
            st output r2
            mov r2 length_msg_hello_fp
            cmp r1 r2
            jz print_msg_name
            jmp loop_msg_2

    print_msg_name:
        mva r0 name
        mov r1 zero
        loop_name:
            lda r2 r0
            st output r2
            inc r0
            inc r1
            cmp r1 r4
            jz print_msg_hello_2
            jmp loop_name

    print_msg_hello_2:
        mva r0 message_hello_sp
        mov r1 zero
        loop_end:
            inc r0
            inc r1
            lda r2 r0
            st output r2
            mov r2 length_msg_hello_sp
            cmp r1 r2
            jz end
            jmp loop_end

    end:
        hlt