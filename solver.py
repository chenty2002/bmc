from z3 import *
import sys
from pathlib import Path

folder = Path(__file__).parent.parent
sys.path.append(str(folder))


class TCube:
    def __init__(self, t=0, solverName='z3'):
        self.t = t
        if solverName == 'z3':
            self.solver = Z3Solver()


class MSolver:
    def __init__(self):
        self.clauses = list()

    def newVar(self, name: str):
        raise NotImplementedError

    def newNot(self, var):
        raise NotImplementedError

    def addClause(self, clause):
        raise NotImplementedError

    def push(self):
        raise NotImplementedError

    def pop(self):
        raise NotImplementedError

    def check(self) -> bool:
        raise NotImplementedError

    def getModel(self):
        raise NotImplementedError


class Z3Solver(MSolver):
    def __init__(self):
        super().__init__()
        self.solver = Solver()

    def newVar(self, name: str):
        return Bool(name)

    def newNot(self, var):
        return Not(var)

    def addClause(self, clause):
        self.clauses.append(Or(clause))
        self.solver.add(Or(clause))

    def push(self):
        self.solver.push()

    def pop(self):
        self.solver.pop()

    def check(self) -> bool:
        if sat == self.solver.check():
            return True
        return False

    def getModel(self):
        if self.check():
            return self.solver.model()
        raise AssertionError("UNSAT")


if __name__ == '__main__':
    # s = MiniSat()
    s = Z3Solver()
    t = s.newVar("t")
    b = s.newVar('b')
    s.addClause([t])
    s.addClause([b])
    if s.check():
        print("YES")
        print(s.getModel())
    else:
        print("OK")

    s.push()
    s.addClause([s.newNot(t)])
    if s.check():
        print("SAT")
        print(s.getModel())
    else:
        print("UNSAT")
    s.pop()
    s.push()
    s.addClause([s.newVar('c')])
    if s.check():
        print("SAT")
        print(s.getModel())
    else:
        print("UNSAT")
    s.pop()
