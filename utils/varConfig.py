from attrdict import AttrDict
import numpy as np


class VarInfo(AttrDict):
    def find(self, var):
        if callable(var): var = var.__name__ if hasattr(var, '__name__') else str(var)

        if var in self:
            return AttrDict(self[var])
        end_pattern = next((self[name]
                           for name in self if var.endswith(name)), None)
        if end_pattern:
            return AttrDict(end_pattern)
        start_pattern = next(
            (self[name] for name in self if var.startswith(name)), None)
        if start_pattern:
            return AttrDict(start_pattern)
        any_pattern = next((self[name] for name in self if var in name), None)
        if any_pattern:
            return AttrDict(any_pattern)


varinfo = VarInfo({
    f"jet_m":     {"bins": np.linspace(0, 60, 30), "xlabel": "Jet Mass"},
    f"jet_E":     {"bins": np.linspace(0, 1000, 30), "xlabel": "Jet Energy"},
    f"jet_pt":    {"bins": np.linspace(0, 1000, 30), "xlabel": "Jet Pt (GeV)"},
    f"jet_btag":  {"bins": np.linspace(0, 1, 30), "xlabel": "Jet Btag"},
    f"jet_qgl":   {"bins": np.linspace(0, 1, 30), "xlabel": "Jet QGL"},
    f"jet_min_dr": {"bins": np.linspace(0, 3, 30), "xlabel": "Jet Min dR"},
    f"jet_eta":   {"bins": np.linspace(-3, 3, 30), "xlabel": "Jet Eta"},
    f"jet_phi":   {"bins": np.linspace(-3.14, 3.14, 30), "xlabel": "Jet Phi"},
    f"n_jet":     {"bins": np.arange(12), "xlabel": "N Jets"},
    f"higgs_m":   {"bins": np.linspace(0, 300, 30), "xlabel": "DiJet Mass"},
    f"higgs_E":   {"bins": np.linspace(0, 500, 30), "xlabel": "DiJet Energy"},
    f"higgs_pt":  {"bins": np.linspace(0, 500, 30), "xlabel": "DiJet Pt (GeV)"},
    f"higgs_eta": {"bins": np.linspace(-3, 3, 30), "xlabel": "DiJet Eta"},
    f"higgs_phi": {"bins": np.linspace(-3.14, 3.14, 30), "xlabel": "DiJet Phi"},
    f"dijet_m":   {"bins": np.linspace(0, 300, 30), "xlabel": "DiJet Mass"},
    f"dijet_E":   {"bins": np.linspace(0, 500, 30), "xlabel": "DiJet Energy"},
    f"dijet_pt":  {"bins": np.linspace(0, 500, 30), "xlabel": "DiJet Pt (GeV)"},
    f"dijet_eta": {"bins": np.linspace(-3, 3, 30), "xlabel": "DiJet Eta"},
    f"dijet_phi": {"bins": np.linspace(-3.14, 3.14, 30), "xlabel": "DiJet Phi"},
    f"n_higgs":   {"bins": np.arange(12), "xlabel": "N DiJets"},
    f"jet_btagsum": {"bins": np.linspace(2, 6, 30), "xlabel": "6 Jet Btag Sum"},
    "event_y23": dict(xlabel="Event y23", bins=np.linspace(0, 0.25, 30)),
    "M_eig_w1": dict(xlabel="Momentum Tensor W1", bins=np.linspace(0, 1, 30)),
    "M_eig_w2": dict(xlabel="Momentum Tensor W2", bins=np.linspace(0, 1, 30)),
    "M_eig_w3": dict(xlabel="Momentum Tensor W3", bins=np.linspace(0, 1, 30)),
    "event_S": dict(xlabel="Event S", bins=np.linspace(0, 1, 30)),
    "event_St": dict(xlabel="Event S_T", bins=np.linspace(0, 1, 30)),
    "event_F": dict(xlabel="Event W2/W1", bins=np.linspace(0, 1, 30)),
    "event_A": dict(xlabel="Event A", bins=np.linspace(0, 0.5, 30)),
    "event_AL": dict(xlabel="Event A_L", bins=np.linspace(-1, 1, 30)),
    "thrust_phi": dict(xlabel="T_T Phi", bins=np.linspace(-3.14, 3.14, 30)),
    "event_Tt": dict(xlabel="1 - T_T", bins=np.linspace(0, 1/3, 30)),
    "event_Tm": dict(xlabel="T_m", bins=np.linspace(0, 2/3, 30)),
    "b_6j_score": dict(xlabel="6 Jet Classifier Score", bins=np.linspace(0, 1, 30)),
    "b_3d_score": dict(xlabel="3 Higgs Classifier Score", bins=np.linspace(0, 1, 30)),
    "b_2j_score": dict(xlabel="2 Jet Classifier Score", bins=np.linspace(0, 1, 30)),
})

varinfo.X_m = dict(bins=np.linspace(500,2000,30))
varinfo.Y1_m = dict(bins=np.linspace(200,1000,30))
varinfo.Y2_m = dict(bins=np.linspace(200,1000,30))
varinfo.H1Y1_m = dict(bins=np.linspace(0,250,30))
varinfo.H2Y1_m = dict(bins=np.linspace(0,250,30))
varinfo.H1Y2_m = dict(bins=np.linspace(0,250,30))
varinfo.H2Y2_m = dict(bins=np.linspace(0,250,30))
