# Evaluation

The drift evaluation set is implemented in `scripts/run_eval.py`. It contains 10 hand-written pairs across `New`, `Related`, and `Potential Conflict` labels.

Latest local run:

```text
Decision Drift Eval
cases=10 correct=10 accuracy=100.00%
01 expected=Potential Conflict actual=Potential Conflict ok=True
02 expected=Related actual=Related ok=True
03 expected=New actual=New ok=True
04 expected=Potential Conflict actual=Potential Conflict ok=True
05 expected=Related actual=Related ok=True
06 expected=New actual=New ok=True
07 expected=Potential Conflict actual=Potential Conflict ok=True
08 expected=Related actual=Related ok=True
09 expected=Potential Conflict actual=Potential Conflict ok=True
10 expected=New actual=New ok=True
```

Decision grounding is checked in `backend/tests/test_pipeline.py`: every extracted decision used in the test includes a verbatim `source_excerpt`.

Known evaluation limitation: the current extractor is deterministic and conservative. It is suitable for offline proof of workflow semantics, but production LLM extraction should be evaluated on a larger human-labeled transcript set.
