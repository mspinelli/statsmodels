# -*- coding: utf-8 -*-
"""
A collection of smooth penalty functions.

Penalties on vectors take a vector argument and return a scalar
penalty.  The gradient of the penalty is a vector with the same shape
as the input value.

Penalties on covariance matrices take two arguments: the matrix and
its inverse, both in unpacked (square) form.  The returned penalty is
a scalar, and the gradient is returned as a vector that contains the
gradient with respect to the free elements in the lower triangle of
the covariance matrix.

All penalties are subtracted from the log-likelihood, so greater
penalty values correspond to a greater degree of penalization.

The penaties should be smooth so that they can be subtracted from log
likelihood functions and optimized using standard methods (i.e. L1
penalties do not belong here).
"""

import numpy as np

class Penalty(object):
    """
    A class for representing a scalar-value penalty.

    Parameters
    ----------
    wts : array-like
        A vector of weights that determines the weight of the penalty
        for each parameter.


    Notes
    -----
    The class has a member called `alpha` that scales the weights.
    """

    def __init__(self, wts):
        self.wts = wts
        self.alpha = 1.

    def func(self, params):
        """
        A penalty function on a vector of parameters.

        Parameters
        ----------
        params : array-like
            A vector of parameters.

        Returns
        -------
        A scalar penaty value; greater values imply greater
        penalization.
        """
        raise NotImplementedError

    def grad(self, params):
        """
        The gradient of a penalty function.

        Parameters
        ----------
        params : array-like
            A vector of parameters

        Returns
        -------
        The gradient of the penalty with respect to each element in
        `params`.
        """
        raise NotImplementedError


class NonePenalty(Penalty):
    """
    A penalty that does not penalize.
    """

    def __init__(self, **kwds):
        if kwds:
            import warnings
            warnings.warn('keywords will be ignored')

    def func(self, params):
        if params.ndim == 2:
            return np.zeros(params.shape[1:])
        else:
            return 0

    def deriv(self, params):
        return np.zeros(params.shape)

    def hessian(self, params):
        # returns diagonal of hessian
        return np.zeros(params.shape[0])


class L2(Penalty):
    """
    The L2 (ridge) penalty.
    """

    def __init__(self, wts=None):
        if wts is None:
            self.wts = 1.
        else:
            self.wts = wts
        self.alpha = 1.

    def func(self, params):
        return np.sum(self.wts * self.alpha * params**2)

    def grad(self, params):
        return 2 * self.wts * self.alpha * params


class L2Univariate(Penalty):
    """
    The L2 (ridge) penalty applied to each parameter.
    """

    def __init__(self, weights=None):
        if weights is None:
            self.weights = 1.
        else:
            self.weights = weights

    def func(self, params):
        return self.weights * params**2

    def deriv(self, params):
        return 2 * self.weights * params

    grad = deriv  # alias for compat

    def deriv2(self, params):
        return 2 * self.weights * np.ones(len(params))


class PseudoHuber(Penalty):
    """
    The pseudo-Huber penalty.
    """

    def __init__(self, dlt, wts=None):
        self.dlt = dlt
        if wts is None:
            self.wts = 1.
        else:
            self.wts = wts
        self.alpha = 1.

    def func(self, params):
        v = np.sqrt(1 + (params / self.dlt)**2)
        v -= 1
        v *= self.dlt**2
        return np.sum(self.wts * self.alpha * v, 0)

    def grad(self, params):
        v = np.sqrt(1 + (params / self.dlt)**2)
        return params * self.wts * self.alpha / v


