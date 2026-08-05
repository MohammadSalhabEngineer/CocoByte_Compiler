import re
import json
from flask import Flask, request, jsonify
from collections import namedtuple

app = Flask(__name__)

@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    return response

# ─────────────────────────────────────────────
# Exceptions & Signal
# ─────────────────────────────────────────────

class LexError(Exception):
    pass

class ParseError(Exception):
    pass

class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value

Token = namedtuple('Token', ['type', 'value', 'line'])

# ─────────────────────────────────────────────
# SCANNER — Lexer
# ─────────────────────────────────────────────

KEYWORDS = {
    'nest', 'squawk', 'peek', 'then', 'land',
    'flap', 'times', 'teach', 'give',
    'true', 'false', 'and', 'or', 'not'
}

TOKEN_RE = re.compile(
    r'(?P<STRING>"([^"\\]|\\.)*")'
    r'|(?P<NUMBER>\d+(?:\.\d+)?)'
    r'|(?P<OP><=|>=|==|!=|[+\-*/<>=])'
    r'|(?P<LPAREN>\()'
    r'|(?P<RPAREN>\))'
    r'|(?P<COMMA>,)'
    r'|(?P<NEWLINE>\n)'
    r'|(?P<SKIP>[ \t\r]+)'
    r'|(?P<COMMENT>#[^\n]*)'
    r'|(?P<WORD>[a-zA-Z_][a-zA-Z0-9_]*)'
    r'|(?P<MISMATCH>.)'
)

def scanner(code):
    tokens = []
    line = 1
    for m in TOKEN_RE.finditer(code):
        kind = m.lastgroup
        val = m.group()
        if kind == 'NEWLINE':
            line += 1
        elif kind in ('SKIP', 'COMMENT'):
            pass
        elif kind == 'MISMATCH':
            raise LexError(f"Unexpected character '{val}' at line {line}")
        elif kind == 'STRING':
            tokens.append(Token('STRING', val[1:-1], line))
        elif kind == 'NUMBER':
            num = float(val) if '.' in val else int(val)
            tokens.append(Token('NUMBER', num, line))
        elif kind == 'OP':
            tokens.append(Token('OPERATOR', val, line))
        elif kind == 'LPAREN':
            tokens.append(Token('LPAREN', val, line))
        elif kind == 'RPAREN':
            tokens.append(Token('RPAREN', val, line))
        elif kind == 'COMMA':
            tokens.append(Token('COMMA', val, line))
        elif kind == 'WORD':
            ttype = 'KEYWORD' if val in KEYWORDS else 'IDENTIFIER'
            tokens.append(Token(ttype, val, line))
    tokens.append(Token('EOF', '', line))
    return tokens

