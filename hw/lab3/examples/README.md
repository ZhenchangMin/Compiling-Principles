# 样例

| 文件 | 输入 | 运行结果 |
| --- | --- | --- |
| sign.cmm / sign.ir | 一个整数 n | 输出 n 的符号：-1、0 或 1 |
| factorial.cmm / factorial.ir | 一个非负整数 m | 输出 m!（例如 6 → 720） |
| arrays.cmm / arrays.ir | 无 | 输出 1、3；对应选做 3.2 手册样例 |
| structure_rejected.cmm | 无 | 不生成 IR，输出下列提示并返回 1 |

```text
Cannot translate: Code contains variables or parameters of structure type.
```

在 Code 中运行 `./parser ../examples/arrays.cmm ../examples/arrays.ir`。IR 可用用户提供的 irsim GUI 打开；read 通过 GUI 输入框提供整数。手册原始样例中的格式排版做了紧凑处理，程序内容保持一致。
