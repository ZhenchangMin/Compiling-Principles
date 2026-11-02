/*
 * 语义分析：沿源文件顺序遍历语法树；NULL 类型表示已诊断的错误，
 * 防止未定义名字引起无意义的类型错误连锁。只依赖 C 标准库。
 */
#include "semantic.h"

typedef struct SemScope SemScope;
typedef struct SemFunction SemFunction;
struct SemScope {
    SemSymbol *symbols;
    SemScope *parent;
};
struct SemFunction {
    const char *name;
    SemType *result;
    SemField *params;
    int defined, first_line;
    SemFunction *next;
};
typedef struct { SemType *type; int lvalue; } SemExpr;

/* 单张散列表 + 作用域链：新符号先插入，离开块时恢复被遮蔽的名字。 */
#define SEM_BUCKETS 4096
static SemSymbol *sem_table[SEM_BUCKETS];
static SemScope *sem_scope;
static SemFunction *sem_functions;
static SemType sem_int = { SEM_INT, NULL, 0, NULL };
static SemType sem_float = { SEM_FLOAT, NULL, 0, NULL };
static const int sem_scoped = 1, sem_structural = 0, sem_declarations = 0;
static int sem_errors, sem_next_variable;

/* 统一管理语义数据的生命周期，共享类型无需分别释放。 */
typedef struct SemAllocation { void *ptr; struct SemAllocation *next; } SemAllocation;
static SemAllocation *sem_allocations;
static void *sem_alloc(size_t size)
{
    void *p = calloc(1, size);
    SemAllocation *a = malloc(sizeof(*a));
    if (!p || !a) { perror("malloc"); exit(1); }
    a->ptr = p; a->next = sem_allocations; sem_allocations = a;
    return p;
}
void semantic_release(void)
{
    while (sem_allocations) {
        SemAllocation *a = sem_allocations;
        sem_allocations = a->next;
        free(a->ptr); free(a);
    }
}
static int sem_named(const Node *n, const char *name)
{ return n && strcmp(n->name, name) == 0; }
static Node *sem_child(const Node *n, const char *name)
{
    if (n) for (int i = 0; i < n->child_count; ++i)
        if (sem_named(n->children[i], name)) return n->children[i];
    return NULL;
}
static void sem_error(int number, int line, const char *format, ...)
{
    va_list ap;
    ++sem_errors;
    printf("Error type %d at Line %d: ", number, line);
    va_start(ap, format); vprintf(format, ap); va_end(ap);
    printf(".\n");
}
static unsigned sem_hash(const char *s)
{
    unsigned h = 0;
    while (*s) h = h * 131u + (unsigned char)*s++;
    return h % SEM_BUCKETS;
}
static void sem_enter(void)
{
    SemScope *s = sem_alloc(sizeof(*s));
    s->parent = sem_scope; sem_scope = s;
}
static void sem_leave(void)
{
    for (SemSymbol *s = sem_scope->symbols; s; s = s->scope_next) {
        unsigned h = sem_hash(s->name);
        /* 同一作用域按插入的逆序删除，因此它一定是对应桶的表头。 */
        sem_table[h] = s->bucket_next;
    }
    sem_scope = sem_scope->parent;
}
static SemSymbol *sem_lookup(const char *name)
{
    for (SemSymbol *s = sem_table[sem_hash(name)]; s; s = s->bucket_next)
        if (!strcmp(s->name, name)) return s;
    return NULL;
}
static SemSymbol *sem_current(const char *name)
{
    for (SemSymbol *s = sem_scope->symbols; s; s = s->scope_next)
        if (!strcmp(s->name, name)) return s;
    return NULL;
}
static SemSymbol *sem_insert(const char *name, SemType *type, int tag, int line)
{
    if (sem_current(name)) {
        sem_error(tag ? 16 : 3, line, "Duplicated %s \"%s\"",
                  tag ? "structure name" : "variable", name);
        return NULL;
    }
    SemSymbol *s = sem_alloc(sizeof(*s));
    s->name = name; s->type = type; s->is_tag = tag; s->ir_id = ++sem_next_variable;
    s->is_global = sem_scope->parent == NULL;
    unsigned h = sem_hash(name);
    s->bucket_next = sem_table[h]; sem_table[h] = s;
    s->scope_next = sem_scope->symbols; sem_scope->symbols = s;
    return s;
}
static SemFunction *sem_find_function(const char *name)
{
    for (SemFunction *f = sem_functions; f; f = f->next)
        if (!strcmp(f->name, name)) return f;
    return NULL;
}
static int sem_equal(SemType *a, SemType *b)
{
    if (!a || !b) return 1; /* 错误类型不能再次触发不匹配错误 */
    if (a == b) return 1;
    if (a->kind != b->kind) return 0;
    if (a->kind == SEM_ARRAY) return sem_equal(a->element, b->element);
    if (a->kind == SEM_STRUCT) {
        if (!sem_structural) return 0; /* 同一结构体定义由同一指针标识 */
        SemField *x = a->fields, *y = b->fields;
        for (; x && y; x = x->next, y = y->next)
            if (!sem_equal(x->type, y->type)) return 0;
        return !x && !y;
    }
    return 1;
}
static int sem_signature(SemFunction *f, SemType *result, SemField *params)
{
    if (!sem_equal(f->result, result)) return 0;
    SemField *a = f->params, *b = params;
    for (; a && b; a = a->next, b = b->next)
        if (!sem_equal(a->type, b->type)) return 0;
    return !a && !b;
}
static int sem_integer(SemType *t) { return t && t->kind == SEM_INT; }
static int sem_numeric(SemType *t)
{ return t && (t->kind == SEM_INT || t->kind == SEM_FLOAT); }
static SemExpr sem_expr(Node *n);
static SemType *sem_specifier(Node *n);
static void sem_definitions(Node *list, SemType *structure);
static void sem_statement(Node *n, SemType *result);

