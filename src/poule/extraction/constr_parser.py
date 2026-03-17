"""Parsers that convert raw backend output into ConstrNode types.

Supports two backends:
- coq-lsp JSON (Constr.t serialized as JSON arrays)
- SerAPI S-expressions
"""

from __future__ import annotations

from poule.extraction.errors import ExtractionError
from poule.normalization import constr_node as cn

# ---------------------------------------------------------------------------
# S-expression tokenizer / parser
# ---------------------------------------------------------------------------


def parse_sexp(text: str) -> list | str:
    """Parse an S-expression string into nested Python lists/strings.

    Atoms become strings; parenthesised groups become lists.
    """
    tokens = _tokenize_sexp(text)
    if not tokens:
        raise ExtractionError("Empty S-expression")
    result, pos = _parse_tokens(tokens, 0)
    return result


def _tokenize_sexp(text: str) -> list[str]:
    tokens: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c == '(':
            tokens.append('(')
            i += 1
        elif c == ')':
            tokens.append(')')
            i += 1
        elif c == '"':
            # quoted string
            j = i + 1
            while j < n and text[j] != '"':
                if text[j] == '\\':
                    j += 1
                j += 1
            tokens.append(text[i + 1:j])
            i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in ('(', ')'):
                j += 1
            tokens.append(text[i:j])
            i = j
    return tokens


def _parse_tokens(tokens: list[str], pos: int) -> tuple[list | str, int]:
    if pos >= len(tokens):
        raise ExtractionError("Unexpected end of S-expression")
    if tokens[pos] == '(':
        lst: list = []
        pos += 1
        while pos < len(tokens) and tokens[pos] != ')':
            item, pos = _parse_tokens(tokens, pos)
            lst.append(item)
        if pos >= len(tokens):
            raise ExtractionError("Unclosed parenthesis in S-expression")
        return lst, pos + 1  # skip ')'
    elif tokens[pos] == ')':
        raise ExtractionError("Unexpected ')' in S-expression")
    else:
        return tokens[pos], pos + 1


# ---------------------------------------------------------------------------
# coq-lsp JSON parser
# ---------------------------------------------------------------------------

_JSON_VARIANT_MAP = {
    "Rel", "Var", "Sort", "Cast", "Prod", "Lambda", "LetIn",
    "App", "Const", "Ind", "Construct", "Case", "Fix", "CoFix",
    "Proj", "Int", "Float",
}


