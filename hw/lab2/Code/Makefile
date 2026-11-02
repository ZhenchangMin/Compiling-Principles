CC = gcc
FLEX = flex
BISON = bison
CFLAGS = -std=c99 -D_POSIX_C_SOURCE=200809L -Wall -Wextra

.PHONY: all clean test
all: parser

syntax.tab.c: syntax.y tree.h
	$(BISON) -d -v -o syntax.tab.c syntax.y

syntax.tab.h: syntax.tab.c

lex.yy.c: lexical.l syntax.tab.h
	$(FLEX) -o lex.yy.c lexical.l

syntax.tab.o: syntax.tab.c lex.yy.c semantic.h tree.h
	$(CC) $(CFLAGS) -c syntax.tab.c -o syntax.tab.o

semantic.o: semantic.c semantic.h tree.h
	$(CC) $(CFLAGS) -c semantic.c -o semantic.o

parser: syntax.tab.o semantic.o
	$(CC) $(CFLAGS) -o parser syntax.tab.o semantic.o -lfl

test: parser
	python3 ../tests/run_tests.py ./parser

clean:
	rm -f parser lex.yy.c syntax.tab.c syntax.tab.h syntax.tab.o semantic.o syntax.output
