"""
The parser for BMC
"""
from collections import Counter
import re

from z3 import *


# from pdr import * #marked


class tCube:
    # make a tcube object associated with frame t.
    def __init__(self, t=0):
        self.t = t
        self.cubeLiterals = list()

    def __lt__(self, other):
        return self.t < other.t

    def clone(self):
        ret = tCube(self.t)
        ret.cubeLiterals = self.cubeLiterals.copy()
        return ret

    def clone_and_sort(self):
        ret = tCube(self.t)
        ret.cubeLiterals = self.cubeLiterals.copy()
        ret.cubeLiterals.sort(key=lambda x: str(_extract(x)[0]))
        return ret

    def remove_true(self):
        self.cubeLiterals = [c for c in self.cubeLiterals if c is not True]

    def __eq__(self, other):
        return Counter(self.cubeLiterals) == Counter(other.cubeLiterals)

    def addModel(self, lMap, model, remove_input):  # not remove input' when add model
        no_var_primes = [l for l in model if str(l)[0] == 'i' or not str(l).endswith(
            '_prime')]  # no_var_prime -> i2, i4, i6, i8, i2', i4', i6' or v2, v4, v6
        if remove_input:
            no_input = [l for l in no_var_primes if str(l)[0] != 'i']  # no_input -> v2, v4, v6
        else:
            no_input = no_var_primes  # no_input -> i2, i4, i6, i8, i2', i4', i6' or v2, v4, v6
        # self.add(simplify(And([lMap[str(l)] == model[l] for l in no_input]))) # HZ:
        for l in no_input:
            self.add(lMap[str(l)] == model[l])  # TODO: Get model overhead is too high, using C API

    def remove_input(self):
        index_to_remove = set()
        for idx, literal in enumerate(self.cubeLiterals):
            children = literal.children()
            assert (len(children) == 2)

            if str(children[0]) in ['True', 'False']:
                v = str(children[1])
            elif str(children[1]) in ['True', 'False']:
                v = str(children[0])
            else:
                assert (False)
            assert (v[0] in ['i', 'v'])
            if v[0] == 'i':
                index_to_remove.add(idx)
        self.cubeLiterals = [self.cubeLiterals[i] for i in range(len(self.cubeLiterals)) if i not in index_to_remove]

    def addAnds(self, ms):
        for i in ms:
            self.add(i)

    def add(self, m):
        self.cubeLiterals.append(m)

    def true_size(self):
        """
        Remove the 'True' in list (not the BoolRef Variable)
        """
        return len(self.cubeLiterals) - self.cubeLiterals.count(True)

    def join(self, model):
        # first extract var,val from cubeLiteral
        literal_idx_to_remove = set()
        model = {str(var): model[var] for var in model}
        for idx, literal in enumerate(self.cubeLiterals):
            if literal is True:
                continue
            var, val = _extract(literal)
            var = str(var)
            assert (var[0] == 'v')
            if var not in model:
                literal_idx_to_remove.add(idx)
                continue
            val2 = model[var]
            if str(val2) == str(val):
                continue  # will not remove
            literal_idx_to_remove.add(idx)
        for idx in literal_idx_to_remove:
            self.cubeLiterals[idx] = True
        return len(literal_idx_to_remove) != 0

    def delete(self, i: int):
        res = tCube(self.t)
        for it, v in enumerate(self.cubeLiterals):
            if i == it:
                res.add(True)
                continue
            res.add(v)
        return res

    def cube(self):
        return simplify(And(self.cubeLiterals))

    # Convert the trans into real cube
    def cube_remove_equal(self):
        res = tCube(self.t)
        for literal in self.cubeLiterals:
            children = literal.children()
            assert (len(children) == 2)
            cube_literal = And(Not(And(children[0], Not(children[1]))), Not(And(children[1], Not(children[0]))))
            res.add(cube_literal)
        return res

    def __repr__(self):
        return str(self.t) + ": " + str(sorted(self.cubeLiterals, key=str))


def _extract(literaleq):
    # we require the input looks like v==val
    children = literaleq.children()
    assert (len(children) == 2)
    if str(children[0]) in ['True', 'False']:
        v = children[1]
        val = children[0]
    elif str(children[1]) in ['True', 'False']:
        v = children[0]
        val = children[1]
    else:
        assert False
    return v, val


class Header:
    def __init__(self, max_idx: int, nIn: int, nLatch: int, nOut: int, nAnd: int, nBad: int, nInvariant):
        self.max_var_index = max_idx
        self.inputs = nIn
        self.latches = nLatch
        self.outputs = nOut
        self.ands = nAnd
        self.bads = nBad
        self.invariants = nInvariant


class Latch:
    def __init__(self, _var: str, _next: str, _init: str):
        self.var = _var
        self.next = _next
        self.init = _init

    def __repr__(self):
        return str(self.var) + ", " \
               + str(self.next) + ", " \
               + str(self.init)


class AND:
    def __init__(self, _lhs: str, _rhs0: str, _rhs1: str):
        self.lhs = _lhs
        self.rhs0 = _rhs0
        self.rhs1 = _rhs1

    def __repr__(self):
        return str(self.lhs) + ", " \
               + str(self.rhs0) + ", " \
               + str(self.rhs1)


