"""
Main function to run BMC
"""
import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

import z3

import bmc
import model


def convert_aig_to_aag(file):
    aig_path = file
    with tempfile.TemporaryDirectory() as tmpdirname:
        aigtoaig_cmd='./aiger/aigtoaig'
        tmpdir = Path(tmpdirname)
        shutil.copy(aig_path, tmpdir)
        subprocess.call([aigtoaig_cmd, aig_path, tmpdir / "tmp.aag"])
        return bmc.BMC(*m.parse(tmpdir / "tmp.aag"))
        

if __name__ == '__main__':
    help_info = "Usage: python main.py <file-name>.aag (or <file-name>.aig) --k <unrolling steps>"
    parser = argparse.ArgumentParser(description="Run tests examples on the BMC algorithm")
    parser.add_argument('--aag', type=str, help='The name of the test to run', default=None, nargs='?')
    parser.add_argument('--k', type=int, help='The number of unrolling steps', default=10, nargs='?')
    args = parser.parse_args()
    m = model.Model()
    # UNSAFE 1 - simple
    #file = "dataset/aig_benchmark/hwmcc07_tip_aag/texas.ifetch1^8.E.aag"
    # UNSAFE 2 - toy
    #file = "dataset/aig_benchmark/hwmcc10-mod/shortp0.aag"
    # SAFE 1 - toy
    # file = "dataset/aig_benchmark/hwmcc07_tip/nusmv.syncarb5^2.B.aag"

    file = args.aag
    if file.endswith(".aig"): 
        bmc = convert_aig_to_aag(file)
    else:
        bmc = bmc.BMC(*m.parse(file))

    for _ in range(1, args.k): 
        print(f"Unrolling k = {_}")
        bmc.unroll()
        bmc.slv.push()
        bmc.add(z3.Not(bmc.post.cube()))
        if bmc.check() == z3.sat:
            print(f"SAT, k = {_}")
            exit(0)
        else:
            bmc.slv.pop()

    # reach here means UNSAT, k = args.k
    print(f"The result is unknown after k {args.k} bound")