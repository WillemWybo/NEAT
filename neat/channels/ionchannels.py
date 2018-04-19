import sympy as sp
import numpy as np


def _insert_function_prefixes(string, prefix='np', 
                              functions=['exp', 'sin', 'cos', 'tan', 'pi']):
    '''
    Prefix all occurences in the input `string` of the functions in the 
    `functions` list with the provided `prefix`.

    Parameters
    ----------
    string: string
        the input string
    prefix: string, optional
        the prefix that is put before each function. Defaults to `'np'`
    functions: list of strings, optional
        the list of functions that will be prefixed. Defaults to
        `['exp', 'sin', 'cos', 'tan', 'pi']`

    Returns
    -------
    string

    Examples
    --------
    >>> _insert_function_prefixes('5. * exp(0.) + 3. * cos(pi)')
    '5. * np.exp(0.) + 3. * np.cos(pi)'
    '''
    for func_name in functions:
        numpy_string = ''
        while len(string) > 0:
            ind = string.find(func_name)
            if ind == -1:
                numpy_string += string
                string = ''
            else:
                numpy_string += string[0:ind] + prefix + '.' + func_name
                string = string[ind+len(func_name):]
        string = numpy_string
    return string


class IonChannel(object):    
    '''
    Base class for all different ion channel types. 

    The algebraic form of the membrance current is stored in three numpy.arrays:
    `varnames`, `powers` and `factors`. An example of how the current is 
    computed is given below:
        `varnames` = ``[['a00', 'a01', 'a02'],
                        ['a10', 'a11', 'a12']]``
        `powers` = ``[[n00, n01, n02],
                      [n10, n11, n12]]``
        `factors` = ``[f0, f1]``
    Then the corresponding probability that the channel is open is given by
        math::`f0 a00^{n00} a01^{n01} a02^{n02} 
                + f1 a10^{n10} a11^{n11} a12^{n12})`
    
    Attributes
    ----------
    *Every derived class should define all these attributes in its constructor, 
    before the base class constructor is called*
    varnames : 2d numpy.ndarray of strings
        The names associated with each channel state variable
    powers : 2d numpy.ndarray of floats or ints
        The powers to which each state variable is raised to compute the 
        channels' open probalility
    factors : numpy.array of floats or ints
        factors which multiply each product of state variables in the sum
    varinf : 2d numpy.ndarray of sympy.expression instances
        The activation functions of the channel state variables
    tauinf : 2d numpy.ndarray of sympy.expression instances\
        The relaxation timescales of the channel state variables

    *The base class then defines the following attributes*
    statevars: 2d numpy.ndarray of sympy.symbols
        Symbols associated with the state variables
    fstatevar: 2d numpy.ndarray of sympy.expression instances
        The functions that give the time-derivative of the statevariables (i.e.
        math::`(varinf - var) / tauinf`)
    fun: sympy.expression
        The analytical form of the open probability
    coeff_curr: list of sympy.expression instances
        TODO
    coeff_statevar: list of sympy.expression instances
        TODO
    '''
    def __init__(self):
        '''
        Will give an error if initialized as is. Should only be initialized from
        it's derived classes.       
        '''
        if not hasattr(self, 'ion'):
            self.ion = ''
        if not hasattr(self, 'concentrations'):
            self.concentrations = []
        # these attributes should be defined
        if not hasattr(self, 'varnames'):
            raise AttributeError('\'varnames\' is not defined')
        if not hasattr(self, 'powers'):
            raise AttributeError('\'powers\' is not defined')
        if not hasattr(self, 'factors'):
            raise AttributeError('\'factors\' is not defined')
        # define the sympy functions
        self.spV = sp.symbols('V')
        self.statevars = np.zeros(self.varnames.shape, dtype=object)
        for ind, name in np.ndenumerate(self.varnames):
            self.statevars[ind] = sp.symbols(name)
        self.fstatevar = (self.varinf - self.statevars) / self.tauinf
        # construct the sympy function for the ion channel current
        terms = []
        for ii, factor in enumerate(self.factors):
            terms.append(factor)
            for jj, var in enumerate(self.statevars[ii]):
                terms[-1] *= var**self.powers[ii,jj]
        self.fun = sum(terms)
        # set the coefficients for the linear expansion
        # self.compute_lincoeff()

    def compute_lincoeff(self):
        '''
        computes coefficients for linear simulation
        '''
        # coefficients for computing current
        fun = self.fun #statevars**self.powers
        coeff = np.zeros(self.statevars.shape, dtype=object)
        # differentiate
        for ind, var in np.ndenumerate(self.statevars):
            coeff[ind] = sp.diff(fun, var,1)
        # substitute
        for ind, var in np.ndenumerate(self.statevars):
            fun = fun.subs(var, self.varinf[ind])
            for ind2, coe in np.ndenumerate(coeff):
                coeff[ind2] = coe.subs(var, self.varinf[ind])
        fun = fun.subs(self.spV, self.V0)
        for ind, coe in np.ndenumerate(coeff):
            coeff[ind] = coe.subs(self.spV, self.V0)
        self.coeff_curr = [np.float64(fun), coeff.astype(float)]
        
        # coefficients for state variable equations
        dfdv = np.zeros(self.statevar.shape, dtype=object)
        dfdx = np.zeros(self.statevar.shape, dtype=object)
        # differentiate
        for ind, var in np.ndenumerate(self.statevars):
            dfdv[ind] = sp.diff(self.fstatevar[ind], self.spV, 1)
            dfdx[ind] = sp.diff(self.fstatevar[ind], var, 1)
        # substitute state variables by their functions
        for ind, var in np.ndenumerate(self.statevars):
            dfdv[ind] = dfdv[ind].subs(var, self.varinf[ind])
        # substitute voltage by its value
        for ind, var in np.ndenumerate(self.statevars):
            dfdv[ind] = dfdv[ind].subs(self.spV, self.V0)
            dfdx[ind] = dfdx[ind].subs(self.spV, self.V0)

        self.coeff_statevar = [dfdv.astype(float), dfdx.astype(float)]

    def write_to_py_file(self):
        file = open('pychannels.py', 'a')
        file.write('\n\n')
        # append the new class
        file.write('class ' + self.__class__.__name__ + 'Sim(SimChannel):\n')
        # write the initialization function
        file.write('    def __init__(self, inloc_inds, Ninloc, es_eq, ' \
                        + 'g_max, e_rev, ' \
                        + 'flag=0, mode=1):\n')
        # write the specific attributes of the class
        power_string = '        self.powers = np.array(['
        for powers_row in self.powers:
            power_string += '['
            for power in powers_row:
                power_string += str(power) + ', '
            power_string += '], '
        power_string += '])\n'
        file.write(power_string)
        factor_string = '        self.factors = np.array(['
        for factor in self.factors:
            factor_string += str(factor) + ', '
        factor_string += '])\n'
        file.write(factor_string)
        # write call to base class constructor
        file.write('        super(' + self.__class__.__name__ + 'Sim, self)' \
                        + '.__init__(self, inloc_inds, Ninloc, es_eq, ' \
                        + 'g_max, e_rev, ' \
                        + 'flag=flag, mode=mode)\n\n')
        # write the functions for the asymptotic values of the state variables
        file.write('    def svinf(self, V):\n')
        file.write('        V = V[self.inloc_inds] if self.mode == 1 ' \
                                                      + 'else V\n')
        file.write('        sv_inf = np.zeros((%d, %d, '%self.varinf.shape \
                                               + 'self.Nelem))\n')
        for ind, var in np.ndenumerate(self.varinf):
            try:
                if self.spV in var.atoms():
                    file.write('        sv_inf[%d,%d,:] = '%ind 
                                        + _insert_function_prefixes(str(var)) \
                                        + '\n')
                else:
                    file.write('        sv_inf[%d,%d,:] = '%ind 
                                                           + str(float(var)) \
                                                           + '\n')
            except AttributeError:
                file.write('        sv_inf[%d,%d,:] = '%ind 
                                                       + str(float(var)) \
                                                       + '\n')

        file.write('        return sv_inf \n\n')
        # write the functions to evaluate relaxation times
        file.write('    def tauinf(self, V):\n')
        file.write('        V = V[self.inloc_inds] if self.mode == 1 ' \
                                                      + 'else V\n')
        file.write('        sv_inf = np.zeros((%d, %d, '%self.varinf.shape \
                                               + 'self.Nelem))\n')
        for ind, tau in np.ndenumerate(self.tauinf):
            try:
                if self.spV in tau.atoms():
                    file.write('        tau_inf[%d,%d,:] = '%ind \
                                        + _insert_function_prefixes(str(tau)) \
                                        + '\n')
                else:
                    file.write('        tau_inf[%d,%d,:] = '%ind \
                                                            + str(float(tau)) \
                                                            + '\n')
            except AttributeError:
                file.write('        tau_inf[%d,%d,:] = '%ind 
                                                        + str(float(tau)) \
                                                        + '\n')

        file.write('        return tau_inf \n\n')
        file.close()

    def write_mod_file(self):
        '''
        Writes a modfile of the ion channel for simulations with neuron
        '''
        file = open('../mech/I' + self.__class__.__name__ + '.mod', 'w')
        
        file.write(': This mod file is automaticaly generated by the \
                        ionc.write_mode_file() function in \
                        /source/ionchannels.py \n\n')
        
        file.write('NEURON {\n')
        file.write('    SUFFIX I' + self.__class__.__name__ + '\n')
        if self.ion == '':
            file.write('    NONSPECIFIC_CURRENT i' + '\n')
        else:
            file.write('    USEION ' + self.ion + ' WRITE i' + self.ion + '\n')
        if len(self.concentrations) > 0:
            for concstring in self.concentrations:
                file.write('    USEION ' + concstring + ' READ ' \
                                      + concstring + 'i' + '\n')
        file.write('    RANGE  g, e' + '\n')
        varstring = 'var0inf'
        taustring = 'tau0'
        for ind in range(len(self.varinf.flatten()[1:])):
            varstring += ', var' + str(ind+1) + 'inf'
            taustring += ', tau' + str(ind+1)
        file.write('    GLOBAL ' + varstring + ', ' + taustring + '\n')
        file.write('    THREADSAFE' + '\n')
        file.write('}\n\n')
        
        file.write('PARAMETER {\n')
        file.write('    g = ' + str(self.g*1e-6) + ' (S/cm2)' + '\n')
        file.write('    e = ' + str(self.e) + ' (mV)' + '\n')
        for ion in self.concentrations:
            file.write('    ' + ion + 'i (mM)' + '\n')
        file.write('}\n\n')
        
        file.write('UNITS {\n')
        file.write('    (mA) = (milliamp)' + '\n')
        file.write('    (mV) = (millivolt)' + '\n')
        file.write('    (mM) = (milli/liter)' + '\n')
        file.write('}\n\n')
        
        file.write('ASSIGNED {\n')
        file.write('    i' + self.ion + ' (mA/cm2)' + '\n')
        # if self.ion != '':
        #     f.write('    e' + self.ion + ' (mV)' + '\n')
        for ind in range(len(self.varinf.flatten())):
            file.write('    var' + str(ind) + 'inf' + '\n')
            file.write('    tau' + str(ind) + ' (ms)' + '\n')
        file.write('    v (mV)' + '\n')
        file.write('}\n\n')
        
        file.write('STATE {\n')
        for ind in range(len(self.varinf.flatten())):
            file.write('    var' + str(ind) + '\n')
        file.write('}\n\n')
        
        file.write('BREAKPOINT {\n')
        file.write('    SOLVE states METHOD cnexp' + '\n')
        calcstring = '    i' + self.ion + ' = g * ('
        l = 0
        for i in range(self.statevar.shape[0]):
            for j in range(self.statevar.shape[1]):
                for k in range(self.powers[i,j]):
                    calcstring += ' var' + str(l) + ' *'
                l += 1
            calcstring += str(self.factors[i,0])
            if i < self.statevar.shape[0] - 1:
                calcstring += ' + '
        # calcstring += ') * (v - e' + self.ion + ')'
        calcstring += ') * (v - e)'
        file.write(calcstring + '\n')
        file.write('}\n\n')
        
        concstring = ''
        for ion in self.concentrations:
            concstring += ', ' + ion + 'i'
        file.write('INITIAL {\n')
        file.write('    rates(v' + concstring + ')' + '\n')
        for ind in range(len(self.varinf.flatten())):
            file.write('    var' + str(ind) + ' = var' + str(ind) + 'inf' + '\n')
        file.write('}\n\n')
        
        file.write('DERIVATIVE states {\n')
        file.write('    rates(v' + concstring + ')' + '\n')
        for ind in range(len(self.varinf.flatten())):
            file.write('    var' + str(ind) + '\' = (var' + str(ind) \
                        + 'inf - var' + str(ind) + ') / tau' + str(ind) + '\n')
        file.write('}\n\n')
        
        concstring = ''
        for ion in self.concentrations:
            concstring += ', ' + ion
        file.write('PROCEDURE rates(v' + concstring + ') {\n')
        for ind, varinf in enumerate(self.varinf.flatten()):
            file.write('    var' + str(ind) + 'inf = ' \
                            + sp.printing.ccode(varinf) + '\n')
            file.write('    tau' + str(ind) + ' = ' \
                            + sp.printing.ccode(self.tau.flatten()[ind]) + '\n')
        file.write('}\n\n')
        
        file.close()


