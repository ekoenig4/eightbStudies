from .. import *
from .. import eightbUtils as eightb

class eightb_analysis_v2(Analysis):
    @classmethod
    def _add_parser(self, parser):
        
        parser.add_argument('--dout', default='template',
                            help='specify directory to save plots into')
        parser.add_argument("--altfile", default=None,
                            help="output file pattern to write file with. Use {base} to substitute existing file")
        parser.add_argument('--ptwp', default='loose',
                            help='Specify preset working point for pt cuts')
        parser.add_argument('--ptcuts', type=float, nargs="*",
                            help='List of jet pt cuts to apply to selected jets')
        parser.add_argument('--use_regressed', default=False, action='store_true',
                            help='Use ptRegressed for pt cuts instead of regular pt')
        parser.add_argument('--btagwp', default='loose',
                            help='Specify preset working point for btag cuts')
        parser.add_argument('--btagcuts', type=int, nargs="*",
                            help='List of jet btag wps cuts to apply to selected jets')
        parser.add_argument('--sr-r', default=0.5, type=float,
                            help='Specify the radius to in higgs mass space for signal region')
        parser.add_argument('--cr-r', default=1.0, type=float,
                            help='Specify the radius to in higgs mass space for control region')
        
        bdt_features = [
            'jet_ht','min_jet_deta','max_jet_deta','min_jet_dr','max_jet_dr'
        ] + [
            f'h{i+1}_{var}'
            for var in ('pt','jet_dr')
            for i in range(4)
        ] + [
            f'h{i+1}{j+1}_{var}'
            for var in ('dphi','deta')
            for i in range(4)
            for j in range(i+1, 4)
        ]
        parser.add_argument('--bdt-features', nargs='+', default=bdt_features)

        return parser

    def plot_n1_histos(self, signal, bkg):
        
        varlist=['n_ele','n_mu','n_presel_jet']
        cuts = [1,1,8]
        selection = ['<','<','>=']
        for var, cut, sel in zip(varlist, cuts, selection):
            cut = draw_cut(x=cut, selection=sel)
            study.h_quick( 
                signal[self.use_signal]+bkg,
                h_label_stat=cut.get_eff,
                legend=True,
                log=True,
                plot_scale=[100]*len(self.use_signal),
                varlist=[var],
                exe=cut,
                saveas=f'{self.dout}/n1_histos/{var}',
            )

    def reweight_bkg(self, bkg):
        bkg.reweight(2.3)
        bkg.set_systematics(0.2)

    def plot_jet_kin_cuts(self, signal, bkg):
        if not self.ptcuts: self.ptcuts = self.ptwp
        ptcuts = eightb.get_jetpt_wp(str(self.ptcuts), self.ptcuts)

        fig, axs = study.get_figax(nvar=8, dim=(-1, 4))
        masks = []
        
        for i in range(8):
            cut=None
            if len(ptcuts) > i:
                cut = draw_cut(x=ptcuts[i])
                def _jet_pt_cut(t, i=i):
                    return t.jet_pt[:,i]>ptcuts[i]
            mask = lambda t : sum(mask(t) for mask in masks) == len(masks)
            study.quick( 
                    signal[self.use_signal]+bkg,
                    masks=mask if any(masks) else None,
                    h_label_stat=(cut.get_eff if cut is not None else None),
                    legend=True,
                    plot_scale=[100]*len(self.use_signal),
                    varlist=[f'jet_pt[:,{i}]'],
                    h_rebin=25,
                    exe=cut,
                    figax=(fig, axs.flat[i])
                )
            if cut is not None:
                masks.append(_jet_pt_cut)
        study.save_fig(fig, f'{self.dout}/n1_histos/jet_pt')
            
        (signal+bkg).apply(
            lambda t : t.extend(
                _jet_btag_ordered=ak.sort(t.jet_btag, axis=-1, ascending=False)
            )
        )
        if not self.btagcuts: self.btagcuts = self.btagwp
        btagcuts = eightb.get_jetbtag_wps(str(self.btagwp), self.btagwp)

        fig, axs = study.get_figax(nvar=8, dim=(-1, 4))
        for i in range(8):
            cut=None
            if len(btagcuts) > i:
                cut = draw_cut(x=jet_btagWP[btagcuts[i]])
                def _jet_btag_cut(t, i=i):
                    return t._jet_btag_ordered[:,i] > jet_btagWP[btagcuts[i]]
            mask = lambda t : sum(mask(t) for mask in masks) == len(masks)
            study.quick( 
                    signal[self.use_signal]+bkg,
                    masks=mask if any(masks) else None,
                    h_label_stat=(cut.get_eff if cut is not None else None),
                    legend=True,
                    plot_scale=[100]*len(self.use_signal),
                    varlist=[f'_jet_btag_ordered[:,{i}]'],
                    xlabels=[f'{ordinal(i+1)} jet_btag'],
                    binlist=[(0,1,30)],
                    h_rebin=25,
                    exe=cut,
                    figax=(fig, axs.flat[i])
                )
            if cut is not None:
                masks.append(_jet_btag_cut)
        study.save_fig(fig, f'{self.dout}/n1_histos/jet_btag')
    
    def jet_kin_cuts(self, signal, bkg, data):
        if not self.ptcuts: self.ptcuts = self.ptwp
        pt_filter = eightb.selected_jet_pt()

        if not self.btagcuts: self.btagcuts = self.btagwp
        btag_filter = eightb.selected_jet_btagwp()

        event_filter = FilterSequence(pt_filter, btag_filter)
        self.signal = signal.apply(event_filter)
        self.bkg = bkg.apply(event_filter)
        self.data = data.apply(event_filter)

    def cutflow(self, signal, bkg, data):
        cutflow_labels = [
            "total", "trigger","met filters", "muon veto", "electron veto", "n_presel_jets >= 8", "selected_jets", "selected_jets_pt", "selected_jets_btag"
        ]

        study.cutflow( 
            signal[self.use_signal] + bkg + data,
            ylim=(1e3, -1),
            xlabel=cutflow_labels,
            legend=True,
            saveas=f'{self.dout}/cutflow'
        )

    def plot_ranker(self, signal, bkg):
        study.quick(
            signal[self.use_signal]+bkg,
            efficiency=True,
            varlist=['yy_quadh_score','yy_quadh_minscore'],
            binlist=[(-0.05,1.05,30)],
            saveas=f'{self.dout}/ranker/reco_rank'
        )
        
    def plot_signal(self, signal):
        varinfo.nfound_select = dict(xlabel='N Higgs Jet')
        varinfo.nfound_presel = dict(xlabel='N Higgs Jet in Preselection')
        varinfo.nfound_select_h = dict(xlabel='N Higgs in Selection')
        varinfo.nfound_paired_h = dict(xlabel='N Higgs Paired')

        study.quick( 
            signal[self.use_signal],
            legend=True,
            varlist=['nfound_select','nfound_paired_h'],
            efficiency=True, ylim=(0,0.85), grid=True,
            saveas=f'{self.dout}/signal/signal_n_reco'
        )

        study.quick2d(
            signal[self.use_signal],
            legend=True,
            varlist=['nfound_presel','nfound_select'],
            efficiency=True,
            saveas=f'{self.dout}/signal/signal_nhiggs_jet'
        )

        study.quick2d(
            signal[self.use_signal],
            legend=True,
            varlist=['nfound_select_h','nfound_paired_h'],
            efficiency=True, show_counts=True, cmin=0.001,
            saveas=f'{self.dout}/signal/signal_nhiggs_paired'
        )

    def plot_unassigned_jet_kin(self, signal, bkg):
        for var in ('pt','btag','eta','phi',):
            study.quick( 
                signal[self.use_signal]+bkg,
                legend=True,
                plot_scale=[10]*len(self.use_signal),
                varlist=[f'jet_{var}[:,{i}]'  for i in range(8) ],
                h_rebin=25,
                dim=(-1, 4),
                saveas=f'{self.dout}/kin/unassigned_jet/{var}'
            )

    def plot_global_jet_kin(self, signal, bkg):
        def global_jet_kin(t):
            max_eta = t.jet_eta[ak.argmax(np.abs(t.jet_eta),axis=-1,keepdims=True)][:,0]
            min_eta = t.jet_eta[ak.argmin(np.abs(t.jet_eta),axis=-1,keepdims=True)][:,0]

            t.extend(
                jet_max_eta=max_eta,
                jet_min_eta=min_eta,
            )
        (signal+bkg).apply(global_jet_kin)
        
        for var in ('jet_ht','jet_max_eta','jet_min_eta'):
            study.quick( 
                signal[self.use_signal]+bkg,
                legend=True,
                plot_scale=[10]*len(self.use_signal),
                varlist=[var],
                h_rebin=25,
                saveas=f'{self.dout}/kin/global_jet/{var}'
            )

        study.quick(
            signal[self.use_signal]+bkg,
            legend=True,
            plot_scale=[10]*len(self.use_signal),
            varlist=['n_loose_btag','n_medium_btag','n_tight_btag'],
            dim=-1,
            saveas=f'{self.dout}/kin/global_jet/btag_multi'
        )

    def plot_assigned_jet_kin(self, signal, bkg):
        for var in ('pt','btag','eta','phi',):
            study.quick( 
                signal[self.use_signal]+bkg,
                legend=True,
                plot_scale=[10]*len(self.use_signal),
                varlist=[f'{quark}_{var}'  for quark in eightb.quarklist ],
                h_rebin=25,
                dim=(-1, 4),
                saveas=f'{self.dout}/kin/assigned_jet/{var}'
            )

    def plot_unassigned_higgs_kin(self, signal, bkg):
        for var in ('pt','m','jet_dr','eta'):
            study.quick( 
                signal[self.use_signal]+bkg,
                legend=True,
                plot_scale=[10]*len(self.use_signal),
                varlist=[f'higgs_{var}[:,{i}]' for i in range(4)],
                h_rebin=25,
                dim=(-1, 4),
                saveas=f'{self.dout}/kin/unassigned_higgs/{var}'
            )

    def plot_assigned_higgs_kin(self, signal, bkg):
        for var in ('pt','m','jet_dr','eta'):
            study.quick( 
                signal[self.use_signal]+bkg,
                legend=True,
                plot_scale=[10]*len(self.use_signal),
                varlist=[f'{higgs}_{var}' for higgs in eightb.higgslist],
                h_rebin=25,
                dim=(-1, 4),
                saveas=f'{self.dout}/kin/assigned_higgs/{var}'
            )

    def plot_assigned_y_kin(self, signal, bkg):
        for var in ('pt','m','higgs_dr','eta'):
            study.quick( 
                signal[self.use_signal]+bkg,
                legend=True,
                plot_scale=[10]*len(self.use_signal),
                varlist=[f'Y{i+1}_{var}' for i in range(2) ],
                h_rebin=25,
                dim=(-1, 2),
                saveas=f'{self.dout}/kin/y/{var}'
            )

    def plot_x_kin(self, signal, bkg, data):

        def renaming_variables(t):
            y1_p4 = build_p4(t, prefix='Y1')
            y2_p4 = build_p4(t, prefix='Y2')
            t.extend(
        #         higgs_jet_dr=t.higgs_dr,
        #         Y1_higgs_dr=t.Y1_dr,
        #         Y2_higgs_dr=t.Y2_dr,
                X_y_dr=calc_dr_p4(y1_p4, y2_p4),
            )
        (signal+bkg+data).apply(renaming_variables)

        study.quick( 
            signal[self.use_signal]+bkg,
            legend=True,
            plot_scale=[10]*len(self.use_signal),
            varlist=[f'X_{var}' for var in ('pt','m','y_dr','eta')],
            h_rebin=25,
            dim=(-1, 4),
            saveas=f'{self.dout}/kin/X_kin'
        )

    def build_higgs_dm(self, signal, bkg, data):
        h4m = signal.higgs_m.apply(lambda m : m[:10000]).cat.to_numpy()
        from scipy import optimize

        def calc_dm(center):
            n = len(center)
            dm = np.sqrt( np.sum( ( (h4m[:,:n]-center)/center )**2, axis=-1 ) )
            return dm

        def _find_best_(center):
            dm = calc_dm(center)
            mask = dm < 0.25
            return 1-np.mean(mask)
            # mu = ak.mean(dm[dm < 100])
            # return mu

        r0 = (125,125,125,125)
        self.center = optimize.fmin(_find_best_, r0,)
        print(np.round(self.center, 2))

        def get_higgs_dm(t, center=self.center):
            dm = [
                np.abs(t.higgs_m[:,i]-m)
                for i, m in enumerate(center)
            ]  
            dm = ak_stack(dm, axis=1)
            
            rm = [
                np.abs(t.higgs_m[:,i]/m)
                for i, m in enumerate(center)
            ]  
            rm = ak_stack(rm, axis=1)

            log_rm = np.abs(np.log10(rm))
            t.extend(higgs_dm=dm, higgs_rm=rm, higgs_log_rm=log_rm)
        (signal+bkg+data).apply(get_higgs_dm)

        def set_hiyj_dm(t):
            dm = t.higgs_dm 
            rm = t.higgs_rm
            log_rm = t.higgs_log_rm

            hiyj_dm = {
                f'H{j}Y{i}_dm':dm[ak.from_regular(t[f'Y{i}_h{j}Idx'][:,None])][:,0]
                for i in (1,2)
                for j in (1,2)
            }
            
            y1_h_dm = np.sqrt( (hiyj_dm['H1Y1_dm'])**2 + (hiyj_dm['H2Y1_dm'])**2)
            y2_h_dm = np.sqrt( (hiyj_dm['H1Y2_dm'])**2 + (hiyj_dm['H2Y2_dm'])**2)

            hiyj_rm = {
                f'H{j}Y{i}_rm':rm[ak.from_regular(t[f'Y{i}_h{j}Idx'][:,None])][:,0]
                for i in (1,2)
                for j in (1,2)
            }

            y1_h_rm = np.sqrt( (hiyj_rm['H1Y1_rm']-1)**2 + (hiyj_rm['H2Y1_rm']-1)**2)
            y2_h_rm = np.sqrt( (hiyj_rm['H1Y2_rm']-1)**2 + (hiyj_rm['H2Y2_rm']-1)**2)

            hiyj_log_rm = {
                f'H{j}Y{i}_log_rm':log_rm[ak.from_regular(t[f'Y{i}_h{j}Idx'][:,None])][:,0]
                for i in (1,2)
                for j in (1,2)
            }
            
            y1_h_log_rm = np.sqrt( (hiyj_log_rm['H1Y1_log_rm'])**2 + (hiyj_log_rm['H2Y1_log_rm'])**2)
            y2_h_log_rm = np.sqrt( (hiyj_log_rm['H1Y2_log_rm'])**2 + (hiyj_log_rm['H2Y2_log_rm'])**2)

            t.extend(**hiyj_dm, Y1_h_dm=y1_h_dm, Y2_h_dm=y2_h_dm, **hiyj_rm, Y1_h_rm=y1_h_rm, Y2_h_rm=y2_h_rm, **hiyj_log_rm, Y1_h_log_rm=y1_h_log_rm, Y2_h_log_rm=y2_h_log_rm, )

        (signal+bkg+data).apply(set_hiyj_dm)

    def plot_unassigned_higgs_m(self, signal, bkg):
        study.pairplot(
            signal[self.use_signal]+bkg,
            legend=True,
            varlist=[f'higgs_m[:,{i}]' for i in range(4)],
            binlist=[(0,500,30)]*4,
            scatter=dict(alpha=0.1, fraction=10000, size=1, discrete=True),
            saveas=f'{self.dout}/pairplot/unassigned_higgs/bkg_m'
        )
        
        study.pairplot(
            signal[self.use_signal]+bkg,
            legend=True,
            varlist=[f'higgs_dm[:,{i}]' for i in range(4)],
            binlist=[(0,250,30)]*4,
            scatter=dict(alpha=0.1, fraction=10000, size=1, discrete=True),
            saveas=f'{self.dout}/pairplot/unassigned_higgs/bkg_dm'
        )
        
        study.pairplot(
            signal[self.use_signal]+bkg,
            legend=True,
            varlist=[f'higgs_rm[:,{i}]' for i in range(4)],
            binlist=[(0,4,30)]*4,
            scatter=dict(alpha=0.1, fraction=10000, size=1, discrete=True),
            saveas=f'{self.dout}/pairplot/unassigned_higgs/bkg_m_ratio'
        )

        study.pairplot(
            signal[self.use_signal]+bkg,
            legend=True,
            varlist=[f'higgs_log_rm[:,{i}]' for i in range(4)],
            binlist=[(0,1,30)]*4,
            scatter=dict(alpha=0.1, fraction=10000, size=1, discrete=True),
            saveas=f'{self.dout}/pairplot/unassigned_higgs/bkg_m_log_ratio'
        )

    def plot_assigned_higgs_m(self, signal, bkg):
        study.pairplot(
            signal[self.use_signal]+bkg,
            legend=True,
            varlist=[f'{h}_m' for h in eightb.higgslist],
            binlist=[(0,500,30)]*4,
            scatter=dict(alpha=0.1, fraction=10000, size=1, discrete=True),
            saveas=f'{self.dout}/pairplot/assigned_higgs/bkg_m'
        )
        
        study.pairplot(
            signal[self.use_signal]+bkg,
            legend=True,
            varlist=[f'{h}_dm' for h in eightb.higgslist],
            binlist=[(0,250,30)]*4,
            scatter=dict(alpha=0.1, fraction=10000, size=1, discrete=True),
            saveas=f'{self.dout}/pairplot/assigned_higgs/bkg_dm'
        )
        
        study.pairplot(
            signal[self.use_signal]+bkg,
            legend=True,
            varlist=[f'{h}_rm' for h in eightb.higgslist],
            binlist=[(0,4,30)]*4,
            scatter=dict(alpha=0.1, fraction=10000, size=1, discrete=True),
            saveas=f'{self.dout}/pairplot/assigned_higgs/bkg_m_ratio'
        )
        
        study.pairplot(
            signal[self.use_signal]+bkg,
            legend=True,
            varlist=[f'{h}_log_rm' for h in eightb.higgslist],
            binlist=[(0,1,30)]*4,
            scatter=dict(alpha=0.1, fraction=10000, size=1, discrete=True),
            saveas=f'{self.dout}/pairplot/assigned_higgs/bkg_m_log_ratio'
        )

    def plot_y_higgs_m(self, signal, bkg):
        study.pairplot(
            signal[self.use_signal]+bkg,
            legend=True,
            varlist=[f'Y{i}_h_dm' for i in (1,2)],
            binlist=[(0,500,30)]*4,
            scatter=dict(alpha=0.1, fraction=10000, size=1, discrete=True),
            saveas=f'{self.dout}/pairplot/y_higgs/bkg_dm'
        )
        
        study.pairplot(
            signal[self.use_signal]+bkg,
            legend=True,
            varlist=[f'Y{i}_h_rm' for i in (1,2)],
            binlist=[(0,4,30)]*4,
            scatter=dict(alpha=0.1, fraction=10000, size=1, discrete=True),
            saveas=f'{self.dout}/pairplot/y_higgs/bkg_m_ratio'
        )
        
        study.pairplot(
            signal[self.use_signal]+bkg,
            legend=True,
            varlist=[f'Y{i}_h_log_rm' for i in (1,2)],
            binlist=[(0,1,30)]*4,
            scatter=dict(alpha=0.1, fraction=10000, size=1, discrete=True),
            saveas=f'{self.dout}/pairplot/y_higgs/bkg_m_log_ratio'
        )

    def plot_abcd_variables(self, signal, bkg):

        study.quick2d( 
            signal[self.use_signal]+bkg,
            legend=True,
            varlist=['H1Y1_rm','H2Y1_rm'],
            binlist=[(0,4,30)]*2,
            scatter=True,
            exe=draw_concentric(x=1, y=1, r1=0.5, r2=1.0),
            saveas=f'{self.dout}/abcd/Y1_H_2d',
        )

        study.quick2d( 
            signal[self.use_signal]+bkg,
            legend=True,
            varlist=['H1Y1_rm','H2Y1_rm'],
            binlist=[(0,4,30)]*2,
            scatter=True,
            exe=draw_concentric(x=1, y=1, r1=0.5, r2=1.0),
            saveas=f'{self.dout}/abcd/Y2_H_2d',
        )

        study.quick2d(
            signal[self.use_signal]+bkg,
            legend=True,
            varlist=['Y1_h_rm','Y2_h_rm'],
            binlist=[(0,4,30)]*2,
            scatter=True,
            saveas=f'{self.dout}/abcd/Y1_Y2_h_rm_2d',
        )

        study.quick2d( 
            signal[self.use_signal]+bkg,
            legend=True, 
            varlist=['n_medium_btag','Y1_h_rm'],
            binlist=[np.arange(4,10),(0, 4, 20)],
            exe=draw_abcd(x_r=(4,5,9), y_r=(0,self.sr_r,self.cr_r), regions=["C","D","A","B"]),
            saveas=f'{self.dout}/btag_vs_Y1_h_rm',
        )

        study.quick2d( 
            signal[self.use_signal]+bkg,
            legend=True, 
            varlist=['n_medium_btag','Y2_h_rm'],
            binlist=[np.arange(4,10),(0, 4, 20)],
            exe=draw_abcd(x_r=(4,5,9), y_r=(0,self.sr_r,self.cr_r), regions=["C","D","A","B"]),
            saveas=f'{self.dout}/btag_vs_Y2_h_rm',
        )

    def build_abcd(self):
        y1_h_sr = Filter(lambda t : t.Y1_h_rm < self.sr_r)
        y1_h_cr = Filter(lambda t : (t.Y1_h_rm > self.sr_r) & (t.Y1_h_rm < self.cr_r))
        # y1_h_rm_ar = Filter(lambda t : t.Y1_h_rm < self.cr_r)
        y1_h_vr = Filter(lambda t : t.Y1_h_rm > self.cr_r)

        medium_btag_sr = Filter(lambda t : t.n_medium_btag > 4)
        medium_btag_cr = Filter(lambda t : t.n_medium_btag <= 4)

        y2_h_sr = Filter(lambda t : t.Y2_h_rm < self.sr_r)
        y2_h_cr = Filter(lambda t : (t.Y2_h_rm > self.sr_r) & (t.Y2_h_rm < self.cr_r))
        y2_h_ar = Filter(lambda t : t.Y2_h_rm < self.cr_r) 
        y2_h_vr = Filter(lambda t : t.Y2_h_rm > self.cr_r) 

        self.ar_bdt = ABCD(
            features=self.bdt_features,
            a = lambda t : y1_h_sr(t) & medium_btag_sr(t) & y2_h_ar(t),
            b = lambda t : y1_h_sr(t) & medium_btag_cr(t) & y2_h_ar(t),
            c = lambda t : y1_h_cr(t) & medium_btag_sr(t) & y2_h_ar(t),
            d = lambda t : y1_h_cr(t) & medium_btag_cr(t) & y2_h_ar(t),
        )

        blind_filter = EventFilter('blinded', filter=lambda t : ~( self.ar_bdt.a(t) ))
        self.blinded_data  = self.data.apply(blind_filter)
        self.bkg_model = self.blinded_data.apply(lambda t : t.asmodel('bkg model'))

        self.vr1_bdt = ABCD(
            features=self.bdt_features,
            a = lambda t : y1_h_sr(t) & medium_btag_sr(t) & y2_h_vr(t),
            b = lambda t : y1_h_sr(t) & medium_btag_cr(t) & y2_h_vr(t),
            c = lambda t : y1_h_cr(t) & medium_btag_sr(t) & y2_h_vr(t),
            d = lambda t : y1_h_cr(t) & medium_btag_cr(t) & y2_h_vr(t),
        )

        self.vr2_bdt = ABCD(
            features=self.bdt_features,
            a = lambda t : y2_h_sr(t) & medium_btag_sr(t) & y1_h_vr(t),
            b = lambda t : y2_h_sr(t) & medium_btag_cr(t) & y1_h_vr(t),
            c = lambda t : y2_h_cr(t) & medium_btag_sr(t) & y1_h_vr(t),
            d = lambda t : y2_h_cr(t) & medium_btag_cr(t) & y1_h_vr(t),
        )

    def _plot_abcd_regions(self, signal, bkg, bdt, key):
        study.quick( 
            signal[self.use_signal]+bkg,
            masks=bdt.mask,
            legend=True, 
            efficiency=True,
            varlist=['n_medium_btag','Y1_h_rm', 'Y2_h_rm'],
            binlist=[np.arange(4,10),(0, 2*self.cr_r, 20), (0, 2*self.cr_r, 20)],
            dim=-1,
            saveas=f'{self.dout}/{key}/variables',
        )

        study.quick2d( 
            signal[self.use_signal]+bkg,
            masks=bdt.mask,
            legend=True, 
            varlist=['n_medium_btag','Y1_h_rm'],
            binlist=[np.arange(4,10),(0, 2*self.cr_r, 20)],
            exe=draw_abcd(x_r=(4,5,9), y_r=(0,self.sr_r,self.cr_r), regions=["C","D","A","B"]),
            saveas=f'{self.dout}/{key}/btag_vs_Y1_h_rm',
        )
        
        study.quick2d( 
            signal[self.use_signal]+bkg,
            masks=bdt.mask,
            legend=True, 
            varlist=['n_medium_btag','Y2_h_rm'],
            binlist=[np.arange(4,10),(0, 2*self.cr_r, 20)],
            exe=draw_abcd(x_r=(4,5,9), y_r=(0,self.sr_r,self.cr_r), regions=["C","D","A","B"]),
            saveas=f'{self.dout}/{key}/btag_vs_Y2_h_rm',
        )
        
        study.quick2d( 
            signal[self.use_signal]+bkg,
            masks=bdt.mask,
            legend=True, 
            varlist=['Y1_h_rm','Y2_h_rm'],
            binlist=[(0, 2*self.cr_r, 20),(0, 2*self.cr_r, 20)],
            saveas=f'{self.dout}/{key}/Y1_h_rm_vs_Y2_h_rm',
            scatter=True,
        )

    def plot_abcd_regions(self, signal, bkg):
        self._plot_abcd_regions(signal, bkg, self.ar_bdt, 'abcd/ar')
        self._plot_abcd_regions(signal, bkg, self.vr1_bdt, 'abcd/vr1')
        self._plot_abcd_regions(signal, bkg, self.vr2_bdt, 'abcd/vr2')

    def var_correlations(self):
        study.quick( 
            self.signal[self.use_signal] + self.bkg,
            legend=True,
            plot_scale=[10]*len(self.use_signal),
            varlist=['n_loose_btag','n_medium_btag','n_tight_btag'],
            dim=-1,
            saveas=f'{self.dout}/btag-multi'
        )

        study.quick2d( 
            self.signal[self.use_signal] + self.bkg,
            varlist=['higgs_m[:,0]','n_medium_btag'],
            dim=-1,
            saveas=f'{self.dout}/2d_higgs_m_vs_mbtag'
        )

        study.compare_masks( 
            self.signal[self.use_signal], self.bkg,
            h_color=None,
            legend=True,
            masks=[lambda t: t.n_medium_btag >=4, lambda t: t.n_medium_btag >=5, lambda t: t.n_medium_btag >=6],
            label=['N Medium Btag >= 4', 'N Medium Btag >= 5', 'N Medium Btag >= 6'],
            varlist=['higgs_m[:,0]'],
            efficiency=True,
            ratio=True, r_inv=True, 
            # r_o_smooth=True,

            saveas=f'{self.dout}/higgs_mass_vs_btagcut'
        )

    def _print_abcd_yields(self):
        print("----- Signal AR -----")
        for lines in zip(*[ self.ar_bdt.print_yields( s, lumi=2018, return_lines=True) for s in self.signal[self.use_signal]]):
            print(' | '.join(lines))

        print("----- Signal VR -----")
        for lines in zip(*[ self.vr_bdt.print_yields( s, lumi=2018, return_lines=True) for s in self.signal[self.use_signal]]):
            print(' | '.join(lines))
            
        print("----- Data/MC AR -----")
        for lines in zip( self.ar_bdt.print_yields( self.blinded_data, return_lines=True), self.ar_bdt.print_yields(self.bkg, lumi=2018, return_lines=True)):
            print(' | '.join(lines))

        print("----- Data/MC VR -----")
        for lines in zip(self.vr_bdt.print_yields(self.blinded_data, return_lines=True), self.vr_bdt.print_yields(self.bkg, lumi=2018, return_lines=True)):
            print(' | '.join(lines))

    def _plot_vr_datamc(self, bdt, key):
        resonances = ['X_m','Y1_m','Y2_m',None]+[f'{h}_m' for h in eightb.higgslist]

        study.quick( 
            self.blinded_data+self.bkg,
            masks=bdt.mask,
            legend=True,
            varlist=resonances,
            binlist=[(500,2000,30)]+[(0,1000,30)]*3+[(0,500,30)]*4,
            h_rebin=15,
            dim=(-1, 4),
            ratio=True, r_ylabel='Data/MC',
            saveas=f'{self.dout}/{key}/datamc_resonant_mass'
        )

    def plot_vr_datamc(self):
        self._plot_vr_datamc(self.vr1_bdt, 'abcd/vr1')
        self._plot_vr_datamc(self.vr2_bdt, 'abcd/vr2')

    def _train_bdt(self, bdt):
        bdt.train(self.bkg_model)
        bdt.print_results(self.bkg_model)

    def _evaluate_bdt(self, bdt, key):
        study.quick_region(
            self.blinded_data , self.bkg_model, self.bkg_model, label=['target','k factor','bdt'],
            h_color=['black','red','orange'], legend=True,
            masks=[bdt.c]*len(self.blinded_data)+[bdt.d]*(len(self.bkg_model)*2),
            scale=[1]*len(self.blinded_data)+[bdt.scale_tree]*len(self.bkg_model)+[bdt.reweight_tree]*len(self.bkg_model),
            varlist=bdt.feature_names,
            h_rebin=15,
            suptitle='BDT Training (Data) D $\\rightarrow$ C',
            ratio=True,
            **study.kstest,
            saveas=f'{self.dout}/{key}/training'
        )

        study.quick_region(
            self.blinded_data , self.bkg_model, self.bkg_model, label=['target','k factor','bdt'],
            h_color=['black','blue','green'], legend=True,
            masks=[bdt.a]*len(self.blinded_data)+[bdt.b]*(len(self.bkg_model)*2),
            scale=[1]*len(self.blinded_data)+[bdt.scale_tree]*len(self.bkg_model)+[bdt.reweight_tree]*len(self.bkg_model),
            varlist=bdt.feature_names,
            h_rebin=15,
            suptitle='BDT Applying (Data) B $\\rightarrow$ A',
            ratio=True,
            **study.kstest,
            saveas=f'{self.dout}/{key}/applying',
        )

        resonances = ['X_m','Y1_m','Y2_m',None]+[f'{h}_m' for h in eightb.higgslist]
        study.quick_region(
            self.blinded_data , self.bkg_model, self.bkg_model, label=['target','k factor','bdt'],
            h_color=['black','blue','green'], legend=True,
            masks=[bdt.a]*len(self.blinded_data)+[bdt.b]*(len(self.bkg_model)*2),
            scale=[1]*len(self.blinded_data)+[bdt.scale_tree]*len(self.bkg_model)+[bdt.reweight_tree]*len(self.bkg_model),
            varlist=resonances,
            binlist=[(500,2000,30)]+[(0,1000,30)]*3+[(0,500,30)]*4,
            h_rebin=15,
            suptitle='BDT Applying (Data) B $\\rightarrow$ A',
            ratio=True,
            **study.kstest,
            saveas=f'{self.dout}/{key}/applying_resonanes',
        )

    def train_vr_bdt(self):
        print("Training VR 1 BDT")
        self._train_bdt(self.vr1_bdt)
        self._evaluate_bdt(self.vr1_bdt, 'abcd/vr1')

        print("Training VR 2 BDT")
        self._train_bdt(self.vr2_bdt)
        self._evaluate_bdt(self.vr2_bdt, 'abcd/vr2')

    def train_ar_bdt(self):

        # %%
        print("Training AR BDT")
        self._train_bdt(self.ar_bdt)

    def calc_limits(self):
        study.quick(
            self.signal[self.use_signal] + self.bkg_model, 
            legend=True,
            masks=[self.ar_bdt.a]*len(self.use_signal)+[self.ar_bdt.b]*len(self.bkg_model),
            scale=[1]*len(self.use_signal)+[self.ar_bdt.reweight_tree]*len(self.bkg_model),
            varlist=['X_m'],
            binlist=[(500,2000,30)],
            title='BDT Bkg Model',
            limits=True,
            l_poi=np.linspace(0,3,21), 
            saveas=f'{self.dout}/limits/bdt_bkg_model'
        )

    def calc_brazil(self):
        study.brazil(
            self.signal+self.bkg_model,
            masks=[self.ar_bdt.a]*len(self.signal)+[self.ar_bdt.b]*len(self.bkg_model),
            scale=[1]*len(self.signal)+[self.ar_bdt.reweight_tree]*len(self.bkg_model),
            varlist=['X_m'],
            binlist=[(500,2000,30)],
            l_poi=np.linspace(0,3,21), 
            saveas=f'{self.dout}/limits/brazil_bdt_bkg_model'
        )
