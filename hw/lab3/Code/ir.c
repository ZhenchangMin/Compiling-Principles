/* Lab 3: linear three-address IR. Optional 3.2 only; no structure lowering. */
#include "ir.h"
#include "semantic.h"
#include <limits.h>

typedef enum { NONE, VARIABLE, TEMPORARY, CONSTANT, ADDRESS } OperandKind;
typedef struct { OperandKind kind; long value; } Operand;
typedef enum {
    FUNCTION, LABEL, ASSIGN, BINARY, LOAD, STORE, JUMP, BRANCH,
    RETURN_VALUE, ALLOCATE, ARGUMENT, CALL, PARAMETER, READ_VALUE, WRITE_VALUE
} CodeKind;
typedef struct Code {
    CodeKind kind;
    Operand result, left, right;
    const char *name;
    char op[3];
    int target;
    struct Code *prev, *next;
} Code;
static Code *head, *tail;
static int next_temp, next_label;
static Node *program;

static int named(const Node *n, const char *name)
{ return n && !strcmp(n->name, name); }
static Node *child(const Node *n, const char *name)
{
    if (n) for (int i = 0; i < n->child_count; ++i)
        if (named(n->children[i], name)) return n->children[i];
    return NULL;
}
static int identifier_exists(Node *n, const char *text)
{
    if (named(n, "ID") && !strcmp(n->text, text)) return 1;
    for (int i = 0; i < n->child_count; ++i)
        if (identifier_exists(n->children[i], text)) return 1;
    return 0;
}
static int new_label(void)
{
    char name[64];
    do { snprintf(name, sizeof(name), "label%d", ++next_label); }
    while (identifier_exists(program, name));
    return next_label;
}
static void *allocate(size_t size)
{
    void *p = calloc(1, size);
    if (!p) { perror("calloc"); exit(1); }
    return p;
}
static Operand operand(OperandKind kind, long value)
{ Operand o = {kind, value}; return o; }
static Operand constant(long value) { return operand(CONSTANT, value); }
static Operand temporary(void) { return operand(TEMPORARY, ++next_temp); }
static Operand variable(SemSymbol *s) { return operand(VARIABLE, s->ir_id); }
static int same(Operand a, Operand b)
{ return a.kind == b.kind && a.value == b.value; }
static Code *emit(CodeKind kind, Operand result, Operand left, Operand right)
{
    Code *c = allocate(sizeof(*c));
    c->kind = kind; c->result = result; c->left = left; c->right = right;
    c->prev = tail;
    if (tail) tail->next = c; else head = c;
    tail = c;
    return c;
}
static Code *simple(CodeKind kind, Operand value)
{ return emit(kind, value, constant(0), constant(0)); }
static void mark(int label) { simple(LABEL, constant(0))->target = label; }
static void jump(int label) { simple(JUMP, constant(0))->target = label; }
static void assign(Operand target, Operand value)
{
    if (!same(target, value)) emit(ASSIGN, target, value, constant(0));
}
static Operand snapshot(Operand value)
{
    if (value.kind != VARIABLE) return value;
    Operand t = temporary(); assign(t, value); return t;
}
static void branch(Operand a, const char *op, Operand b, int target)
{
    Code *c = emit(BRANCH, constant(0), a, b);
    snprintf(c->op, sizeof(c->op), "%.2s", op); c->target = target;
}
static Operand raw_binary(const char *op, Operand a, Operand b)
{
    Operand result = temporary();
    Code *c = emit(BINARY, result, a, b);
    snprintf(c->op, sizeof(c->op), "%.2s", op);
    return result;
}
/* irsim implements / with Python // (floor). Divide magnitudes and restore
   the sign so source integer division truncates toward zero on either VM. */
