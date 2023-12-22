"""
Tests for qutip.solver.heom.bofin_fit
"""
import numpy as np
import pytest
from qutip.solver.heom.bofin_fit import (
    pack, unpack, _rmse, _fit, _leastsq, _run_fit, SpectralFitter,
    CorrelationFitter, OhmicBath

)
from qutip.solver.heom.bofin_baths import (
    UnderDampedBath
)
from qutip import sigmax


def test_pack():
    n = np.random.randint(100)
    before = np.random.rand(3, n)
    a, b, c = before
    assert len(pack(a, b, c)) == n * 3
    assert (pack(a, b, c) == before.flatten()).all()


def test_unpack():
    n = np.random.randint(100)
    before = np.random.rand(3, n)
    a, b, c = before
    assert (unpack(pack(a, b, c)) == before).all()


def test_rmse():
    lam = 0.05
    gamma = 4
    w0 = 2

    def func(x, lam, gamma, w0):
        return np.exp(-lam * x) + gamma / w0
    x = np.linspace(1, 100, 10)
    y = func(x, lam, gamma + 1e-8, w0)
    assert np.isclose(_rmse(func, x, y, lam, gamma, w0), 0)


def test_leastsq():
    w = np.linspace(0.1, 10 * 5, 1000)
    N = 2

    def spectral(w, a, b, c):
        tot = 0
        for i in range(len(a)):
            tot += (
                2
                * a[i]
                * b[i]
                * w
                / (((w + c[i]) ** 2 + b[i] ** 2)
                    * ((w - c[i]) ** 2 + b[i] ** 2))
            )
        return tot
    a, b, c = [list(range(2))]*3
    J = spectral(w, a, b, c)
    sigma = 1e-4
    J_max = abs(max(J, key=abs))
    wc = w[np.argmax(J)]
    guesses = pack([J_max] * N, [wc] * N, [wc] * N)
    lower = pack(
        [-100 * J_max] * N, [0.1 * wc] * N, [0.1 * wc] * N)
    upper = pack(
        [100 * J_max] * N, [100 * wc] * N, [100 * wc] * N)
    a2, b2, c2 = _leastsq(
        spectral,
        J,
        w,
        guesses=guesses,
        lower=lower,
        upper=upper,
        sigma=sigma,
    )
    J2 = spectral(w, a2, b2, c2)
    assert np.isclose(J, J2).all()


def test_fit():
    a, b, c = [list(range(2))] * 3
    w = np.linspace(0.1, 10 * 5, 1000)

    def spectral(w, a, b, c):
        tot = 0
        for i in range(len(a)):
            tot += (
                2
                * a[i]
                * b[i]
                * w
                / (((w + c[i]) ** 2 + b[i] ** 2)
                    * ((w - c[i]) ** 2 + b[i] ** 2))
            )
        return tot
    J = spectral(w, a, b, c)
    rmse, [a2, b2, c2] = _fit(spectral, J, w, N=2)
    J2 = spectral(w, a2, b2, c2)
    assert np.isclose(J, J2).all()
    assert rmse < 1e-15


def test_run_fit():
    a, b, c = [list(range(3))] * 3
    w = np.linspace(0.1, 10 * 5, 100)

    def spectral(w, a, b, c):
        tot = 0
        for i in range(len(a)):
            tot += (
                2
                * a[i]
                * b[i]
                * w
                / (((w + c[i]) ** 2 + b[i] ** 2)
                    * ((w - c[i]) ** 2 + b[i] ** 2))
            )
        return tot
    J = spectral(w, a, b, c)
    rmse, [a2, b2, c2] = _run_fit(spectral, J, w, final_rmse=1e-10)
    J2 = spectral(w, a2, b2, c2)
    assert np.isclose(J, J2).all()
    assert rmse < 1e-10


class TestSpectralFitter:

    def test_spectral_density_approx(self):
        J = 0.4
        a, b, c = [list(range(2))] * 3
        w = 1
        T = 1
        bath = SpectralFitter(T, sigmax(), 0, np.sin, Nk=2)
        assert bath._spectral_density_approx(w, a, b, c) == J
        a, b, c = [list(range(3))] * 3
        w = 2
        assert bath._spectral_density_approx(w, a, b, c) == J

    def test_get_fit(self):
        T = 1
        wc = 1
        w = np.linspace(0.1, 10 * wc, 1000)
        ud = UnderDampedBath(sigmax(), lam=0.05, w0=1, gamma=1, T=T, Nk=1)
        fs = SpectralFitter(T, sigmax(), w, ud.spectral_density, Nk=1)
        bath, _ = fs.get_fit(N=1)
        assert np.isclose(
            bath.spectral_density_approx(w)-ud.spectral_density(w),np.zeros_like(w),atol=1e-5).all()

    @pytest.mark.filterwarnings('ignore::RuntimeWarning')
    def test_generate_bath(self):
        Q = sigmax()
        T = 1
        w = np.linspace(0, 15, 20000)
        ud = UnderDampedBath(Q, lam=0.05, w0=1, gamma=1, T=T, Nk=1)
        fs = SpectralFitter(T, Q, w, ud.spectral_density, Nk=1)
        _, fitinfo = fs.get_fit(N=1)
        fbath = fs._generate_bath(fitinfo['params'])
        for i in range(len(fbath.exponents)):
            assert np.isclose(fbath.exponents[i].ck, ud.exponents[i].ck)
            if (fbath.exponents[i].ck2 != ud.exponents[i].ck2):
                assert np.isclose(fbath.exponents[i].ck2, ud.exponents[i].ck2)
            assert np.isclose(fbath.exponents[i].vk, ud.exponents[i].vk)


