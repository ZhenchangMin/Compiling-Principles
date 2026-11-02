# 实验三：中间代码生成

实现必做内容，**只完成选做 3.2**（一维数组参数、高维数组变量）。未实现选做 3.1 的结构体翻译，没有 `--all` 等额外选做开关。只有类型定义而没有结构体变量或参数时，无须生成结构体 IR，不因此拒绝。词法/语法/语义前端沿用 lab1、lab2，新增类型与符号注解及独立 IR 模块。

## 编译与使用

Ubuntu / WSL 中安装 GCC、Flex、Bison、make 后：

```bash
cd Code
make clean
make
./parser ../examples/arrays.cmm ../examples/arrays.ir
```

接口：`./parser 输入文件 输出文件`。成功返回 0、控制台无输出，IR 写入输出文件，每行一条指令。解析器只依赖 C 标准库，不依赖 Python、PyQt、libfl、liby。请在 Linux/WSL 中重新编译，提交包不附平台相关二进制。

支持：整数表达式、初始化与赋值、六种比较、短路与/或/非、if/else、while、递归、普通函数调用、read/write、一维局部数组、多维局部数组、数组整体赋值/初始化及一维数组引用传参。write 返回 0；数组形参中的写入会改变原数组；实参从左到右计算、从右到左 ARG，PARAM 按声明顺序。

## 错误与未支持范围

错误信息写到 stdout，输出文件中不混入诊断。有词法、语法、语义错误或不支持的翻译范围时返回 1，不创建或修改指定 IR 文件。文件或命令行参数错误写入 stderr 并返回 1。

```text
Error type A at Line L: description.
Error type B at Line L: description.
Error type N at Line L: description.
```

对未选择的 3.1，严格输出手册提示（末尾换行）：

```text
Cannot translate: Code contains variables or parameters of structure type.
```

其他超出实验假设的输入：

| 输入 | stdout 提示 |
| --- | --- |
| 浮点变量/常量 | `Cannot translate: Code contains floating-point constants or variables.` |
| 全局变量的实际读写 | `Cannot translate: Code contains global variables.` |
| 高维数组形参 | `Cannot translate: Code contains parameters of multi-dimensional array type.` |
| 长度非正或总大小超过 INT_MAX 的数组 | `Cannot translate: Array size must be positive and fit in 32-bit memory.` |
| 函数声明 | `Error type B at Line L: Function declarations are disabled in this mode.` |

3.2 已实现，因此不使用“高维数组或数组参数不能翻译”的整体拒绝提示；仅拒绝仍在假设外的高维形参。沿用前端对词法错误、语法错误和整数/数组语义错误的编号与行号。含结构体变量或参数、浮点的输入在语义分析前拒绝；全局变量仅声明而未使用时忽略，实际读写仍拒绝。

## 验证

```bash
cd Code
make test
```

164/164 项测试通过，涵盖手册样例、递归、循环、1～4 维数组、数组参数别名与转传、短路副作用、嵌套调用、实参快照、负数除法、变量/标号冲突和各类错误。标准测试只需要 Python 3 标准库。测试文件中内嵌源程序，不依赖未打包的临时数据。

严格编译和检测版本：

```bash
make clean
make CFLAGS='-std=c99 -D_POSIX_C_SOURCE=200809L -Wall -Wextra -Werror -pedantic -O2'
make clean
make CFLAGS='-std=c99 -D_POSIX_C_SOURCE=200809L -Wall -Wextra -Werror -pedantic -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -no-pie'
ASAN_OPTIONS=detect_leaks=1 python3 ../tests/run_tests.py ./parser --results ../tests/results_sanitizers.json
```

普通及检测版本均通过 164/164；130 个合法输入另外通过所提供原版 irsim.pyc 的语法检查和执行。测试记录见 tests/results*.json。

### 使用所给 irsim 复核

`irsim/note.txt` 要求 `python3.8 irsim.pyc`。其 GUI 需要 PyQt5；本目录不改写、也不复制原模拟器字节码。测试适配器只替换 Qt 界面入口和输入输出部件，运行原有 IRSim 类中的检查、内存、调用和执行方法。

先用普通 Python 保存全部合法 IR（以下在 lab3 根目录）：

```bash
python3 tests/run_tests.py Code/parser --keep generated
```

再用 Python 3.8 执行：

```bash
python3.8 tests/run_official_irsim.py irsim/irsim.pyc generated/manifest.json tests/results_official_irsim.json
```

也可使用 GUI 打开 examples/*.ir；输入值见 examples/README.md。模拟器的原始代码将 `/` 转换成 Python `//`，本编译器对运行时除法先除幅值、再恢复符号，保证例如 -7/3 得到 -2。

## 文件与提交

- `Code/`：Flex/Bison/C 源码、头文件和 Makefile。
- `report.pdf`：用户现有实验报告，本次修复保持文件内容不变。
- `实验报告.md`：可编辑报告。
- `examples/`：手册对应源码与生成 IR；含拒绝结构体示例。
- `tests/`：独立执行器、原版 irsim 适配器与验证记录。
- `proj3_fixed.zip`：**仅包含 Code/ 与 report.pdf**，用于提交。

不修改 lab1、lab2；lab3 原始说明、irsim/ 和 irsim.rar 均保留。

提交 ZIP 已解压到独立目录，从源码并行严格编译成功，并通过 164/164 项测试；记录见 tests/results_package.json。

## 本次隐藏测试排查

评测第 2 组只有 A-3 失败；没有其源码及诊断输出，无法确认触发条件。已复现并修复两处过度拒绝：

- 旧版将数组整体赋值和初始化当成不支持的操作，直接返回 1；新版按相对地址复制，复制到源数组或目标数组结束为止，不重绑定数组参数地址。
- 旧版只要出现全局变量声明就拒绝；新版允许未使用的声明，仍拒绝实际读写。

选做范围仍只有 3.2；结构体的拒绝提示不变。未修改 report.pdf 和实验报告.md，新包内 PDF 与用户当前 report.pdf 的 SHA256 一致。新增回归覆盖数组复制后的独立性、不同长度、链式赋值、多维数组与行复制、参数别名及未使用的全局声明。能否通过隐藏 A-3 需重新提交验证。