static Operand divide(Operand a, Operand b)
{
    Operand sign = temporary(); assign(sign, constant(0));
    Operand x = temporary(), y = temporary(); assign(x, a); assign(y, b);
    int positive_x = new_label(), positive_y = new_label(), done = new_label();
    branch(x, ">=", constant(0), positive_x);
    emit(BINARY, x, constant(0), x)->op[0] = '-'; assign(sign, constant(1)); mark(positive_x);
    branch(y, ">=", constant(0), positive_y);
    emit(BINARY, y, constant(0), y)->op[0] = '-';
    emit(BINARY, sign, constant(1), sign)->op[0] = '-'; mark(positive_y);
    Operand result = raw_binary("/", x, y);
    branch(sign, "==", constant(0), done);
    emit(BINARY, result, constant(0), result)->op[0] = '-'; mark(done);
    return result;
}
static Operand binary(const char *op, Operand a, Operand b)
{
    if (a.kind == CONSTANT && b.kind == CONSTANT) {
        long long x = a.value, y = b.value, result = 0;
        int fold = 1;
        switch (*op) {
        case '+': result = x + y; break;
        case '-': result = x - y; break;
        case '*': result = x * y; break;
        case '/': if (!y) fold = 0; else result = x / y; break;
        default: fold = 0; break;
        }
        if (fold && result >= INT_MIN && result <= INT_MAX) return constant((long)result);
    }
    if (b.kind == CONSTANT) {
        if (b.value == 0 && (*op == '+' || *op == '-')) return a;
        if (b.value == 1 && (*op == '*' || *op == '/')) return a;
        if (b.value == 0 && *op == '*') return constant(0);
    }
    if (a.kind == CONSTANT && a.value == 0) {
        if (*op == '+') return b;
        if (*op == '*') return constant(0);
    }
    if (*op == '/') return divide(a, b);
    return raw_binary(op, a, b);
}
/* Checked before generation, so sizes fit the VM's byte-sized DEC operand. */
static long width(SemType *t)
{ return t->kind == SEM_ARRAY ? t->size * width(t->element) : 4; }

int ir_check_syntax(Node *root)
{
    /* A standalone type definition allocates no structure variable and needs
       no IR. This is allowed even without optional structure translation. */
    if (named(root, "ExtDef") && root->child_count == 2 &&
        named(root->children[1], "SEMI")) return 0;
    if (named(root, "StructSpecifier")) {
        puts("Cannot translate: Code contains variables or parameters of structure type.");
        return 1;
    }
    if (named(root, "FLOAT") || (named(root, "TYPE") && !strcmp(root->text, "float"))) {
        puts("Cannot translate: Code contains floating-point constants or variables."); return 1;
    }
    for (int i = 0; i < root->child_count; ++i)
        if (ir_check_syntax(root->children[i])) return 1;
    return 0;
}
static int valid_width(SemType *type, long *size)
{
    if (type->kind != SEM_ARRAY) { *size = 4; return 1; }
    long element;
    if (!valid_width(type->element, &element) || type->size <= 0 ||
        type->size > INT_MAX / element) return 0;
    *size = type->size * element;
    return 1;
}
static int check_types(Node *n)
{
    long size;
    /* The handout excludes global-variable use, not unused declarations. */
    if (named(n, "Exp") && n->symbol && n->symbol->is_global) {
        puts("Cannot translate: Code contains global variables."); return 1;
    }
    if (named(n, "VarDec") && n->type) {
        if (!valid_width(n->type, &size)) {
            puts("Cannot translate: Array size must be positive and fit in 32-bit memory."); return 1;
        }
        if (n->symbol && n->symbol->is_parameter && n->type->kind == SEM_ARRAY &&
            n->type->element->kind == SEM_ARRAY) {
            puts("Cannot translate: Code contains parameters of multi-dimensional array type."); return 1;
        }
    }
    for (int i = 0; i < n->child_count; ++i)
        if (check_types(n->children[i])) return 1;
    return 0;
}
static Operand expression(Node *n);
static void condition(Node *n, int yes, int no);
static void statement(Node *n);
static void compound(Node *n);
static Node *unparen(Node *n)
{
    while (n->child_count == 3 && named(n->children[0], "LP")) n = n->children[1];
    return n;
}
static int effects(Node *n)
{
    if (named(n, "Exp") && (named(n->children[0], "ID") && n->child_count > 1)) return 1;
    if (named(n, "ASSIGNOP")) return 1;
    for (int i = 0; i < n->child_count; ++i) if (effects(n->children[i])) return 1;
    return 0;
}
/* Arrays yield addresses, scalars yield values. Each subscript advances by
   sizeof(element), so a[i][j] uses i*(columns*4) followed by j*4. */
