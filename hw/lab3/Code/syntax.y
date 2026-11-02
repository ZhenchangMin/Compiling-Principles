%code requires {
#include "tree.h"
}

%code provides {
Node *make_token_node(const char *name, const char *text, int line);
}

%{
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>

int yylex(void);
void yyerror(const char *msg);
extern int yylineno;
extern FILE *yyin;
extern int lexical_error;
extern int last_lexical_error_line;
extern int lexical_eof_error;
extern int previous_token_line;
extern int current_token_line;
extern int previous_token_code;
extern int current_token_code;

static int syntax_error = 0;
static int last_syntax_error_line = -1;
static struct Node *root = NULL;
static struct Node *allocated_nodes = NULL;
%}

%code {
static Node *make_node(const char *name, int child_count, ...);

}

%define parse.error verbose

%union {
    Node *node;
}

%token <node> INT FLOAT ID
%token <node> SEMI COMMA
%token <node> ASSIGNOP RELOP
%token <node> PLUS MINUS STAR DIV
%token <node> AND OR DOT NOT
%token <node> TYPE
%token <node> LP RP LB RB LC RC
%token <node> STRUCT RETURN IF ELSE WHILE

%type <node> Program ExtDefList ExtDef Specifier StructSpecifier OptTag Tag
%type <node> ExtDecList VarDec FunDec VarList ParamDec CompSt StmtList Stmt
%type <node> DefList Def DecList Dec Exp Args

%right ASSIGNOP
%left OR
%left AND
%left RELOP
%left PLUS MINUS
%left STAR DIV
%right NOT UMINUS
%left LP RP LB RB DOT
%precedence LOWER_THAN_ELSE
%precedence ELSE

%start Program

%%

Program
    : ExtDefList
      {
          $$ = make_node("Program", 1, $1);
          root = $$;
      }
    ;

ExtDefList
    : ExtDef ExtDefList
      { $$ = make_node("ExtDefList", 2, $1, $2); }
    | %empty
      { $$ = NULL; }
    ;

ExtDef
    : Specifier ExtDecList SEMI
      { $$ = make_node("ExtDef", 3, $1, $2, $3); }
    | Specifier ExtDecList error SEMI
      { $$ = make_node("ExtDef", 2, $1, $2); }
    | Specifier ExtDecList error
      { $$ = make_node("ExtDef", 2, $1, $2); }

    | Specifier SEMI
      { $$ = make_node("ExtDef", 2, $1, $2); }
    | Specifier FunDec CompSt
      { $$ = make_node("ExtDef", 3, $1, $2, $3); }
    | Specifier FunDec SEMI
      { $$ = make_node("ExtDef", 3, $1, $2, $3); }
    | Specifier error CompSt
      { $$ = make_node("ExtDef", 2, $1, $3); }
    | error SEMI
      { $$ = NULL; }
    | error RC
      { $$ = NULL; }
    ;

Specifier
    : TYPE
      { $$ = make_node("Specifier", 1, $1); }
    | StructSpecifier
      { $$ = make_node("Specifier", 1, $1); }
    ;

StructSpecifier
    : STRUCT OptTag LC DefList RC
      { $$ = make_node("StructSpecifier", 5, $1, $2, $3, $4, $5); }
    | STRUCT error LC DefList RC
      { $$ = make_node("StructSpecifier", 4, $1, $3, $4, $5); }
    | STRUCT Tag
      { $$ = make_node("StructSpecifier", 2, $1, $2); }
    ;

OptTag
    : ID
      { $$ = make_node("OptTag", 1, $1); }
    | %empty
      { $$ = NULL; }
    ;

Tag
    : ID
      { $$ = make_node("Tag", 1, $1); }
    ;

ExtDecList
    : VarDec
      { $$ = make_node("ExtDecList", 1, $1); }
    | VarDec COMMA ExtDecList
      { $$ = make_node("ExtDecList", 3, $1, $2, $3); }
    ;

VarDec
    : ID
      { $$ = make_node("VarDec", 1, $1); }
    | VarDec LB INT RB
      { $$ = make_node("VarDec", 4, $1, $2, $3, $4); }
    | VarDec LB error RB
      { $$ = $1; }
    | VarDec LB INT error
      { $$ = $1; }
    ;

FunDec
    : ID LP VarList RP
      { $$ = make_node("FunDec", 4, $1, $2, $3, $4); }
    | ID LP RP
      { $$ = make_node("FunDec", 3, $1, $2, $3); }
    | ID LP error RP
      { $$ = make_node("FunDec", 3, $1, $2, $4); }
    | ID LP VarList error
      { $$ = make_node("FunDec", 3, $1, $2, $3); }
    ;

VarList
    : ParamDec COMMA VarList
      { $$ = make_node("VarList", 3, $1, $2, $3); }
    | ParamDec
      { $$ = make_node("VarList", 1, $1); }
    ;

ParamDec
    : Specifier VarDec
      { $$ = make_node("ParamDec", 2, $1, $2); }
    ;

CompSt
    : LC DefList StmtList RC
      { $$ = make_node("CompSt", 4, $1, $2, $3, $4); }
    | error RC
      { $$ = NULL; }
    ;

