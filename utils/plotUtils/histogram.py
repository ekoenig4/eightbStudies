from ..utils import flatten, autobin, get_bin_centers, get_bin_widths, is_iter, get_avg_std, init_attr, restrict_array, get_bin_centers
from ..xsecUtils import lumiMap
from ..classUtils import ObjIter,AttrArray
from . import function
from .graph import Graph
import numpy as np
import numba
import awkward as ak
import re
import copy

class Stats:
    def __init__(self,histo):
        self.nevents = np.sum(histo.histo)
        self.ess = self.nevents**2/np.sum(histo.error**2)
        if self.nevents > 0:

            if histo.array is not None:
                self.mean, self.stdv = get_avg_std(histo.array,histo.weights,histo.bins)
                self.minim, self.maxim = np.min(histo.array), np.max(histo.array)
            else:
                x = get_bin_centers(histo.bins)
                self.mean = np.sum(x*histo.histo)/self.nevents
                self.stdv = np.sqrt( np.sum( (histo.histo*(x - self.mean))**2 )/self.nevents )
                self.minim, self.maxim = x[histo.histo > 0][0], x[histo.histo > 0][-1]
        else:
            self.mean = self.stdv = self.minim = self.maxim = 0
        
    def __str__(self):
        return '\n'.join([ f'{key}={float(value):0.3e}' for key,value in vars(self).items() ])


@numba.jit(nopython=True, parallel=True, fastmath=True)
def numba_weighted_histo(array : np.array, bins : np.array, weights : np.array) -> np.array:
    counts = np.zeros( bins.shape[0]-1 )
    for i,(lo, hi) in enumerate(zip(bins[:-1],bins[1:])):
        mask = (array >= lo) & (array < hi)
        counts[i] = np.sum(weights[mask])
    errors = np.sqrt(counts)
    return counts,errors

@numba.jit(nopython=True, parallel=True, fastmath=True)
def numba_weighted_histo_sumw2(array : np.array, bins : np.array, weights : np.array) -> np.array:
    counts = np.zeros( bins.shape[0]-1 )
    errors = np.zeros( bins.shape[0]-1 )
    weights2 = weights**2
    for i,(lo, hi) in enumerate(zip(bins[:-1],bins[1:])):
        mask = (array >= lo) & (array < hi)
        counts[i] = np.sum(weights[mask])
        errors[i] = np.sum(weights2[mask])
    errors = np.sqrt(errors)
    return counts,errors

@numba.jit(nopython=True, parallel=True, fastmath=True)
def numba_unweighted_histo(array : np.array, bins : np.array) -> np.array:
    counts = np.zeros( bins.shape[0]-1 )
    for i,(lo, hi) in enumerate(zip(bins[:-1],bins[1:])):
        mask = (array >= lo) & (array < hi)
        counts[i] = np.sum(mask)
    errors = np.sqrt(counts)
    return counts,errors

def histogram(array, bins, weights, sumw2=False):
    if weights is None: return numba_unweighted_histo(array, bins)
    elif not sumw2: return numba_weighted_histo(array,bins,weights)
    return numba_weighted_histo_sumw2(array, bins, weights)

def apply_systematic(histo, error, systematic):
    if systematic is None: return error 

    if isinstance(systematic, float):
        systematic = systematic * histo
        error = np.sqrt( error**2 + systematic**2 )

    return error