def parse_constr_json(raw: dict | list) -> cn.Rel | cn.Var | cn.Sort | cn.Cast | cn.Prod | cn.Lambda | cn.LetIn | cn.App | cn.Const | cn.Ind | cn.Construct | cn.Case | cn.Fix | cn.CoFix | cn.Proj | cn.Int | cn.Float:
    """Parse a coq-lsp JSON term into a ConstrNode.

    The JSON format uses two-element arrays: ``["Tag", payload]``.
    """
    if not isinstance(raw, (list, tuple)) or len(raw) < 1:
        raise ExtractionError(f"Expected JSON array for Constr term, got: {type(raw).__name__}")

    tag = raw[0]
    if tag not in _JSON_VARIANT_MAP:
        raise ExtractionError(f"Unrecognized Constr variant: {tag!r}")

    if tag == "Rel":
        return cn.Rel(n=_expect_int(raw[1], "Rel index"))

    if tag == "Var":
        return cn.Var(name=_expect_str(raw[1], "Var name"))

    if tag == "Sort":
        sort_val = raw[1]
        if isinstance(sort_val, str):
            return cn.Sort(sort=sort_val)
        if isinstance(sort_val, list) and len(sort_val) >= 1:
            return cn.Sort(sort=str(sort_val[0]))
        return cn.Sort(sort=str(sort_val))

    if tag == "Cast":
        if len(raw) < 4:
            raise ExtractionError("Cast requires term, kind, and type")
        term = parse_constr_json(raw[1])
        # raw[2] is the cast kind — discard
        typ = parse_constr_json(raw[3])
        return cn.Cast(term=term, type=typ)

    if tag == "Prod":
        if len(raw) < 4:
            raise ExtractionError("Prod requires binder, type, and body")
        binder = raw[1]
        name = _extract_binder_name(binder)
        typ = parse_constr_json(raw[2])
        body = parse_constr_json(raw[3])
        return cn.Prod(name=name, type=typ, body=body)

    if tag == "Lambda":
        if len(raw) < 4:
            raise ExtractionError("Lambda requires binder, type, and body")
        binder = raw[1]
        name = _extract_binder_name(binder)
        typ = parse_constr_json(raw[2])
        body = parse_constr_json(raw[3])
        return cn.Lambda(name=name, type=typ, body=body)

    if tag == "LetIn":
        if len(raw) < 5:
            raise ExtractionError("LetIn requires binder, def, type, and body")
        binder = raw[1]
        name = _extract_binder_name(binder)
        val = parse_constr_json(raw[2])
        typ = parse_constr_json(raw[3])
        body = parse_constr_json(raw[4])
        return cn.LetIn(name=name, value=val, type=typ, body=body)

    if tag == "App":
        if len(raw) < 3:
            raise ExtractionError("App requires function and arguments")
        func = parse_constr_json(raw[1])
        args_raw = raw[2]
        if not isinstance(args_raw, list):
            raise ExtractionError("App arguments must be a list")
        args = [parse_constr_json(a) for a in args_raw]
        return cn.App(func=func, args=args)

    if tag == "Const":
        payload = raw[1]
        fqn = _extract_const_fqn(payload)
        return cn.Const(fqn=fqn)

    if tag == "Ind":
        payload = raw[1]
        fqn = _extract_ind_fqn(payload)
        return cn.Ind(fqn=fqn)

    if tag == "Construct":
        payload = raw[1]
        fqn = _extract_ind_fqn(payload)
        index = payload.get("constructor", 1) if isinstance(payload, dict) else 1
        return cn.Construct(fqn=fqn, index=index)

    if tag == "Case":
        if len(raw) < 4:
            raise ExtractionError("Case requires case_info, scrutinee, and branches")
        case_info = raw[1]
        ind_name = ""
        if isinstance(case_info, dict):
            ind_name = case_info.get("inductive", case_info.get("ind_name", ""))
        elif isinstance(case_info, list) and len(case_info) >= 1:
            ind_name = str(case_info[0]) if not isinstance(case_info[0], list) else ""
        scrutinee = parse_constr_json(raw[2])
        branches_raw = raw[3]
        if not isinstance(branches_raw, list):
            branches_raw = []
        branches = [parse_constr_json(b) for b in branches_raw]
        return cn.Case(ind_name=ind_name, scrutinee=scrutinee, branches=branches)

    if tag == "Fix":
        if len(raw) < 4:
            raise ExtractionError("Fix requires fix_info, types, and bodies")
        fix_info = raw[1]
        index = 0
        if isinstance(fix_info, int):
            index = fix_info
        elif isinstance(fix_info, dict):
            index = fix_info.get("index", 0)
        # raw[2] = types (discard), raw[3] = bodies
        bodies_raw = raw[3] if len(raw) > 3 else raw[2]
        if not isinstance(bodies_raw, list):
            bodies_raw = [bodies_raw]
        bodies = [parse_constr_json(b) for b in bodies_raw]
        return cn.Fix(index=index, bodies=bodies)

    if tag == "CoFix":
        if len(raw) < 3:
            raise ExtractionError("CoFix requires index and bodies")
        fix_info = raw[1]
        index = 0
        if isinstance(fix_info, int):
            index = fix_info
        elif isinstance(fix_info, dict):
            index = fix_info.get("index", 0)
        bodies_raw = raw[-1]
        if not isinstance(bodies_raw, list):
            bodies_raw = [bodies_raw]
        bodies = [parse_constr_json(b) for b in bodies_raw]
        return cn.CoFix(index=index, bodies=bodies)

    if tag == "Proj":
        if len(raw) < 3:
            raise ExtractionError("Proj requires projection info and term")
        proj_info = raw[1]
        name = ""
        if isinstance(proj_info, dict):
            name = proj_info.get("projection", "")
        elif isinstance(proj_info, str):
            name = proj_info
        term = parse_constr_json(raw[2])
        return cn.Proj(name=name, term=term)

    if tag == "Int":
        return cn.Int(value=_expect_int(raw[1], "Int value"))

    if tag == "Float":
        val = raw[1]
        if isinstance(val, (int, float)):
            return cn.Float(value=float(val))
        raise ExtractionError(f"Float value must be numeric, got: {type(val).__name__}")

    raise ExtractionError(f"Unrecognized Constr variant: {tag!r}")  # pragma: no cover


