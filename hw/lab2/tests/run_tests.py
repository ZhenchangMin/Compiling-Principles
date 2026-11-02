#!/usr/bin/env python3
"""验收测试：精确比较错误编号与行号；合法输入要求 stdout 完全为空。"""
import collections
import json
import pathlib
import re
import subprocess
import sys
import tempfile

CASES = []
def add(name, source, expected=(), basic=False):
    CASES.append((name, source, list(expected), basic))

# 要求 PDF 中的 17 个必做样例（代码行号保持与原文一致）。
official = [
("int main()\n{\n int i = 0;\n j = i + 1;\n}\n", [(1,4)]),
("int main()\n{\n int i = 0;\n inc(i);\n}\n", [(2,4)]),
("int main()\n{\n int i, j;\n int i;\n}\n", [(3,4)]),
("int func(int i)\n{\n return i;\n}\n\nint func()\n{\n return 0;\n}\n\nint main()\n{\n}\n", [(4,6)]),
("int main()\n{\n int i;\n i = 3.7;\n}\n", [(5,4)]),
("int main()\n{\n int i;\n 10 = i;\n}\n", [(6,4)]),
("int main()\n{\n float j;\n 10 + j;\n}\n", [(7,4)]),
("int main()\n{\n float j = 1.7;\n return j;\n}\n", [(8,4)]),
("int func(int i)\n{\n return i;\n}\n\nint main()\n{\n func(1, 2);\n}\n", [(9,8)]),
("int main()\n{\n int i;\n i[0];\n}\n", [(10,4)]),
("int main()\n{\n int i;\n i(10);\n}\n", [(11,4)]),
("int main()\n{\n int i[10];\n i[1.5] = 10;\n}\n", [(12,4)]),
("struct Position\n{\n float x, y;\n};\n\nint main()\n{\n int i;\n i.x;\n}\n", [(13,9)]),
("struct Position\n{\n float x, y;\n};\n\nint main()\n{\n struct Position p;\n if (p.n == 3.7)\n return 0;\n}\n", [(14,9)]),
("struct Position\n{\n float x, y;\n int x;\n};\n\nint main()\n{\n}\n", [(15,4)]),
("struct Position\n{\n float x;\n};\n\nstruct Position\n{\n int y;\n};\n\nint main()\n{\n}\n", [(16,6)]),
("int main()\n{\n struct Position pos;\n}\n", [(17,3)]),
]
for i, (src, expected) in enumerate(official, 1):
    add("official_required_%02d" % i, src, expected)
    add("basic_required_%02d" % i, src, expected, True)

# PDF 的六个选做样例。
optional = [
("int func(int a);\n\nint func(int a)\n{\n return 1;\n}\n\nint main()\n{\n}\n", []),
("struct Position\n{\n float x,y;\n};\n\nint func(int a);\n\nint func(struct Position p);\n\nint main()\n{\n}\n", [(19,8),(18,6)]),
("int func()\n{\n int i = 10;\n return i;\n}\n\nint main()\n{\n int i;\n i = func();\n}\n", []),
("int func()\n{\n int i = 10;\n return i;\n}\n\nint main()\n{\n int i;\n int i, j;\n i = func();\n}\n", [(3,10)]),
("struct Temp1\n{\n int i;\n float j;\n};\n\nstruct Temp2\n{\n int x;\n float y;\n};\n\nint main()\n{\n struct Temp1 t1;\n struct Temp2 t2;\n t1 = t2;\n}\n", []),
("struct Temp1\n{\n int i;\n float j;\n};\n\nstruct Temp2\n{\n int x;\n};\n\nint main()\n{\n struct Temp1 t1;\n struct Temp2 t2;\n t1 = t2;\n}\n", [(5,16)]),
]
for i, (src, expected) in enumerate(optional, 1):
    add("official_optional_%02d" % i, src, expected)