# ─────────────────────────────────────────────
# PARSER — Recursive Descent
# ─────────────────────────────────────────────

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos]

    def advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def consume(self, ttype=None, value=None):
        tok = self.advance()
        if ttype and tok.type != ttype:
            raise ParseError(f"Expected {ttype} but got '{tok.value}' at line {tok.line}")
        if value and tok.value != value:
            raise ParseError(f"Expected '{value}' but got '{tok.value}' at line {tok.line}")
        return tok

    def match_val(self, value):
        if self.peek().value == value:
            return self.advance()
        return None

    def at_end(self):
        return self.peek().type == 'EOF'

    def parse(self):
        body = self.parse_statements(top_level=True)
        return {'node': 'Program', 'body': body}

    def parse_statements(self, top_level=False):
        stmts = []
        while True:
            tok = self.peek()
            if tok.type == 'EOF':
                break
            if tok.type == 'KEYWORD' and tok.value == 'land':
                if not top_level:
                    break
                # stray land at top level — skip it
                self.advance()
                continue
            stmt = self.parse_statement()
            if stmt is not None:
                stmts.append(stmt)
        return stmts

    def parse_statement(self):
        tok = self.peek()
        if tok.type == 'KEYWORD':
            if tok.value == 'nest':
                return self.parse_assign()
            if tok.value == 'squawk':
                return self.parse_print()
            if tok.value == 'peek':
                return self.parse_if()
            if tok.value == 'flap':
                return self.parse_loop()
            if tok.value == 'teach':
                return self.parse_funcdef()
            if tok.value == 'give':
                return self.parse_return()
        return self.parse_expr_stmt()

    def parse_assign(self):
        tok = self.consume('KEYWORD', 'nest')
        name_tok = self.consume('IDENTIFIER')
        self.consume('OPERATOR', '=')
        value = self.parse_expression()
        return {'node': 'Assign', 'name': name_tok.value, 'value': value, 'line': tok.line}

    def parse_print(self):
        tok = self.consume('KEYWORD', 'squawk')
        self.consume('LPAREN')
        args = []
        if self.peek().type != 'RPAREN':
            args = self.parse_expr_list()
        self.consume('RPAREN')
        return {'node': 'Print', 'args': args, 'line': tok.line}

    def parse_if(self):
        tok = self.consume('KEYWORD', 'peek')
        condition = self.parse_expression()
        self.consume('KEYWORD', 'then')
        body = self.parse_block()
        return {'node': 'If', 'condition': condition, 'body': body, 'line': tok.line}

    def parse_loop(self):
        tok = self.consume('KEYWORD', 'flap')
        count = self.parse_expression()
        self.consume('KEYWORD', 'times')
        body = self.parse_block()
        return {'node': 'Loop', 'count': count, 'body': body, 'line': tok.line}

    def parse_funcdef(self):
        tok = self.consume('KEYWORD', 'teach')
        name_tok = self.consume('IDENTIFIER')
        self.consume('LPAREN')
        params = []
        if self.peek().type != 'RPAREN':
            params.append(self.consume('IDENTIFIER').value)
            while self.peek().type == 'COMMA':
                self.advance()
                params.append(self.consume('IDENTIFIER').value)
        self.consume('RPAREN')
        self.consume('KEYWORD', 'then')
        body = self.parse_block()
        return {'node': 'FunctionDef', 'name': name_tok.value, 'params': params, 'body': body, 'line': tok.line}

    def parse_return(self):
        tok = self.consume('KEYWORD', 'give')
        value = self.parse_expression()
        return {'node': 'Return', 'value': value, 'line': tok.line}

    def parse_block(self):
        stmts = []
        while True:
            tok = self.peek()
            if tok.type == 'EOF':
                raise ParseError(f"Expected 'land' but reached end of file")
            if tok.type == 'KEYWORD' and tok.value == 'land':
                self.advance()
                break
            stmt = self.parse_statement()
            if stmt is not None:
                stmts.append(stmt)
        return stmts

    def parse_expr_stmt(self):
        expr = self.parse_expression()
        return expr

    def parse_expr_list(self):
        args = [self.parse_expression()]
        while self.peek().type == 'COMMA':
            self.advance()
            args.append(self.parse_expression())
        return args

    def parse_expression(self):
        return self.parse_or()

    def parse_or(self):
        left = self.parse_and()
        while self.peek().type == 'KEYWORD' and self.peek().value == 'or':
            op_tok = self.advance()
            right = self.parse_and()
            left = {'node': 'BinOp', 'op': 'or', 'left': left, 'right': right, 'line': op_tok.line}
        return left

    def parse_and(self):
        left = self.parse_not()
        while self.peek().type == 'KEYWORD' and self.peek().value == 'and':
            op_tok = self.advance()
            right = self.parse_not()
            left = {'node': 'BinOp', 'op': 'and', 'left': left, 'right': right, 'line': op_tok.line}
        return left

    def parse_not(self):
        if self.peek().type == 'KEYWORD' and self.peek().value == 'not':
            op_tok = self.advance()
            operand = self.parse_not()
            return {'node': 'UnaryOp', 'op': 'not', 'operand': operand, 'line': op_tok.line}
        return self.parse_comparison()

    def parse_comparison(self):
        left = self.parse_additive()
        cmp_ops = {'<', '>', '<=', '>=', '==', '!='}
        while self.peek().type == 'OPERATOR' and self.peek().value in cmp_ops:
            op_tok = self.advance()
            right = self.parse_additive()
            left = {'node': 'BinOp', 'op': op_tok.value, 'left': left, 'right': right, 'line': op_tok.line}
        return left

    def parse_additive(self):
        left = self.parse_multiplicative()
        while self.peek().type == 'OPERATOR' and self.peek().value in ('+', '-'):
            op_tok = self.advance()
            right = self.parse_multiplicative()
            left = {'node': 'BinOp', 'op': op_tok.value, 'left': left, 'right': right, 'line': op_tok.line}
        return left

    def parse_multiplicative(self):
        left = self.parse_unary()
        while self.peek().type == 'OPERATOR' and self.peek().value in ('*', '/'):
            op_tok = self.advance()
            right = self.parse_unary()
            left = {'node': 'BinOp', 'op': op_tok.value, 'left': left, 'right': right, 'line': op_tok.line}
        return left

    def parse_unary(self):
        if self.peek().type == 'OPERATOR' and self.peek().value == '-':
            op_tok = self.advance()
            operand = self.parse_unary()
            return {'node': 'UnaryOp', 'op': '-', 'operand': operand, 'line': op_tok.line}
        return self.parse_primary()

    def parse_primary(self):
        tok = self.peek()

        if tok.type == 'NUMBER':
            self.advance()
            return {'node': 'Number', 'value': tok.value, 'line': tok.line}

        if tok.type == 'STRING':
            self.advance()
            return {'node': 'String', 'value': tok.value, 'line': tok.line}

        if tok.type == 'KEYWORD' and tok.value == 'true':
            self.advance()
            return {'node': 'Bool', 'value': True, 'line': tok.line}

        if tok.type == 'KEYWORD' and tok.value == 'false':
            self.advance()
            return {'node': 'Bool', 'value': False, 'line': tok.line}

        if tok.type == 'IDENTIFIER':
            self.advance()
            if self.peek().type == 'LPAREN':
                self.advance()
                args = []
                if self.peek().type != 'RPAREN':
                    args = self.parse_expr_list()
                self.consume('RPAREN')
                return {'node': 'Call', 'name': tok.value, 'args': args, 'line': tok.line}
            return {'node': 'Identifier', 'name': tok.value, 'line': tok.line}

        if tok.type == 'LPAREN':
            self.advance()
            expr = self.parse_expression()
            self.consume('RPAREN')
            return expr

        raise ParseError(f"Unexpected token '{tok.value}' at line {tok.line}")


