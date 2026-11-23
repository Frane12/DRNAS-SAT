#!/usr/bin/env python3
"""DRNAS DELTA1 — compact, exact affine GF(2) proof engine.

A combinational Boolean net is classified as *affine* if each output can be
represented by a constant bit plus XOR of input bits. Represent that ANF with
one Python integer: low bit = constant; bit i+1 = coefficient of input bit i.
XOR is ^. The gate evaluator only supports AND/OR/MUX when their inputs make
the operation provably affine (constants, identical/complementary expressions,
etc.). Unsupported nonlinear dependencies return UNKNOWN, NEVER a proof.

For a difference, the engine proves ONE differing output and stops immediately,
rather than expanding all outputs. For equality it proves EVERY output bit.
Trust boundary: Yosys 2-state synthesized gate netlist, not source RTL or
a DRAT/LRAT proof over the SAT baseline's original CNF.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

SUPPORTED = {"$_BUF_", "$_NOT_", "$_XOR_", "$_XNOR_", "$_AND_",
             "$_NAND_", "$_OR_", "$_NOR_", "$_MUX_"}


class Unknown(Exception):
    pass


def affine_and(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    if a == 1:
        return b
    if b == 1:
        return a
    if a == b:
        return a
    if (a ^ b) == 1:
        return 0
    raise Unknown("NON_AFFINE_AND: independent variable products required")


def affine_or(a: int, b: int) -> int:
    # a OR b = NOT( NOT(a) AND NOT(b) ), valid for all Boolean functions.
    return affine_and(a ^ 1, b ^ 1) ^ 1


def evaluate_gate(kind: str, args: dict[str, int]) -> int:
    if kind not in SUPPORTED:
        raise Unknown("UNSUPPORTED_CELL " + kind)
    if "A" not in args:
        raise Unknown("MISSING_GATE_A " + kind)
    a = args["A"]
    if kind == "$_BUF_":
        return a
    if kind == "$_NOT_":
        return a ^ 1
    if "B" not in args:
        raise Unknown("MISSING_GATE_B " + kind)
    b = args["B"]
    if kind == "$_XOR_":
        return a ^ b
    if kind == "$_XNOR_":
        return a ^ b ^ 1
    if kind == "$_AND_":
        return affine_and(a, b)
    if kind == "$_NAND_":
        return affine_and(a, b) ^ 1
    if kind == "$_OR_":
        return affine_or(a, b)
    if kind == "$_NOR_":
        return affine_or(a, b) ^ 1
    if kind == "$_MUX_":
        if "S" not in args:
            raise Unknown("MISSING_MUX_SELECTOR")
        s = args["S"]
        if s == 0:
            return a
        if s == 1:
            return b
        if a == b:
            return a
        if (a ^ b) == 1:
            return a ^ s
        raise Unknown("NON_AFFINE_MUX: variable-dependent mux")
    raise Unknown("UNSUPPORTED_CELL " + kind)


def analyze(netlist: dict, interface: dict) -> dict:
    name = interface["top"]
    module = netlist["modules"].get(name)
    if not isinstance(module, dict):
        raise Unknown("NETLIST_TOP_MISSING")
    ports = module["ports"]
    inputs = []
    known: dict[object, int] = {"0": 0, "1": 1}
    for port in sorted(ports):
        entry = ports[port]
        if entry["direction"] != "input":
            continue
        for offset, bit in enumerate(entry["bits"]):
            if not isinstance(bit, int):
                raise Unknown("NON_BINARY_INPUT")
            if bit not in known:
                ix = len(inputs)
                known[bit] = 1 << (ix + 1)
                inputs.append({"port": port, "position": offset,
                               "index": ix, "yosys_bit": bit})
    drivers: dict[int, tuple[str, dict, str]] = {}
    for cname, cell in module.get("cells", {}).items():
        outs = [p for p, direction in cell.get("port_directions", {}).items()
                if direction == "output"]
        if not outs and "Y" in cell["connections"]:
            outs = ["Y"]
        for out in outs:
            for bit in cell["connections"][out]:
                if isinstance(bit, int):
                    if bit in drivers:
                        raise Unknown("MULTIPLE_DRIVERS")
                    drivers[bit] = (cname, cell, out)

    # Mark and cap diagnostic counters; they are not used to decide status.
    visiting: set[int] = set()
    counts = {"resolved_gates": 0, "affine_gate_ops": 0}
    memo_unknown = {}
    def resolve(bit) -> int:
        if bit in known:
            return known[bit]
        if bit in ("x", "z") or not isinstance(bit, int):
            raise Unknown("UNDEFINED_OR_INVALID_BIT")
        if bit in memo_unknown:
            raise Unknown(memo_unknown[bit])
        if bit in visiting:
            raise Unknown("COMBINATIONAL_LOOP")
        driver = drivers.get(bit)
        if driver is None:
            raise Unknown("UNDRIVEN_BIT " + str(bit))
        _, cell, yport = driver
        kind = cell["type"]
        if yport != "Y" or len(cell["connections"].get("Y", [])) != 1:
            raise Unknown("UNSUPPORTED_MULTI_OUTPUT_CELL")
        if kind not in SUPPORTED:
            memo_unknown[bit] = "UNSUPPORTED_CELL " + kind
            raise Unknown(memo_unknown[bit])
        visiting.add(bit)
        try:
            ins = {}
            for p, bits in cell["connections"].items():
                if p in ("A", "B", "S"):
                    if len(bits) != 1:
                        raise Unknown("NON_SCALAR_GATE_PORT")
                    ins[p] = resolve(bits[0])
            answer = evaluate_gate(kind, ins)
        except Unknown as ex:
            memo_unknown[bit] = str(ex)
            raise
        finally:
            visiting.remove(bit)
        known[bit] = answer
        counts["resolved_gates"] += 1
        counts["affine_gate_ops"] += 1
        return answer

    checked = []
    unknowns = []
    mismatch = None
    total_outputs = 0
    for pair in interface["pairs"]:
        a_port, b_port = pair["reference"], pair["candidate"]
        left, right = ports[a_port]["bits"], ports[b_port]["bits"]
        if len(left) != len(right):
            raise Unknown("OUTPUT_WIDTH_MISMATCH")
        total_outputs += len(left)
    for pair in interface["pairs"]:
        a_port, b_port = pair["reference"], pair["candidate"]
        left, right = ports[a_port]["bits"], ports[b_port]["bits"]
        for offset, (a, b) in enumerate(zip(left, right)):
            try:
                amask, bmask = resolve(a), resolve(b)
            except Unknown as ex:
                unknowns.append({"port": pair["port"], "position": offset,
                                 "why": str(ex)})
                continue
            delta = amask ^ bmask
            checked.append({"port": pair["port"], "position": offset,
                            "reference_mask": hex(amask),
                            "candidate_mask": hex(bmask),
                            "difference_mask": hex(delta)})
            if delta:
                # One output already proves whole modules DIFFERENT. Do not
                # reconstruct remaining outputs (especially with 2048 inputs).
                mismatch = (pair["port"], offset, a, b, delta)
                break
        if mismatch:
            break

    result = {"engine": "DRNAS-DELTA1-AFFINE-20261123",
              "input_basis": inputs,
              "output_count": total_outputs,
              "checked_outputs": checked,
              "unknown_outputs": unknowns,
              "metrics": {**counts, "input_bits": len(inputs),
                          "checked_output_bits": len(checked)},
              "trust_boundary": "exact on Yosys 2-state synthesized gate netlist"}
    if mismatch:
        port, offset, a, b, delta = mismatch
        # Construct a witness from the delta coefficients.
        # If constant=1, the all-zero vector falsifies equivalence.
        # Otherwise flip the least indexed variable with nonzero coefficient.
        state = 0
        if not (delta & 1):
            flag = delta & -delta
            state = flag >> 1
        witness = [{"port": v["port"], "position": v["position"],
                    "value": int(bool(state & (1 << v["index"])))}
                   for v in inputs]
        amask = next(x for x in checked
                     if x["port"] == port and x["position"] == offset)["reference_mask"]
        bmask = next(x for x in checked
                     if x["port"] == port and x["position"] == offset)["candidate_mask"]
        eval_affine = lambda m: ((m & 1).bit_count() +
                                 ((m >> 1) & state).bit_count()) & 1
        va, vb = eval_affine(int(amask, 16)), eval_affine(int(bmask, 16))
        if va == vb:
            raise Unknown("INTERNAL_WITNESS_NOT_DIFFERENT")
        result["witness"] = {"output_port": port, "position": offset,
                             "inputs": witness,
                             "reference_bit": va, "candidate_bit": vb}
        result["status"] = "DIFFERENT_NETLIST"
    elif unknowns:
        result["status"] = "UNKNOWN_UNSUPPORTED"
    elif len(checked) != total_outputs:
        result["status"] = "UNKNOWN_UNSUPPORTED"
        result["unknown_outputs"].append({"why": "INCOMPLETE_OUTPUT_COVERAGE"})
    else:
        result["status"] = "EQUIVALENT_NETLIST"
    return result


def write_certificate(netlist_file: Path, interface_file: Path, output: Path) -> dict:
    raw = netlist_file.read_bytes()
    ib = interface_file.read_bytes()
    result = analyze(json.loads(raw), json.loads(ib))
    result["netlist_sha256"] = hashlib.sha256(raw).hexdigest()
    result["interface_sha256"] = hashlib.sha256(ib).hexdigest()
    output.write_text(json.dumps(result, indent=2) + "\n")
    return result
