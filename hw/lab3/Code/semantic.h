#ifndef CMM_SEMANTIC_H
#define CMM_SEMANTIC_H
#include "tree.h"
typedef struct SemType SemType;
typedef struct SemField SemField;
typedef struct SemSymbol SemSymbol;
enum SemKind { SEM_INT, SEM_FLOAT, SEM_ARRAY, SEM_STRUCT };
struct SemType {
    enum SemKind kind;
    SemType *element;
    long size;
    SemField *fields;
};
struct SemField {
    const char *name;
    SemType *type;
    int line;
    Node *declaration;
    SemField *next;
};
struct SemSymbol {
    const char *name;
    SemType *type;
    int is_tag, ir_id, is_parameter, is_global;
    SemSymbol *bucket_next, *scope_next;
};
/* Annotations remain valid until semantic_release(), after IR generation. */
int semantic_analyze(Node *program);
void semantic_release(void);
#endif
