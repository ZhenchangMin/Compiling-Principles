%{
#include <stdio.h>
#include <stdlib.h>
#include "syntax.tab.h"

int lexical_error = 0;
int last_lexical_error_line = -1;
int lexical_eof_error = 0;
/* Track the two most recently emitted grammar tokens.  yylineno alone points
   at the lookahead token, which is often one line too late for a missing
   delimiter/semicolon diagnosed only after the next token is read. */
int previous_token_line = -1;
int current_token_line = -1;
int previous_token_code = 0;
int current_token_code = 0;
static int comment_start_line = -1;

static int emit_token(int token, const char *name, const char *text)
{
    previous_token_line = current_token_line;
    previous_token_code = current_token_code;
    current_token_line = yylineno;
    current_token_code = token;
    yylval.node = make_token_node(name, text, yylineno);
    return token;
}
%}

%option yylineno noyywrap noinput nounput
%x COMMENT

DEC         (0|[1-9][0-9]*)
OCT         0[0-7]+
HEX         0[xX][0-9a-fA-F]+
BAD_OCT     0[0-9]+
BAD_HEX     0[xX][0-9A-Za-z_]*

UNSUPPORTED_SCI (([0-9]+\.[0-9]*)|(\.[0-9]+))[eE][+-]?[0-9]+
FLOAT_BASE  [0-9]+\.[0-9]+

ID          [_a-zA-Z][_a-zA-Z0-9]*

SEMI        ";"
COMMA       ","
ASSIGNOP    "="
RELOP       (">="|"<="|"=="|"!="|">"|"<")
PLUS        "+"
MINUS       "-"
STAR        "*"
DIV         "/"
AND         "&&"
OR          "||"
DOT         "."
NOT         "!"
TYPE        ("int"|"float")
LP          "("
RP          ")"
LB          "["
RB          "]"
LC          "{"
RC          "}"
STRUCT      "struct"
RETURN      "return"
IF          "if"
ELSE        "else"
WHILE       "while"

%%

"//"[^\n]*             { /* ignore line comment */ }
"/*"                   {
                            comment_start_line = yylineno;
                            BEGIN(COMMENT);
                        }
<COMMENT>"*/"          { BEGIN(INITIAL); }
<COMMENT>\n            { /* yylineno maintained by flex */ }
<COMMENT>.              { /* ignore block-comment contents */ }
<COMMENT><<EOF>>        {
                            lexical_error = 1;
                            lexical_eof_error = 1;
                            last_lexical_error_line = comment_start_line;
                            printf("Error type A at Line %d: Unterminated block comment.\n",
                                   comment_start_line);
                            BEGIN(INITIAL);
                            return 0;
                        }
{TYPE}                  { return emit_token(TYPE, "TYPE", yytext); }
{STRUCT}                { return emit_token(STRUCT, "STRUCT", NULL); }
{RETURN}                { return emit_token(RETURN, "RETURN", NULL); }
{IF}                    { return emit_token(IF, "IF", NULL); }
{ELSE}                  { return emit_token(ELSE, "ELSE", NULL); }
{WHILE}                 { return emit_token(WHILE, "WHILE", NULL); }

{UNSUPPORTED_SCI}       {
                            lexical_error = 1;
                            last_lexical_error_line = yylineno;
                            printf(
                                    "Error type A at Line %d: Unsupported scientific notation \"%s\".\n",
                                    yylineno, yytext);
                            return emit_token(FLOAT, "FLOAT", "0.000000");
                        }
{FLOAT_BASE}            {
                            char value[128];
                            snprintf(value, sizeof(value), "%f", strtod(yytext, NULL));
                            return emit_token(FLOAT, "FLOAT", value);
                        }

{HEX}                   {
                            lexical_error = 1;
                            last_lexical_error_line = yylineno;
                            printf(
                                    "Error type A at Line %d: Unsupported hexadecimal integer '%s'.\n",
                                    yylineno, yytext);
                            return emit_token(INT, "INT", "0");
                        }
{BAD_HEX}               {
                            lexical_error = 1;
                            last_lexical_error_line = yylineno;
                            printf(
                                    "Error type A at Line %d: Illegal hexadecimal number '%s'.\n",
                                    yylineno, yytext);
                            return emit_token(INT, "INT", "0");
                        }
{OCT}                   {
                            lexical_error = 1;
                            last_lexical_error_line = yylineno;
                            printf(
                                    "Error type A at Line %d: Unsupported octal integer '%s'.\n",
                                    yylineno, yytext);
                            return emit_token(INT, "INT", "0");
                        }
{BAD_OCT}               {
                            lexical_error = 1;
                            last_lexical_error_line = yylineno;
                            printf(
                                    "Error type A at Line %d: Illegal octal number '%s'.\n",
                                    yylineno, yytext);
                            return emit_token(INT, "INT", "0");
                        }
{DEC}                   {
                            char value[128];
                            snprintf(value, sizeof(value), "%ld", strtol(yytext, NULL, 10));
                            return emit_token(INT, "INT", value);
                        }

{ID}                    { return emit_token(ID, "ID", yytext); }

{SEMI}                  { return emit_token(SEMI, "SEMI", NULL); }
{COMMA}                 { return emit_token(COMMA, "COMMA", NULL); }
{ASSIGNOP}              { return emit_token(ASSIGNOP, "ASSIGNOP", NULL); }
{RELOP}                 { return emit_token(RELOP, "RELOP", yytext); }
{PLUS}                  { return emit_token(PLUS, "PLUS", NULL); }
{MINUS}                 { return emit_token(MINUS, "MINUS", NULL); }
{STAR}                  { return emit_token(STAR, "STAR", NULL); }
{DIV}                   { return emit_token(DIV, "DIV", NULL); }
{AND}                   { return emit_token(AND, "AND", NULL); }
{OR}                    { return emit_token(OR, "OR", NULL); }
{DOT}                   { return emit_token(DOT, "DOT", NULL); }
{NOT}                   { return emit_token(NOT, "NOT", NULL); }
{LP}                    { return emit_token(LP, "LP", NULL); }
{RP}                    { return emit_token(RP, "RP", NULL); }
{LB}                    { return emit_token(LB, "LB", NULL); }
{RB}                    { return emit_token(RB, "RB", NULL); }
{LC}                    { return emit_token(LC, "LC", NULL); }
{RC}                    { return emit_token(RC, "RC", NULL); }

[ \t\r]+               { /* ignore horizontal whitespace */ }
\n                      { /* ignore newline */ }

.                       {
                            lexical_error = 1;
                            last_lexical_error_line = yylineno;
                            printf(
                                    "Error type A at Line %d: Mysterious character \"%s\".\n",
                                    yylineno, yytext);
                        }

%%
