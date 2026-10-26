# Benchmarks

The pilot is scored on **already-solved, published public rare-disease cases** with the
known answer hidden from the agents. This measures a research protocol — it is not advice
to any person, and uses no real private patient data.

## Case format

Each case is a JSON file in `cases/` matching `src.utils.schema.CaseInput`, PLUS a hidden
ground-truth answer kept OUT of the case file the agents see (store answers separately in
`cases/_answers.json`, gitignored if they would reveal benchmark solutions).

## Scoring

`score.py` computes top-1 and top-5 hit rate: did the correct causal gene/variant appear
in the agents' ranked candidates, and at what rank. Run-to-run improvement is tracked so we
can see whether the protocol gets better as it iterates.

```bash
python -m benchmarks.score --cases benchmarks/cases --out benchmarks/results
```

## First task (Day 1)

Assemble 3–5 solved public cases across different genes and disease types. Expand to 10–20.