class Histo:
    @staticmethod
    def add(this, that):
        try:
            np.testing.assert_allclose(this.bins, that.bins)
        except AssertionError:
            raise Warning("Unable to add histograms together")

        counts = this.histo + that.histo
        error = np.sqrt( this.error**2 + that.error**2 )

        return Histo(counts, this.bins, error)

    @classmethod
    def from_th1d(cls, th1d, scale=1, **kwargs):
        counts = scale*th1d.counts()
        error = scale*th1d.errors()
        bins = th1d.axis().edges()

        return cls(counts, bins, error, **kwargs)

    @classmethod
    def from_graph(cls, graph, **kwargs):
        y = graph.y_array 
        yerr = graph.yerr 
        
        x = graph.x_array 
        xerr = graph.xerr

        hi_edges = (x + xerr)
        lo_edges = (x - xerr)
        
        # n = (y/(yerr+1e-12))**2
        # n = n.round().astype(int)

        # w = yerr**2/(y+1e-12)
        
        bins = np.concatenate([lo_edges[:1], hi_edges])
        return cls(y, bins, yerr, **kwargs)

    @classmethod 
    def from_array(cls, array, bins=None, weights=None, nbins=30, rebin=None, restrict=False, sumw2=True, **kwargs):
        array = flatten(array)

        if weights is not None:
            weights = flatten(weights)
            if weights.shape != array.shape:
                weights = flatten(ak.ones_like(array)*weights)
        else:
            weights= np.ones(array.shape)
        
        bins = autobin(array, bins=bins, nbins=nbins)
        if rebin:
            bins = np.linspace(bins[0], bins[-1], rebin)

        if restrict:
            array, weights = restrict_array(array, bins=bins, weights=weights)

        counts, error = histogram(array, bins, weights, sumw2=sumw2)

        histo = cls(counts, bins, error=error, array=array, weights=weights, **kwargs)
        return histo

    def to_th1d(self, name="", title="", bin_labels=None):
        from array import array
        import ROOT 

        th1d = ROOT.TH1D(name, title, len(self.bins)-1, array('d', self.bins))
        for i, (n, e) in enumerate( zip(self.histo, self.error) ):
            th1d.SetBinContent(i+1, n)
            th1d.SetBinError(i+1, e)

            if bin_labels is not None:
                th1d.GetXaxis().SetBinLabel(i+1, bin_labels[i])
        

        return th1d


    def __init__(self, counts, bins, error=None, array=None, weights=None,
                       efficiency=False, density=False, cumulative=False, lumi=None, scale=1, plot_scale=1,
                       is_data=False, is_signal=False, is_model=False, fit=None, continous=False, ndata=None, 
                       systematics=None, label_stat='events', __id__=None, **kwargs):
        self.__id__ = __id__

        self.histo = counts 
        self.bins = bins 

        self.error = error
        if error is None:
            self.error = np.sqrt(counts)
        self.systematics = systematics

        self.array = array 
        self.weights = weights

        self.ndata = ndata 
        if ndata is None:
            self.ndata = np.sum(self.histo)
            
        self.is_data = is_data 
        self.is_signal = is_signal 
        self.is_bkg = not (is_data or is_signal)
        self.is_model = is_model

        lumi,_ = lumiMap.get(lumi,(lumi,None))
        self.lumi = lumi
        if not self.is_data: 
            self.histo = lumi*self.histo 
            self.error = lumi*self.error
            if self.weights is not None:
                self.weights = lumi*self.weights
            
        self.continous = continous
        
        self.stats = Stats(self)
        self.rescale(scale, efficiency=efficiency, density=density)

        fit_kwargs = { key[4:]:value for key,value in kwargs.items() if key.startswith('fit_') }
        self.kwargs = { key:value for key,value in kwargs.items() if not key.startswith('fit_') }
        self.fit = vars(function).get(fit, None)
        if self.fit is not None:
            self.fit = self.fit.fit_histo(self, **fit_kwargs)

        self.cdf(cumulative)
        self.set_attrs(label_stat=label_stat, plot_scale=plot_scale)


    def set_attrs(self, label_stat=None, plot_scale=1, systematics=None, **kwargs):
        if systematics is not None:
            self.add_systematics(systematics)

        kwargs = dict(self.kwargs, **kwargs)
        
        self.label = kwargs.get('label',None)
        self.plot_scale = plot_scale
        
        if self.plot_scale != 1:
            self.label = f"{self.label}($\\times${self.plot_scale})"

        self.kwargs = kwargs
        if label_stat is not None:
            self.set_label(label_stat)
        return self
    
    def rescale(self, scale=None, efficiency=False, density=False):
        if scale is None: scale = 1

        self.density = density 
        self.efficiency = efficiency
        self.scale = scale

        # if scale is 'xs': scale = scale/lumi
        # if density or efficiency or cumulative: scale = 1/np.sum(self.weights)
        if density or efficiency: scale = 1/np.sum(self.histo)

        self.histo = scale*self.histo
        self.error = scale*self.error
        self.add_systematics()

        if np.any( self.histo < 0 ):
            self.error = np.where(self.histo < 0, 0, self.error)
            self.histo = np.where(self.histo < 0, 0, self.histo)

        if self.density:
            self.widths = get_bin_widths(self.bins)
            self.histo /= self.widths 
            self.error /= self.widths
        return self


    # def __init__(self, array, bins=None, weights=None, efficiency=False, density=False, cumulative=False, lumi=None, restrict=False,
    #              label_stat='events', is_data=False, is_signal=False, is_model=False, sumw2=True, scale=1, plot_scale=1, __id__=None, fit=None,
    #              continous=False, ndata=None, nbins=30, rebin=None, systematics=None, transform=None,
    #              **kwargs):
    #     if transform is not None: array = transform(array)

    #     self.array = flatten(array)
    #     self.counts = len(self.array)
    #     self.ndata = self.counts if ndata is None else ndata

    #     if weights is not None:
    #         self.weights = flatten(weights)
    #         if self.weights.shape != self.array.shape:
    #             self.weights = flatten(ak.ones_like(array)*weights)
    #     else:
    #         self.weights= np.ones((self.counts,))

    #     self.systematics = systematics
    #     self.ndata = self.weights.sum()
        
    #     self.bins = autobin(self.array, bins=bins, nbins=nbins)
    #     if rebin:
    #         self.bins = np.linspace(self.bins[0], self.bins[-1], rebin)
        
    #     self.sumw2 = sumw2

    #     if restrict:
    #         self.array, self.weights = restrict_array(self.array, bins=self.bins, weights=self.weights)
        
    #     fit_kwargs = { key[4:]:value for key,value in kwargs.items() if key.startswith('fit_') }
    #     self.kwargs = { key:value for key,value in kwargs.items() if not key.startswith('fit_') }
    #     self.label = kwargs.get('label',None)

    #     if plot_scale != 1:
    #         self.label = f"{self.label}($\\times${plot_scale})"
        
    #     self.is_data = is_data 
    #     self.is_signal = is_signal 
    #     self.is_bkg = not (is_data or is_signal)
    #     self.is_model = is_model
        
    #     lumi,_ = lumiMap.get(lumi,(lumi,None))
    #     self.lumi = lumi
    #     if not is_data: self.weights = lumi * self.weights
            
    #     self.density = density 
    #     self.cumulative = cumulative
    #     self.efficiency = efficiency
    #     self.continous = continous
    #     self.plot_scale = plot_scale
    #     # if not (scale is None or is_iter(scale)):
    #     #     self.weights = scale*self.weights

    #     self.stats = Stats(self)      
    #     if scale is 'xs': scale = scale/lumi
    #     # if density or efficiency or cumulative: scale = 1/np.sum(self.weights)
    #     if density or efficiency: scale = 1/np.sum(self.weights)
    #     self.rescale(scale)

    #     self.fit = vars(function).get(fit, None)
    #     if self.fit is not None:
    #         self.fit = self.fit.fit_histo(self, **fit_kwargs)

    #     self.cdf(cumulative)
        
    #     self.set_label(label_stat)  

    # def __repr__(self):
    #     return f"<Histogram: {self.sample}>"
        
    # def rescale(self,scale):
    #     if scale is not None:
    #         if is_iter(scale): 
    #             scale = flatten(scale)

    #         self.weights = scale * self.weights
        
    #     self.histo, self.error = histogram(self.array, self.bins, self.weights, sumw2=self.sumw2)

    #     self.add_systematics()

    #     if np.any( self.histo < 0 ):
    #         self.error = np.where(self.histo < 0, 0, self.error)
    #         self.histo = np.where(self.histo < 0, 0, self.histo)

    #     if self.density:
    #         self.widths = get_bin_widths(self.bins)
    #         self.histo /= self.widths 
    #         self.error /= self.widths

    def add_systematics(self, systematics=None):
        if systematics is None: systematics = self.systematics
        if systematics is None: return
        if not isinstance(systematics, list): systematics = [systematics]

        for systematic in systematics:
            self.error = apply_systematic(self.histo, self.error, systematic)

                
    def cdf(self, cumulative):
        if hasattr(self, 'cumulative'): return self

        self.cumulative = cumulative

        if cumulative == 1: # CDF Below 
            if self.density: 
                self.histo *= self.widths
                self.error *= self.widths
            self.histo = np.cumsum(self.histo)
            self.error = np.sqrt( np.cumsum(self.error**2) )
        elif cumulative == -1: # CDF Above
            if self.density: 
                self.histo *= self.widths
                self.error *= self.widths
            self.histo = np.cumsum(self.histo[::-1])[::-1]
            self.error = np.sqrt(np.cumsum(self.error[::-1]**2))[::-1]
        return self

    def ecdf(self, sf=False):
        order = np.argsort(self.array)

        total = np.sum(self.weights)
        total_err = np.sqrt( np.sum(self.weights**2) )

        x = self.array[order]
        weights = self.weights[order]

        if np.issubdtype(x.dtype, np.integer):
            discrete_x = np.unique(x)
            discrete_w = ((x == discrete_x[:,None]) * weights).sum(axis=-1)

            x, weights = discrete_x, discrete_w

        x, weights = restrict_array(x, self.bins, weights=weights)

        y = weights.cumsum()/total
        y = np.clip(y, 0, 1)

        # yerr = 2*np.stack([y*total_err/total,(1-y)*total_err/total]).min(axis=0)

        weights = weights/total

        if sf: y = 1 - y

        return Graph(x, y, yerr=None, weights=weights, **self.kwargs)
        # return (x,y), dict(yerr=None, weights=weights, **self.kwargs)

    def sample(self, fraction=0.1):
        ndata = int(self.counts*fraction)
        mask = np.zeros_like(self.array)
        mask[:ndata] = 1
        mask = np.random.permutation(mask) == 1

        array = self.array[mask]
        weights = self.weights[mask] if self.weights is not None else None
        return Histo.from_array(array, bins=self.bins, weights=weights)
                    
    def set_label(self, label_stat='events'):
        nevents = self.stats.nevents
        mean = self.stats.mean
        stdv = self.stats.stdv
        
        
        if label_stat is None: pass
        elif callable(label_stat):
            label_stat = label_stat(self)
        elif any(re.findall(r'{(.*?)}', label_stat)):
            label_stat = label_stat.format(**vars(self))
        elif label_stat == 'events':
            label_stat = f'{nevents:0.2e}'
        elif label_stat == 'mean':
            label_stat = f'$\mu={mean:0.2}$'
        elif label_stat == 'mean_stdv':
            exponent = int(np.log10(np.abs(mean)))
            exp_str = "" if exponent == 0 else "\\times 10^{"+str(exponent)+"}"
            label_stat = f'$\mu={mean/(10**exponent):0.2f} \pm {stdv/(10**exponent):0.2f} {exp_str}$'
            # label_stat = f'$\mu={mean:0.2e}\pm{stdv:0.2e}$'
        elif label_stat == 'exp_lim':
            if hasattr(self.stats, 'exp_limits'):
                std_1 = max(self.stats.exp_limits[2+1]-self.stats.exp_limits[2], self.stats.exp_limits[2]-self.stats.exp_limits[2-1])
                label_stat = f'CL$^{{95\%}}r<{self.stats.exp_limits[2]:0.3}\pm{std_1:0.3}$'

        else: label_stat = f'{getattr(self.stats,label_stat):0.2e}'

        self.kwargs['label'] = self.label
        if label_stat is not None:
            if self.label is not None:
                self.kwargs['label'] = f'{self.kwargs["label"]} ({label_stat})'
            else:
                self.kwargs['label'] = f'{label_stat}'


