"""Generic engine: compares a data dict against a sub-tree of
meta_contract.yaml, field by field. No pydantic, direct comparison
(ADR-005).

Does not know where `data` came from - an authoring YAML
(`authoring.py`), what the writer stamped into the parquet
(`provenance.py`), a JSON fragment from the scanner (`mechanical.py`), or
an inspect sidecar (`inspect.py`).
Each of those modules resolves which sub-tree of the contract
(`top_spec`) applies to it and calls `check_metadata` with that - this
file only knows how to compare."""

from __future__ import annotations

import datetime as dt
import logging

from .contract import ContractError

log = logging.getLogger(__name__)

__all__ = ["check_metadata"]

_SCALARS = {
    "str": str,
    "bool": bool,
    "date": dt.date,
    "datetime": dt.datetime,
}


def _is_int(value) -> bool:
    """True for an ``int`` that is not a ``bool`` (``bool`` subclasses ``int``)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_date(value) -> bool:
    """True for a ``date`` that is not a ``datetime`` (``datetime`` subclasses ``date``)."""
    return isinstance(value, dt.date) and not isinstance(value, dt.datetime)


# Checks that a value has the type declared in its contract spec.
def _type_ok(spec: dict, value) -> bool:
    """Check whether `value` matches the type declared in `spec`.

    Parameters
    ----------
    spec : dict
        Field spec from the contract. Must have a ``type`` key; needs
        ``values`` too when ``type`` is ``enum``.
    value : Any
        The value to check.

    Returns
    -------
    bool
        True if `value` matches `spec["type"]`.

    Raises
    ------
    ContractError
        If `spec["type"]` is not one of the closed vocabulary tokens -
        a type the validator doesn't know about is a bug in the
        contract, not a bad value.

    Notes
    -----
    ``date``/``datetime`` accept either a native object (YAML-authored
    data, which PyYAML parses natively) or an ISO-format string
    (data round-tripped through JSON, e.g. ``mechanical.scanned_at`` /
    ``provenance.written_at``, both written with
    ``json.dumps(..., default=str)``).

    ``int`` (also as a ``dict[str,int]`` value) rejects ``bool``, even
    though a ``bool`` is an ``int`` in python. Same for ``date``: it
    rejects a ``datetime`` (a subclass of ``date``), and an ISO datetime
    string too (``date.fromisoformat`` fails on it). The other way round
    loses nothing: ``datetime`` accepts a ``date`` as midnight, as it
    already does with a date-only ISO string (``datetime.fromisoformat``).
    ``list[object]`` only checks that each item is a dict: the item's
    ``fields:`` are validated by `_check_group`.
    """
    token = spec["type"]
    if token in ("date", "datetime") and isinstance(value, str):
        try:
            _SCALARS[token].fromisoformat(value)
            return True
        except ValueError:
            return False
    if token == "int":
        return _is_int(value)
    if token == "date":
        return _is_date(value)
    if token == "datetime":
        return isinstance(value, dt.date)
    if token in _SCALARS:
        return isinstance(value, _SCALARS[token])
    if token == "list[str]":
        return isinstance(value, list) and all(isinstance(x, str) for x in value)
    if token == "list":
        return isinstance(value, list)
    if token == "dict[str,str]":
        return isinstance(value, dict) and all(
            isinstance(k, str) and isinstance(v, str) for k, v in value.items()
        )
    if token == "dict[str,int]":
        return isinstance(value, dict) and all(
            isinstance(k, str) and _is_int(v) for k, v in value.items()
        )
    if token == "dict[str,list]":
        return isinstance(value, dict) and all(
            isinstance(k, str) and isinstance(v, list) for k, v in value.items()
        )
    if token == "dict[str,dict]":
        return isinstance(value, dict) and all(
            isinstance(k, str) and isinstance(v, dict) for k, v in value.items()
        )
    if token == "enum":
        return value in spec["values"]
    if token == "object":
        return isinstance(value, dict)
    if token == "list[object]":
        return isinstance(value, list) and all(isinstance(x, dict) for x in value)
    raise ContractError(f"type `{token}` outside the closed vocabulary")


# Validates every field of a group (dict of specs) against the actual dict;
# recursive for type=object fields (so `keys`/`semantics` are validated by
# the same function) and for each item of a type=list[object] field.
def _check_group(
        fields_spec: dict, data: dict, path: str, errors: list, debts: list
        ) -> None:
    """Validate every field declared in `fields_spec` against `data`.

    Recurses into nested ``object`` fields and into each item of a
    ``list[object]`` field (e.g. ``inspect.findings``), validated against
    the field's ``fields:`` with an indexed path
    (``inspect.findings[0].severity``). A field's ``default:`` is not
    applied. Findings are appended to `errors`/`debts` in place (no return
    value) so nested calls share the same two accumulators.

    Parameters
    ----------
    fields_spec : dict
        Mapping of field name -> spec, taken from the contract at this level.
    data : dict
        The actual value being validated at this level.
    path : str
        Dotted path to this level, used to prefix messages (e.g. `"meta.keys"`).
    errors : list
        Accumulator for schema errors (mutated in place).
    debts : list
        Accumulator for missing `required: expected` fields (mutated in place).

    Returns
    -------
    None

    Raises
    ------
    ContractError
        If an ``object`` / ``list[object]`` field has a value to validate
        but its spec has no ``fields:`` mapping - a bug in the contract,
        like an unknown type token (`_type_ok`).
    KeyError
        If a field spec has no ``type`` or ``required``, or an ``enum``
        has no ``values:`` - also a bug in the contract.
    """
    for name in set(data) - set(fields_spec):
        errors.append(f"{path}.{name}: field not declared in the contract")

    for name, spec in fields_spec.items():
        field_path = f"{path}.{name}"
        for key in ("type", "required"):
            if key not in spec:
                raise KeyError(f"{field_path}: contract field declared without `{key}:`")
        if spec["type"] == "enum" and "values" not in spec:
            raise KeyError(f"{field_path}: type `enum` declared without `values:`")
        value = data.get(name)
        required = spec["required"]

        if value is None:
            if required is True:
                errors.append(f"{field_path}: missing (required)")
            elif required == "expected":
                debts.append(field_path)
            continue

        if not _type_ok(spec, value):
            if spec["type"] == "enum":
                errors.append(f"{field_path}: value `{value}` not in {spec['values']}")
            else:
                errors.append(f"{field_path}: invalid type, expected `{spec['type']}`")
            continue

        if spec["type"] in ("object", "list[object]") and not isinstance(spec.get("fields"), dict):
            raise ContractError(f"{field_path}: type `{spec['type']}` declared without `fields:`")
        if spec["type"] == "object":
            _check_group(spec["fields"], value, field_path, errors, debts)
        elif spec["type"] == "list[object]":
            for i, item in enumerate(value):
                _check_group(spec["fields"], item, f"{field_path}[{i}]", errors, debts)


# Entry point: checks that `data` is a dict, runs `_check_group` once
# against `top_spec`, and decides what to do with the errors/debts it
# collected (log or raise).
def check_metadata(
        data: dict, top_spec: dict, *, path: str = "meta",
        on_error_raise: bool = False, label: str | None = None) -> bool:
    """Validate `data` against `top_spec`, a contract sub-tree already
    resolved by the caller.

    Parameters
    ----------
    data : dict
        The block to validate.
    top_spec : dict
        Mapping of field name -> spec, the slice of the contract `data`
        is checked against (e.g. ``{"keys": ..., "semantics": ...}`` for
        authoring, or the whole ``mechanical`` group).
    path : str, default "meta"
        Root label used to prefix error/debt messages (e.g. `"meta"` or
        `"mechanical"`).
    on_error_raise : bool, default False
        Raise instead of logging and returning False on a schema error.
    label : str, optional
        Prefix for log messages (e.g. the table name) - useful when
        checking many blocks in a batch.

    Returns
    -------
    bool
        True if `data` validates. A missing `required: expected` field is
        debt, not a failure, and does not affect the result. False on any
        schema error (wrong type, invalid enum, missing `required: true`
        field, or a field the contract doesn't declare).

    Raises
    ------
    TypeError
        If `data` is not a dict and `on_error_raise` is True.
    ValueError
        If there are schema errors and `on_error_raise` is True.
    """
    tag = f"[{label}] " if label else ""

    if not isinstance(data, dict):
        msg = f"{tag}expected a dict, got {type(data).__name__}"
        if on_error_raise:
            raise TypeError(msg)
        log.error(msg)
        return False

    errors: list[str] = []
    debts: list[str] = []
    _check_group(top_spec, data, path, errors, debts)

    if errors:
        if on_error_raise:
            raise ValueError("; ".join(errors))
        for err in errors:
            log.error("%s%s", tag, err)
        return False

    for debt in debts:
        log.info("%s`%s` not declared", tag, debt)
    return True
