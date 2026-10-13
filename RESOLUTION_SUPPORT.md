# ClusterSLM symbol-resolution milestone

This milestone improves the shared graph before adding further language adapters.

## Included

- The symbol index is built from adapter-provided symbol spans, so leaf functions
  and methods are indexed even when they contain no calls.
- Call resolution prefers a unique symbol in the caller's own module, accepts a
  globally unique short-name match, and leaves ambiguous short-name matches
  unresolved rather than inventing edges.
- Unknown external calls are excluded from the graph by default to reduce noisy
  connections between unrelated components. `resolve_call_graph(...,
  include_unresolved=True)` remains available for debugging/legacy visualization.
- Every symbol with a source span is represented as a graph node with language,
  file, kind, and line metadata. A `CONTAINS` edge connects its module to the
  symbol.
- New tests cover leaf functions, ambiguous matches, external-call filtering,
  and graph metadata.

## Current limitations

- Import edges are module-level, not yet symbol-level. Named imports and aliases
  are not yet used to resolve a call to a specific imported symbol.
- Dynamic dispatch, reflection, dependency injection, framework route mapping,
  and cross-language data flow are not resolved by this milestone.
- JavaScript/TypeScript parsing depends on `tree-sitter-language-pack` being
  installed in the active environment. A skipped parser test is not a passing
  parser verification.
- The SLM worker is still mocked unless an external findings JSON is supplied.
  The graph is context infrastructure, not a vulnerability detector by itself.

## Validation

Run from the repository root:

```powershell
python -m unittest discover -s tests -v
```


## Import-aware symbol resolution (next milestone)

The resolver now records import bindings for Python `from ... import ... as ...`, Python module aliases such as `import auth as a`, JavaScript/TypeScript named import aliases, and namespace imports such as `import * as api`. When the imported repository file and symbol can be identified, calls are connected directly to that symbol instead of relying only on a global short-name guess. External imports and unresolved/ambiguous names remain unresolved by design.

This remains static syntax-based resolution: default-export semantics, complex package layouts, dynamic imports, re-exports, TypeScript type resolution, and cross-language runtime bindings are not fully modeled. JavaScript/TypeScript parser tests require `tree-sitter-language-pack`.