class TestCorrelationFitter:

    def test_corr_approx(self):
        t = np.linspace(0, 20, 50)  # TODO FIXX TESTS
        C = np.exp(-t)
        bath = CorrelationFitter(sigmax(), 1, t, C)
        t2 = np.linspace(0, 20, 100)  # TODO FIXX TESTS
        C2 = np.exp(-t2)
        assert np.isclose(C2, bath._C_fun(t2), rtol=1e-3).all()
        assert np.isclose(C, bath._C_array).all()

    def test_get_fit(self):
        a, b, c = [
            np.array([1, 1, 1]),
            np.array([-1, -1, -1]),
            np.array([1, 1, 1])]
        t = np.linspace(0, 10, 1000)
        corr = np.sum(
            a[:, None] * np.exp(b[:, None] * t) * np.exp(1j * c[:, None] * t),
            axis=0)
        bath = CorrelationFitter(Q=sigmax(), T=1, t=t, C=corr)
        bbath, fitInfo = bath.get_fit(Nr=3, Ni=3)
        a2, b2, c2 = fitInfo['params_real']
        a3, b3, c3 = fitInfo['params_imag']
        C2 = np.real(bath._corr_approx(t, a2, b2, c2))
        C3 = np.imag(bath._corr_approx(t, a3, b3, c3))
        assert np.isclose(np.real(corr), C2).all()
        assert np.isclose(np.imag(corr), C3).all()

    @pytest.mark.filterwarnings('ignore::RuntimeWarning')
    def test_generate_bath(self):
        Q = sigmax()
        T = 1
        t = np.linspace(0, 30, 200)
        ud = UnderDampedBath(Q, lam=0.05, w0=1, gamma=1, T=T, Nk=1)
        fc = CorrelationFitter(Q, T, t, ud.correlation_function)
        _, fitInfo = fc.get_fit(final_rmse=1e-5)
        fbath = fc._generate_bath(
            fitInfo['params_real'],
            fitInfo['params_imag'])
        fittedbath = fbath.correlation_function_approx(t)
        assert np.isclose(
            np.real(ud.correlation_function(t)),
            np.real(fittedbath),
            atol=1e-4).all()
        assert np.isclose(
            np.imag(ud.correlation_function(t)),
            np.imag(fittedbath),
            atol=1e-4).all()  # one order below final_rmse


class TestOhmicBath:
    def test_ohmic_spectral_density(self):
        mp = pytest.importorskip("mpmath")
        alpha = 0.5
        wc = 1
        T = 1
        Q = sigmax()
        w = np.linspace(0, 50 * wc, 10000)
        bath = OhmicBath(s=1, alpha=alpha, Q=Q, T=T, wc=wc)
        J = bath.spectral_density(w)
        J2 = bath.alpha * w * np.exp(-abs(w) / wc)
        assert np.isclose(J, J2).all()

    def test_ohmic_correlation(self):
        mp = pytest.importorskip("mpmath")
        alpha = 0.5
        wc = 1
        T = 1
        Q = sigmax()
        t = np.linspace(0, 10, 10)
        bath = OhmicBath(s=3, alpha=alpha, Q=Q, T=T, wc=wc)
        C = bath.correlation_function(t)
        Ctest = np.array(
            [
                1.11215545e00 + 0.00000000e00j,
                -2.07325102e-01 + 3.99285208e-02j,
                -3.56854914e-02 + 2.68834062e-02j,
                -1.02997412e-02 + 5.98374459e-03j,
                -3.85107084e-03 + 1.71629063e-03j,
                -1.71424113e-03 + 6.14748921e-04j,
                -8.66216773e-04 + 2.59388769e-04j,
                -4.81154330e-04 + 1.23604055e-04j,
                -2.87395509e-04 + 6.46270269e-05j,
                -1.81762994e-04 + 3.63396778e-05j,
            ]
        )
        assert np.isclose(C, Ctest).all()

    def test_make_correlation_fit(self):
        mp = pytest.importorskip("mpmath")
        w = np.linspace(0.1, 5, 2000)
        ob = OhmicBath(Q=sigmax(), T=1, alpha=0.05, wc=5, s=1)
        bath, fitinfo = ob.make_correlation_fit(w,Nr=3,Ni=3)
        assert np.isclose(
            np.real(bath.correlation_function(w) - bath.correlation_function_approx(w)),
            np.zeros_like(w),
            atol=3e-3).all() # this test can be closer but would take longer

    def test_make_spectral_fit(self):
        w = np.linspace(0, 80, 2000)
        ob = OhmicBath(Q=sigmax(), T=1, alpha=0.05, wc=5, s=1)
        bath, _ = ob.make_spectral_fit(w, rmse=1e-5)
        assert np.isclose(
            bath.spectral_density_approx(w) - bath.spectral_density(w),
            np.zeros_like(w),
            atol=2e-4).all()
