import json, warnings, inspect
warnings.filterwarnings('ignore')
import sympy
from sympy import Symbol, Q, ask, refine, simplify, sqrt, log, Abs, symbols
out={'sympy_version':sympy.__version__}
# --- OLD-STYLE (symbol-attached) assumptions ---
from sympy.core.assumptions import _assume_defined
out['old_style_assumption_predicates_count']=len(_assume_defined)
out['old_style_assumption_predicates']=sorted(_assume_defined)
# the implication rules
from sympy.core.assumptions import _assume_rules
out['old_style_implication_rules_count']=len(_assume_rules.defined_facts) if hasattr(_assume_rules,'defined_facts') else None
try:
    out['old_style_full_implications_count']=len(_assume_rules.full_implications)
except Exception as e:
    out['old_style_full_implications_count']=None
# --- NEW-STYLE (Q.) assumptions ---
qpreds=sorted(n for n in dir(Q) if not n.startswith('_'))
out['Q_predicate_count']=len(qpreds)
out['Q_predicates']=qpreds
from sympy.assumptions.assume import Predicate
out['Q_entries_that_are_Predicate']=len([n for n in qpreds if isinstance(getattr(Q,n),Predicate)])
# handler-registered predicates in ask
out['ask_returns_None_for_unknown']= (ask(Q.positive(Symbol('x'))) is None)
# --- demonstrate what assumptions actually do ---
x=Symbol('x'); xp=Symbol('xp', positive=True); xr=Symbol('xr', real=True)
demo={}
demo['sqrt(x**2) unassumed']=str(sqrt(x**2))
demo['sqrt(xp**2) positive']=str(sqrt(xp**2))
demo['sqrt(xr**2) real']=str(sqrt(xr**2))
demo['refine(sqrt(x**2), Q.positive(x))']=str(refine(sqrt(x**2), Q.positive(x)))
demo['Abs(xp)']=str(Abs(xp))
demo['ask(Q.positive(x))']=repr(ask(Q.positive(x)))
demo['ask(Q.positive(x), Q.positive(x))']=repr(ask(Q.positive(x), Q.positive(x)))
demo['ask(Q.positive(x+1), Q.positive(x))']=repr(ask(Q.positive(x+1), Q.positive(x)))
demo['ask(Q.positive(x*y), Q.positive(x) & Q.positive(y))']=repr(ask(Q.positive(x*Symbol('y')), Q.positive(x) & Q.positive(Symbol('y'))))
demo['ask(Q.even(2*x), Q.integer(x))']=repr(ask(Q.even(2*x), Q.integer(x)))
demo['ask(Q.prime(x**2+x+41), Q.integer(x)) -- open conjecture-ish']=repr(ask(Q.prime(x**2+x+41), Q.integer(x)))
demo['contradictory assumptions Symbol(positive=True, negative=True)']=None
try:
    Symbol('c', positive=True, negative=True)
    demo['contradictory assumptions Symbol(positive=True, negative=True)']='ACCEPTED SILENTLY'
except Exception as e:
    demo['contradictory assumptions Symbol(positive=True, negative=True)']=f'{type(e).__name__}: {e}'
# assumption on a symbol is NOT a type -- show that a positive symbol is still an Expr and can be substituted with anything
demo['xp.subs(xp,-5)']=str(xp.subs(xp,-5))
demo['xp.is_positive']=repr(xp.is_positive)
demo['x.is_positive (unknown)']=repr(x.is_positive)
out['demonstrations']=demo
# --- satask (SAT-based) ---
try:
    from sympy.assumptions.satask import satask
    out['satask_available']=True
    out['satask_example_ask(Q.positive(x*y), Q.positive(x)&Q.positive(y))']=repr(satask(Q.positive(x*Symbol('y')), Q.positive(x)&Q.positive(Symbol('y'))))
except Exception as e:
    out['satask_available']=str(e)
print(json.dumps(out,indent=1))
