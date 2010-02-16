import numpy as np
from ase import Atoms
from ase.constraints import FixedPlane, FixAtoms
from ase.optimize.test import run_test
from gpaw import GPAW, Mixer
from gpaw.poisson import PoissonSolver

def get_calculator():
    basis = 'szp'
    calc = GPAW(gpts = (64, 64, 128), # ca h=0.25
                width = 0.1,
                nbands = -5,
                xc='LDA',
                mode='lcao',
                txt=None,
                mixer=Mixer(beta=0.1, nmaxold=5, weight=50.0),
                poissonsolver=PoissonSolver(nn='M', relax='GS'),
                stencils=(3, 3),
                basis=basis)
    return calc

def get_atoms():
    srf = Atoms('Cu64',[(1.2763,    1.2763,    4.0000),
                        (3.8290,    1.2763,    4.0000),
                        (6.3816,    1.2763,    4.0000),
                        (8.9343,    1.2763,    4.0000),
                        (1.2763,    3.8290,    4.0000),
                        (3.8290,    3.8290,    4.0000),
                        (6.3816,    3.8290,    4.0000),
                        (8.9343,    3.8290,    4.0000),
                        (1.2763,    6.3816,    4.0000),
                        (3.8290,    6.3816,    4.0000),
                        (6.3816,    6.3816,    4.0000),
                        (8.9343,    6.3816,    4.0000),
                        (1.2763,    8.9343,    4.0000),
                        (3.8290,    8.9343,    4.0000),
                        (6.3816,    8.9343,    4.0000),
                        (8.9343,    8.9343,    4.0000),
                        (0.0000,    0.0000,    5.8050),
                        (2.5527,    0.0000,    5.8050),
                        (5.1053,    0.0000,    5.8050),
                        (7.6580,    0.0000,    5.8050),
                        (0.0000,    2.5527,    5.8050),
                        (2.5527,    2.5527,    5.8050),
                        (5.1053,    2.5527,    5.8050),
                        (7.6580,    2.5527,    5.8050),
                        (0.0000,    5.1053,    5.8050),
                        (2.5527,    5.1053,    5.8050),
                        (5.1053,    5.1053,    5.8050),
                        (7.6580,    5.1053,    5.8050),
                        (0.0000,    7.6580,    5.8050),
                        (2.5527,    7.6580,    5.8050),
                        (5.1053,    7.6580,    5.8050),
                        (7.6580,    7.6580,    5.8050),
                        (1.2409,    1.2409,    7.6081),
                        (3.7731,    1.2803,    7.6603),
                        (6.3219,    1.3241,    7.6442),
                        (8.8935,    1.2669,    7.6189),
                        (1.2803,    3.7731,    7.6603),
                        (3.8188,    3.8188,    7.5870),
                        (6.3457,    3.8718,    7.6649),
                        (8.9174,    3.8340,    7.5976),
                        (1.3241,    6.3219,    7.6442),
                        (3.8718,    6.3457,    7.6649),
                        (6.3945,    6.3945,    7.6495),
                        (8.9576,    6.3976,    7.6213),
                        (1.2669,    8.8935,    7.6189),
                        (3.8340,    8.9174,    7.5976),
                        (6.3976,    8.9576,    7.6213),
                        (8.9367,    8.9367,    7.6539),
                        (0.0582,    0.0582,    9.4227),
                        (2.5965,   -0.2051,    9.4199),
                        (5.1282,    0.0663,    9.4037),
                        (7.6808,   -0.0157,    9.4235),
                        (-0.2051,   2.5965,    9.4199),
                        (2.1913,    2.1913,    9.6123),
                        (5.0046,    2.5955,    9.4873),
                        (7.5409,    2.5336,    9.4126),
                        (0.0663,    5.1282,    9.4037),
                        (2.5955,    5.0046,    9.4873),
                        (5.3381,    5.3381,    9.6106),
                        (7.8015,    5.0682,    9.4237),
                        (-0.0157,   7.6808,    9.4235),
                        (2.5336,    7.5409,    9.4126),
                        (5.0682,    7.8015,    9.4237),
                        (7.6155,    7.6155,    9.4317)])
    c2=Atoms('C2', [(3.2897,    3.2897,   10.6627),
                    (4.2113,    4.2113,   10.6493)])
    srf.extend(c2)
    srf.pbc=(1, 1, 0)
    srf.set_cell([ 10.2106, 10.2106, 20.6572],scale_atoms=False) 

    mask=[a.index < 32  for a in srf]
    c1 = FixedPlane(-1, (1/np.sqrt(2), 1/np.sqrt(2), 1))
    c2 = FixedPlane(-2, (1/np.sqrt(2), 1/np.sqrt(2), 1))
    constraint = FixAtoms(mask=mask)
    srf.set_constraint([constraint, c1, c2])
    return srf

run_test(get_atoms, get_calculator, 'C2_Cu100')
