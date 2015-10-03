# -*- coding: utf-8 -*-

import numpy as np
cimport numpy as np
from scipy.linalg.cython_blas cimport dgemm
from scipy.linalg.cython_lapack cimport dgesv
import cython
from libc.math cimport exp, sqrt
from libcpp cimport bool


cdef mdot(double alpha, double[::1,:] a, double[::1,:] b, double beta, double[::1,:] c):
    cdef:
        char *transa = 'n'
        char *transb = 'n'
        int m = a.shape[0], n=b.shape[1], k=a.shape[1]
    dgemm(transa, transb, &m, &n, &k, &alpha, &a[0, 0], &m, &b[0, 0],
                   &k, &beta, &c[0, 0], &m)

cdef solve(double[::1, :] A, double[::1, :] B):
    cdef int n = A.shape[0], nrhs = B.shape[1], info
    cdef np.ndarray[int] piv = np.zeros(n, dtype=np.intc)
    dgesv(&n, &nrhs, &A[0, 0], &n, &piv[0], &B[0, 0], &n, &info)

cdef extern from "hfc.h":
    void cgnew(size_t N, double *g, double dv, int k)

def gnew(np.ndarray[np.float64_t, ndim=2] g, double dv, int k):
    cdef int N=g.shape[0]
    cgnew(N, &g[0,0], dv, k)

cpdef g2flip(np.ndarray[np.float64_t, ndim=2] g,
             np.ndarray[np.float64_t, ndim=1] dv,
             lk):
    """Update the interacting Green function at arbitrary spinflips

    Using the Woodbury matrix identity it is possible to perform an
    update of two simultaneous spin flips. I calculate
    .. math :: G'_{ij} = G_{ij}
              - U_{if}(\delta_{fg} + U_{\bar{k}g})^{-1}G_{\bar{l}j}

    where :math:`i,j,l,k\in{1..L}` the time slices and :math:`f,g\in{1,2}`
    the 2 simultaneous spin flips. :math:`\bar{l}` lists the flipped
    spin entry
    .. math :: U_{if} = (\delta_{i\bar{l}} - G_{i\bar{l}})(\exp(-2V_\bar{l})-1)\delta_{\bar{l}f}

"""
    d2 = np.asfortranarray(np.eye(len(lk)))
    U = -g[:, lk].copy(order='A')
    np.add.at(U, lk, d2)
    U *= np.asfortranarray(np.exp(dv) - 1.)

    V = g[lk, :].copy(order='F')
    mat=np.asfortranarray(d2 + U[lk, :])
    solve(mat, V)

    mdot(-1., U, V, 1, g)


cdef extern from "gsl/gsl_rng.h":
    ctypedef struct gsl_rng_type:
        pass
    ctypedef struct gsl_rng:
        pass
    gsl_rng_type *gsl_rng_mt19937
    gsl_rng *gsl_rng_alloc(gsl_rng_type * T)
    double uniform "gsl_rng_uniform"(gsl_rng *r)
    void cyset_seed "gsl_rng_set"(gsl_rng *r, unsigned long int)

cdef extern from "gsl/gsl_randist.h":
    double normal "gsl_ran_gaussian"(gsl_rng *r, double sigma)

cdef gsl_rng *r = gsl_rng_alloc(gsl_rng_mt19937)

def set_seed(seed=84263):
    cyset_seed(r, seed)

@cython.boundscheck(False)
@cython.wraparound(False)
@cython.cdivision(True)
def updateDHS(np.ndarray[np.float64_t, ndim=2] gup,
              np.ndarray[np.float64_t, ndim=2] gdw,
              np.ndarray[np.float64_t, ndim=1] v,
              int subblock_len,
              bool Heatbath = True):
    cdef double dv, ratup, ratdw, rat
    cdef int j, i, up, dw, pair, sn, N=v.shape[0], acc = 0, nrat = 0
    sn = int(N/subblock_len)
    order = [int(a+subblock_len*b) for a in range(subblock_len) for b in range(sn)]
    for j in order:
        dv = -2.*v[j]
        ratup = 1. + (1. - gup[j, j])*(exp( dv)-1.)
        ratdw = 1. + (1. - gdw[j, j])*(exp(-dv)-1.)
        rat = ratup * ratdw
        if rat<0:
            nrat += 1
        if Heatbath:
            rat = rat/(1.+rat)

        if rat > uniform(r):
            acc += 1
            v[j] *= -1.
            cgnew(N, &gup[0,0],  dv, j)
            cgnew(N, &gdw[0,0], -dv, j)
    return acc, nrat
