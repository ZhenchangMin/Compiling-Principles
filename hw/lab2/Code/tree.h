#ifndef CMM_TREE_H
#define CMM_TREE_H

/* Flex/Bison 和语义分析共享的语法树结点。空产生式不生成结点，
   查询子结点使用名字，不能假定可空结点始终占据固定下标。 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>

typedef struct Node {
    char name[32];
    char text[128];
    int line, child_count;
    struct Node *children[8];
    struct Node *allocated_next;
} Node;
#endif