static Operand address(Node *n)
{
    n = unparen(n);
    if (n->child_count == 1) {
        SemSymbol *s = n->symbol;
        return s->is_parameter ? variable(s) : operand(ADDRESS, s->ir_id);
    }
    Operand base = expression(n->children[0]);
    Operand index = expression(n->children[2]);
    Operand offset = binary("*", index, constant(width(n->type)));
    /* Keep memory operands as *temporary/variable, even at offset zero. */
    Operand result = binary("+", base, offset);
    if (result.kind == ADDRESS) {
        Operand t = temporary(); assign(t, result); result = t;
    }
    return result;
}
static int boolean_expression(Node *n)
{
    return named(n->children[0], "NOT") || child(n, "AND") ||
           child(n, "OR") || child(n, "RELOP");
}
/* Folding the last producer into a scalar assignment avoids redundant copies.
   Only a temporary produced by the final instruction can be redirected. */
static void store_scalar(Operand target, Operand value)
{
    if (value.kind == TEMPORARY && tail && same(tail->result, value) &&
        (tail->kind == BINARY || tail->kind == LOAD || tail->kind == CALL ||
         tail->kind == READ_VALUE)) tail->result = target;
    else assign(target, value);
}
/* C-- allows assignment between arrays with the same base type and rank.
   Copy their contents, not the address; stop when either array is exhausted.
   Cursor temporaries leave array-parameter pointer slots unchanged. */