def _extract_binder_name(binder: dict | str) -> str:
    if isinstance(binder, str):
        return binder
    if isinstance(binder, dict):
        return binder.get("binder_name", binder.get("name", "_"))
    return "_"


def _extract_const_fqn(payload: dict | str) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        return payload.get("constant", payload.get("fqn", ""))
    raise ExtractionError(f"Cannot extract FQN from Const payload: {payload!r}")


def _extract_ind_fqn(payload: dict | str) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        return payload.get("inductive", payload.get("fqn", ""))
    raise ExtractionError(f"Cannot extract FQN from Ind/Construct payload: {payload!r}")


def _expect_int(val: object, context: str) -> int:
    if isinstance(val, int):
        return val
    raise ExtractionError(f"{context} must be an integer, got: {type(val).__name__}")


def _expect_str(val: object, context: str) -> str:
    if isinstance(val, str):
        return val
    raise ExtractionError(f"{context} must be a string, got: {type(val).__name__}")


# ---------------------------------------------------------------------------
# SerAPI S-expression parser
# ---------------------------------------------------------------------------

def parse_constr_sexp(raw: str | list) -> cn.Rel | cn.Var | cn.Sort | cn.Cast | cn.Prod | cn.Lambda | cn.LetIn | cn.App | cn.Const | cn.Ind | cn.Construct | cn.Case | cn.Fix | cn.CoFix | cn.Proj | cn.Int | cn.Float:
    """Parse a SerAPI S-expression into a ConstrNode.

    Accepts either a raw S-expression string or a pre-parsed nested list.
    """
    if isinstance(raw, str):
        raw = parse_sexp(raw)

    if isinstance(raw, str):
        # bare atom — shouldn't be a valid top-level term
        raise ExtractionError(f"Expected S-expression list, got atom: {raw!r}")

    if not isinstance(raw, list) or len(raw) < 1:
        raise ExtractionError(f"Expected non-empty S-expression list, got: {raw!r}")

    tag = raw[0]
    if not isinstance(tag, str):
        raise ExtractionError(f"Expected variant tag string, got: {tag!r}")

    if tag not in _JSON_VARIANT_MAP:
        raise ExtractionError(f"Unrecognized Constr variant: {tag!r}")

    if tag == "Rel":
        return cn.Rel(n=int(raw[1]))

    if tag == "Var":
        name = _sexp_extract_id(raw[1]) if len(raw) > 1 else ""
        return cn.Var(name=name)

    if tag == "Sort":
        sort_str = _sexp_sort_kind(raw[1] if len(raw) > 1 else "Set")
        return cn.Sort(sort=sort_str)

    if tag == "Cast":
        if len(raw) < 3:
            raise ExtractionError("Cast S-expression needs term and type")
        term = parse_constr_sexp(raw[1])
        # Cast kind may or may not be present; type is last
        typ = parse_constr_sexp(raw[-1]) if len(raw) >= 4 else parse_constr_sexp(raw[2])
        return cn.Cast(term=term, type=typ)

    if tag == "Prod":
        if len(raw) < 4:
            raise ExtractionError("Prod S-expression needs name, type, body")
        name = _sexp_extract_binder(raw[1])
        typ = parse_constr_sexp(raw[2])
        body = parse_constr_sexp(raw[3])
        return cn.Prod(name=name, type=typ, body=body)

    if tag == "Lambda":
        if len(raw) < 4:
            raise ExtractionError("Lambda S-expression needs name, type, body")
        name = _sexp_extract_binder(raw[1])
        typ = parse_constr_sexp(raw[2])
        body = parse_constr_sexp(raw[3])
        return cn.Lambda(name=name, type=typ, body=body)

    if tag == "LetIn":
        if len(raw) < 5:
            raise ExtractionError("LetIn S-expression needs name, def, type, body")
        name = _sexp_extract_binder(raw[1])
        val = parse_constr_sexp(raw[2])
        typ = parse_constr_sexp(raw[3])
        body = parse_constr_sexp(raw[4])
        return cn.LetIn(name=name, value=val, type=typ, body=body)

    if tag == "App":
        if len(raw) < 3:
            raise ExtractionError("App S-expression needs function and args")
        func = parse_constr_sexp(raw[1])
        args_raw = raw[2] if isinstance(raw[2], list) and len(raw[2]) > 0 and isinstance(raw[2][0], list) else raw[2:]
        if isinstance(args_raw, list) and len(args_raw) > 0 and isinstance(args_raw[0], list) and isinstance(args_raw[0][0] if args_raw[0] else None, list):
            args = [parse_constr_sexp(a) for a in args_raw[0]]
        elif isinstance(args_raw, list) and len(args_raw) > 0 and isinstance(args_raw[0], str) and args_raw[0] in _JSON_VARIANT_MAP:
            args = [parse_constr_sexp(args_raw)]
        else:
            # args_raw is a list of sexp terms
            args = [parse_constr_sexp(a) for a in (args_raw if isinstance(args_raw, list) else [args_raw])]
        return cn.App(func=func, args=args)

    if tag == "Const":
        fqn = _sexp_extract_const_fqn(raw)
        return cn.Const(fqn=fqn)

    if tag == "Ind":
        fqn = _sexp_extract_ind_fqn(raw)
        return cn.Ind(fqn=fqn)

    if tag == "Construct":
        fqn = _sexp_extract_ind_fqn(raw)
        index = _sexp_extract_constructor_index(raw)
        return cn.Construct(fqn=fqn, index=index)

    if tag == "Case":
        ind_name = ""
        scrutinee_idx = 2
        # Case structure varies; try to extract ind name and parts
        if len(raw) >= 4:
            # Try to find the inductive name from case_info
            if isinstance(raw[1], list):
                ind_name = _sexp_deep_find_ind_name(raw[1])
            scrutinee = parse_constr_sexp(raw[2])
            branches = [parse_constr_sexp(b) for b in raw[3:] if isinstance(b, list)]
        elif len(raw) >= 3:
            scrutinee = parse_constr_sexp(raw[1])
            branches = [parse_constr_sexp(b) for b in raw[2:] if isinstance(b, list)]
        else:
            raise ExtractionError("Case S-expression too short")
        return cn.Case(ind_name=ind_name, scrutinee=scrutinee, branches=branches)

    if tag == "Fix":
        if len(raw) < 3:
            raise ExtractionError("Fix S-expression needs index and bodies")
        index = int(raw[1]) if isinstance(raw[1], str) and raw[1].isdigit() else 0
        bodies = [parse_constr_sexp(b) for b in raw[2:] if isinstance(b, list)]
        return cn.Fix(index=index, bodies=bodies)

    if tag == "CoFix":
        if len(raw) < 3:
            raise ExtractionError("CoFix S-expression needs index and bodies")
        index = int(raw[1]) if isinstance(raw[1], str) and raw[1].isdigit() else 0
        bodies = [parse_constr_sexp(b) for b in raw[2:] if isinstance(b, list)]
        return cn.CoFix(index=index, bodies=bodies)

    if tag == "Proj":
        if len(raw) < 3:
            raise ExtractionError("Proj S-expression needs projection info and term")
        name = _sexp_extract_proj_name(raw[1])
        term = parse_constr_sexp(raw[2])
        return cn.Proj(name=name, term=term)

    if tag == "Int":
        return cn.Int(value=int(raw[1]))

    if tag == "Float":
        return cn.Float(value=float(raw[1]))

    raise ExtractionError(f"Unrecognized Constr variant: {tag!r}")  # pragma: no cover