class HistoList(ObjIter):

    @classmethod 
    def from_counts(cls, counts, bins=None, **kwargs):
        attrs = AttrArray(counts=counts, **kwargs)
        kwargs = attrs[attrs.fields[1:]]
        
        multi_binned = isinstance(bins, list)
    
        histolist = []
        for i,count in enumerate(counts):
            _bins = bins[i] if multi_binned else bins
            histo = Histo(count,bins=_bins, **{ key:value[i] for key,value in kwargs.items() })
            if bins is None: bins = histo.bins
            histolist.append(histo)
        return cls(histolist)

    @classmethod
    def from_arrays(cls, arrays, bins=None, **kwargs):
        attrs = AttrArray(arrays=arrays,**kwargs)
        kwargs = attrs[attrs.fields[1:]]
        
        multi_binned = isinstance(bins, list)
    
        histolist = []
        for i,array in enumerate(arrays):
            _bins = bins[i] if multi_binned else bins
            histo = Histo.from_array(array,bins=_bins, **{ key:value[i] for key,value in kwargs.items() })
            if not isinstance(bins, np.ndarray): bins = histo.bins
            histolist.append(histo)
        return cls(histolist)

    def __repr__(self): return f"HistoList<{repr(self.objs)}>"
            
class DataList(HistoList):

    @classmethod
    def from_arrays(cls, arrays, bins=None, histtype=None, **kwargs):
        return super(cls,cls).from_arrays(arrays, bins=bins, **kwargs)

    
    @classmethod
    def from_counts(cls, counts, bins=None, histtype=None, **kwargs):
        return super(cls,cls).from_counts(counts, bins=bins, **kwargs)

    def __repr__(self): return f"DataList<{repr(self.objs)}>"