def parser(tokens):
    return Parser(tokens).parse()

# ─────────────────────────────────────────────
# SEMANTIC ANALYZER
# ─────────────────────────────────────────────

def semantic_analyzer(ast):
    issues = []

    def error(msg, line=0):
        issues.append({'type': 'error', 'message': msg, 'line': line})

    def warning(msg, line=0):
        issues.append({'type': 'warning', 'message': msg, 'line': line})

    # scope_stack: list of dicts. Each dict maps name -> info
    # info is either {"kind": "var"} or {"kind": "function", "param_count": N}
    scope_stack = [{}]
    in_function = [False]

    def declare(name, info):
        scope_stack[-1][name] = info

    def lookup(name):
        for frame in reversed(scope_stack):
            if name in frame:
                return frame[name]
        return None

    def push():
        scope_stack.append({})

    def pop():
        scope_stack.pop()

    def analyze(node):
        if node is None:
            return
        kind = node.get('node')

        if kind == 'Program':
            # Pre-declare all top-level functions first
            for child in node.get('body', []):
                if child.get('node') == 'FunctionDef':
                    declare(child['name'], {'kind': 'function', 'param_count': len(child.get('params', []))})
            for child in node.get('body', []):
                analyze(child)

        elif kind == 'Assign':
            analyze(node['value'])
            declare(node['name'], {'kind': 'var'})

        elif kind == 'FunctionDef':
            # Already pre-declared at Program level; here we walk the body
            push()
            for param in node.get('params', []):
                declare(param, {'kind': 'var'})
            old = in_function[0]
            in_function[0] = True
            for stmt in node.get('body', []):
                analyze(stmt)
            in_function[0] = old
            pop()

        elif kind == 'If':
            analyze(node['condition'])
            push()
            for stmt in node.get('body', []):
                analyze(stmt)
            pop()

        elif kind == 'Loop':
            analyze(node['count'])
            push()
            for stmt in node.get('body', []):
                analyze(stmt)
            pop()

        elif kind == 'Return':
            if not in_function[0]:
                warning("'give' used outside of a function", node.get('line', 0))
            analyze(node['value'])

        elif kind == 'Print':
            for arg in node.get('args', []):
                analyze(arg)

        elif kind == 'BinOp':
            analyze(node['left'])
            analyze(node['right'])

        elif kind == 'UnaryOp':
            analyze(node['operand'])

        elif kind == 'Identifier':
            if lookup(node['name']) is None:
                error(f"Undeclared variable '{node['name']}'", node.get('line', 0))

        elif kind == 'Call':
            info = lookup(node['name'])
            if info is None:
                error(f"Undeclared function '{node['name']}'", node.get('line', 0))
            elif info.get('kind') == 'function':
                expected = info['param_count']
                got = len(node.get('args', []))
                if got != expected:
                    error(
                        f"Function '{node['name']}' expects {expected} argument(s) but got {got}",
                        node.get('line', 0)
                    )
            for arg in node.get('args', []):
                analyze(arg)

        elif kind in ('Number', 'String', 'Bool'):
            pass

    analyze(ast)
    ok = not any(i['type'] == 'error' for i in issues)
    return issues, ok