static void copy_array(Operand target, Operand source, SemType *target_type, SemType *source_type)
{
    if (same(target, source)) return;
    long bytes = width(target_type), source_bytes = width(source_type);
    if (source_bytes < bytes) bytes = source_bytes;
    Operand to = temporary(), from = temporary(), word = temporary();
    assign(to, target); assign(from, source);
    if (bytes <= 16) {
        for (long offset = 0; offset < bytes; offset += 4) {
            emit(LOAD, word, from, constant(0)); emit(STORE, to, word, constant(0));
            if (offset + 4 < bytes) {
                emit(BINARY, to, to, constant(4))->op[0] = '+';
                emit(BINARY, from, from, constant(4))->op[0] = '+';
            }
        }
        return;
    }
    Operand remaining = temporary(); assign(remaining, constant(bytes));
    int loop = new_label(); mark(loop);
    emit(LOAD, word, from, constant(0)); emit(STORE, to, word, constant(0));
    emit(BINARY, to, to, constant(4))->op[0] = '+';
    emit(BINARY, from, from, constant(4))->op[0] = '+';
    emit(BINARY, remaining, remaining, constant(4))->op[0] = '-';
    branch(remaining, ">", constant(0), loop);
}
static Operand call(Node *n)
{
    const char *name = n->children[0]->text;
    Node *args = child(n, "Args");
    if (!strcmp(name, "read")) {
        Operand t = temporary(); simple(READ_VALUE, t); return t;
    }
    if (!strcmp(name, "write")) {
        Operand value = expression(args->children[0]);
        simple(WRITE_VALUE, value); return constant(0);
    }
    int count = 0;
    for (Node *p = args; p; p = child(p, "Args")) ++count;
    Operand *values = allocate((size_t)(count ? count : 1) * sizeof(*values));
    int i = 0;
    /* Evaluate left to right, save values, then emit ARG right to left.
       Nested calls complete before the outer call's first ARG. */
    for (Node *p = args; p; p = child(p, "Args"))
        values[i++] = snapshot(expression(p->children[0]));
    while (i) simple(ARGUMENT, values[--i]);
    free(values);
    Operand t = temporary(); simple(CALL, t)->name = name; return t;
}
static Operand expression(Node *n)
{
    n = unparen(n);
    Node *a = n->children[0];
    if (n->child_count == 1) {
        if (named(a, "INT")) return constant(strtol(a->text, NULL, 0));
        if (n->type->kind == SEM_ARRAY) return address(n);
        return variable(n->symbol);
    }
    if (named(a, "ID")) return call(n);
    if (child(n, "LB")) {
        Operand addr = address(n);
        if (n->type->kind == SEM_ARRAY) return addr;
        Operand t = temporary(); emit(LOAD, t, addr, constant(0)); return t;
    }
    if (child(n, "ASSIGNOP")) {
        Node *lhs = unparen(a);
        if (lhs->type->kind == SEM_ARRAY) {
            Operand target = address(lhs);
            Operand value = expression(n->children[2]);
            copy_array(target, value, lhs->type, n->children[2]->type);
            return target;
        }
        int scalar = lhs->child_count == 1;
        Operand target = scalar ? variable(lhs->symbol) : address(lhs);
        Operand value = expression(n->children[2]);
        if (scalar) { store_scalar(target, value); return target; }
        emit(STORE, target, value, constant(0)); return value;
    }
    if (boolean_expression(n)) {
        Operand t = temporary(); int yes = new_label(), no = new_label();
        assign(t, constant(0)); condition(n, yes, no);
        mark(yes); assign(t, constant(1)); mark(no); return t;
    }
    if (n->child_count == 2) return binary("-", constant(0), expression(n->children[1]));
    Operand left = expression(a);
    if (effects(n->children[2])) left = snapshot(left);
    Operand right = expression(n->children[2]);
    const char *op = named(n->children[1], "PLUS") ? "+" :
                     named(n->children[1], "MINUS") ? "-" :
                     named(n->children[1], "STAR") ? "*" : "/";
    return binary(op, left, right);
}
static void condition(Node *n, int yes, int no)
{
    n = unparen(n);
    if (named(n->children[0], "NOT")) { condition(n->children[1], no, yes); return; }
    if (child(n, "AND")) {
        int next = new_label(); condition(n->children[0], next, no); mark(next);
        condition(n->children[2], yes, no); return;
    }
    if (child(n, "OR")) {
        int next = new_label(); condition(n->children[0], yes, next); mark(next);
        condition(n->children[2], yes, no); return;
    }
    Operand left, right; const char *op;
    if (child(n, "RELOP")) {
        left = expression(n->children[0]);
        if (effects(n->children[2])) left = snapshot(left);
        right = expression(n->children[2]); op = n->children[1]->text;
    } else { left = expression(n); right = constant(0); op = "!="; }
    Code *c = emit(BRANCH, constant(0), left, right);
    snprintf(c->op, sizeof(c->op), "%.2s", op); c->target = yes; jump(no);
}
/* Value-discarding expressions must still retain calls and short-circuiting. */
static void discard(Node *n)
{
    n = unparen(n);
    if (child(n, "ASSIGNOP") || (named(n->children[0], "ID") && n->child_count > 1)) {
        (void)expression(n); return;
    }
    if (!effects(n)) return;
    if (child(n, "AND") || child(n, "OR")) {
        int done = new_label(); condition(n, done, done); mark(done); return;
    }
    for (int i = 0; i < n->child_count; ++i)
        if (named(n->children[i], "Exp")) discard(n->children[i]);
}
static void compound(Node *n)
{
    for (Node *defs = child(n, "DefList"); defs; defs = child(defs, "DefList")) {
        for (Node *decs = child(defs->children[0], "DecList"); decs; decs = child(decs, "DecList")) {
            Node *dec = decs->children[0], *var = dec->children[0];
            if (var->type->kind == SEM_ARRAY) {
                Code *c = simple(ALLOCATE, variable(var->symbol)); c->left = constant(width(var->type));
            }
            if (dec->child_count == 3) {
                Operand value = expression(dec->children[2]);
                if (var->type->kind == SEM_ARRAY)
                    copy_array(operand(ADDRESS, var->symbol->ir_id), value, var->type, dec->children[2]->type);
                else store_scalar(variable(var->symbol), value);
            }
        }
    }
    for (Node *list = child(n, "StmtList"); list; list = child(list, "StmtList"))
        statement(list->children[0]);
}
static void statement(Node *n)
{
    Node *first = n->children[0];
    if (named(first, "CompSt")) { compound(first); return; }
    if (named(first, "Exp")) { discard(first); return; }
    if (named(first, "RETURN")) { simple(RETURN_VALUE, expression(n->children[1])); return; }
    if (named(first, "IF")) {
        int yes = new_label(), no = new_label();
        condition(n->children[2], yes, no); mark(yes); statement(n->children[4]);
        if (n->child_count == 7) {
            int done = new_label(); jump(done); mark(no); statement(n->children[6]); mark(done);
        } else mark(no);
        return;
    }
    int start = new_label(), body = new_label(), done = new_label();
    mark(start); condition(n->children[2], body, done); mark(body);
    statement(n->children[4]); jump(start); mark(done);
}
static void remove_code(Code *c)
{
    if (c->prev) c->prev->next = c->next; else head = c->next;
    if (c->next) c->next->prev = c->prev; else tail = c->prev;
    free(c);
}
static const char *inverse(const char *op)
{
    if (!strcmp(op, "==")) return "!=";
    if (!strcmp(op, "!=")) return "==";
    if (!strcmp(op, "<")) return ">=";
    if (!strcmp(op, ">")) return "<=";
    if (!strcmp(op, "<=")) return ">";
    return "<";
}
static void optimize(void)
{
    for (Code *c = head; c; c = c->next) {
        /* IF p GOTO L1; GOTO L2; LABEL L1 -> IF !p GOTO L2; LABEL L1 */
        if (c->kind == BRANCH && c->next && c->next->kind == JUMP &&
            c->next->next && c->next->next->kind == LABEL &&
            c->target == c->next->next->target) {
            Code *j = c->next; char op[3];
            snprintf(op, sizeof(op), "%s", inverse(c->op));
            memcpy(c->op, op, sizeof(op)); c->target = j->target; remove_code(j);
        }
        if (c->kind == JUMP && c->next && c->next->kind == LABEL && c->target == c->next->target) {
            Code *prev = c->prev; remove_code(c); c = prev;
        }
        if (!c) break;
    }
}
static void print_operand(FILE *out, Operand o)
{
    const char *prefix = o.kind == CONSTANT ? "#" : o.kind == ADDRESS ? "&v" :
                         o.kind == TEMPORARY ? "t" : "v";
    fprintf(out, "%s%ld", prefix, o.value);
}
static void print_code(FILE *out, Code *c)
{
    switch (c->kind) {
    case FUNCTION: fprintf(out, "FUNCTION %s :", c->name); break;
    case LABEL: fprintf(out, "LABEL label%d :", c->target); break;
    case JUMP: fprintf(out, "GOTO label%d", c->target); break;
    case BRANCH:
        fputs("IF ", out); print_operand(out, c->left); fprintf(out, " %s ", c->op);
        print_operand(out, c->right); fprintf(out, " GOTO label%d", c->target); break;
    case ASSIGN: case BINARY: case LOAD: case STORE: case CALL:
        if (c->kind == STORE) fputc('*', out);
        print_operand(out, c->result); fputs(" := ", out);
        if (c->kind == CALL) { fprintf(out, "CALL %s", c->name); break; }
        if (c->kind == LOAD) fputc('*', out);
        print_operand(out, c->left);
        if (c->kind == BINARY) { fprintf(out, " %s ", c->op); print_operand(out, c->right); }
        break;
    default:
        fputs(c->kind == RETURN_VALUE ? "RETURN " : c->kind == ALLOCATE ? "DEC " :
              c->kind == ARGUMENT ? "ARG " : c->kind == PARAMETER ? "PARAM " :
              c->kind == READ_VALUE ? "READ " : "WRITE ", out);
        print_operand(out, c->result);
        if (c->kind == ALLOCATE) fprintf(out, " %ld", c->left.value);
        break;
    }
    fputc('\n', out);
}
int ir_generate(Node *root, const char *output_path)
{
    if (check_types(root)) return 1;
    head = tail = NULL; next_temp = next_label = 0; program = root;
    for (Node *list = child(root, "ExtDefList"); list; list = child(list, "ExtDefList")) {
        Node *ext = list->children[0], *fun = child(ext, "FunDec");
        if (!fun) continue;
        simple(FUNCTION, constant(0))->name = fun->children[0]->text;
        for (Node *params = child(fun, "VarList"); params; params = child(params, "VarList")) {
            Node *var = params->children[0]->children[1]; simple(PARAMETER, variable(var->symbol));
        }
        compound(child(ext, "CompSt"));
    }
    optimize();
    FILE *out = fopen(output_path, "w");
    int failed = !out;
    if (!out) perror(output_path);
    else {
        for (Code *c = head; c; c = c->next) print_code(out, c);
        int write_error = ferror(out), close_error = fclose(out);
        if (write_error || close_error) { perror(output_path); failed = 1; }
    }
    while (head) remove_code(head);
    return failed;
}

