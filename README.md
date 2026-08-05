# CocoByte

CocoByte is a small bird-themed programming language together with a complete interpreter
for it, written from scratch in Python. The interpreter implements every classic front-end
stage — lexical analysis, parsing, semantic analysis and execution — and exposes each stage
through a Flask HTTP API so a browser front-end can display exactly what the compiler is
doing at every step. The result is a teaching tool: you type CocoByte code on the left, press
Run, and step through the token stream, the abstract syntax tree, the semantic report and the
program output on the right.

## How it works

The interpreter is a four-phase pipeline, all implemented in `CocoByte/app.py`:

1. **Scanner (lexer)** — a single master regular expression (`TOKEN_RE`) drives a
   `finditer` loop that classifies each match as a string, number, operator, parenthesis,
   comma, comment, whitespace or word. Words are looked up against the keyword set and
   emitted as either `KEYWORD` or `IDENTIFIER`. Every token carries its source line, and an
   unrecognised character raises a `LexError` naming the character and line.
2. **Parser** — a hand-written recursive-descent parser produces a dictionary-based AST
   (`Program`, `Assign`, `Print`, `If`, `Loop`, `FunctionDef`, `Return`, `Call`, `BinOp`,
   `UnaryOp`, `Identifier`, `Number`, `String`, `Bool`). Expression parsing is layered so
   precedence falls out naturally: `or` → `and` → `not` → comparison → additive →
   multiplicative → unary → primary. Blocks are terminated by the `land` keyword, and a
   missing `land` raises a `ParseError`.
3. **Semantic analyzer** — walks the AST with a stack of scopes. It pre-declares all
   top-level functions so mutual and forward references work, then reports undeclared
   variables, calls to undeclared functions, arity mismatches between a call and its
   definition, and warns about `give` (return) used outside a function. Errors and warnings
   are collected with line numbers rather than thrown, so the front-end can list them all.
4. **Executor** — a tree-walking interpreter. Scopes are `Environment` objects chained by a
   `parent` pointer, which gives functions proper closures; a function value is stored as a
   record holding its AST node plus the environment it was defined in. `return` is
   implemented by raising a `ReturnSignal` exception caught at the call boundary. Runtime
   guards cover division by zero, non-numeric loop counts, calling a non-function, type
   errors in binary operations, and a recursion depth cap of 500.

Execution only runs if the semantic phase reported no errors, so the front-end can always
show *why* a program was rejected.

## The CocoByte language

| Keyword | Meaning |
| --- | --- |
| `nest` | variable assignment |
| `squawk` | print (accepts multiple comma-separated arguments) |
| `peek` / `then` | if statement |
| `flap` / `times` | counted loop |
| `teach` | function definition |
| `give` | return |
| `land` | end of a block |
| `true`, `false`, `and`, `or`, `not` | booleans and logical operators |

Comments start with `#`. Numbers may be integers or floats, strings use double quotes, and
the operators are `+ - * /` and `< > <= >= == !=`.

A sample program:

```
nest total = 0
flap 5 times
  nest total = total + 1
  squawk(total)
land

teach fibonacci(n) then
  peek n <= 1 then
    give n
  land
  give fibonacci(n-1) + fibonacci(n-2)
land

squawk("Fibonacci of 10 is:", fibonacci(10))
```

## Features

- Complete interpreter pipeline with each phase inspectable in isolation.
- User-defined functions with parameters, recursion and lexical closures.
- Conditionals, counted loops, arithmetic, comparison and boolean logic.
- Error reporting with line numbers at the lexical, syntactic, semantic and runtime levels.
- A single-page web IDE (`index.html`) with a code editor, six built-in example programs
  (hello world, variables and math, if statement, recursive Fibonacci, loop, ASCII parrot)
  and a four-tab stepper for Scanner, Parser, Semantic Analyzer and Output.
- CORS-enabled `POST /run` API: send `{"code": "..."}` and receive
  `{"tokens": [...], "ast": {...}, "semantic": {"ok": bool, "issues": [...]}, "output": [...], "error": null}`.

## Tech stack

- Python 3 and Flask for the interpreter and HTTP API
- Python's `re` module as the lexer engine, `collections.namedtuple` for tokens
- HTML, CSS and vanilla JavaScript (no framework, no build step) for the front-end

## Project structure

```
CocoByte_Compiler_Project_Salhab/
├── CocoByte/
│   ├── app.py                   # Scanner, Parser, Semantic Analyzer, Executor, Flask API
│   ├── index.html               # Single-page web IDE that calls POST /run
│   └── angry_parrot_sound.mp3   # Sound effect played by the front-end
├── Cocobyte_Presentation.pptx   # Course presentation
├── .gitignore
└── README.md
```

## Getting started

```bash
cd CocoByte
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install flask
python app.py
```

The backend starts on `http://127.0.0.1:5000` (the front-end posts to that exact address).
With the server running, open `CocoByte/index.html` directly in a browser, write CocoByte
code in the editor and press **Run**.

## Author

Mohammad Salhab
