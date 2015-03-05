# -*- coding: utf-8 -*-
"""
=========================
DMFT loop
=========================

To treat the Anderson impurity model and solve it using the continuous time
Quantum Monte Carlo algorithm in the hybridization expansion
"""
from __future__ import division, absolute_import, print_function
import sys
sys.path.append('/home/oscar/libs/lib')

import numpy as np
from dmft.common import matsubara_freq, greenF, gw_invfouriertrans, gt_fouriertrans
import pyalps.cthyb as cthyb  # the solver module
import pyalps.mpi as mpi     # MPI library (required)
from pyalps.hdf5 import archive


def save_pm_delta(parms, gtau):
    save_delta = archive(parms["DELTA"], 'w')
    delta = parms['t']**2 * gtau.mean(axis=0)
    save_delta['/Delta_0'] = delta
    save_delta['/Delta_1'] = delta
    del save_delta

def recover_measurement(parms, measure):
    iteration = archive(parms['BASENAME'] + '.out.h5', 'r')
    data = []
    for i in range(parms['N_ORBITALS']):
        data.append(iteration[measure+'/{}/mean/value'.format(i)])
    del iteration
    return np.asarray(data)

def save_iter_step(parms, iter_count, measure, data):
    save = archive(parms['BASENAME']+'steps.h5', 'w')
    for i, data_vector in enumerate(data):
        save['iter_{}/{}/{}/'.format(iter_count, measure, i)] = data_vector
    del save

def start_delta(parms):
    iwn = matsubara_freq(parms['BETA'], parms['N_MATSUBARA'])
    tau = np.linspace(0, parms['BETA'], parms['N_TAU']+1)

    giw = greenF(iwn, mu=0., D=2*parms['t'])
    gtau = gw_invfouriertrans(giw, tau, iwn, beta)

    save_pm_delta(parms, np.asarray((gtau, gtau)))


## DMFT loop
def dmft_loop(parms):
    gw_old = np.zeros(parms['N_MATSUBARA'])
    term = False
    iwn = matsubara_freq(parms['BETA'], parms['N_MATSUBARA'])
    tau = np.linspace(0, parms['BETA'], parms['N_TAU']+1)
    for n in range(20):
        cthyb.solve(parms)
        if mpi.rank == 0:
            print('dmft loop ', n)
            g_tau = recover_measurement(parms, 'G_tau')
            save_iter_step(parms, n, 'G_tau', g_tau)
            # inverting for AFM self-consistency
            save_pm_delta(parms, g_tau)
            g_w = recover_measurement(parms, 'G_omega').mean(axis=0)
            dev = np.abs(gw_old - g_w)[:20].max()
            print('conv criterion', dev)
            conv = dev < 0.01
            gw_old = g_w
            term = mpi.broadcast(value=conv, root=0)
        else:
            term = mpi.broadcast(root=0)

        mpi.world.barrier() # wait until solver input is written

        if term:
            print('end on iterartion: ', n)
            print('running longer time final avg')
            parms['MAX_TIME'] = 300
            cthyb.solve(parms)
            g_tau = recover_measurement(parms, 'G_tau')
            save_pm_delta(parms, g_tau)
            mpi.world.barrier() # wait until solver input is written
            break


## master looping
if __name__ == "__main__":
    BETA = [50.]#[8, 9, 13, 15, 18, 20, 25, 30, 40, 50]
    U = np.arange(1, 7, 0.4)
    for beta in BETA:
        for u_int in U:
            parms = {
                'SWEEPS'              : 100000000,
                'THERMALIZATION'      : 1000,
                'N_MEAS'              : 50,
                'MAX_TIME'            : 1,
                'N_HISTOGRAM_ORDERS'  : 50,
                'SEED'                : 5,

                'N_ORBITALS'          : 2,
                'DELTA'               : "delta_b{}.h5".format(beta, u_int),
                'DELTA_IN_HDF5'       : 1,
                'BASENAME'            : 'PM_MI_b{}_U{}'.format(beta, u_int),

                't'                   : 1.,
                'U'                   : u_int,
                'MU'                  : u_int/2.,
                'N_TAU'               : 1000,
                'N_MATSUBARA'         : 250,
                'MEASURE_freq'        : 1,
                'BETA'                : beta,
                'VERBOSE'             : 1,
                'SPINFLIP'            : 1,
            }
            if mpi.rank == 0 and u_int == U[0]:
                start_delta(parms)
                print('write delta at beta ', str(beta))

            mpi.world.barrier()

            dmft_loop(parms)