class SCAD(Penalty):
    """
    The SCAD penalty of Fan and Li.

    The SCAD penalty is linear around zero as a L1 penalty up to threshold tau.
    The SCAD penalty is constant for values larger than c*tau.
    The middle segment is quadratic and connect the two segments with a continuous
    derivative.
    The penalty is symmetric around zero.

    Parameterization follows Boo, Johnson, Li and Tan 2011.
    Fan and Li use lambda instead of tau, and a instead of c. Fan and Li
    recommend setting c=3.7.

    f(x) = { tau |x|                                   if 0 <= |x| < tau
           { -(|x|^2 - 2 c tau |x| + tau^2) / (2 (c - 1)   if tau <= |x| < c tau
           { (c + 1) tau^2 / 2                         if c tau <= |x|


    References
    ----------
    Buu, Anne, Norman J. Johnson, Runze Li, and Xianming Tan. "New variable
    selection methods for zero‐inflated count data with applications to the
    substance abuse field."
    Statistics in medicine 30, no. 18 (2011): 2326-2340.

    Fan, Jianqing, and Runze Li. "Variable selection via nonconcave penalized
    likelihood and its oracle properties."
    Journal of the American statistical Association 96, no. 456 (2001):
    1348-1360.
    """

    def __init__(self, tau, c=3.7, weights=None):
        if weights is None:
            self.weights = 1.
        else:
            self.weights = weights
        self.tau = tau
        self.c = c

    def func(self, params):

        # 3 segments in absolute value
        tau = self.tau
        p_abs = np.atleast_1d(np.abs(params))
        res = np.empty(p_abs.shape, p_abs.dtype)
        res.fill(np.nan)
        mask1 = p_abs < tau
        mask3 = p_abs >= self.c * tau
        res[mask1] = tau * p_abs[mask1]
        mask2 = ~mask1 & ~mask3
        p_abs2 = p_abs[mask2]
        tmp = (p_abs2**2 - 2 * self.c * tau * p_abs2 + tau**2)
        res[mask2] = -tmp / (2 * (self.c - 1))
        res[mask3] = (self.c + 1) * tau**2 / 2.

        return (self.weights * res).sum(0)

    def grad(self, params):

        # 3 segments in absolute value
        tau = self.tau
        p = np.atleast_1d(params)
        p_abs = np.abs(p)
        p_sign = np.sign(p)
        res = np.empty(p_abs.shape)
        res.fill(np.nan)

        mask1 = p_abs < tau
        mask3 = p_abs >= self.c * tau
        mask2 = ~mask1 & ~mask3
        res[mask1] = p_sign[mask1] * tau
        tmp = p_sign[mask2] * (p_abs[mask2] - self.c * tau)
        res[mask2] = -tmp / (self.c - 1)
        res[mask3] = 0

        return self.weights * res

    def deriv2(self, params):
        """Second derivative of function

        This returns scalar or vector in same shape as params, not a square
        Hessian. If the return is 1 dimensional, then it is the diagonal of
        the Hessian.
        """

        # 3 segments in absolute value
        tau = self.tau
        p = np.atleast_1d(params)
        p_abs = np.abs(p)
        res = np.zeros(p_abs.shape)

        mask1 = p_abs < tau
        mask3 = p_abs >= self.c * tau
        mask2 = ~mask1 & ~mask3
        res[mask2] = -1 / (self.c - 1)

        return self.weights * res


class SCADSmoothed(SCAD):
    """
    The SCAD penalty of Fan and Li, quadratically smoothed around zero.

    This follows Fan and Li 2001 equation (3.7).

    Parameterization follows Boo, Johnson, Li and Tan 2011


    TODO: Use delegation instead of subclassing, so smoothing can be added to all
    penalty classes.

    """

    def __init__(self, tau, c=3.7, c0=None, wts=None, restriction=None):
        if wts is None:
            self.weights = 1.
        else:
            self.weights = wts
        self.alpha = 1.
        self.tau = tau
        self.c = c
        self.c0 = c0 if c0 is not None else tau * 0.1
        if self.c0 > tau:
            raise ValueError('c0 cannot be larger than tau')

        # get coefficients for quadratic approximation
        c0 = self.c0
        deriv_c0 = super(SCADSmoothed, self).grad(c0)
        value_c0 = super(SCADSmoothed, self).func(c0)
        self.aq1 = value_c0 - 0.5 * deriv_c0 * c0
        self.aq2 = 0.5 * deriv_c0 / c0
        self.restriction = restriction

    def func(self, params):
        # TODO: `and np.size(params) > 1` is hack for llnull, need better solution
        if self.restriction is not None and np.size(params) > 1:
            params = self.restriction.dot(params)
        # need to temporarily override weights for call to super
        # Note: we have the same problem with `restriction`
        weights = self.weights
        self.weights = 1.
        value = super(SCADSmoothed, self).func(params[None, ...])
        self.weights = weights

        # shift down so func(0) == 0
        value -= self.aq1
        #change the segment corrsponding to quadratic approximation
        p_abs = np.atleast_1d(np.abs(params))
        mask = p_abs < self.c0
        p_abs_masked = p_abs[mask]
        value[mask] = self.aq2 * p_abs_masked**2

        return (self.weights * value).sum(0)

    def grad(self, params):
        if self.restriction is not None and np.size(params) > 1:
            params = self.restriction.dot(params)
        # need to temporarily override weights for call to super
        weights = self.weights
        self.weights = 1.
        value = super(SCADSmoothed, self).grad(params)
        self.weights = weights

        #change the segment corrsponding to quadratic approximation
        p = np.atleast_1d(params)
        mask = np.abs(p) < self.c0
        value[mask] = 2 * self.aq2 * p[mask]

        if self.restriction is not None and np.size(params) > 1:
            return weights * value.dot(self.restriction)
        else:
            return weights * value

    def deriv2(self, params):
        if self.restriction is not None and np.size(params) > 1:
            params = self.restriction.dot(params)
        # need to temporarily override weights for call to super
        weights = self.weights
        self.weights = 1.
        value = super(SCADSmoothed, self).deriv2(params)
        self.weights = weights

        #change the segment corrsponding to quadratic approximation
        p = np.atleast_1d(params)
        #p_abs = np.abs(p)
        mask = np.abs(p) < self.c0
        #p_abs_masked = p_abs[mask]
        value[mask] = 2 * self.aq2

        if self.restriction is not None and np.size(params) > 1:
            # note: super returns 1d array for diag, i.e. hessian_diag
            # TODO: weights are missing
            return (self.restriction.T * value).dot(self.restriction)
        else:
            return value