# ---------------------------------------------------------------------------
# S-expression helpers
# ---------------------------------------------------------------------------


def _sexp_extract_id(node: str | list) -> str:
    """Extract an Id from forms like (Id foo) or just a string."""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        if len(node) >= 2 and node[0] == "Id":
            return str(node[1])
        # Recurse into first element
        for item in node:
            result = _sexp_extract_id(item)
            if result:
                return result
    return ""


def _sexp_extract_binder(node: str | list) -> str:
    """Extract binder name from (Name (Id x)) or Anonymous."""
    if isinstance(node, str):
        return "_" if node == "Anonymous" else node
    if isinstance(node, list):
        if len(node) >= 2 and node[0] == "Name":
            return _sexp_extract_id(node[1])
        if node[0] == "Anonymous":
            return "_"
    return "_"


def _sexp_sort_kind(node: str | list) -> str:
    """Extract sort kind string from Sort payload."""
    if isinstance(node, str):
        return node
    if isinstance(node, list) and len(node) >= 1:
        if isinstance(node[0], str):
            return node[0]
    return "Type"


def _sexp_extract_dirpath_ids(dirpath: list) -> list[str]:
    """Extract Id values from (DirPath ((Id X) (Id Y) ...))."""
    if not isinstance(dirpath, list) or len(dirpath) < 2 or dirpath[0] != "DirPath":
        return []
    ids_list = dirpath[1]
    if not isinstance(ids_list, list):
        return []
    result = []
    for item in ids_list:
        if isinstance(item, list) and len(item) >= 2 and item[0] == "Id":
            result.append(str(item[1]))
    return result