/* a[2][3] 的语法树外层是 [3]，递归向内传递类型，得到正确维度次序。 */
static SemType *sem_vardec(Node *n, SemType *base, Node **id)
{
    if (n->child_count == 1) { *id = n->children[0]; return base; }
    SemType *array = sem_alloc(sizeof(*array));
    array->kind = SEM_ARRAY; array->element = base;
    array->size = strtol(n->children[2]->text, NULL, 10);
    return sem_vardec(n->children[0], array, id);
}
static SemType *sem_specifier(Node *n)
{
    Node *first = n->children[0];
    if (sem_named(first, "TYPE"))
        return !strcmp(first->text, "int") ? &sem_int : &sem_float;
    Node *tag = sem_child(first, "Tag");
    if (tag) {
        Node *id = tag->children[0];
        SemSymbol *s = sem_lookup(id->text);
        if (!s || !s->is_tag) {
            sem_error(17, id->line, "Undefined structure \"%s\"", id->text);
            return NULL;
        }
        return s->type;
    }
    SemType *t = sem_alloc(sizeof(*t));
    t->kind = SEM_STRUCT;
    /* 域名仅存入所属结构体，避免与变量或其他结构体的域互相污染。 */
    sem_definitions(sem_child(first, "DefList"), t);
    Node *opt = sem_child(first, "OptTag");
    if (opt) sem_insert(opt->children[0]->text, t, 1, opt->children[0]->line);
    return t;
}
static void sem_field(SemType *structure, Node *id, SemType *type)
{
    SemField **tail = &structure->fields;
    for (; *tail; tail = &(*tail)->next) {
        if (!strcmp((*tail)->name, id->text)) {
            sem_error(15, id->line, "Redefined field \"%s\"", id->text);
            return;
        }
    }
    SemField *f = sem_alloc(sizeof(*f));
    f->name = id->text; f->type = type; f->line = id->line;
    *tail = f;
}
static void sem_decs(Node *list, SemType *base, SemType *structure)
{
    while (list) {
        Node *dec = list->children[0], *id = NULL;
        SemType *t = sem_vardec(dec->children[0], base, &id);
        if (structure) {
            sem_field(structure, id, t);
            if (dec->child_count == 3)
                sem_error(15, id->line, "Field \"%s\" cannot be initialized", id->text);
        } else {
            id->symbol = sem_insert(id->text, t, 0, id->line);
            dec->children[0]->symbol = id->symbol;
            dec->children[0]->type = t;
            if (dec->child_count == 3) {
                SemExpr value = sem_expr(dec->children[2]);
                if (!sem_equal(t, value.type))
                    sem_error(5, id->line, "Type mismatched for assignment");
            }
        }
        list = sem_child(list, "DecList");
    }
}
static void sem_definitions(Node *list, SemType *structure)
{
    while (list) {
        Node *def = list->children[0];
        SemType *t = sem_specifier(def->children[0]);
        sem_decs(sem_child(def, "DecList"), t, structure);
        list = sem_child(list, "DefList");
    }
}
static SemExpr sem_value(SemType *type, int lvalue)
{ SemExpr e = {type, lvalue}; return e; }
static SemExpr sem_call(Node *n)
{
    Node *id = n->children[0], *args = sem_child(n, "Args");
    SemSymbol *s = sem_lookup(id->text);
    SemFunction *f = sem_find_function(id->text);
    int bad = 0;
    if (s && !s->is_tag) sem_error(11, id->line, "\"%s\" is not a function", id->text);
    else if (!f) sem_error(2, id->line, "Undefined function \"%s\"", id->text);
    SemField *param = f ? f->params : NULL;
    for (; args; args = sem_child(args, "Args")) {
        SemExpr actual = sem_expr(args->children[0]);
        if (!param) bad = 1;
        else {
            if (!sem_equal(param->type, actual.type)) bad = 1;
            param = param->next;
        }
    }
    if (param) bad = 1;
    if (f && !(s && !s->is_tag) && bad)
        sem_error(9, id->line, "Arguments do not match function \"%s\"", id->text);
    return sem_value(f && !(s && !s->is_tag) ? f->result : NULL, 0);
}
static SemExpr sem_expr_impl(Node *n);
static SemExpr sem_expr(Node *n)
{
    SemExpr result = sem_expr_impl(n);
    if (n) n->type = result.type;
    return result;
}
static SemExpr sem_expr_impl(Node *n)
{
    if (!n) return sem_value(NULL, 0);
    Node *a = n->children[0];
    if (n->child_count == 1) {
        if (sem_named(a, "INT")) return sem_value(&sem_int, 0);
        if (sem_named(a, "FLOAT")) return sem_value(&sem_float, 0);
        SemSymbol *s = sem_lookup(a->text);
        if (!s || s->is_tag) {
            sem_error(1, a->line, "Undefined variable \"%s\"", a->text);
            return sem_value(NULL, 1);
        }
        n->symbol = a->symbol = s;
        return sem_value(s->type, 1);
    }
    if (sem_named(a, "ID")) return sem_call(n);
    if (sem_named(a, "LP")) return sem_expr(n->children[1]);
    if (n->child_count == 2) {
        SemExpr e = sem_expr(n->children[1]);
        if (e.type && (sem_named(a, "NOT") ? !sem_integer(e.type) : !sem_numeric(e.type))) {
            sem_error(7, n->line, "Type mismatched for operands");
            return sem_value(NULL, 0);
        }
        return sem_value(e.type, 0);
    }
    Node *op = n->children[1];
    SemExpr left = sem_expr(a);
    if (sem_named(op, "DOT")) {
        Node *id = n->children[2];
        if (!left.type) return sem_value(NULL, left.lvalue);
        if (left.type->kind != SEM_STRUCT) {
            sem_error(13, n->line, "Illegal use of \".\"");
            return sem_value(NULL, 0);
        }
        for (SemField *f = left.type->fields; f; f = f->next)
            if (!strcmp(f->name, id->text)) return sem_value(f->type, left.lvalue);
        sem_error(14, n->line, "Non-existent field \"%s\"", id->text);
        return sem_value(NULL, left.lvalue);
    }
    SemExpr right = sem_expr(n->children[2]);
    if (sem_named(op, "LB")) {
        if (left.type && left.type->kind != SEM_ARRAY)
            sem_error(10, n->line, "Indexed expression is not an array");
        if (right.type && !sem_integer(right.type))
            sem_error(12, n->children[2]->line, "Array index is not an integer");
        return sem_value(left.type && left.type->kind == SEM_ARRAY
                         ? left.type->element : NULL, left.lvalue);
    }
    if (sem_named(op, "ASSIGNOP")) {
        if (!left.lvalue) sem_error(6, n->line, "The left-hand side must be a variable");
        if (!sem_equal(left.type, right.type))
            sem_error(5, n->line, "Type mismatched for assignment");
        return sem_value(left.type && right.type ? left.type : NULL, 0);
    }
    if (!left.type || !right.type) return sem_value(NULL, 0);
    int logical = sem_named(op, "AND") || sem_named(op, "OR");
    if (!sem_equal(left.type, right.type) ||
        (logical ? !sem_integer(left.type) : !sem_numeric(left.type))) {
        sem_error(7, n->line, "Type mismatched for operands");
        return sem_value(NULL, 0);
    }
    return sem_value(logical || sem_named(op, "RELOP") ? &sem_int : left.type, 0);
}
static void sem_compound(Node *n, SemType *result, int new_scope)
{
    if (new_scope && sem_scoped) sem_enter();
    sem_definitions(sem_child(n, "DefList"), NULL);
    Node *list = sem_child(n, "StmtList");
    while (list) {
        sem_statement(list->children[0], result);
        list = sem_child(list, "StmtList");
    }
    if (new_scope && sem_scoped) sem_leave();
}
static void sem_statement(Node *n, SemType *result)
{
    if (!n) return;
    Node *first = n->children[0];
    if (sem_named(first, "CompSt")) { sem_compound(first, result, 1); return; }
    if (sem_named(first, "Exp")) { sem_expr(first); return; }
    if (sem_named(first, "RETURN")) {
        SemExpr e = sem_expr(n->children[1]);
        if (!sem_equal(e.type, result))
            sem_error(8, n->line, "Type mismatched for return");
        return;
    }
    SemExpr condition = sem_expr(n->children[2]);
    if (condition.type && !sem_integer(condition.type))
        sem_error(7, n->children[2]->line, "Condition must have type int");
    sem_statement(n->children[4], result);
    if (n->child_count == 7) sem_statement(n->children[6], result);
}
static SemField *sem_parameters(Node *list)
{
    SemField *head = NULL, **tail = &head;
    while (list) {
        Node *param = list->children[0], *id = NULL;
        SemType *base = sem_specifier(param->children[0]);
        SemType *t = sem_vardec(param->children[1], base, &id);
        SemField *f = sem_alloc(sizeof(*f));
        f->name = id->text; f->line = id->line; f->type = t;
        f->declaration = param->children[1];
        *tail = f; tail = &f->next;
        list = sem_child(list, "VarList");
    }
    return head;
}
static void sem_external(Node *n)
{
    SemType *t = sem_specifier(n->children[0]);
    Node *vars = sem_child(n, "ExtDecList");
    if (vars) {
        while (vars) {
            Node *id = NULL;
            SemType *v = sem_vardec(vars->children[0], t, &id);
            sem_insert(id->text, v, 0, id->line);
            vars = sem_child(vars, "ExtDecList");
        }
        return;
    }
    Node *dec = sem_child(n, "FunDec");
    if (!dec) return;
    Node *id = dec->children[0], *body = sem_child(n, "CompSt");
    if (!body && !sem_declarations) {
        printf("Error type B at Line %d: Function declarations are disabled in this mode.\n", id->line);
        return;
    }
    /* 参数中定义的结构体和参数本身属于函数作用域；声明不泄漏参数。 */
    if (sem_scoped || !body) sem_enter();
    SemField *params = sem_parameters(sem_child(dec, "VarList"));
    SemFunction *f = sem_find_function(id->text);
    if (!f) {
        f = sem_alloc(sizeof(*f));
        f->name = id->text; f->result = t; f->params = params;
        f->first_line = id->line;
        f->next = sem_functions; sem_functions = f;
    } else if (body && f->defined) {
        sem_error(4, id->line, "Redefined function \"%s\"", id->text);
    } else if (!sem_signature(f, t, params)) {
        sem_error(19, id->line, "Inconsistent declaration of function \"%s\"", id->text);
    }
    if (body) f->defined = 1;
    for (SemField *p = params; p; p = p->next) {
        SemSymbol *symbol = sem_insert(p->name, p->type, 0, p->line);
        if (symbol) symbol->is_parameter = 1;
        p->declaration->symbol = symbol;
        p->declaration->type = p->type;
    }
    if (body) sem_compound(body, t, 0);
    if (sem_scoped || !body) sem_leave();
}
int semantic_analyze(Node *program)
{
    sem_errors = sem_next_variable = 0;
    Node *list = sem_child(program, "ExtDefList");
    if (!sem_declarations) {
        int invalid = 0, last_line = -1;
        for (Node *item = list; item; item = sem_child(item, "ExtDefList")) {
            Node *ext = item->children[0];
            Node *dec = sem_child(ext, "FunDec");
            if (dec && !sem_child(ext, "CompSt")) {
                int line = dec->children[0]->line;
                if (line != last_line)
                    printf("Error type B at Line %d: Function declarations are disabled in this mode.\n", line);
                last_line = line;
                invalid = 1;
            }
        }
        /* 此模式的函数声明属于语法错误，不继续制造次生语义错误。 */
        if (invalid) return 1;
    }
    sem_enter();
    SemFunction *read_fn = sem_alloc(sizeof(*read_fn));
    SemFunction *write_fn = sem_alloc(sizeof(*write_fn));
    SemField *write_param = sem_alloc(sizeof(*write_param));
    read_fn->name = "read"; read_fn->result = &sem_int; read_fn->defined = 1;
    write_param->name = "value"; write_param->type = &sem_int;
    write_fn->name = "write"; write_fn->result = &sem_int; write_fn->defined = 1;
    write_fn->params = write_param; write_fn->next = read_fn;
    sem_functions = write_fn;
    while (list) {
        sem_external(list->children[0]);
        list = sem_child(list, "ExtDefList");
    }
    if (sem_declarations)
        for (SemFunction *f = sem_functions; f; f = f->next)
            if (!f->defined)
                sem_error(18, f->first_line, "Declared function \"%s\" is not defined", f->name);
    sem_leave();
    sem_functions = NULL;
    return sem_errors;
}