class Stack(HistoList):

    @classmethod
    def from_counts(cls, counts, bins=None, density=False, cumulative=False, efficiency=False, stack_fill=False, label_stat='events', histtype=None, **kwargs):
        stack = super(cls,cls).from_counts(counts, bins=bins, label_stat=label_stat, **kwargs)
        if isinstance(label_stat, list): label_stat = label_stat[0]

        stack.stack_fill = stack_fill
        stack.bins = stack[-1].bins
        # stack.histo = sum([ h.histo for h in stack ])
        # stack.error = np.sqrt(sum([ h.error**2 for h in stack ]))

        stack.opts = dict(density=density, efficiency=efficiency, cumulative=cumulative, label_stat=label_stat, color='grey', label='MC-Bkg')

        if not stack_fill:
            # if density or cumulative or efficiency: 
            if density or efficiency: 
                nevents = stack.stats.nevents.npy.sum()
                stack.apply(lambda histo : histo.rescale(1/nevents))
            if cumulative:
                stack.apply(lambda histo : histo.cdf(cumulative))
        return stack

    @classmethod
    def from_arrays(cls, arrays, bins=None, density=False, cumulative=False, efficiency=False, stack_fill=False, label_stat='events', histtype=None, **kwargs):
        stack = super(cls,cls).from_arrays(arrays, bins=bins, label_stat=label_stat, **kwargs)
        if isinstance(label_stat, list): label_stat = label_stat[0]

        stack.stack_fill = stack_fill
        stack.bins = stack[-1].bins
        stack.array = np.concatenate([ h.array for h in stack ])
        stack.weights = np.concatenate([ h.weights for h in stack ])

        stack.opts = dict(density=density, efficiency=efficiency, cumulative=cumulative, label_stat=label_stat, color='grey', label='MC-Bkg')

        if not stack_fill:
            # if density or cumulative or efficiency: 
            if density or efficiency: 
                nevents = stack.stats.nevents.npy.sum()
                stack.apply(lambda histo : histo.rescale(1/nevents))
            if cumulative:
                stack.apply(lambda histo : histo.cdf(cumulative))
        return stack


    # def __init__(self, arrays, bins=None, density=False, cumulative=False, efficiency=False, stack_fill=False, label_stat='events', histtype=None, **kwargs):
    #     super().__init__(arrays, bins=bins, label_stat=label_stat, **kwargs)
    #     if isinstance(label_stat, list): label_stat = label_stat[0]

    #     self.stack_fill = stack_fill
    #     self.bins = self[-1].bins
    #     self.array = np.concatenate([ h.array for h in self ])
    #     self.weights = np.concatenate([ h.weights for h in self ])

    #     self.opts = dict(density=density, efficiency=efficiency, cumulative=cumulative, label_stat=label_stat, color='grey', label='MC-Bkg')

    #     if not stack_fill:
    #         # if density or cumulative or efficiency: 
    #         if density or efficiency: 
    #             nevents = self.stats.nevents.npy.sum()
    #             self.apply(lambda histo : histo.rescale(1/nevents))
    #         if cumulative:
    #             self.apply(lambda histo : histo.cdf(cumulative))

    def get_histo(self):
        if hasattr(self, 'array'):
            return Histo.from_array(self.array, self.bins, self.weights, systematics=self[0].systematics, **self.opts)
        
        # stack.histo = sum([ h.histo for h in stack ])
        # stack.error = np.sqrt(sum([ h.error**2 for h in stack ]))
        return Histo(self.histo, self.bins, self.error, systematics=self[0].systematics, **self.opts)
    def __repr__(self): return f"Stack<{repr(self.objs)}>"
        

