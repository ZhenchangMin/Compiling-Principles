#ifndef CMM_SEMANTIC_H
#define CMM_SEMANTIC_H
#include "tree.h"
enum SemanticMode {
    SEM_MODE_SCOPE_ONLY = 0, /* 默认提交：只启用选做 2.2 */
    SEM_MODE_BASIC = 1,
    SEM_MODE_ALL = 2         /* 本地对照，必须明确使用 --all */
};
void semantic_analyze(Node *program, int mode);
#endif
