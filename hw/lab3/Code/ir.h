#ifndef CMM_IR_H
#define CMM_IR_H
#include "tree.h"
int ir_check_syntax(Node *root);
int ir_generate(Node *root, const char *output_path);
#endif
