#!/usr/bin/env python
# coding: utf-8

from . import *

def njets(*args,**kwargs):
    study = Study(*args,**kwargs)
    
    nrows,ncols = 1,1
    fig,axs = plt.subplots(nrows=nrows,ncols=ncols,figsize=(8,5))
    
    weights = [ selection["scale"] for selection in study.selections ]
    n_jet_list = [ selection["n_jet"] for selection in study.selections ]
    hist_multi(n_jet_list,weights=weights,bins=range(12),xlabel="N Jet",figax=(fig,axs),**vars(study))

    fig.suptitle(study.title)
    fig.tight_layout()
    plt.show()
    if study.saveas: save_fig(fig,"njets",study.saveas)

def jets(*args,**kwargs):
    study = Study(*args,**kwargs)
    
    varlist=["jet_pt","jet_phi","jet_eta","jet_btag","jet_qgl"]
    
    nrows,ncols = 2,3
    fig,axs = plt.subplots(nrows=nrows,ncols=ncols,figsize=(16,10))
    
    weights = [ selection["scale"] for selection in study.selections ]
    jet_weights = [ selection["jet_scale"] for selection in study.selections ]
    for i,varname in enumerate(varlist):
        hists = [ selection[varname] for selection in study.selections ]
        info = study.varinfo[varname]
        hist_multi(hists,weights=jet_weights,**info,figax=(fig,axs[i//ncols,i%ncols]),**vars(study))

    n_jet_list = [ selection["n_jet"] for selection in study.selections ]
    hist_multi(n_jet_list,bins=range(12),weights=weights,xlabel="N Jet",figax=(fig,axs[1,2]),**vars(study))

    fig.suptitle(study.title)
    fig.tight_layout()
    plt.show()
    if study.saveas: save_fig(fig,"jets",study.saveas)

def njet_var_sum(*args,variable="jet_btag",**kwargs):
    study = Study(*args,**kwargs)

    nrows,ncols = 2,2
    fig,axs = plt.subplots(nrows=nrows,ncols=ncols,figsize=(16,10))
    info = study.varinfo[variable]
    binmax = info['bins'][-1]
    
    weights = [ selection["scale"] for selection in study.selections ]
    selection_vars = [ ak.fill_none(ak.pad_none(selection[variable],6,axis=-1,clip=1),0) for selection in study.selections ]
    for i in range(4):
        ijet = i+3
        ijet_var_sum = [ ak.sum(var[:,:ijet],axis=-1) for var in selection_vars ]

        bins = np.linspace(0,binmax*(1+0.05*ijet),50)
        if variable == "jet_btag": bins = np.linspace(0,binmax*ijet,50)
        
        hist_multi(ijet_var_sum,weights=weights,bins=bins,**vars(study),xlabel=f"{ijet} {info['xlabel']} Sum",figax=(fig,axs[i//ncols,i%ncols]))

    fig.suptitle(study.title)
    fig.tight_layout()
    plt.show()
    if study.saveas: save_fig(fig,f"n{variable}_sum",study.saveas)

        
def jet_display(*args,ie=0,printout=[],boosted=False,**kwargs):
    study = Study(*args,title="",**kwargs)
    tree = study.selections[0]
    
    for out in printout:
        print(f"{out}: {tree[out][ie]}")

    njet = tree["n_jet"][ie]
    jet_pt = tree["jet_pt"][ie][np.newaxis]
    jet_eta = tree["jet_eta"][ie][np.newaxis]
    jet_phi = tree["jet_phi"][ie][np.newaxis]
    jet_m = tree["jet_m"][ie][np.newaxis]

    if boosted:
        boost = com_boost_vector(jet_pt,jet_eta,jet_phi,jet_m,njet=njet)
        boosted_jets = vector.obj(pt=jet_pt,eta=jet_eta,phi=jet_phi,m=jet_m).boost_p4(boost)
        jet_pt,jet_eta,jet_phi,jet_m = boosted_jets.pt,boosted_jets.eta,boosted_jets.phi,boosted_jets.m
    
    fig = plt.figure(figsize=(10,5))
    plot_barrel_display(jet_eta,jet_phi,jet_pt,figax=(fig,fig.add_subplot(1,2,1)))
    plot_endcap_display(jet_eta,jet_phi,jet_pt,figax=(fig,fig.add_subplot(1,2,2,projection='polar')))
    
    r,l,e,id = [ tree[info][ie] for info in ("Run","Event","LumiSec","sample_id") ]
    sample = tree.samples[id]

    title = f"{sample} | Run: {r} | Lumi: {l} | Event: {e}"
    if boosted: title = f"Boosted COM: {title}"
    fig.suptitle(title)
    fig.tight_layout()
    plt.show()

    if study.saveas: save_fig(fig,"jet_display",study.saveas)
    
def jet_sphericity(*args,**kwargs):
    study = Study(*args,**kwargs)
    
    nrows,ncols = 2,3
    fig,axs = plt.subplots(nrows=nrows,ncols=ncols,figsize=(16,10))
    shapes = ["M_eig_w1","M_eig_w2","M_eig_w3","event_S","event_St","event_A"]
    weights = [ selection["scale"] for selection in study.selections ]
    for i,shape in enumerate(shapes):
        shape_var = [ selection[shape] for selection in study.selections ]
        info = shapeinfo[shape]
        hist_multi(shape_var,weights=weights,**info,**vars(study),figax=(fig,axs[i//ncols,i%ncols]))
    fig.tight_layout()
    plt.show()
    if study.saveas: save_fig(fig,"sphericity",study.saveas)
        
def jet_thrust(*args,**kwargs):
    study = Study(*args,**kwargs)
    
    nrows,ncols = 1,3
    fig,axs = plt.subplots(nrows=nrows,ncols=ncols,figsize=(16,5))
    shapes = ["thrust_phi","event_Tt","event_Tm"]
    weights = [ selection["scale"] for selection in study.selections ]
    
    for i,shape in enumerate(shapes):
        shape_var = [ selection[shape] for selection in study.selections ]
        info = shapeinfo[shape]
        hist_multi(shape_var,weights=weights,**info,**vars(study),figax=(fig,axs[i]))
    fig.tight_layout()
    plt.show()
    if study.saveas: save_fig(fig,"thrust",study.saveas)