# ─────────────────────────────────────────────
# EXECUTOR
# ─────────────────────────────────────────────

class Environment:
    def __init__(self, parent=None):
        self.vars = {}
        self.parent = parent

    def get(self, name):
        if name in self.vars:
            return self.vars[name]
        if self.parent:
            return self.parent.get(name)
        raise RuntimeError(f"Undefined variable '{name}'")

    def set(self, name, value):
        self.vars[name] = value

    def assign(self, name, value):
        if name in self.vars:
            self.vars[name] = value
        elif self.parent:
            self.parent.assign(name, value)
        else:
            self.vars[name] = value


def executor(ast):
    output = []
    MAX_DEPTH = 500

    def execute(node, env, depth=0):
        if depth > MAX_DEPTH:
            raise RuntimeError("Maximum recursion depth exceeded")

        kind = node.get('node')

        if kind == 'Program':
            # Hoist all top-level function definitions
            for stmt in node.get('body', []):
                if stmt.get('node') == 'FunctionDef':
                    env.set(stmt['name'], {'__type__': 'function', 'node': stmt, 'closure': env})
            for stmt in node.get('body', []):
                if stmt.get('node') != 'FunctionDef':
                    execute(stmt, env, depth)

        elif kind == 'Assign':
            val = eval_expr(node['value'], env, depth)
            env.assign(node['name'], val)

        elif kind == 'Print':
            parts = [str(eval_expr(a, env, depth)) for a in node.get('args', [])]
            output.append(' '.join(parts))

        elif kind == 'If':
            cond = eval_expr(node['condition'], env, depth)
            if cond:
                child_env = Environment(parent=env)
                for stmt in node.get('body', []):
                    execute(stmt, child_env, depth)

        elif kind == 'Loop':
            count = eval_expr(node['count'], env, depth)
            if not isinstance(count, (int, float)):
                raise RuntimeError(f"Loop count must be a number, got {type(count).__name__}")
            count = int(count)
            child_env = Environment(parent=env)
            for _ in range(count):
                for stmt in node.get('body', []):
                    execute(stmt, child_env, depth)

        elif kind == 'FunctionDef':
            env.set(node['name'], {'__type__': 'function', 'node': node, 'closure': env})

        elif kind == 'Return':
            val = eval_expr(node['value'], env, depth)
            raise ReturnSignal(val)

        elif kind == 'Call':
            eval_expr(node, env, depth)

        else:
            eval_expr(node, env, depth)

    def eval_expr(node, env, depth=0):
        kind = node.get('node')

        if kind == 'Number':
            return node['value']

        if kind == 'String':
            return node['value']

        if kind == 'Bool':
            return node['value']

        if kind == 'Identifier':
            return env.get(node['name'])

        if kind == 'BinOp':
            left = eval_expr(node['left'], env, depth)
            right = eval_expr(node['right'], env, depth)
            return eval_binop(node['op'], left, right, node.get('line', 0))

        if kind == 'UnaryOp':
            operand = eval_expr(node['operand'], env, depth)
            op = node['op']
            if op == '-':
                return -operand
            if op == 'not':
                return not operand

        if kind == 'Call':
            func = env.get(node['name'])
            if not isinstance(func, dict) or func.get('__type__') != 'function':
                raise RuntimeError(f"'{node['name']}' is not a function")
            func_node = func['node']
            closure = func['closure']
            params = func_node.get('params', [])
            args = [eval_expr(a, env, depth) for a in node.get('args', [])]
            if len(args) != len(params):
                raise RuntimeError(
                    f"Function '{node['name']}' expects {len(params)} arg(s) but got {len(args)}"
                )
            call_env = Environment(parent=closure)
            for p, a in zip(params, args):
                call_env.set(p, a)
            try:
                for stmt in func_node.get('body', []):
                    execute(stmt, call_env, depth + 1)
                return None
            except ReturnSignal as r:
                return r.value

        if kind == 'Print':
            parts = [str(eval_expr(a, env, depth)) for a in node.get('args', [])]
            output.append(' '.join(parts))
            return None

        raise RuntimeError(f"Unknown AST node: {kind}")

    def eval_binop(op, left, right, line):
        try:
            if op == '+':  return left + right
            if op == '-':  return left - right
            if op == '*':  return left * right
            if op == '/':
                if right == 0:
                    raise RuntimeError(f"Division by zero at line {line}")
                return left / right
            if op == '>':  return left > right
            if op == '<':  return left < right
            if op == '>=': return left >= right
            if op == '<=': return left <= right
            if op == '==': return left == right
            if op == '!=': return left != right
            if op == 'and': return bool(left) and bool(right)
            if op == 'or':  return bool(left) or bool(right)
        except TypeError as e:
            raise RuntimeError(f"Type error in '{op}' operation at line {line}: {e}")
        raise RuntimeError(f"Unknown operator: {op}")

    global_env = Environment()
    execute(ast, global_env)
    return output