def _sexp_build_fqn(dirpath_ids: list[str], name: str) -> str:
    """Build FQN from reversed DirPath ids and a name."""
    # DirPath ids are in reverse order: (Id Init) (Id Coq) means Coq.Init
    parts = list(reversed(dirpath_ids))
    parts.append(name)
    return ".".join(parts)


def _sexp_extract_const_fqn(raw: list) -> str:
    """Extract FQN from Const S-expression.

    Form: (Const ((constant (DirPath (...)) (Id name)) (Instance ())))
    """
    try:
        # Navigate to the constant info
        payload = raw[1]  # ((constant ...) (Instance ()))
        if isinstance(payload, list) and len(payload) >= 1:
            const_info = payload[0] if isinstance(payload[0], list) else payload
            # Find DirPath and Id
            dirpath_ids = []
            name = ""
            for item in (const_info if isinstance(const_info, list) else [const_info]):
                if isinstance(item, list):
                    if item[0] == "DirPath":
                        dirpath_ids = _sexp_extract_dirpath_ids(item)
                    elif item[0] == "Id":
                        name = str(item[1])
                elif isinstance(item, str) and item not in ("constant", "Instance"):
                    name = item
            if dirpath_ids or name:
                return _sexp_build_fqn(dirpath_ids, name)
    except (IndexError, TypeError, KeyError):
        pass
    raise ExtractionError(f"Cannot extract FQN from Const S-expression: {raw!r}")


def _sexp_extract_ind_fqn(raw: list) -> str:
    """Extract FQN from Ind or Construct S-expression.

    Ind form: (Ind ((ind (MutInd (DirPath (...)) (Id name))) (Instance ())))
    """
    try:
        payload = raw[1]
        if isinstance(payload, list) and len(payload) >= 1:
            ind_info = payload[0] if isinstance(payload[0], list) else payload
            # Navigate through nested structure to find DirPath and Id
            return _sexp_deep_find_fqn(ind_info)
    except (IndexError, TypeError, KeyError):
        pass
    raise ExtractionError(f"Cannot extract FQN from Ind/Construct S-expression: {raw!r}")


def _sexp_deep_find_fqn(node: list | str) -> str:
    """Recursively search for DirPath + Id pattern to build an FQN."""
    if isinstance(node, str):
        return ""
    if not isinstance(node, list):
        return ""

    dirpath_ids: list[str] = []
    name = ""

    for item in node:
        if isinstance(item, list):
            if len(item) >= 2 and item[0] == "DirPath":
                dirpath_ids = _sexp_extract_dirpath_ids(item)
            elif len(item) >= 2 and item[0] == "Id":
                name = str(item[1])
            elif len(item) >= 2 and item[0] == "MutInd":
                # Recurse into MutInd
                result = _sexp_deep_find_fqn(item)
                if result:
                    return result

    if dirpath_ids or name:
        return _sexp_build_fqn(dirpath_ids, name)

    # Try recursing into sub-lists
    for item in node:
        if isinstance(item, list):
            result = _sexp_deep_find_fqn(item)
            if result:
                return result

    return ""


def _sexp_extract_constructor_index(raw: list) -> int:
    """Extract constructor index from Construct S-expression."""
    # The index is typically embedded; default to 1
    try:
        payload = raw[1]
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, str) and item.isdigit():
                    return int(item)
                if isinstance(item, list) and len(item) >= 2:
                    if isinstance(item[1], str) and item[1].isdigit():
                        return int(item[1])
    except (IndexError, TypeError):
        pass
    return 1


def _sexp_extract_proj_name(node: str | list) -> str:
    """Extract projection name from Proj info."""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        # Try to build FQN from DirPath + Id
        result = _sexp_deep_find_fqn(node)
        if result:
            return result
        return _sexp_extract_id(node)
    return ""


def _sexp_deep_find_ind_name(node: list) -> str:
    """Try to find an inductive name from case info S-expression."""
    result = _sexp_deep_find_fqn(node)
    return result if result else ""
