import json, warnings, inspect
warnings.filterwarnings('ignore')
import sympy
out={'sympy_version':sympy.__version__}
# ---- sympy.stats ----
import sympy.stats as st
pub=[n for n in dir(st) if not n.startswith('_')]
out['sympy_stats_public_names']=len(pub)
# distribution constructors: public callables whose name is CapWords and which live in sympy.stats.*_rv_types
import sympy.stats.crv_types as crv, sympy.stats.drv_types as drv, sympy.stats.frv_types as frv
import sympy.stats.rv_interface as rvi
import sympy.stats.joint_rv_types as jrv
import sympy.stats.matrix_distributions as md
import sympy.stats.random_matrix_models as rmm
import sympy.stats.stochastic_process_types as spt
def named(mod):
    return sorted(n for n in getattr(mod,'__all__',[]) )
out['continuous_distributions']=named(crv); out['continuous_distributions_count']=len(named(crv))
out['discrete_distributions']=named(drv); out['discrete_distributions_count']=len(named(drv))
out['finite_distributions']=named(frv); out['finite_distributions_count']=len(named(frv))
out['joint_distributions']=named(jrv); out['joint_distributions_count']=len(named(jrv))
out['matrix_distributions']=named(md); out['matrix_distributions_count']=len(named(md))
out['random_matrix_models']=named(rmm); out['random_matrix_models_count']=len(named(rmm))
out['stochastic_processes']=named(spt); out['stochastic_processes_count']=len(named(spt))
out['total_named_distribution_constructors']=sum(out[k] for k in
   ['continuous_distributions_count','discrete_distributions_count','finite_distributions_count',
    'joint_distributions_count','matrix_distributions_count','random_matrix_models_count'])
# RandomSymbol vs Symbol: is a RandomVariable a value?
from sympy.stats.rv import RandomSymbol
from sympy import Symbol, Expr
X=st.Normal('X',0,1)
out['RandomSymbol_type']=type(X).__name__
out['RandomSymbol_mro']=[c.__name__ for c in type(X).__mro__]
out['RandomSymbol_is_Expr']=isinstance(X,Expr)
out['RandomSymbol_is_Symbol_subclass']=isinstance(X,Symbol)
out['X_plus_1_type']=type(X+1).__name__
out['X_plus_1_is_Expr']=isinstance(X+1,Expr)
# CRITICAL: does sympy distinguish a distribution object from a random variable from a value?
out['type_of_distribution_object']=type(st.rv.pspace(X).distribution).__name__
out['can_add_RV_to_number_without_error']= str(X+1)
out['E(X)']=str(st.E(X))
out['P(X>0)']=str(st.P(X>0))
out['X_gt_0_type']=type(X>0).__name__
# ---- sympy.physics.units ----
import sympy.physics.units as u
from sympy.physics.units import Quantity, Dimension
upub=[n for n in dir(u) if not n.startswith('_')]
out['physics_units_public_names']=len(upub)
qs=sorted(n for n in upub if isinstance(getattr(u,n),Quantity))
out['physics_units_Quantity_instances_count']=len(qs)
out['physics_units_Quantity_instances']=qs
ds=sorted(n for n in upub if isinstance(getattr(u,n),Dimension))
out['physics_units_Dimension_instances_count']=len(ds)
out['physics_units_Dimension_instances']=ds
# does unit arithmetic type-check?
m=u.meter; s=u.second
demo={}
demo['meter + second (accepted?)']=None
try:
    r=m+s; demo['meter + second (accepted?)']=f'ACCEPTED, result={r}'
except Exception as e:
    demo['meter + second (accepted?)']=f'{type(e).__name__}: {e}'
from sympy.physics.units.systems import SI
try:
    demo['SI dim check of meter+second']=str(SI.get_dimensional_expr(m+s))
except Exception as e:
    demo['SI dim check of meter+second']=f'{type(e).__name__}: {e}'
try:
    from sympy.physics.units.util import convert_to
    demo['convert_to(meter, second)']=str(convert_to(m, s))
except Exception as e:
    demo['convert_to(meter, second)']=f'{type(e).__name__}: {e}'
try:
    from sympy.physics.units import check_dimensions
    demo['check_dimensions(meter+second)']=str(check_dimensions(m+s))
except Exception as e:
    demo['check_dimensions(meter+second)']=f'{type(e).__name__}: {e}'
out['units_demonstrations']=demo
print(json.dumps(out,indent=1,default=str))
