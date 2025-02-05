import os
os.environ['KMP_WARNINGS'] = 'off'
import sys
import git

import uproot as ut
import awkward as ak
import numpy as np
import math
import vector
import sympy as sp

import re
from tqdm import tqdm
import timeit
import re

sys.path.append( git.Repo('.', search_parent_directories=True).working_tree_dir )
from utils import *

from utils.notebookUtils.driver.run_analysis import RunAnalysis
from utils.notebookUtils import required, dependency, optional

varinfo.feynnet_maxscore = dict(bins=(-0.05,1.05,30))
varinfo.feynnet_minscore = dict(bins=(-0.05,1.05,30))

org_features = [
    jet_ht, min_jet_deta, max_jet_deta, min_jet_dr, max_jet_dr, 
    'h_pt', 'h_j_dr', h_deta, h_dphi
]

new_features = [
    'X_m','Y1_m','Y2_m','H1Y1_m','H2Y1_m','H1Y2_m','H2Y2_m','feynnet_minscore','feynnet_maxscore'
]

@cache_variable(bins=(0,500,30))
def Y1_hm_chi(t):
    return np.sqrt( ak.sum( (t.h_m[:,:2]-125)**2, axis=1 ) )

@cache_variable(bins=(0,500,30))
def Y2_hm_chi(t):
    return np.sqrt( ak.sum( (t.h_m[:,2:]-125)**2, axis=1 ) )

hm_r = dict(
    ar=50,
    vr=100,
    cr=125,
)

bdtVersions = {
    'org': {
        'ar': ABCD(
            features=org_features,
            a=lambda t : (t.n_medium_btag >  4) & ( Y1_hm_chi(t) < 125/2 ) & ( Y2_hm_chi(t) < 125 ),
            b=lambda t : (t.n_medium_btag == 4) & ( Y1_hm_chi(t) < 125/2 ) & ( Y2_hm_chi(t) < 125 ),
            c=lambda t : (t.n_medium_btag >  4) & ( Y1_hm_chi(t) > 125/2 ) & ( Y2_hm_chi(t) < 125 ),
            d=lambda t : (t.n_medium_btag == 4) & ( Y1_hm_chi(t) > 125/2 ) & ( Y2_hm_chi(t) < 125 ),
        ),
        'vr': ABCD(
            features=org_features,
            a=lambda t : (t.n_medium_btag >  4) & ( Y1_hm_chi(t) < 125/2 ) & ( Y2_hm_chi(t) > 125 ),
            b=lambda t : (t.n_medium_btag == 4) & ( Y1_hm_chi(t) < 125/2 ) & ( Y2_hm_chi(t) > 125 ),
            c=lambda t : (t.n_medium_btag >  4) & ( Y1_hm_chi(t) > 125/2 ) & ( Y2_hm_chi(t) > 125 ),
            d=lambda t : (t.n_medium_btag == 4) & ( Y1_hm_chi(t) > 125/2 ) & ( Y2_hm_chi(t) > 125 ),
        )
    },
    "new":{
        'ar': ABCD(
            features=org_features,
            a=lambda t : (t.n_medium_btag > 4) & ( hm_chi(t) < hm_r['ar'] ),
            b=lambda t : ((t.n_medium_btag == 4)) & ( hm_chi(t) < hm_r['ar'] ),
            c=lambda t : (t.n_medium_btag > 4) & ( hm_chi(t) > hm_r['vr'] ) & ( hm_chi(t) < hm_r['cr'] ),
            d=lambda t : ((t.n_medium_btag == 4)) & ( hm_chi(t) > hm_r['vr'] ) & ( hm_chi(t) < hm_r['cr'] ),
        ),
        'vr': ABCD(
            features=org_features,
            a=lambda t : (t.n_medium_btag > 4) & ( hm_chi(t) > 50 ) & ( hm_chi(t) < hm_r['vr'] ),
            b=lambda t : ((t.n_medium_btag == 4)) & ( hm_chi(t) > 50 ) & ( hm_chi(t) < hm_r['vr'] ),
            c=lambda t : (t.n_medium_btag > 4) & ( hm_chi(t) > hm_r['vr'] ) & ( hm_chi(t) < hm_r['cr'] ),
            d=lambda t : ((t.n_medium_btag == 4)) & ( hm_chi(t) > hm_r['vr'] ) & ( hm_chi(t) < hm_r['cr'] ),
        )

    }
}