class HistoFromGraph(Histo):
    def __init__(self, graph, bins=None, kernel=None, label_stat=None, eps=1e-1, **kwargs):

        kernel = {
            'gaussian':function.gaussian,

        }.get(kernel, None)

        kwargs['color'] = kwargs.get('color', graph.kwargs['color'])
        kwargs = { key:value for key,value in kwargs.items() if not key.startswith('fit_') }

        if kernel is None: 
            super().__init__(graph.y_array, bins=bins, label_stat=label_stat, **kwargs)
            return
    
        ndata = len(graph.y_array)
        # x_lo, x_hi = self.bins[0], self.bins[-1]
        # self.bins = np.linspace(x_lo, x_hi, nbins)
        
        array = np.array([])
        weights = np.array([])
        bins = autobin(graph.y_array) if bins is None else bins
        self.x_array = get_bin_centers(bins)
        for mu, sigma in zip(graph.y_array, graph.yerr):
            sigma = max(sigma, eps)
            array = np.concatenate([array, self.x_array])
            y = kernel.pdf(self.x_array, mu, sigma)
            weights = np.concatenate([weights, y])

        super().__init__(array, bins=bins, weights=weights, ndata=ndata, label_stat=label_stat, **kwargs)

class HistoListFromGraphs(ObjIter):
    def __init__(self, graphs, bins=None, **kwargs):
        attrs = AttrArray(graphs=graphs,**kwargs)
        kwargs = attrs[attrs.fields[1:]]

        histolist = []
        for i,graph in enumerate(graphs):
            histo = HistoFromGraph(graph,bins=bins, **{ key:value[i] for key,value in kwargs.items() })
            if bins is None: bins = histo.bins
            histolist.append(histo)
        super().__init__(histolist)