add("basic_global_variables", optional[2][0], [(3,9)], True)
add("basic_global_duplicates", optional[3][0], [(3,9),(3,10)], True)
add("basic_nominal_types", optional[4][0], [(5,17)], True)
add("basic_nominal_mismatch", optional[5][0], [(5,16)], True)

add("empty", "")
add("valid_arithmetic", "int main(){int a;float b;a=(1+2)*3/4-5;b=-1.2+2.3;return !a;}")
add("valid_float_comparison", "int main(){float a; a=1.0;if(a<2.0)return 1;else return 0;}")
add("array_dimensions_sizes", "int main(){int a[2][3],b[5][7];a=b;return a[1][2];}")
add("array_dimension_mismatch", "int main(){int a[2][3],b[5];\na=b;}", [(5,2)])
add("array_base_mismatch", "int main(){int a[2];float b[2];\na=b;}", [(5,2)])
add("array_parameter", "int f(int a[2][3]){return a[1][2];}\nint main(){int b[4][5];return f(b);}")
add("array_parameter_dimension", "int f(int a[2][3]){return a[1][2];}\nint main(){int b[4];return f(b);}", [(9,2)])
add("array_bad_second_index", "int main(){int a[2][3];\na[1][2.0]=1;}", [(12,2)])
add("array_too_many_indices", "int main(){int a[2];\na[0][0];}", [(10,2)])
add("array_index_multiline", "int main(){int a[2];\na[\n1.0];}", [(12,3)])
add("scalar_index_and_float", "int main(){int a;\na[1.0];}", [(10,2),(12,2)])
add("struct_initialization", "struct A {\nint a=1;\n};", [(15,2)])
add("variable_tag_collision", "struct A{int x;};\nint A;", [(3,2)])
add("tag_variable_collision", "int A;\nstruct A{int x;};", [(16,2)])
add("field_names_are_local", "struct A{int x;};struct B{int x;};int x;int main(){struct A a; a.x=x;}")
add("nominal_same_definition", "struct A{int x;};int main(){struct A a,b;a=b;}", (), True)
add("nominal_anonymous_unique", "int main(){struct{int x;}a;struct{int y;}b;\na=b;}", [(5,2)], True)
add("nominal_anonymous_shared", "int main(){struct{int x;}a,b;a=b;}", (), True)
add("structural_anonymous", "int main(){struct{int x;}a;struct{int y;}b;a=b;}")
add("structural_order", "struct A{int x;float y;};struct B{float a;int b;};\nint main(){struct A a;struct B b;a=b;}", [(5,2)])
add("structural_nested_array", "struct A{int x;struct{float f;int i;}b[10];};\nstruct B{struct{int i;float f;}b[10];int c;};\nint main(){struct A a;struct B b;a=b;}", [(5,3)])
add("structural_nested_equal", "struct A{int x;struct{float f;int i;}b[10];};\nstruct B{int z;struct{float g;int j;}c[3];};\nint main(){struct A a;struct B b;a=b;}")
add("struct_parameter", "struct A{int x;};struct B{int y;};int f(struct A a){return a.x;}int main(){struct B b;return f(b);}")
add("struct_return", "struct A{int x;};struct A f(){struct A a;return a;}int main(){struct A b;b=f();return b.x;}")
add("struct_return_mismatch", "struct A{int x;};\nint f(){struct A a;return a;}", [(8,2)])
add("struct_member_array", "struct A{float x[2][3];};int main(){struct A a;a.x[0][1]=1.0;return 0;}")
add("scope_shadow_restore", "int x;int main(){x=1;{float x;x=1.0;}x=2;return x;}")
add("scope_disappears", "int main(){{int x;x=1;}\nx=2;}", [(1,2)])
add("scope_siblings", "int main(){{int x;x=1;}{float x;x=1.0;}return 0;}")
add("scope_parameter_duplicate", "int f(int a){\nint a;return a;}", [(3,2)])
add("scope_parameter_shadow", "int f(int a){{float a;a=1.0;}return a;}")
add("scope_parameter_not_visible", "int f(int a){return a;}\nint g(){return a;}", [(1,2)])
add("scope_local_function_shadow", "int f(){return 0;}int main(){{int f;\nf();}\nreturn f();}", [(11,2)])
add("scope_tag_shadow", "struct A{int x;};int main(){{struct A{float y;};struct A a;a.y=1.0;}struct A b;return b.x;}")
# 文法要求块内声明在语句之前，上一条应改为显式嵌套恢复检验。
CASES[-1] = ("scope_tag_shadow", "struct A{int x;};int main(){struct A b;{struct A{float y;}a;a.y=1.0;}return b.x;}", [], False)
add("recursive_function", "int f(int x){if(x)return f(x-1);return 0;}")
add("forward_without_declaration", "int f(){return g();}\nint g(){return 1;}", [(2,1)])
add("forward_with_declaration", "int g();int f(){return g();}int g(){return 1;}")
add("mutual_recursion", "int g(int x);int f(int x){if(x)return g(x-1);return 0;}int g(int y){return f(y);}")
add("declaration_no_definition", "int f(int x);\nint main(){return f(1);}", [(18,1)])
add("declaration_parameters_not_global", "int f(int x);\nint main(){return x;}\nint f(int y){return y;}", [(1,2)])
add("consistent_declarations", "int f(int x);int f(int y);int f(int z){return z;}int f(int a);")
add("conflicting_return", "int f(int x);\nfloat f(int y);\nint f(int z){return z;}", [(19,2)])
add("conflicting_definition", "int f(int x);\nint f(float x){return 0;}", [(19,2)])
add("conflicting_after_definition", "int f(int x){return x;}\nint f(float y);", [(19,2)])
add("duplicate_definition_priority", "int f(){return 0;}\nfloat f(){return 1.0;}", [(4,2)])
add("duplicate_parameter", "int f(int a,\nfloat a){return 0;}", [(3,2)])
add("call_too_few", "int f(int a,float b){return a;}\nint main(){return f(1);}", [(9,2)])
add("call_wrong_type", "int f(int a){return a;}\nint main(){return f(1.0);}", [(9,2)])
add("call_no_arguments", "int f(int a){return a;}\nint main(){return f();}", [(9,2)])
add("call_extra_arguments", "int f(){return 0;}\nint main(){return f(1);}", [(9,2)])
add("call_checks_argument_errors", "int f(int a){return a;}\nint main(){return f(x);}", [(1,2)])
add("undefined_call_checks_args", "int main(){\nf(x);}", [(2,2),(1,2)])
add("condition_float", "int main(){\nif(1.0)return 0;}", [(7,2)])
add("condition_array", "int main(){int a[2];\nwhile(a)a[0]=1;}", [(7,2)])
add("logic_float", "int main(){\n1.0&&2.0;}", [(7,2)])
add("not_float", "int main(){\n!1.0;}", [(7,2)])
add("unary_struct", "struct A{int x;};int main(){struct A a;\n-a;}", [(7,2)])
add("relational_struct", "struct A{int x;};int main(){struct A a,b;\na==b;}", [(7,2)])
add("array_arithmetic", "int main(){int a[2];\na+1;}", [(7,2)])
add("init_type_mismatch", "int main(){\nint a=1.0;}", [(5,2)])
add("lvalue_arithmetic", "int main(){int x;\nx+1=2;}", [(6,2)])
add("lvalue_function", "int f(){return 0;}int main(){\nf()=1;}", [(6,2)])
add("lvalue_assignment_result", "int main(){int x;\n(x=1)=2;}", [(6,2)])
add("lvalue_parenthesized", "int main(){int x;(x)=1;return x;}")
add("multiple_independent_errors", "int main(){\nx=1;\nf();\nreturn 1.0;}", [(1,2),(2,3),(8,4)])
add("invalid_type_suppression", "int main(){\nstruct Missing a;\na.x=1;}", [(17,2)])
add("basic_global_param", "int f(int a){return a;}int g(){return a;}", (), True)
add("basic_block_persists", "int main(){{int a;a=1;}return a;}", (), True)
add("valid_comments", "/* intro */int main(){// local\nint x;x=1;return x;}")
add("syntax_blocks_semantics", "int main(){int x\nreturn x;}", [("B",1)])
add("lexical_blocks_semantics", "int main(){\n~x;}", [("A",2)])