class Notebook(RunAnalysis):
    @staticmethod
    def add_parser(parser):
        parser.add_argument("--model", default='feynnet_trgkin_mx_my_reweight_extsig', help="specify the feynnet model to use for analysis")
        parser.add_argument("--bdt", default='new', help="specify the bdt version to use for analysis", choices=bdtVersions.keys()) 
        parser.add_argument("--serial", action='store_true', help="run in serial mode")
        parser.add_argument("--btag", type=lambda v : bool(int(v)), help="run btag selections", default=False)
        parser.set_defaults(
            module='fc.eightb.preselection.t8btag_minmass',
            use_signal='feynnet_plus_list',
        )

    @required
    def init(self, signal):
        
        # self.use_signal = [ i for i, mass in enumerate(signal.apply(lambda t : t.mass)) if mass in ( '(800, 350)', '(1200, 450)', '(1200, 250)' ) ]
        self.use_signal = [ i for i, mass in enumerate(signal.apply(lambda t : t.mass)) if mass in ( '(700, 300)', '(1000, 450)', '(1200, 500)' ) ]
        self.dout = f'feynnet/{self.model}/{self.bdt}'
        self.model = getattr(eightb.models, self.model)

        ar_bdt = bdtVersions[self.bdt]['ar']
        vr_bdt = bdtVersions[self.bdt]['vr']

        self.bdt = ar_bdt
        self.vr_bdt = vr_bdt

    @required
    def trigger_kinematics(self, signal, bkg, data):
        pt_filter = eightb.selected_jet_pt('trigger')

        def pfht(t):
            return ak.sum(t.jet_pt[(t.jet_pt > 30)], axis=-1)
        pfht_filter = EventFilter('pfht330', filter=lambda t : pfht(t) > 330)

        event_filter = FilterSequence(pfht_filter, pt_filter)
        self.signal = signal.apply(event_filter)
        self.bkg = bkg.apply(event_filter)
        self.data = data.apply(event_filter)

    @required
    def load_feynnet(self, signal, bkg, data):

        load_feynnet = eightb.f_load_feynnet_assignment(self.model.analysis)
        if self.serial:
            (signal+bkg+data).apply( load_feynnet, report=True )
        else:
            import multiprocessing as mp
            with mp.Pool(8) as pool:
            # import concurrent.futures as cf
            # with cf.ProcessPoolExecutor(5) as pool:
                (data+bkg+signal).parallel_apply( load_feynnet, report=True, pool=pool )
            # study.plot_timing(load_feynnet, saveas=f'{self.dout}/load_feynnet_timing')

        (signal+bkg+data).apply( add_h_j_dr, report=True )
        (signal+bkg+data).apply( eightb.assign, report=True )

    @dependency(load_feynnet)
    def feynnet_signal_efficiency(self, signal):
        fig, ax = study.get_figax(size=(10,8))

        study.mxmy_phase(
            signal,
            label=signal.mass.list,
            zlabel='Reconstruction Efficiency',
            efficiency=True,

            f_var=lambda t: ak.mean(t.x_signalId[t.nfound_select==8]==0),
            g_cmap='jet',

            xlabel='$M_X$ (GeV)',
            ylabel='$M_Y$ (GeV)',

            # xlim=(550,1250),
            # ylim=(200,650),
            zlim=np.linspace(0,1,11),

            figax=(fig,ax),
            saveas=f'{self.dout}/signal_efficiency_2d.png'
        )


    @required
    def btag_selections(self, signal, bkg, data):
        if not self.btag: return

        self.dout = f'{self.dout}/btag_selections'
        btag_filter = eightb.selected_jet_btagwp('loose')

        self.signal = signal.apply(btag_filter)
        self.bkg = bkg.apply(btag_filter)
        self.data = data.apply(btag_filter)

    @optional
    def plot_cutflow(self, signal, bkg, data):
        study.cutflow(
            signal[self.use_signal]+bkg+data,
            legend=True,
            size=(10,10),
            ylim=(1e2, 1e12),
            saveas=f'{self.dout}/cutflow',
        )

    def plot_signal_mcbkg(self, signal, bkg):
        study.quick(
            signal[self.use_signal]+bkg,
            legend=True,
            varlist=['X_m','Y1_m','Y2_m',None,'H1Y1_m','H2Y1_m','H1Y2_m','H2Y2_m'],
            efficiency=True,
            saveas=f'{self.dout}/signal_mcbkg',
        )

        study.quick(
            signal[self.use_signal]+bkg,
            legend=True,
            varlist=['n_loose_btag','n_medium_btag','n_tight_btag'],
            efficiency=True,
            saveas=f'{self.dout}/signal_mcbkg_btag',
        )

        study.quick(
            signal[self.use_signal]+bkg,
            varlist=new_features+org_features,
            h_rebin=15,
            legend=True,
            efficiency=True,
            saveas=f'{self.dout}/signal_mcbkg_bdt_features',
        )

    @required
    @dependency(load_feynnet)
    def force_feynnet(self):
        pass

    @required
    def blind_data(self, data):
        blinded = EventFilter('blinded', filter=lambda t :  ~self.bdt.a(t) )
        self.blinded_data = data.apply(blinded)
        self.bkg_model = self.blinded_data.asmodel()

    @optional
    def plot_blinded_data(self, bkg, blinded_data):
        study.quick(
            blinded_data+bkg,
            masks=lambda t: t.n_medium_btag == 3,
            varlist=['X_m', 'Y1_m', 'Y2_m', None]+[f'{H}_m' for H in eightb.higgslist],
            efficiency=True,
            legend=True,
            h_rebin=15,
            ratio=True,
            saveas=f'{self.dout}/blinded_data_3btag',
            # log=True,
        )

    
    def plot_feynnet_scores(self, signal, bkg, blinded_data):
        study.quick(
            signal[self.use_signal]+bkg,
            varlist=['feynnet_maxscore', 'feynnet_minscore'],
            h_rebin=15,
            legend=True,
            efficiency=True,
            saveas=f'{self.dout}/feynnet_scores',
        )

        study.quick(
            blinded_data+bkg,
            masks=lambda t : t.n_medium_btag == 3,
            varlist=['feynnet_maxscore', 'feynnet_minscore'],
            h_rebin=15,
            legend=True,
            ratio=True,
            efficiency=True,
            saveas=f'{self.dout}/feynnet_scores_3btag',
        )

    @optional
    def plot_abcd_region(self, blinded_data, bkg):
        study.quick(
            blinded_data+bkg,
            varlist=[hm_chi],
            binlist=[(0,300,30)],
            h_rebin=15,
            legend=True,
            ratio=True,
            efficiency=True,
            saveas=f'{self.dout}/hm_chi2',
        )

        study.quick2d(
            blinded_data,
            varlist=['H1Y1_m','H2Y1_m'],
            binlist=[(0,500,30),(0,500,30)],
            interp=True,
            h_cmap='jet',
            # size=(5,10),
            colorbar=True,

            exe=[
                draw_circle(x=125,y=125,r=50, text=None, linewidth=2),
                lambda ax, **kwargs : ax.text(125, 125, 'AR', horizontalalignment='center', verticalalignment='center', fontsize=20),

                draw_circle(x=125,y=125,r=75, text=None, linewidth=2, color='red'),
                lambda ax, **kwargs : ax.text(200, 200, 'VR', horizontalalignment='center', verticalalignment='center', fontsize=20, color='red'),

                draw_circle(x=125,y=125,r=125, text=None, linewidth=2, color='purple'),
                lambda ax, **kwargs : ax.text(250, 250, 'CR', horizontalalignment='center', verticalalignment='center', fontsize=20, color='purple'),
            ],
            saveas=f'{self.dout}/abcd_region',
        )

    def build_ar_bdt(self, bkg_model):
        txt = self.bdt.print_yields(bkg_model, return_lines=True)
        txtpath = study.make_path(f'{self.dout}/ar_bdt_yields.txt')
        with open(txtpath, 'w') as f:
            f.write('\n'.join(txt))
        print('\n'.join(txt))

    @dependency(build_ar_bdt)
    def train_ar_bdt(self, bkg_model):
        self.bdt.train(bkg_model)
        self.bdt.print_results(bkg_model)
    
    @dependency(train_ar_bdt)
    def plot_ar_bdt(self, signal, bkg_model):
        study.quick(
            signal[self.use_signal]+bkg_model,
            masks=[self.bdt.a]*len(self.use_signal) + [self.bdt.b]*len(bkg_model),
            scale=[1]*len(self.use_signal) + [self.bdt.reweight_tree]*len(bkg_model),
            varlist=['X_m', 'Y1_m', 'Y2_m', None]+[f'{H}_m' for H in eightb.higgslist],
            h_rebin=50,
            legend=True,
            saveas=f'{self.dout}/ar_bdt',
        )

    @dependency(train_ar_bdt)
    def plot_extraction_variables(self, signal, bkg_model):
        study.quick(
            signal[self.use_signal]+bkg_model,
            masks=[self.bdt.a]*len(self.use_signal) + [self.bdt.b]*len(bkg_model),
            scale=[1]*len(self.use_signal) + [self.bdt.reweight_tree]*len(bkg_model),
            varlist=['X_m',flatten_mxmy, hilbert_mxmy],
            h_rebin=50,
            legend=True,
            dim=-1,
            saveas=f'{self.dout}/extraction_variables',
        )   

    def _plot_limits(self, sig_models, tag):
        limits = np.array([
            [model.mx, model.my]+model.h_sig.stats.exp_limits
            for model in sig_models
        ])

        outfn = study.make_path(f'{self.dout}/{tag}_limits.csv')
        np.savetxt(outfn, limits, delimiter=',', header='mx,my,exp_lim_2.5,exp_lim_16,exp_lim_50,exp_lim_84,exp_lim_97.5')

        study.brazil_limits(
            sig_models,
            xlabel='my',
            saveas=f'{self.dout}/{tag}_limits_my',
        )

        study.brazil_limits(
            sig_models,
            xlabel='mx',
            saveas=f'{self.dout}/{tag}_limits_mx',
        )

        study.brazil2d_limits(
            sig_models,
            zlim=np.linspace(0,100,11),
            g_cmap='jet',
            saveas=f'{self.dout}/{tag}_2d_limits',
        )

        fig, ax = study.get_figax()
        pltargs = dict(
            g_markersize=2,
            legend=dict(loc='upper right'),
            ylim=(0,150),
            xlabel='$M_{X}$ [GeV]',
            ylabel=r'$\sigma(X\rightarrow YY\rightarrow 4H)$ [fb] @ 95% CL',
            grid=True,
        )
        for my in np.unique( limits[:,1] ):
            mx = limits[:,0][limits[:,1]==my]
            lim = limits[:,4][limits[:,1]==my]
            graph_array(mx, lim, g_label=f'MY={my} GeV', figax='same', **pltargs) 
        study.save_fig(fig, f'{self.dout}/{tag}_limits_mx_simple')

        nmodels = len(sig_models)
        fig, axs = study.get_figax(nmodels, sharey=True)
        for i, ax in enumerate(axs.flat):
            if i >= nmodels: 
                ax.set_visible(False)
                continue

            model = sig_models[i]
            plot_model(model, legend=True, figax=(fig, axs.flat[i]))
        study.save_fig(fig, f'{self.dout}/{tag}_models')


    @dependency(train_ar_bdt)
    def get_mx_limits(self, signal, bkg_model):
        sig_mx_models = study.limits(
            signal+bkg_model,
            masks=[self.bdt.a]*len(signal) + [self.bdt.b]*len(bkg_model),
            scale=[1]*len(signal) + [self.bdt.reweight_tree]*len(bkg_model),
            varlist=['X_m'],
            h_rebin=50,
            h_overflow=True,
            poi=np.linspace(0,10,31),
        )   

        self._plot_limits(sig_mx_models, 'mx')

    # @dependency(train_ar_bdt)
    # def get_flatten_mxmy_limits(self, signal, bkg_model):
    #     sig_flatten_mxmy_models = study.limits(
    #         signal+bkg_model,
    #         masks=[self.bdt.a]*len(signal) + [self.bdt.b]*len(bkg_model),
    #         scale=[1]*len(signal) + [self.bdt.reweight_tree]*len(bkg_model),
    #         varlist=[flatten_mxmy],
    #         binlist=[(0,1,50)],
    #         poi=np.linspace(0,10,31),
    #     )   

    #     self._plot_limits(sig_flatten_mxmy_models, 'flatten_mxmy')

    # @dependency(train_ar_bdt)
    # def get_hilbert_mxmy_limits(self, signal, bkg_model):
    #     sig_hilbert_mxmy_models = study.limits(
    #         signal+bkg_model,
    #         masks=[self.bdt.a]*len(signal) + [self.bdt.b]*len(bkg_model),
    #         scale=[1]*len(signal) + [self.bdt.reweight_tree]*len(bkg_model),
    #         varlist=[hilbert_mxmy],
    #         binlist=[(0,1,50)],
    #         poi=np.linspace(0,10,31),
    #     )   

    #     self._plot_limits(sig_hilbert_mxmy_models, 'hilbert_mxmy')

    def build_vr_bdt(self, bkg_model):
        txt = self.vr_bdt.print_yields(bkg_model, return_lines=True)
        txtpath = study.make_path(f'{self.dout}/vr_bdt_yields.txt')
        with open(txtpath, 'w') as f:
            f.write('\n'.join(txt))
        print('\n'.join(txt))

    @dependency(build_vr_bdt)
    def train_vr_bdt(self, bkg_model):
        self.vr_bdt.train(bkg_model)
        self.vr_bdt.print_results(bkg_model)

    @dependency(train_vr_bdt)
    def plot_vr_features(self, blinded_data, bkg_model):
        study.quick(
            blinded_data+bkg_model,
            masks=[self.vr_bdt.a]*len(blinded_data) + [self.vr_bdt.b]*len(bkg_model),
            scale=[1]*len(blinded_data) + [self.vr_bdt.scale_tree]*len(bkg_model),
            varlist=new_features+org_features,
            h_rebin=15,
            suptitle='VR BDT Pre-Fit',
            legend=True,

            ratio=True,
            **study.kstest,
            saveas=f'{self.dout}/vr_features_prefit',
        )

        study.quick(
            blinded_data+bkg_model,
            masks=[self.vr_bdt.a]*len(blinded_data) + [self.vr_bdt.b]*len(bkg_model),
            scale=[1]*len(blinded_data) + [self.vr_bdt.reweight_tree]*len(bkg_model),
            varlist=new_features+org_features,
            h_rebin=15,
            suptitle='VR BDT Post-Fit',
            legend=True,

            ratio=True,
            **study.kstest,
            saveas=f'{self.dout}/vr_features_postfit',
        )

    @dependency(train_vr_bdt)
    def plot_vr_bdt(self, blinded_data, bkg_model):
        study.quick(
            blinded_data+bkg_model,
            masks=[self.vr_bdt.a]*len(blinded_data) + [self.vr_bdt.b]*len(bkg_model),
            scale=[1]*len(blinded_data) + [self.vr_bdt.scale_tree]*len(bkg_model),
            varlist=['X_m', 'Y1_m', 'Y2_m', None]+[f'{H}_m' for H in eightb.higgslist],
            h_rebin=15,
            suptitle='VR BDT Pre-Fit',
            legend=True,

            ratio=True,
            **study.kstest,
            saveas=f'{self.dout}/vr_bdt_prefit',
        )

        study.quick(
            blinded_data+bkg_model,
            masks=[self.vr_bdt.a]*len(blinded_data) + [self.vr_bdt.b]*len(bkg_model),
            scale=[1]*len(blinded_data) + [self.vr_bdt.reweight_tree]*len(bkg_model),
            varlist=['X_m', 'Y1_m', 'Y2_m', None]+[f'{H}_m' for H in eightb.higgslist],
            h_rebin=15,
            suptitle='VR BDT Post-Fit',
            legend=True,

            ratio=True,
            **study.kstest,
            saveas=f'{self.dout}/vr_bdt_postfit',
        )



if __name__ == '__main__': 
    Notebook.main()