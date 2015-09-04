# -*- coding: utf-8 -*-
"""
@author: Óscar Nájera
"""
#from __future__ import division, absolute_import, print_function
from pytriqs.applications.impurity_solvers.cthyb import Solver
from pytriqs.archive import *
from pytriqs.gf.local import *
from pytriqs.operators import *
from time import time
import argparse
import dmft.RKKY_dimer as rt
import dmft.common as gf
import numpy as np
import pytriqs.utility.mpi as mpi

# Set the solver parameters
params = {
    'n_cycles': int(2e6),
    'length_cycle': 80,
    'n_warmup_cycles': int(5e4),
    'move_double': True,
#    'measure_pert_order': True,
    'random_seed': int(time()/2**14+time()/2**16*mpi.rank)
}

HINT = U * (n('up', 0) * n('down', 0) + n('up', 1) * n('down', 1))


def load_gf(g_iw, g_iwd, g_iwo):
    """Loads into the first greenfunction the equal diagonal terms and the
    offdiagonals. Input in GF_view"""

    g_iw['0', '0'] << g_iwd
    g_iw['1', '1'] << g_iwd
    g_iw['0', '1'] << g_iwo
    g_iw['1', '0'] << g_iwo


def mix_gf_dimer(gmix, omega, mu, tab):
    """Dimer formation Green function term

    .. math::

        G_{mix}(i\omega_n) =ao
    """
    gmix['0', '0'] = omega + mu
    gmix['0', '1'] = -tab
    gmix['1', '0'] = -tab
    gmix['1', '1'] = omega + mu
    return gmix


def cthyb_last_run(u_int, tp, BETA, file_str):
    u = 'U'+str(u_int)
    with rt.HDFArchive(file_str.format(tp=tp, BETA=BETA)) as last_run:
        lastit = mpi.bcast(last_run[u].keys()[-1])
        setup = mpi.bcast(last_run[u][lastit]['setup'])
        gd = mpi.bcast(last_run[u][lastit]['G_iwd'])
        go = mpi.bcast(last_run[u][lastit]['G_iwo'])

    S = Solver(beta=setup['BETA'], gf_struct={'up': [0, 1], 'down': [0, 1]},
               n_iw=setup['n_points'], n_tau=1025, n_l=15)

    for name, gblock in S.G_iw:
        load_gf(gblock, gd, go)

    U = setup['U']
    gmix = mix_gf_dimer(S.G_iw['up'].copy(), iOmega_n, U/2., setup['tp'])
    for name, g0block in S.G0_iw:
        g0block << inverse(gmix - 0.25*S.G_iw['up'])

    S.solve(h_int=HINT, **params)

    if mpi.is_master_node():
        with rt.HDFArchive(file_str.format(**setup)+'ct') as last_run:
            last_run[u]['it00/G_iw'] = S.G_iw
            last_run[u]['it00/G_tau'] = S.G_tau


parser = argparse.ArgumentParser(description='DMFT loop for a dimer bethe\
                                                      lattice solved by CTHYB')
parser.add_argument('beta', metavar='B', type=float,
                    default=20., help='The inverse temperature')
parser.add_argument('tp', default=0.18, help='The dimerization strength')

args = parser.parse_args()
ur = np.arange(2, 3, 0.1)
for u_int in ur:
    cthyb_last_run(u_int, args.tp, args.beta,
                   '/home/oscar/dev/dmft-learn/examples/Hirsh-Fye/disk/metf_HF_Ul_tp{tp}_B{BETA}.h5')
