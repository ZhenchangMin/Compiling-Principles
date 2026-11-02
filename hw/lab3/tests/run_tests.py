"""End-to-end translation tests and a small independent IR execution checker.
No third-party packages. Generated IR can also be checked by run_official_irsim.py.
"""
import argparse
import json
import math
from pathlib import Path
import random
import re
import subprocess
import tempfile


def execute_ir(text, inputs):
    code = [line.split() for line in text.splitlines() if line.strip()]
    labels = {c[1]: i for i, c in enumerate(code) if c[0] in ('FUNCTION', 'LABEL')}
    functions = {}
    current = None
    for c in code:
        if c[0] == 'FUNCTION':
            current = c[1]
            functions[current] = {}
        if current:
            for token in c:
                if re.fullmatch(r'[&*]?[vt]\d+', token):
                    functions[current].setdefault(token.lstrip('&*'), 4)
            if c[0] == 'DEC': functions[current][c[1]] = int(c[2])
    memory, next_address, frames, pending, output = {}, 4, [], [], []
    data = iter(inputs)

    def new_frame(name):
        nonlocal next_address
        frame = {}
        for var, size in functions[name].items():
            frame[var] = next_address
            for offset in range(0, size, 4): memory[next_address + offset] = 0
            next_address += size
        return frame

    frame = new_frame('main')

    def value(token):
        if token.startswith('#'): return int(token[1:])
        if token.startswith('&'): return frame[token[1:]]
        if token.startswith('*'): return memory[memory[frame[token[1:]]]]
        return memory[frame[token]]

    def store(token, result):
        address = memory[frame[token[1:]]] if token.startswith('*') else frame[token]
        if address not in memory: raise RuntimeError('Illegal memory access')
        memory[address] = result

    ip, steps = labels['main'], 0
    while 0 <= ip < len(code):
        steps += 1
        if steps > 1000000: raise RuntimeError('Instruction limit exceeded')
        c = code[ip]
        if c[0] in ('LABEL', 'FUNCTION', 'DEC'): pass
        elif c[0] == 'GOTO': ip = labels[c[1]]; continue
        elif c[0] == 'IF':
            a, b = value(c[1]), value(c[3])
            matches = {'==': a == b, '!=': a != b, '>': a > b,
                       '<': a < b, '>=': a >= b, '<=': a <= b}
            if matches[c[2]]: ip = labels[c[5]]; continue
        elif c[0] == 'READ': store(c[1], next(data))
        elif c[0] == 'WRITE': output.append(value(c[1]))
        elif c[0] == 'ARG': pending.append(value(c[1]))
        elif c[0] == 'PARAM': store(c[1], pending.pop())
        elif c[0] == 'RETURN':
            result = value(c[1])
            if not frames: return output, result, steps
            frame, ip, destination = frames.pop()
            store(destination, result)
        elif len(c) == 4 and c[2] == 'CALL':
            frames.append((frame, ip, c[0]))
            frame = new_frame(c[3]); ip = labels[c[3]]; continue
        elif len(c) == 3 and c[1] == ':=': store(c[0], value(c[2]))
        elif len(c) == 5 and c[1] == ':=':
            a, b = value(c[2]), value(c[4])
            result = a + b if c[3] == '+' else a - b if c[3] == '-' else a * b if c[3] == '*' else a // b
            store(c[0], result)
        else: raise RuntimeError('Unrecognized instruction: %r' % c)
        ip += 1
    raise RuntimeError('Program counter out of bounds')