class SimChannel(object):
    def __init__(self, inloc_inds, Ninloc, es_eq, conc_eq,
                        g_max, e_rev, 
                        powers,
                        flag=0, mode=1):
        '''
        Creates a vectorized simulation object and accepts a vector of voltages.

        Let N be the number of state variables.

        Parameters
        ----------
        inloc_inds : numpy.array of ints
            indices of locations where ionchannel has to be simulated
        Ninloc : int
            the total number of input locations
        es_eq : float or numpy.array of floats
            The equilibrium potential. As float, signifies that the 
            equilibirum potential is the same everywhere. As numpy.array
            (number of elements equal to `Ninloc`), signifies the 
            equilibrium as each location
        g_max : numpy.array of floats
            The maximal conductance of the ion channel at each location
        e_rev : numpy.array of floats
            The reversal potential of the ion channel at each location
        flag : {0, 1}, optional
            Mode of simulation. `0` simulates the full current, `1` the 
            non-passive current. Defaults to 1
        mode : {0, 1}, optional 
            If 0, simulates the channel at all locations. If 1, only 
            simulates at the locations indicated in `inloc_inds`
        '''
        # integration mode
        self.flag = flag
        self.mode = mode
        # inloc info
        self.Ninloc = Ninloc
        self.inloc_inds = inloc_inds
        if mode == 1:
            self.Nelem = len(inloc_inds)
            self.elem_inds = copy.copy(self.inloc_inds)
        else:
            self.Nelem = Ninloc
            self.elem_inds = np.arange(self.Ninloc)
        # equilibirum potentials
        if type(es_eq) == float:
            self.es_eq = es_eq * np.ones(self.Ninloc)
        else:
            self.es_eq = es_eq
        # maximal conductance and reversal
        if mode == 1:
            self.g_max = g_max[inloc_inds]
            self.e_rev = e_rev[inloc_inds]
        else:
            self.g_max = g_max
            self.e_rev = e_rev
        # state variables array (initialized to equilibirum)
        self.sv = self.svinf(es_eq)
        # set equilibirum state variable values
        self.sv_eq = copy.deepcopy(self.sv)
        self.tau_eq = self.tauinf(self.es_eq[self.elem_inds])
        # equilibirum open probability
        self.p_open_eq = self.get_p_open(self.sv_eq)

    def reset(self):
        self.sv = self.sveq

    def get_p_open(self, sv=None):
        if sv == None: sv = self.sv
        self._p_open = np.sum(self.factors[:,np.newaxis] * \
                              np.product(sv**self.powers[:,:,np.newaxis], 
                                         1),
                              0)
        return self._p_open

    def set_p_open(self, illegal):
        raise AttributeError("`popen` is a read-only attribute")

    p_open = property(get_p_open, set_p_open)

    def advance(self, dt, V):
        '''
        Advance the ion channels internal variables one timestep

        Parameters
        ----------
            dt : float
                the timestep
            V : numpy.array of floats
                Voltage at each location
        '''
        svinf = self.svinf(V)
        tauinf = self.tauinf(V)
        prop1 = np.exp(-dt/tauinf)
        # advance the variables     
        self.sv *= prop1
        self.sv += (1. - prop1) * svinf

    def get_current_general(self, V, I_out=None):
        '''
        Get the channel current given the voltage, according to integration 
        paradigm

        Parameters
        ----------
        V : numpy.array of floats
            Location voltage (length should be equal to `self.Ninloc`)
        I_out : {numpy.array of floats, None}, optional
            Array to store the output current. Defaults to None, in which case
            a new array is created.

        Returns
        -------
        numpy.array of floats
            The channel current at each location
        '''
        if self.flag == 1:
            return self.get_current_np(V, I_out=I_out)
        else:
            return self.get_current(V, I_out=I_out)

    def get_current(self, V, I_out=None):
        '''
        Get the full channel current given the voltage.

        Parameters
        ----------
        V : numpy.array of floats
            Location voltage (length should be equal to `self.Ninloc`)
        I_out : {numpy.array of floats, None}, optional
            Array to store the output current. Defaults to None, in which case
            a new array is created.

        Returns
        -------
        numpy.array of floats
            The channel current at each location
        '''
        if I_out == None: I_out = np.zeros(self.Ninloc)
        if self.mode == 1:
            I_out[self.inloc_inds] -= self.g * self.p_open \
                                      * (V[self.inloc_inds] - self.e)
        else:
            I_out -= self.g * self.popen \
                     * (V - self.e)
        return I_out

    def get_current_np(self, V, I_out=None):
        '''
        Get the non-passive channel current given the voltage.

        Parameters
        ----------
        V : numpy.array of floats
            Location voltage (length should be equal to `self.Ninloc`)
        I_out : {numpy.array of floats, None}, optional
            Array to store the output current. Defaults to None, in which case
            a new array is created.

        Returns
        -------
        numpy.array of floats
            The channel current at each location
        '''
        if I_out == None: I_out = np.zeros(self.Ninloc)
        if self.mode == 1:
            I_out[self.inloc_inds] -= self.g_max \
                                      * (self.p_open - self.p_open_eq) \
                                      * (V[self.inloc_inds] - self.e_rev)
        else:
            I_out -= self.g_max \
                     * (self.p_open - self.p_open_eq) \
                     * (V - self.e_rev)
        return I_out

    def get_conductance_general(self, G_out=None, I_out=None):
        '''
        Let the channel current be :math:`-g (V-e)`. Returns :math:`-g` and 
        :math:`-g (E_eq-e)`. Returns the component according to integration 
        paradigm.

        Parameters
        ----------
        V : numpy.array of floats
            Location voltage (length should be equal to `self.Ninloc`)
        G_out : {numpy.array of floats, None}, optional
            Array to store the output :math:`-g`. Defaults to None, in 
            which case a new array is created.
        I_out : {numpy.array of floats, None}, optional
            Array to store the output :math:`-g (E_eq-e)`. Defaults to None, in 
            which case a new array is created.

        Returns
        -------
        (numpy.array of floats, numpy.array of floats)
            :math:`-g` at each location and :math:`-g (E_eq-e)` at each location
        '''
        if self.flag == 1:
            return self.get_conductance_np(G_out=G_out, I_out=I_out)
        else:
            return self.get_conductance(G_out=G_out, I_out=I_out)

    def get_conductance(self, G_out=None, I_out=None):
        '''
        Let the channel current be :math:`-g (V-e)`. Returns :math:`-g` and 
        :math:`-g (E_eq-e)`. Returns the full component

        Parameters
        ----------
        V : numpy.array of floats
            Location voltage (length should be equal to `self.Ninloc`)
        G_out : {numpy.array of floats, None}, optional
            Array to store the output :math:`-g`. Defaults to None, in 
            which case a new array is created.
        I_out : {numpy.array of floats, None}, optional
            Array to store the output :math:`-g (E_eq-e)`. Defaults to None, in 
            which case a new array is created.

        Returns
        -------
        (numpy.array of floats, numpy.array of floats)
            :math:`-g` at each location and :math:`-g (E_eq-e)` at each location
        '''
        if G_out == None: G_out = np.zeros(self.Ninloc)
        if I_out == None: I_out = np.zeros(self.Ninloc)
        p_open = self.p_open
        if self.mode == 1:
            G_out[self.inloc_inds] -= self.g_max * p_open
            I_out[self.inloc_inds] -= self.g_max * p_open \
                                      * (self.es_eq - self.e_rev)
        else:
            G_out -= self.g_max * p_open
            I_out -= self.g_max * p_open \
                     * (self.es_eq - self.e_rev)
        return G_out, I_out

    def get_conductance_np(self, G_out=None, I_out=None):
        '''
        Let the channel current be :math:`-g (V-e)`. Returns :math:`-g` and 
        :math:`-g (E_eq-e)`. Returns the non-passive component

        Parameters
        ----------
        V : numpy.array of floats
            Location voltage (length should be equal to `self.Ninloc`)
        G_out : {numpy.array of floats, None}, optional
            Array to store the output :math:`-g`. Defaults to None, in 
            which case a new array is created.
        I_out : {numpy.array of floats, None}, optional
            Array to store the output :math:`-g (E_eq-e)`. Defaults to None, in 
            which case a new array is created.

        Returns
        -------
        (numpy.array of floats, numpy.array of floats)
            :math:`-g` at each location and :math:`-g (E_eq-e)` at each location
        '''
        if G_out == None: G_out = np.zeros(self.Ninloc)
        if I_out == None: I_out = np.zeros(self.Ninloc)
        p_open = self.p_open - self.p_open_eq
        if self.mode == 1:
            G_out[self.inloc_inds] -= self.g_max * p_open
            I_out[self.inloc_inds] -= self.g_max * p_open \
                                      * (self.es_eq - self.e_rev)
        else:
            G_out -= self.g_max * p_open
            I_out -= self.g_max * p_open \
                     * (self.es_eq - self.e_rev)
        return G_out, I_out