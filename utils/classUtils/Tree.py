from . import *

import glob

def add_sample(self,fname,tfile,total_events,ttree,sample,xsec,scale):
    self.nfiles += 1
    self.filenames.append(fname)
    self.tfiles.append(tfile)
    self.total_events.append(total_events)
    self.raw_events.append(ak.size(ttree["Run"]))
    self.ttrees.append(ttree)
    self.samples.append(sample)
    self.xsecs.append(xsec)
    self.scales.append(scale)

def init_file(self,tfname):
    tfile = ut.open(tfname)
    total_events = ak.sum(tfile["n_events"].to_numpy(),axis=None)
    ttree = tfile["sixBtree"].arrays()

    valid = ak.count(ttree) > 0

    if not valid and self.verify: return
    sample,xsec = next( ((key,value) for key,value in xsecMap.items() if key in tfname),("unk",1) )
    scale = xsec / total_events
    add_sample(self,tfname,tfile,total_events,ttree,sample,xsec,scale)

def init_dir(self,tdir):
    tfname = f"{tdir}/ntuple_*.root"
    filelist = glob.glob(tfname)

    tfiles = [ ut.open(fname) for fname in filelist ]
    total_events = sum([ak.sum(tfile["n_events"].to_numpy(),axis=None) for tfile in tfiles])
    ttrees = list(ut.iterate(tfname,allow_missing=True))
    if len(ttrees) == 0: return
    ttree = ak.concatenate(ttrees)
    valid = ak.count(ttree) > 0

    if not valid and self.verify: return
    sample,xsec = next( ((key,value) for key,value in xsecMap.items() if key in tfname),("unk",1) )
    scale = xsec / total_events
    add_sample(self,tfname,tfiles,total_events,ttree,sample,xsec,scale)
    
class Tree:
    def __init__(self,filenames,verify=True):
        if type(filenames) != list: filenames = [filenames]
        self.verify = verify
        
        self.nfiles = 0
        self.filenames = []
        self.tfiles = []
        self.total_events = []
        self.raw_events = []
        self.ttrees = []
        self.samples = []
        self.xsecs = []
        self.scales = []
        
        for fname in filenames: self.addTree(fname)
        self.valid = self.nfiles > 0

        if not self.valid: return
        self.ttree = ak.concatenate(self.ttrees)

        sample_id = ak.concatenate([ i*ak.ones_like(tree["Run"]) for i,tree in enumerate(self.ttrees) ])
        
        self.extended = {"sample_id":sample_id}
        self.nevents = sum(self.raw_events)
        self.is_signal = all("NMSSM" in fname for fname in self.filenames)
        
        self.all_events_mask = ak.ones_like(self["Run"]) == 1
        self.all_jets_mask = ak.ones_like(self["jet_pt"]) == 1

        self.mask = self.all_events_mask
        self.jets_selected = self.all_jets_mask
        
        self.sixb_jet_mask = self["jet_signalId"] != -1
        self.bkgs_jet_mask = self.sixb_jet_mask == False

        self.sixb_found_mask = self["nfound_all"] == 6

        self.build_scale_weights()
        # self.reco_XY()
    def __str__(self):
        if not self.valid: return "invalid"
        sample_string = [
            f"=== File Info ===",
            f"File: {self.filenames}",
            f"Total Events:    {self.total_events}",
            f"Raw Events:      {self.raw_events}",
            f"Selected Events: {self.nevents}",
        ]
        return "\n".join(sample_string)
    def __getitem__(self,key): 
        if key in self.extended:
            return self.extended[key]
        return self.ttree[key]
    def addTree(self,fname):
        if os.path.isdir(fname): init_dir(self,fname)
        else:                    init_file(self,fname)
    def build_scale_weights(self):
        jet_scale = ak.concatenate([ ak.full_like(tree["jet_pt"],scale) for scale,tree in zip(self.scales,self.ttrees)])
        event_scale = jet_scale[:,0]
        self.extended.update({"scale":event_scale,"jet_scale":jet_scale})
    
    def reco_XY(self):
        bjet_p4 = lambda key : vector.obj(pt=self[f"gen_{key}_recojet_pt"],eta=self[f"gen_{key}_recojet_eta"],
                                          phi=self[f"gen_{key}_recojet_phi"],mass=self[f"gen_{key}_recojet_m"])
        hx_b1 = bjet_p4("HX_b1")
        hx_b2 = bjet_p4("HX_b2")
        hy1_b1= bjet_p4("HY1_b1")
        hy1_b2= bjet_p4("HY1_b2")
        hy2_b1= bjet_p4("HY2_b1")
        hy2_b2= bjet_p4("HY2_b2")
        
        Y = hy1_b1 + hy1_b2 + hy2_b1 + hy2_b2
        X = hx_b1 + hx_b2 + Y
        
        self.extended.update({"X_pt":X.pt,"X_m":X.mass,"X_eta":X.eta,"X_phi":X.phi,
                              "Y_pt":Y.pt,"Y_m":Y.mass,"Y_eta":Y.eta,"Y_phi":Y.phi})
    def calc_jet_dr(self,compare=None,tag="jet"):
        select_eta = self.ttree["jet_eta"]
        select_phi = self.ttree["jet_phi"]

        if compare is None: compare = self.jets_selected
        
        compare_eta = self.ttree["jet_eta"][compare]
        compare_phi = self.ttree["jet_phi"][compare]
        
        dr = calc_dr(select_eta,select_phi,compare_eta,compare_phi)
        dr_index = ak.local_index(dr,axis=-1)

        remove_self = dr != 0
        dr = dr[remove_self]
        dr_index = dr_index[remove_self]

        imin_dr = ak.argmin(dr,axis=-1,keepdims=True)
        imax_dr = ak.argmax(dr,axis=-1,keepdims=True)

        min_dr = ak.flatten(dr[imin_dr],axis=-1)
        imin_dr = ak.flatten(dr_index[imin_dr],axis=-1)

        max_dr = ak.flatten(dr[imax_dr],axis=-1)
        imax_dr = ak.flatten(dr_index[imax_dr],axis=-1)

        self.extended.update({f"{tag}_min_dr":min_dr,f"{tag}_imin_dr":imin_dr,f"{tag}_max_dr":max_dr,f"{tag}_imax_dr":imax_dr})

    def copy(self):
        new_tree = CopyTree(self)
        return new_tree
        
class CopyTree(Tree):
    def __init__(self,tree):
        copy_fields(tree,self)
