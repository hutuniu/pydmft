# -*- coding: utf-8 -*-
r"""
Test over the two impurity rkky interaction
"""
# Created Mon Feb 22 10:45:05 2016
# Author: Óscar Nájera

from __future__ import division, absolute_import, print_function
import numpy as np
import pytest
import dmft.common as gf
import dmft.dimer as dimer
import slaveparticles.quantum.operators as op


def test_sorted_basis():
    """Test sorted fermion matrix operators respect commutation relations"""
    oper = dimer.sorted_basis()
    for i in range(4):
        for j in range(4):
            ant = op.anticommutator(oper[i], oper[j].T).todense()
            if i == j:
                assert np.allclose(ant, np.eye(16))
            else:
                assert np.allclose(ant, 0)


@pytest.mark.parametrize("u_int, mu, tp",
                         [(1, 0, 0.3), (2, 1, 0.5), (3, 0.2, 0.7)])
def test_hamiltonian_eigen_energies(u_int, mu, tp):
    """Test local basis and diagonal basis isolated dimer Hamiltonians
       have same energy spectrum"""
    h_loc, _ = dimer.hamiltonian(u_int, mu, tp)
    h_dia, _ = dimer.hamiltonian_diag(u_int, mu, tp)

    eig_e_loc, _ = op.diagonalize(h_loc.todense())
    eig_e_dia, _ = op.diagonalize(h_dia.todense())

    assert np.allclose(eig_e_loc, eig_e_dia)


@pytest.mark.parametrize("u_int, mu, tp",
                         [(1, 0, 0.3), (2, 0, 0.5), (3, 0., 0.8)])
def test_dimer_energies(u_int, mu, tp, beta=100):
    h_loc, (a_up, b_up, a_dw, b_dw) = dimer.hamiltonian(u_int, mu, tp)
    e_imp = (tp * (a_up.T * b_up + a_dw.T * b_dw +
                   b_up.T * a_up + b_dw.T * a_dw)).todense()
    eig_e, eig_v = op.diagonalize(h_loc.todense())
    w_n = gf.matsubara_freq(beta, 2**8)  # n=2**7=256
    gf_di = op.gf_lehmann(eig_e, eig_v, a_up.T, beta, 1j * w_n)
    gf_of = op.gf_lehmann(eig_e, eig_v, a_up.T, beta, 1j * w_n, b_up)
    ekin_gf = dimer.ekin(gf_di, gf_of, w_n, tp, beta, 0)
    ekin_ed = op.expected_value(e_imp, eig_e, eig_v, beta)

    assert abs(ekin_ed - ekin_gf) < 5e-4

    epot_gf = dimer.epot(gf_di, w_n, beta, u_int **
                         2 / 4 + tp**2, ekin_gf, u_int)

    docc = (a_up.T * a_up * a_dw.T * a_dw +
            b_up.T * b_up * b_dw.T * b_dw).todense()

    epot_ed = op.expected_value(docc, eig_e, eig_v, beta) * u_int

    assert abs(epot_ed - epot_gf) < 1e-3