StmtList
    : Stmt StmtList
      { $$ = make_node("StmtList", 2, $1, $2); }
    | %empty
      { $$ = NULL; }
    ;

Stmt
    : Exp SEMI
      { $$ = make_node("Stmt", 2, $1, $2); }
    | Exp error
      { $$ = make_node("Stmt", 1, $1); }
    | error SEMI
      { $$ = NULL; }
    | CompSt
      { $$ = make_node("Stmt", 1, $1); }
    | RETURN Exp SEMI
      { $$ = make_node("Stmt", 3, $1, $2, $3); }
    | RETURN error SEMI
      { $$ = make_node("Stmt", 2, $1, $3); }
    | RETURN Exp error
      { $$ = make_node("Stmt", 2, $1, $2); }
    | IF LP Exp RP Stmt %prec LOWER_THAN_ELSE
      { $$ = make_node("Stmt", 5, $1, $2, $3, $4, $5); }
    | IF LP Exp RP Stmt ELSE Stmt
      { $$ = make_node("Stmt", 7, $1, $2, $3, $4, $5, $6, $7); }
    | IF LP error RP Stmt %prec LOWER_THAN_ELSE
      { $$ = make_node("Stmt", 4, $1, $2, $4, $5); }
    | IF LP error RP Stmt ELSE Stmt
      { $$ = make_node("Stmt", 6, $1, $2, $4, $5, $6, $7); }
    | IF LP Exp error Stmt %prec LOWER_THAN_ELSE
      { $$ = make_node("Stmt", 4, $1, $2, $3, $5); }
    | IF LP Exp error Stmt ELSE Stmt
      { $$ = make_node("Stmt", 6, $1, $2, $3, $5, $6, $7); }
    | WHILE LP Exp RP Stmt
      { $$ = make_node("Stmt", 5, $1, $2, $3, $4, $5); }
    | WHILE LP Exp error Stmt
      { $$ = make_node("Stmt", 4, $1, $2, $3, $5); }
    | WHILE LP error RP Stmt
      { $$ = make_node("Stmt", 4, $1, $2, $4, $5); }
    ;

DefList
    : Def DefList
      { $$ = make_node("DefList", 2, $1, $2); }
    | %empty
      { $$ = NULL; }
    ;

Def
    : Specifier DecList SEMI
      { $$ = make_node("Def", 3, $1, $2, $3); }
    | Specifier error SEMI
      { $$ = make_node("Def", 1, $1); }
    | Specifier DecList error
      { $$ = make_node("Def", 2, $1, $2); }
    ;

DecList
    : Dec
      { $$ = make_node("DecList", 1, $1); }
    | Dec COMMA DecList
      { $$ = make_node("DecList", 3, $1, $2, $3); }
    ;

Dec
    : VarDec
      { $$ = make_node("Dec", 1, $1); }
    | VarDec ASSIGNOP Exp
      { $$ = make_node("Dec", 3, $1, $2, $3); }
    ;

Exp
    : Exp ASSIGNOP Exp
      { $$ = make_node("Exp", 3, $1, $2, $3); }
    | Exp AND Exp
      { $$ = make_node("Exp", 3, $1, $2, $3); }
    | Exp OR Exp
      { $$ = make_node("Exp", 3, $1, $2, $3); }
    | Exp RELOP Exp
      { $$ = make_node("Exp", 3, $1, $2, $3); }
    | Exp RELOP error Exp %prec RELOP
      { $$ = make_node("Exp", 3, $1, $2, $4); }
    | Exp PLUS Exp
      { $$ = make_node("Exp", 3, $1, $2, $3); }
    | Exp MINUS Exp
      { $$ = make_node("Exp", 3, $1, $2, $3); }
    | Exp STAR Exp
      { $$ = make_node("Exp", 3, $1, $2, $3); }
    | Exp DIV Exp
      { $$ = make_node("Exp", 3, $1, $2, $3); }
    | LP Exp RP
      { $$ = make_node("Exp", 3, $1, $2, $3); }
    | LP error RP
      { $$ = NULL; }
    | MINUS Exp %prec UMINUS
      { $$ = make_node("Exp", 2, $1, $2); }
    | NOT Exp
      { $$ = make_node("Exp", 2, $1, $2); }
    | ID LP Args RP
      { $$ = make_node("Exp", 4, $1, $2, $3, $4); }
    | ID LP RP
      { $$ = make_node("Exp", 3, $1, $2, $3); }
    | ID LP error RP
      { $$ = make_node("Exp", 3, $1, $2, $4); }
    | ID LP Args error
      { $$ = make_node("Exp", 3, $1, $2, $3); }
    | Exp LB Exp RB %prec LB
      { $$ = make_node("Exp", 4, $1, $2, $3, $4); }
    | Exp LB error RB %prec LB
      { $$ = $1; }
    | Exp LB Exp error %prec LB
      { $$ = make_node("Exp", 3, $1, $2, $3); }
    | Exp DOT ID %prec DOT
      { $$ = make_node("Exp", 3, $1, $2, $3); }
    | ID
      { $$ = make_node("Exp", 1, $1); }
    | INT
      { $$ = make_node("Exp", 1, $1); }
    | FLOAT
      { $$ = make_node("Exp", 1, $1); }
    ;