# ─────────────────────────────────────────────
# Flask Route
# ─────────────────────────────────────────────

@app.route('/run', methods=['POST', 'OPTIONS'])
def run():
    if request.method == 'OPTIONS':
        return '', 204

    data = request.get_json(force=True) or {}
    code = data.get('code', '')

    result = {
        'tokens': [],
        'ast': {},
        'semantic': {'ok': False, 'issues': []},
        'output': [],
        'error': None
    }

    # Phase 1 — Scanner
    try:
        tokens = scanner(code)
        result['tokens'] = [{'type': t.type, 'value': t.value, 'line': t.line} for t in tokens]
    except LexError as e:
        result['error'] = str(e)
        return jsonify(result)

    # Phase 2 — Parser
    try:
        ast = parser(tokens)
        result['ast'] = ast
    except ParseError as e:
        result['error'] = str(e)
        return jsonify(result)

    # Phase 3 — Semantic Analyzer
    try:
        issues, ok = semantic_analyzer(ast)
        result['semantic'] = {'ok': ok, 'issues': issues}
    except Exception as e:
        result['semantic'] = {'ok': False, 'issues': [{'type': 'error', 'message': str(e), 'line': 0}]}

    # Phase 4 — Executor (only if semantic ok)
    if result['semantic']['ok']:
        try:
            out = executor(ast)
            result['output'] = out
        except RuntimeError as e:
            result['error'] = str(e)

    return jsonify(result)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