# 默认提交模式：仅选做 2.2。原有全扩展测试使用明确的 --all。
for i, (src, expected) in enumerate(official, 1):
    add("scope_only_required_%02d" % i, src, expected, None)
scope_expected = [[("B",1)], [("B",6),("B",8)], [], [(3,10)], [(5,17)], [(5,16)]]
for i, ((src, _), expected) in enumerate(zip(optional,scope_expected),1):
    add("scope_only_optional_%02d" % i, src, expected, None)
add("scope_only_nested_shadow", "int x;int main(){{float x;x=1.0;}return x;}", (), None)
add("scope_only_function_locals", "int f(){int x;return x;}int g(){int x;return x;}", (), None)
add("scope_only_same_tag", "struct A{int x;};int main(){struct A a,b;a=b;}", (), None)
add("scope_only_distinct_tags", "struct A{int x;};struct B{int y;};\nint main(){struct A a;struct B b;a=b;}", [(5,2)], None)
add("scope_only_anonymous_unique", "int main(){struct{int x;}a;struct{int y;}b;\na=b;}", [(5,2)], None)
add("scope_only_no_decl_cascade", "int f(int x);\nint main(){return f(y);}", [("B",1)], None)
add("scope_only_array_sizes", "int main(){int a[2][3],b[5][7];a=b;return a[1][2];}", (), None)
add("scope_only_scope_exit", "int main(){{int a;a=1;}\nreturn a;}", [(1,2)], None)
add("scope_only_nominal_call", "struct A{int x;};struct B{int y;};int f(struct A p){return p.x;}\nint main(){struct B q;return f(q);}", [(9,2)], None)

