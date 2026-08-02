CC ?= cc
CFLAGS ?= -O3 -std=c11 -D_POSIX_C_SOURCE=200809L -Wall -Wextra -Wpedantic -Werror
LDFLAGS ?=

all: pdrs-c

pdrs-c: pdrs_native.c
	$(CC) $(CFLAGS) $< -o $@ $(LDFLAGS)

sanitize: pdrs_native.c
	$(CC) -O1 -g -std=c11 -D_POSIX_C_SOURCE=200809L -Wall -Wextra -Wpedantic -Werror -fsanitize=address,undefined $< -o pdrs-c-sanitize

clean:
	rm -f pdrs-c pdrs-c-sanitize

.PHONY: all sanitize clean
