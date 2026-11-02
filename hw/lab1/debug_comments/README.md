# D-3 comment debug suite

Generated to debug Lab1 comment handling independently of the OJ.

## Structure
- cases/: 18 valid-comment programs + 5 invalid-comment edge cases
- controls/: comment-stripped controls preserving line structure for valid cases
- out/: current parser outputs and temporary fully-supported-comment parser outputs

## Main findings
1. Current V19-style behavior produced exactly one Type B on each comment-start line for all 18 valid-comment cases tested.
2. A temporary fully-supported comment lexer produced output exactly equal to the line-preserving comment-stripped control for all 18 valid-comment cases.
3. Edge cases nested/stray right comment produce one error as expected.
4. A fully-supported comment implementation currently has a real EOF-recovery bug for unterminated block comments: it reports both lexical A and parser B on the same line. This is relevant if we later target optional 1.3 / Group3, but it does not explain current Group1 D-3.
5. Since V19 matches our expected D-3-style behavior across these tests but OJ D-3 still fails, the remaining discrepancy is probably in a hidden edge case or in the grader's exact expectation, not the common inline-comment placements.