def cases():
    result = []
    def ok(name, source, output, inputs=(), returned=0):
        result.append(dict(name=name, source=source, output=output, input=list(inputs), returned=returned))
    def bad(name, source, diagnostic):
        result.append(dict(name=name, source=source, diagnostic=diagnostic))

    sign = '''int main() {
int n; n = read();
if (n > 0) write(1); else if (n < 0) write(-1); else write(0);
return 0; }'''
    for n in (-15, 0, 27): ok('manual_sign_%s' % n, sign, [(n > 0) - (n < 0)], [n])
    factorial = '''int fact(int n) {
if (n == 1) return n; else return n * fact(n - 1);
}
int main() { int m, result; m = read();
if (m > 1) result = fact(m); else result = 1;
write(result); return 0; }'''
    for n in (0, 1, 2, 6, 9): ok('manual_fact_%s' % n, factorial, [math.factorial(n)], [n])
    arrays = '''int add(int temp[2]) { return temp[0] + temp[1]; }
int main() {
int op[2]; int r[1][2]; int i = 0, j = 0;
while (i < 2) { while (j < 2) { op[j] = i + j; j = j + 1; }
r[0][i] = add(op); write(r[0][i]); i = i + 1; j = 0; }
return 0; }'''
    ok('manual_optional_3_2', arrays, [1, 3])
    bad('manual_optional_3_1_rejected', '''struct Operands { int o1; int o2; };
int add(struct Operands temp) { return temp.o1 + temp.o2; }
int main() { struct Operands op; op.o1 = 1; op.o2 = 2; write(add(op)); return 0; }''',
        r'^Cannot translate: Code contains variables or parameters of structure type\.\n$')
    ok('arithmetic_precedence', 'int main(){write(2+3*4-18/3); write((2+3)*4); return 0;}', [8,20])
    ok('unary_negation', 'int main(){int a=read();write(-a);write(-(-a));return 0;}', [-7,7], [7])
    ok('write_returns_zero', 'int main(){int x;x=write(8);write(x);return write(3);}', [8,0,3])
    ok('read_discarded', 'int main(){read();write(read());return 0;}', [9], [4,9])
    ok('nested_calls', '''int f(int x){return x+1;}
int g(int x,int y,int z){return x*100+y*10+z;}
int main(){write(g(f(1),f(f(1)),f(3)));return 0;}''', [234])
    ok('arg_value_snapshot', '''int f(int a,int b){return a*10+b;}
int main(){int x=1;write(f(x,x=3));write(x);return 0;}''',[13,3])
    ok('arithmetic_snapshot', 'int main(){int x=2;write(x+(x=5));write(x);return 0;}', [7,5])
    ok('relation_snapshot', 'int main(){int x=2;write(x<(x=5));write(x);return 0;}', [1,5])
    ok('nested_assignment', 'int main(){int a,b,c;a=b=c=7;write(a+b+c);return 0;}',[21])
    ok('assignment_result_snapshot', 'int main(){int x;write((x=1)+(x=2));return 0;}',[3])
    ok('condition_assignment', 'int main(){int x=0;if(x=2)write(x);while(x=x-1)write(x);return 0;}',[2,1])
    ok('dangling_else', 'int main(){if(1)if(0)write(1);else write(2);return 0;}',[2])
    ok('short_circuit_skip', 'int main(){int x=0;0&&(x=1);1||(x=2);write(x);write(0&&read());write(1||read());return 0;}',[0,0,1])
    ok('short_circuit_calls', 'int main(){int x=0;1&&(x=3);0||(x=4);write(x);write(!x);return 0;}',[4,0])
    ok('logical_value_normalized', 'int main(){write(2&&3);write(0||9);write(!0);write(!!3);return 0;}',[1,1,1,1])
    ok('nested_logic', 'int main(){int x=0;if((0||1)&&!(0&&read()))x=7;write(x);return 0;}',[7])
    ok('relation_all', 'int main(){write(1<2);write(1>2);write(2<=2);write(3>=2);write(1==1);write(1!=1);return 0;}',[1,0,1,1,1,0])
    ok('array_basic', 'int main(){int a[4];int i=0;while(i<4){a[i]=i*i;i=i+1;}write(a[0]+a[1]+a[2]+a[3]);return 0;}',[14])
    ok('array_2d_stride', 'int main(){int a[2][3];int i=0,j;while(i<2){j=0;while(j<3){a[i][j]=10*i+j;j=j+1;}i=i+1;}write(a[0][2]);write(a[1][0]);write(a[1][2]);return 0;}',[2,10,12])
    ok('array_3d_stride', 'int main(){int a[2][3][4];int i=0,j,k;while(i<2){j=0;while(j<3){k=0;while(k<4){a[i][j][k]=i*100+j*10+k;k=k+1;}j=j+1;}i=i+1;}write(a[0][2][3]);write(a[1][0][0]);write(a[1][2][3]);return 0;}',[23,100,123])
    ok('array_4d', 'int main(){int a[2][2][3][4];a[1][1][2][3]=91;write(a[1][1][2][3]);return 0;}',[91])
    ok('array_param_write_through', '''int set(int a[3],int x){a[1]=x;return a[1];}
int main(){int b[3];b[1]=2;write(set(b,8));write(b[1]);return 0;}''',[8,8])
    ok('array_param_forward', '''int set(int a[3]){a[2]=11;return 0;}
int forward(int b[3]){return set(b);}
int main(){int c[3];forward(c);write(c[2]);return 0;}''',[11])
    ok('array_param_alias', '''int set(int a[2],int b[2]){a[0]=3;b[1]=a[0]+1;return b[0];}
int main(){int c[2];write(set(c,c));write(c[1]);return 0;}''',[3,4])
    ok('array_row_as_1d', '''int add(int a[3]){return a[0]+a[1]+a[2];}
int main(){int m[2][3];m[1][0]=2;m[1][1]=3;m[1][2]=4;write(add(m[1]));return 0;}''',[9])
    ok('array_subscript_effect', 'int main(){int a[3];int i=0;a[i=i+1]=i+4;write(a[1]);write(i);return 0;}',[5,1])
    ok('array_rhs_mutation', '''int change(int a[2]){a[0]=9;return 2;}
int main(){int b[2];b[0]=1;write(b[0]+change(b));write(b[0]);return 0;}''',[3,9])
    ok('array_assignment_result', 'int main(){int a[2];int x=3;write((a[0]=x)+(x=8));write(a[0]);return 0;}',[11,3])
    ok('array_parenthesized', 'int main(){int a[2];(a)[1]=5;write((a[1]));return 0;}',[5])
    ok('recursive_array', '''int sum(int a[4],int n){if(n==0)return 0;return a[n-1]+sum(a,n-1);}
int main(){int b[4];b[0]=1;b[1]=2;b[2]=3;b[3]=4;write(sum(b,4));return 0;}''',[10])
    ok('recursive_local_array', '''int f(int n){int a[2];a[0]=n;a[1]=n+1;if(n==0)return a[1];return a[0]+f(n-1)+a[1];}
int main(){write(f(4));return 0;}''',[25])
    ok('recursive_fibonacci', '''int fib(int n){if(n<2)return n;return fib(n-1)+fib(n-2);}
int main(){write(fib(10));return 0;}''',[55])
    ok('nested_loop', 'int main(){int i=0,j,s=0;while(i<5){j=0;while(j<i){s=s+1;j=j+1;}i=i+1;}write(s);return 0;}',[10])
    ok('early_return', 'int f(int x){if(x)return 7;return 3;}int main(){write(f(1));write(f(0));return 0;}',[7,3])
    ok('unused_pure_expression', 'int main(){int x=1;x+3;!x;write(x);return 0;}',[1])
    ok('discard_nested_effects', 'int main(){int x=0;-(x=2)+(x=3);write(x);return 0;}',[3])
    ok('case_sensitive', 'int main(){int a=2,A=3;write(a*10+A);return 0;}',[23])
    ok('label_collision', 'int label1(int x){if(x)return 1;return 2;}int main(){if(1)write(label1(0));return 0;}',[2])
    ok('ir_name_collision', 'int main(){int t1=4,v1=2,label1=3;write(t1+v1+label1);return 0;}',[9])
    ok('unused_structure_type_only', 'struct S{int x;};int main(){write(3);return 0;}',[3])
    ok('unused_global_declaration', 'int unused;int main(){write(3);return 0;}',[3])
    ok('unused_global_array', 'int unused[3];int main(){int a[2];a[0]=5;write(a[0]);return 0;}',[5])
    for a,b in [(7,3),(-7,3),(7,-3),(-7,-3),(6,-3),(-6,3),(0,-3),(1,2),(-1,2),(-2147483648,3)]:
        expected = abs(a)//abs(b) * (-1 if (a<0)!=(b<0) else 1)
        ok('division_runtime_%s_%s' % (a,b), 'int main(){int a=read(),b=read();write(a/b);return 0;}',[expected],[a,b])
        ok('division_constant_%s_%s' % (a,b), 'int main(){write((%s)/(%s));return 0;}'%(a,b),[expected])
    for a,b in [(-3,4),(0,0),(7,-2),(9,9)]:
        ok('dynamic_relations_%s_%s'%(a,b), 'int main(){int a=read(),b=read();write(a<b);write(a>b);write(a<=b);write(a>=b);write(a==b);write(a!=b);return 0;}',
           [int(a<b),int(a>b),int(a<=b),int(a>=b),int(a==b),int(a!=b)],[a,b])
    rng = random.Random(301)
    for i in range(35):
        a,b,c,d = [rng.randint(-20,20) for _ in range(4)]
        ok('random_arithmetic_%02d'%i, 'int main(){int a=read(),b=read(),c=read(),d=read();write((a+b)*(c-d)-a*c);return 0;}',[(a+b)*(c-d)-a*c],[a,b,c,d])
    for size in range(1,9):
        ok('array_sum_%s'%size, '''int sum(int a[%s],int n){int i=0,s=0;while(i<n){s=s+a[i];i=i+1;}return s;}
int main(){int b[%s];int i=0;while(i<%s){b[i]=i*3+1;i=i+1;}write(sum(b,%s));return 0;}'''%(size,size,size,size),[sum(i*3+1 for i in range(size))])
    bad('undefined_variable','int main(){return x;}',r'^Error type 1 at Line 1: Undefined variable "x"\.\n$')
    bad('undefined_function','int main(){return f();}',r'^Error type 2 at Line 1: Undefined function "f"\.\n$')
    bad('duplicate_variable','int main(){int a,a;return 0;}',r'^Error type 3 at Line 1:')
    bad('duplicate_function','int f(){return 0;}int f(){return 0;}int main(){return 0;}',r'^Error type 4 at Line 1:')
    bad('bad_assignment','int main(){int a[2];int b;a=b;return 0;}',r'^Error type 5 at Line 1:')
    bad('non_lvalue','int main(){1=2;return 0;}',r'^Error type 6 at Line 1:')
    bad('bad_operands','int main(){int a[2];return a+1;}',r'^Error type 7 at Line 1:')
    bad('bad_return','int main(){int a[2];return a;}',r'^Error type 8 at Line 1:')
    bad('read_arity','int main(){return read(1);}',r'^Error type 9 at Line 1:')
    bad('write_arity','int main(){return write();}',r'^Error type 9 at Line 1:')
    bad('write_array','int main(){int a[2];return write(a);}',r'^Error type 9 at Line 1:')
    bad('not_array','int main(){int a;return a[0];}',r'^Error type 10 at Line 1:')
    bad('not_function','int main(){int a;return a();}',r'^Error type 11 at Line 1:')
    bad('array_index_array','int main(){int a[2],b[2];return a[b];}',r'^Error type 12 at Line 1:')
    bad('builtin_redefinition','int read(){return 0;}int main(){return 0;}',r'^Error type 4 at Line 1:')
    bad('function_declaration','int f();int main(){return 0;}',r'^Error type B at Line 1: Function declarations are disabled')
    bad('lexical_error','int main(){return @1;}',r'^Error type A at Line 1:')
    bad('syntax_error','int main(){return ;}',r'^Error type B at Line 1:')
    bad('syntax_line','int main(){\nint a\nreturn 0;\n}',r'^Error type B at Line 2:')
    bad('global_rejected','int a;int main(){return a;}',r'^Cannot translate: Code contains global variables\.\n$')
    bad('global_store_rejected','int a;int main(){a=3;return 0;}',r'^Cannot translate: Code contains global variables\.\n$')
    bad('global_array_use_rejected','int a[2];int main(){return a[0];}',r'^Cannot translate: Code contains global variables\.\n$')
    bad('float_rejected','int main(){float a;return 0;}',r'^Cannot translate: Code contains floating-point constants or variables\.\n$')
    bad('float_literal_rejected','int main(){return 1.0;}',r'^Cannot translate: Code contains floating-point constants or variables\.\n$')
    bad('struct_array_rejected','struct S{int x;};int main(){struct S a[2];return 0;}',r'^Cannot translate: Code contains variables or parameters of structure type\.\n$')
    bad('multidim_param_rejected','int f(int a[2][3]){return a[0][0];}int main(){return 0;}',r'^Cannot translate: Code contains parameters of multi-dimensional array type\.\n$')
    bad('zero_array_rejected','int main(){int a[0];return 0;}',r'^Cannot translate: Array size must be positive and fit in 32-bit memory\.\n$')
    bad('huge_array_rejected','int main(){int a[1000000000];return 0;}',r'^Cannot translate: Array size must be positive and fit in 32-bit memory\.\n$')
    ok('array_assignment_copy', 'int main(){int a[3],b[3];b[0]=7;b[1]=8;b[2]=9;a=b;b[0]=99;write(a[0]);write(a[1]);write(a[2]);return 0;}',[7,8,9])
    ok('array_initializer_copy', 'int main(){int a[2];int x=(a[0]=5),y=(a[1]=6);int b[2]=a;a[0]=9;write(b[0]);write(b[1]);return 0;}',[5,6])
    ok('array_copy_short_target', 'int main(){int a[2],b[3];b[0]=1;b[1]=2;b[2]=3;a=b;write(a[0]);write(a[1]);return 0;}',[1,2])
    ok('array_copy_short_source', 'int main(){int a[3],b[2];a[2]=9;b[0]=1;b[1]=2;a=b;write(a[0]);write(a[1]);write(a[2]);return 0;}',[1,2,9])
    ok('array_copy_self', 'int main(){int a[2];a[0]=3;a[1]=4;a=a;write(a[0]);write(a[1]);return 0;}',[3,4])
    ok('array_copy_chain', 'int main(){int a[2],b[2],c[2];c[0]=5;c[1]=6;a=b=c;c[0]=9;write(a[0]);write(a[1]);write(b[0]);write(b[1]);return 0;}',[5,6,5,6])
    ok('array_copy_indexed_result', 'int main(){int a[2],b[2];b[0]=7;b[1]=8;write((a=b)[1]);return 0;}',[8])
    ok('array_copy_multidim', 'int main(){int a[2][3],b[2][3];int i=0,j;while(i<2){j=0;while(j<3){b[i][j]=i*10+j;j=j+1;}i=i+1;}a=b;b[1][2]=99;write(a[0][2]);write(a[1][0]);write(a[1][2]);return 0;}',[2,10,12])
    ok('array_copy_row', 'int main(){int a[2][3];a[0][0]=2;a[0][1]=3;a[0][2]=4;a[1]=a[0];a[0][0]=9;write(a[1][0]);write(a[1][1]);write(a[1][2]);return 0;}',[2,3,4])
    ok('array_copy_param', 'int copy(int a[2],int b[2]){a=b;a[1]=8;return a[0];}int main(){int c[2],d[2];d[0]=5;d[1]=6;write(copy(c,d));write(c[1]);write(d[1]);return 0;}',[5,8,6])
    ok('array_copy_param_alias', 'int copy(int a[2],int b[2]){a=b;a[1]=9;return b[1];}int main(){int c[2];c[0]=3;c[1]=4;write(copy(c,c));write(c[0]);return 0;}',[9,3])
    ok('array_copy_large', 'int main(){int a[100],b[100];int i=0,s=0;while(i<100){b[i]=i;i=i+1;}a=b;i=0;while(i<100){s=s+a[i];i=i+1;}write(s);return 0;}',[4950])
    return result


