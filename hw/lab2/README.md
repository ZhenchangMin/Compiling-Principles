# 实验二：C-- 语义分析

提交默认实现必做错误类型 1–17 和选做 2.2（嵌套作用域），对应平台第 2 组。

## 编译和运行

在 Ubuntu / WSL 中，需要 GCC、Flex、Bison 和 libfl：

~~~bash
cd Code
make clean
make
./parser path/to/input.cmm
~~~

默认只启用嵌套作用域。函数声明报 Type B；结构体采用名等价。
`--all` 仅用于本地对照完整扩展，不是提交默认模式。
如需使用原始必做假设（全局变量作用域、结构体名等价、无函数声明）：

~~~bash
./parser --basic path/to/input.cmm
~~~

合法输入不输出任何内容。语义错误逐条输出到 stdout：
`Error type N at Line L: description.`
语义错误处理完成返回 0；无法打开文件、参数过多时返回 1。
不提供输入文件时从 stdin 读取。

## 文件说明

| 文件 | 内容 |
| --- | --- |
| Code/lexical.l | 沿用 lab1 的扫描器 |
| Code/syntax.y | 语法树、函数声明文法和程序入口 |
| Code/tree.h | 共享语法树结点 |
| Code/semantic.c、semantic.h | 符号表、作用域、类型构造和语义检查 |
| Code/Makefile | 编译与测试 |
| report.pdf | 两页实验报告，正文与页码不小于 11pt |
| 实验报告.md | 报告的可编辑文字版本 |
| tests/run_tests.py | 148 项精确验收测试，含内嵌的 C-- 测试源码 |
| tests/results*.json | 普通版本、内存检测版本与参考编译版本的测试记录 |

## 验证

~~~bash
cd Code
make test
~~~

仅测试脚本需要 Python 3；parser 不依赖 Python。

实测：WSL Ubuntu 24.04，GCC 13.3.0、Flex 2.6.4、Bison 3.8.2。

- 严格编译 `-Wall -Wextra -Werror -pedantic` 通过。
- 普通版本：148/148 项测试通过。
- AddressSanitizer + UndefinedBehaviorSanitizer：148/148 通过，启用泄漏检查。
- lab1 参考 Makefile：本机缺少 liby，在临时副本中去掉冗余的 `-ly` 后编译，148/148 通过；原参考文件未修改。
- PDF 要求中的 17 个必做样例、6 个选做样例均已验证。
- ZIP 解压后可从源码重新编译。

默认数组等价只比较基类型与维数；结构体同一定义共享类型标识，不同定义不等价。
默认函数必须先定义再调用；分析函数体前登记，支持直接递归。

## 提交

提交 `proj2_submission.zip`，只包含 Code/ 与 report.pdf。
README、可编辑报告、测试脚本与结果另存在 lab2 目录，不放入提交 ZIP。不包含生成的 .c 文件、.o 文件和平台相关可执行文件。