def read_in(fileName: str):
    """
    :param fileName:
    :return: inputs, latches, outputs, ands, bads, invariants, annotations
    """
    inputs = list()
    outputs = list()
    bads = list()
    latches = list()
    ands = list()
    invariants = list()
    annotations = list()

    HEADER_PATTERN = re.compile(r"aag (\d+) (\d+) (\d+) (\d+) (\d+)(?: (\d+))?(?: (\d+))?\n")
    IO_PATTERN = re.compile(r"(\d+)\n")
    LATCH_PATTERN = re.compile(r"(\d+) (\d+)(?: (\d+))?\n")
    AND_PATTERN = re.compile(r"(\d+) (\d+) (\d+)\n")
    ANNOTATION_PATTERN = re.compile(r"\S+ (\S+)\n")

    with open(fileName, 'r') as f:
        head_line = f.readline()
        cont = re.match(HEADER_PATTERN, head_line)
        if cont is None:
            print("Don't support constraint, fairness, justice property yet")
            exit(1)

        header = Header(
            int(cont.group(1)),
            int(cont.group(2)),
            int(cont.group(3)),
            int(cont.group(4)),
            int(cont.group(5)),
            int(cont.group(6)) if cont.group(6) is not None else 0,
            int(cont.group(7)) if cont.group(7) is not None else 0
        )

        input_num = header.inputs
        output_num = header.outputs
        bad_num = header.bads
        latch_num = header.latches
        and_num = header.ands
        invariant_num = header.invariants

        for line in f.readlines():
            if input_num > 0:
                h = re.match(IO_PATTERN, line)
                if h:
                    # print("input node")
                    inputs.append(h.group(1))
                    # print(str(h.group(1)))
                    input_num -= 1
            elif latch_num > 0:
                h = re.match(LATCH_PATTERN, line)
                if h:
                    # print("latches node")
                    if h.group(3) is None:
                        # print(h.groups())
                        latches.append(Latch(h.group(1), h.group(2), "0"))
                    else:
                        # print(h.groups())
                        latches.append(Latch(h.group(1), h.group(2), h.group(3)))
                    latch_num -= 1
            elif output_num > 0:
                h = re.match(IO_PATTERN, line)
                if h:
                    # print("output node")
                    outputs.append(h.group(1))
                    # print(str(h.group(1)))
                    output_num -= 1
            elif bad_num > 0:
                h = re.match(IO_PATTERN, line)
                if h:
                    # print("bad node")
                    bads.append(h.group(1))
                    # print(str(h.group(1)))
                    bad_num -= 1
            elif invariant_num > 0:
                h = re.match(IO_PATTERN, line)
                if h:
                    # print("invariant node")
                    invariants.append(h.group(1))
                    # print(str(h.group(1)))
                    invariant_num -= 1
            elif and_num > 0:
                h = re.match(AND_PATTERN, line)
                if h:
                    # print("and node")
                    # print(str(h.groups()))
                    ands.append(AND(h.group(1), h.group(2), h.group(3)))
                    and_num -= 1
            else:
                h = re.match(ANNOTATION_PATTERN, line)
                if h:
                    annotations.append(h.group(1))
        return inputs, latches, outputs, ands, bads, invariants, annotations