def main():
    arg = argparse.ArgumentParser()
    arg.add_argument('parser')
    arg.add_argument('--keep', type=Path)
    arg.add_argument('--results', type=Path, default=Path(__file__).with_name('results.json'))
    args = arg.parse_args()
    parser = str(Path(args.parser).resolve())
    temp = tempfile.TemporaryDirectory()
    directory = args.keep or Path(temp.name)
    directory.mkdir(parents=True, exist_ok=True)
    results, manifest = [], []
    for case in cases():
        source, ir = directory/(case['name']+'.cmm'), directory/(case['name']+'.ir')
        source.write_text(case['source'], encoding='utf-8')
        # Error inputs must never truncate or replace an existing IR file.
        ir.write_text('SENTINEL\n', encoding='ascii')
        try:
            process = subprocess.run([parser, str(source), str(ir)], capture_output=True, text=True, timeout=10)
            assert not process.stderr, process.stderr
            if 'diagnostic' in case:
                assert process.returncode != 0, process.returncode
                assert re.search(case['diagnostic'],process.stdout), repr(process.stdout)
                assert ir.read_text() == 'SENTINEL\n', 'Error input modified output'
                results.append(dict(name=case['name'],passed=True,diagnostic=process.stdout.strip()))
            else:
                assert process.returncode == 0, (process.returncode,process.stdout)
                assert process.stdout == '', repr(process.stdout)
                actual, returned, steps = execute_ir(ir.read_text(), case['input'])
                assert actual == case['output'], (actual,case['output'])
                assert returned == case['returned'], (returned,case['returned'])
                results.append(dict(name=case['name'],passed=True,instructions=steps))
                manifest.append(dict(name=case['name'],ir=ir.name,input=case['input'],output=case['output']))
        except Exception as error:
            results.append(dict(name=case['name'],passed=False,error=str(error)))
    # CLI failures are separate from source diagnostics and use stderr.
    for name, argv in [('missing_args',[]),('too_many_args',['a','b','c']),
                       ('missing_input',[str(directory/'missing.cmm'),str(directory/'out.ir')]),
                       ('same_file',[str(source),str(source)]),
                       ('output_missing_directory',[str(directory/'manual_sign_0.cmm'),str(directory/'missing'/'a.ir')])]:
        p = subprocess.run([parser]+argv,capture_output=True,text=True)
        results.append(dict(name=name,passed=p.returncode!=0 and bool(p.stderr)))
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    summary = dict(passed=sum(c['passed'] for c in results),total=len(results),cases=results)
    args.results.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print('%s/%s tests passed'%(summary['passed'],summary['total']))
    for c in results:
        if not c['passed']: print(c)
    temp.cleanup()
    return int(summary['passed']!=summary['total'])


if __name__ == '__main__': raise SystemExit(main())