class ConstraintsPenalty(object):
    """
    Penalty applied to linear transformation of parameters

    Parameters
    ----------
    penalty: instance of penalty function
        currently this requires an instance of a univariate, vectorized
        penalty class
    weights : None or ndarray
        weights for adding penalties of transformed params
    restriction : None or ndarray
        If it is not None, then restriction defines a linear transformation
        of the parameters. The penalty function is applied to each transformed
        parameter independently.


    Notes
    -----
    `restrictions` allows us to impose penalization on contrasts or stochastic
    constraints of the original parameters.
    Examples for these contrast are difference penalities or all pairs
    penalties.

    """

    def __init__(self, penalty, weights=None, restriction=None):

        self.penalty = penalty
        if weights is None:
            self.weights = 1.
        else:
            self.weights = weights

        if restriction is not None:
            restriction = np.asarray(restriction)

        self.restriction = restriction

    def func(self, params):
        """evaluate penalty function at params

        Parameter
        ---------
        params : ndarray
            array of parameters at which derivative is evaluated

        Returns
        -------
        deriv2 : ndarray
            value(s) of penalty function
        """
        # TODO: `and np.size(params) > 1` is hack for llnull, need better solution
        if self.restriction is not None: # and np.size(params) > 1:
            params = self.restriction.dot(params)

        value = self.penalty.func(params)

        return (self.weights * value.T).T.sum(0)

    def deriv(self, params):
        """first derivative of penalty function w.r.t. params

        Parameter
        ---------
        params : ndarray
            array of parameters at which derivative is evaluated

        Returns
        -------
        deriv2 : ndarray
            array of first partial derivatives
        """
        if self.restriction is not None: # and np.size(params) > 1:
            params = self.restriction.dot(params)

        value = self.penalty.deriv(params)

        if self.restriction is not None: # and np.size(params) > 1:
            return self.weights * value.T.dot(self.restriction)
        else:
            return (self.weights * value.T)

    grad = deriv

    def deriv2(self, params):
        """second derivative of penalty function w.r.t. params

        Parameter
        ---------
        params : ndarray
            array of parameters at which derivative is evaluated

        Returns
        -------
        deriv2 : ndarray, 2-D
            second derivative matrix
        """

        if self.restriction is not None and np.size(params) > 1:
            params = self.restriction.dot(params)

        value = self.penalty.deriv2(params)

        if self.restriction is not None:
            # note: univariate penalty returns 1d array for diag,
            # i.e. hessian_diag
            v = (self.restriction.T * value * self.weights)
            value = v.dot(self.restriction)
        else:
            value = np.diag(self.weights * value)

        return value


class L2ContraintsPenalty(ConstraintsPenalty):
    """convenience class of ConstraintsPenalty with L2 penalization

    """

    def __init__(self, weights=None, restriction=None, sigma_prior=None):

        if sigma_prior is not None:
            raise NotImplementedError('sigma_prior is not implemented yet')

        penalty = L2Univariate()

        super(L2ContraintsPenalty, self).__init__(penalty, weights=weights,
                                                  restriction=restriction)


class CovariancePenalty(object):

    def __init__(self, wt):
        self.wt = wt

    def func(self, mat, mat_inv):
        """
        Parameters
        ----------
        mat : square matrix
            The matrix to be penalized.
        mat_inv : square matrix
            The inverse of `mat`.

        Returns
        -------
        A scalar penalty value
        """
        raise NotImplementedError

    def grad(self, mat, mat_inv):
        """
        Parameters
        ----------
        mat : square matrix
            The matrix to be penalized.
        mat_inv : square matrix
            The inverse of `mat`.

        Returns
        -------
        A vector containing the gradient of the penalty
        with respect to each element in the lower triangle
        of `mat`.
        """
        raise NotImplementedError


class PSD(CovariancePenalty):
    """
    A penalty that converges to +infinity as the argument matrix
    approaches the boundary of the domain of symmetric, positive
    definite matrices.
    """

    def func(self, mat, mat_inv):
        try:
            cy = np.linalg.cholesky(mat)
        except np.linalg.LinAlgError:
            return np.inf
        return -2 * self.wt * np.sum(np.log(np.diag(cy)))

    def grad(self, mat, mat_inv):
        cy = mat_inv.copy()
        cy = 2*cy - np.diag(np.diag(cy))
        i,j = np.tril_indices(mat.shape[0])
        return -self.wt * cy[i,j]
