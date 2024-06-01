.data:
    input: 1
    output: 2

.code:
    loop:
        ld r0 input
        st output r0
        jnz loop
