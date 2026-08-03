# Evidence layers

The revision preserves the original committed measurements as evidence v1. The new synthetic and allocation experiments form evidence v2. The external-program workflow writes to `results/real_program_v2` and never overwrites v1. This separation prevents later reruns from silently changing the historical basis of earlier claims.