def main():
    parser = pathlib.Path(sys.argv[1] if len(sys.argv)>1 else "../Code/parser").resolve()
    records = []
    with tempfile.TemporaryDirectory(prefix="cmm_lab2_") as tmp:
        for name, source, expected, basic in CASES:
            file = pathlib.Path(tmp)/(name+".cmm")
            file.write_text(source, encoding="utf-8")
            cmd = [str(parser)] + (["--basic"] if basic is True else ["--all"] if basic is False else []) + [str(file)]
            result = subprocess.run(cmd, text=True, capture_output=True, timeout=5)
            found = []
            format_ok = True
            for line in result.stdout.splitlines():
                m = re.fullmatch(r"Error type ([0-9]+|[AB]) at Line ([0-9]+): .+\.", line)
                if not m:
                    format_ok = False
                else:
                    number = int(m[1]) if m[1].isdigit() else m[1]
                    found.append((number, int(m[2])))
            passed = (result.returncode == 0 and not result.stderr and format_ok
                      and collections.Counter(found)==collections.Counter(map(tuple,expected)))
            records.append(dict(name=name, basic=basic, passed=passed, expected=expected,
                                actual=found, stdout=result.stdout, stderr=result.stderr,
                                returncode=result.returncode))
            if not passed:
                print("FAIL", name, "expected", expected, "actual", found,
                      "rc", result.returncode, "stdout",repr(result.stdout),"stderr",repr(result.stderr))
    passed = sum(r["passed"] for r in records)
    print("%d/%d tests passed" % (passed,len(records)))
    if "--json" in sys.argv:
        target = pathlib.Path(sys.argv[sys.argv.index("--json")+1])
        target.write_text(json.dumps(dict(passed=passed,total=len(records),tests=records),
                                     ensure_ascii=False,indent=2),encoding="utf-8")
    return 0 if passed==len(records) else 1

if __name__=="__main__":
    raise SystemExit(main())