class Model:
    def __init__(self):
        self.inputs = []
        self.vars = []
        self.primed_vars = []
        self.inp_prime = []
        self.trans = tCube()
        self.init = tCube()
        self.post = tCube()
        self.pv2next = dict()
        self.inp_prime = []
        self.filename = ''

    def parse(self, fileName):
        """
        :param fileName:
        :return:
        """
        self.filename = fileName
        i, l, o, a, b, c, annotations = read_in(fileName)

        ann_i = 0
        # input node
        inp = dict()
        self.inputs = list()
        for it in i:
            if ann_i < len(annotations):
                name = "i" + it + "[" + annotations[ann_i] + "]"
            else:
                name = "i" + it
            ann_i += 1
            inp[it] = Bool(name)
            self.inputs.append(inp[it])

        # input'
        pinp = dict()
        self.inp_prime = list()
        for it in i:
            # pinp[it] = Bool(str(inp[it]) + '\'') # v -> v'
            pinp[it] = Bool(str(inp[it]) + '_prime')  # v -> v_prime, change this, because we want generate .smt2 later
            self.inp_prime.append(pinp[it])

        print("inputs: ", self.inputs)

        # vars of latch
        vs = dict()
        self.vars = list()
        for it in l:
            if ann_i < len(annotations):
                name = "v" + it.var + "[" + annotations[ann_i] + "]"
            else:
                name = "v" + it.var
            ann_i += 1
            vs[it.var] = Bool(name)
            self.vars.append(vs[it.var])

        # vars' of latch
        pvs = dict()
        self.primed_vars = list()
        for it in l:
            # pvs[it.var] = Bool(str(vs[it.var]) + '\'')
            pvs[it.var] = Bool(
                str(vs[it.var]) + '_prime')  # v -> v_prime, change this, because we want generate .smt2 later
            self.primed_vars.append(pvs[it.var])

        # and gate node => And(and1, and2)
        ands = dict()
        for it in a:
            rs0 = True
            rs1 = True
            if it.rhs0 == "1":
                rs0 = True
            elif it.rhs0 == "0":
                rs0 = False
            elif int(it.rhs0) & 1 != 0:
                v = str(int(it.rhs0) - 1)
                if v in inp.keys():
                    rs0 = Not(inp[v])
                elif v in vs.keys():
                    rs0 = Not(vs[v])
                elif v in ands.keys():
                    rs0 = Not(ands[v])
                else:
                    print("Error in AND definition, in node " + v)
                    exit(1)
            else:
                v = it.rhs0
                if v in inp.keys():
                    rs0 = inp[v]
                elif v in vs.keys():
                    rs0 = vs[v]
                elif v in ands.keys():
                    rs0 = ands[v]
                else:
                    print("Error in AND definition, in node " + v)
                    exit(1)

            if it.rhs1 == "1":
                rs1 = True
            elif it.rhs1 == "0":
                rs1 = False
            elif int(it.rhs1) & 1 != 0:
                v = str(int(it.rhs1) - 1)
                if v in inp.keys():
                    rs1 = Not(inp[v])
                elif v in vs.keys():
                    rs1 = Not(vs[v])
                elif v in ands.keys():
                    rs1 = Not(ands[v])
                else:
                    print("Error in AND definition, in node " + v)
                    exit(1)
            else:
                v = it.rhs1
                if v in inp.keys():
                    rs1 = inp[v]  # input
                elif v in vs.keys():
                    rs1 = vs[v]  # vars of latch (in dict)
                elif v in ands.keys():
                    rs1 = ands[v]
                else:
                    print("Error in AND definition, in node " + v)
                    exit(1)

            ands[it.lhs] = And(rs0, rs1)

        # initial condition, init = And(inits{Bool(latch_node)})
        inits_var = list()
        for it in l:
            if it.init == "0":
                inits_var.append(Not(vs[it.var]))
            elif it.init == "1":
                inits_var.append(vs[it.var])
        self.init.addAnds(inits_var)

        # transition. trans_items: asserts.
        trans_items = list()
        for it in l:
            if it.next == "1":
                trans_items.append(pvs[it.var] == And(True))
                self.pv2next[pvs[it.var]] = And(True)
            elif it.next == "0":
                trans_items.append(pvs[it.var] == And(False))
                self.pv2next[pvs[it.var]] = And(False)
            elif int(it.next) & 1 == 0:
                v = it.next
                if v in inp.keys():
                    trans_items.append(pvs[it.var] == inp[v])
                    self.pv2next[pvs[it.var]] = inp[v]
                elif v in vs.keys():
                    trans_items.append(pvs[it.var] == vs[v])
                    self.pv2next[pvs[it.var]] = vs[v]
                elif v in ands.keys():
                    trans_items.append(pvs[it.var] == ands[v])
                    self.pv2next[pvs[it.var]] = ands[v]
                else:
                    print("Error in transition relation")
                    exit(1)
            else:
                v = str(int(it.next) - 1)
                if v in inp.keys():
                    trans_items.append(pvs[it.var] == Not(inp[v]))
                    self.pv2next[pvs[it.var]] = Not(inp[v])
                elif v in vs.keys():
                    trans_items.append(pvs[it.var] == Not(vs[v]))
                    self.pv2next[pvs[it.var]] = Not(vs[v])
                elif v in ands.keys():
                    trans_items.append(pvs[it.var] == Not(ands[v]))
                    self.pv2next[pvs[it.var]] = Not(ands[v])
                else:
                    print("Error in transition relation")
                    exit(1)
        self.trans.addAnds(trans_items)

        print("trans:", self.trans.cube())
        # print(self.trans.cube())

        # postulate
        property_items = list()
        # bads
        # for it in b:
        for it in o:  # output as bad state
            tmp = int(it)
            if tmp & 1 == 0:
                if it in inp.keys():
                    property_items.append(Not(inp[it]))
                elif it in vs.keys():
                    property_items.append(Not(vs[it]))
                elif it in ands.keys():
                    property_items.append(Not(ands[it]))
                else:
                    print("Error in property definition")
                    exit(1)
            else:
                it = str(int(it) - 1)
                if it in inp.keys():
                    property_items.append(inp[it])
                elif it in vs.keys():
                    property_items.append(vs[it])
                elif it in ands.keys():
                    property_items.append(ands[it])
                else:
                    print("Error in property definition")
                    exit(1)

        self.post.addAnds(property_items)
        # self.post.add(Or(vs['54'], vs['66'], Not(vs['68']), Not(vs['56'])))
        # print("postAdded")
        print("self.inputs: ", self.inputs)
        print("self.vars: ", self.vars)
        return self.inputs, self.vars, self.primed_vars, self.init, self.trans, self.post, self.pv2next, self.inp_prime, self.filename


if __name__ == '__main__':
    pass
