# %%
import os

from sklearn.preprocessing import label_binarize
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

# %%
varinfo.X_m = dict(bins=np.linspace(500,2000,30))
varinfo.Y1_m = dict(bins=np.linspace(200,1000,30))
varinfo.Y2_m = dict(bins=np.linspace(200,1000,30))
varinfo.H1Y1_m = dict(bins=np.linspace(0,250,30))
varinfo.H2Y1_m = dict(bins=np.linspace(0,250,30))
varinfo.H1Y2_m = dict(bins=np.linspace(0,250,30))
varinfo.H2Y2_m = dict(bins=np.linspace(0,250,30))
varinfo.quadh_score = dict(bins=(0,0.7,30))

# %%

print("Getting Trees")

signal = ObjIter([Tree(fc.eightb.preselection_ranked_quadh.NMSSM_XYY_YToHH_8b_MX_1000_MY_450)])
qcd = ObjIter([Tree(fc.eightb.preselection_ranked_quadh.QCD_B_List)])
ttbar = ObjIter([Tree(fc.eightb.preselection_ranked_quadh.TTJets)])
bkg = qcd + ttbar

# data = ObjIter([Tree(fc.eightb.preselection_ranked_quadh.JetHT_Run2018A_UL)])

# %%

def set_target(tree):
  tree = tree.copy()
  tree.sample = 'target'
  return tree

def set_model(tree):
  tree = tree.copy()
  tree.sample = 'model'
  tree.is_model = True
  return tree

target = bkg.apply(set_target)
model = bkg.apply(set_model)

feature_names = [
    f'{obj}_m'
    for obj in ['X']+eightb.ylist+eightb.higgslist
]

def apply_abcd(v1_r, v2_r, tag=""):
  print(f'Processing ABCD region - {tag}')

  r_a, r_b, r_c, r_d = get_abcd_masks(v1_r, v2_r)

  abcd = ABCD(feature_names, r_a, r_b, r_c, r_d)
  abcd.train(model)

  print(f'K Factor: {abcd.k_factor:0.3}')

  if target.is_data.npy.all():
    label = 'Data'
    lumi=20180
  else:
    label = 'MC-Bkg'
    lumi=2018

  fig, axs = study.get_figax(2)

  study.quick2d_region(
    target, label=[label],
    varlist=['n_medium_btag','quadh_score'],
    contour=True,
    figax=(fig,axs[0]),
    exe=draw_abcd(x_r=v1_r, y_r=v2_r)
  )

  study.quick2d(
    signal,
    varlist=['n_medium_btag','quadh_score'],
    figax=(fig,axs[1]),
    contour=True,
    exe=draw_abcd(x_r=v1_r, y_r=v2_r)
  )

  fig.tight_layout()

  study.save_fig(fig, '', f'{tag}/abcd_regions')

  print('Comparing Target/Model')
  varlist = [f'{obj}_{var}' for obj in ['X']+eightb.ylist+eightb.higgslist for var in ('m','pt','eta','phi')]
  fig, axs = study.quick_region(
    target, model, 
    varlist=varlist,
    h_color=None, label=['target','model'], legend=True,
    masks=[r_a]*len(target) + [r_b]*len(model),
    scale=[None]*len(target) + [abcd.reweight_tree]*len(model),
    h_label_stat=lambda h:f'{np.sum(h.weights):0.2e}',
    lumi=lumi,
    legend_loc='upper left',
    dim=(-1,4),

    ratio=True,
    r_size='50%',
    r_fill_error=True,
    r_ylabel=r'$\frac{target}{model}$',
    r_label_stat='y_mean_std',
    r_legend=True,
    r_legend_loc='upper left',

    empirical=True,
    # e_ylim=(-0.15,1.15),
    e_show=False,

    e_difference=True,
    e_d_size='75%',
    e_d_ylabel='$\Delta$ ECDF',
    e_d_legend_loc='upper left',
    saveas=f'{tag}/model_comparison',

    title=tag,
    return_figax=True,
  )


  print('')
  cutoff = 1.358
  ks = np.array([ax.store.empiricals.differences[0].stats.ks for ax in axs.flatten()])
  nks = np.mean(ks < cutoff)
  ypos = np.arange(ks.shape[0])

  fig,ax = plt.subplots(figsize=(8,10))
  ax.barh(ypos, ks, label=f'Fraction KS < {cutoff}: {nks:0.2}')
  ax.set_yticks(ypos, labels=varlist)
  ax.invert_yaxis()  # labels read top-to-bottom
  ax.set(xlabel="KS Test Statstic", title=tag, xlim=(0, 2.0))

  ylim = ax.get_ylim()
  ax.plot([cutoff, cutoff], ylim, 'k')
  ax.set(ylim=ylim)
  ax.xaxis.grid(True)

  ax.legend(loc='upper left')
  fig.tight_layout()

  study.save_fig(fig, '', f'{tag}/kstest')


# %%

abcd_regions = {
  'nominal':                    [(0,5,9),(0,0.2 ,0.7)],
  'validation/btag_hi':         [(3,5,9),(0,0.2 ,0.7)],
  'validation/btag_lo':         [(0,3,5),(0,0.2 ,0.7)],
  'validation/score_lo':        [(0,5,9),(0,0.15,0.2)],
  'validation/btag_hi_score_lo':[(3,5,9),(0,0.15,0.2)],
  'validation/btag_lo_score_lo':[(0,3,5),(0,0.15,0.2)]
}

for tag, (v1_r, v2_r) in abcd_regions.items():
  apply_abcd(v1_r, v2_r, tag=tag)

# %%