Args
    : Exp COMMA Args
      { $$ = make_node("Args", 3, $1, $2, $3); }
    | Exp
      { $$ = make_node("Args", 1, $1); }
    ;

%%

/*
 * The grading Makefile generates lex.yy.c but does not compile/link it
 * separately. Include the generated scanner here so yylex, yyin,
 * yylineno and lexical_error are compiled into syntax.tab.o.
 */
#include "lex.yy.c"
#include "semantic.h"
#include "ir.h"

Node *make_token_node(const char *name, const char *text, int line)
{
    Node *node = (Node *)calloc(1, sizeof(Node));
    if (node == NULL) {
        perror("calloc");
        exit(1);
    }

    node->allocated_next = allocated_nodes;
    allocated_nodes = node;
    snprintf(node->name, sizeof(node->name), "%s", name);
    if (text != NULL) {
        snprintf(node->text, sizeof(node->text), "%s", text);
    }
    node->line = line;
    return node;
}

static Node *make_node(const char *name, int child_count, ...)
{
    Node *node = (Node *)calloc(1, sizeof(Node));
    if (node == NULL) {
        perror("calloc");
        exit(1);
    }

    node->allocated_next = allocated_nodes;
    allocated_nodes = node;
    snprintf(node->name, sizeof(node->name), "%s", name);

    va_list ap;
    va_start(ap, child_count);
    for (int i = 0; i < child_count; ++i) {
        Node *child = va_arg(ap, Node *);
        if (child != NULL && node->child_count < 8) {
            node->children[node->child_count++] = child;
            if (node->line == 0) {
                node->line = child->line;
            }
        }
    }
    va_end(ap);

    if (node->line == 0) {
        node->line = 1;
    }
    return node;
}

static int token_can_end_expression(int token)
{
    return token == ID || token == INT || token == FLOAT ||
           token == RP || token == RB;
}

static int syntax_error_report_line(const char *msg)
{
    int line = yylineno;

    /* At EOF there is no lookahead token carrying a useful source line.
       Attribute a missing trailing delimiter to the last real token. */
    if (yychar == YYEOF && current_token_line > 0) {
        return current_token_line;
    }

    /* `return ;` is grammatically invalid because Stmt requires RETURN Exp SEMI.
       If RETURN and SEMI are split across lines, Bison reports at the lookahead
       semicolon; attribute the missing-value error to RETURN instead. */
    if (current_token_code == SEMI && previous_token_code == RETURN &&
        previous_token_line > 0) {
        return previous_token_line;
    }

    /* Bison reports an error after it has read the lookahead.  For a common
       class of omissions, the lookahead begins on the next line while the
       malformed construct ended on the previous line.  Use the preceding
       token's line only for these omission-shaped cases; otherwise retain
       Bison's current-token line so existing error locations are unchanged. */
    if (current_token_line > previous_token_line && previous_token_line > 0 &&
        token_can_end_expression(previous_token_code)) {
        if (strstr(msg, "expecting SEMI") != NULL ||
            current_token_code == RETURN ||
            current_token_code == TYPE ||
            current_token_code == STRUCT ||
            current_token_code == IF ||
            current_token_code == WHILE ||
            current_token_code == RC) {
            line = previous_token_line;
        }
    }

    return line;
}

void yyerror(const char *msg)
{
    syntax_error = 1;

    /* EOF inside a block comment has already been diagnosed by the scanner.
       Do not cascade a second parser error from the now-incomplete construct. */
    if (lexical_eof_error) {
        return;
    }

    /* A lexical error can leave a token sequence that is syntactically
       impossible on the same line. Avoid reporting that secondary error. */
    if (last_lexical_error_line == yylineno) {
        return;
    }

    int report_line = syntax_error_report_line(msg);

    /* Error productions may encounter the same malformed construct more
       than once while synchronizing. Report at most one Type B per line. */
    if (last_syntax_error_line == report_line) {
        return;
    }

    last_syntax_error_line = report_line;
    printf("Error type B at Line %d: %s.\n", report_line, msg);
}

int main(int argc, char **argv)
{
    if (argc != 3) {
        fprintf(stderr, "Usage: %s input.cmm output.ir\n", argv[0]);
        return 1;
    }
    if (!strcmp(argv[1], argv[2])) {
        fprintf(stderr, "Input and output files must be different.\n");
        return 1;
    }
    yyin = fopen(argv[1], "r");
    if (!yyin) { perror(argv[1]); return 1; }

    int result = yyparse();

    int status = result != 0 || lexical_error || syntax_error;
    if (!status && root) {
        status = ir_check_syntax(root);
        if (!status) status = semantic_analyze(root) != 0;
        if (!status) status = ir_generate(root, argv[2]);
    }
    semantic_release();
    fclose(yyin);

    yylex_destroy();
    while (allocated_nodes) {
        Node *next = allocated_nodes->allocated_next;
        free(allocated_nodes); allocated_nodes = next;
    }
    return status ? 1 : 0;
}
