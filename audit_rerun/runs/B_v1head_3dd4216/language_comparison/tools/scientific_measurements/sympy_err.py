import json, warnings
warnings.filterwarnings('ignore')
import sympy
from sympy import *
out={'sympy_version':sympy.__version__}
x,y=symbols('x y')
def t(l,f):
    try:
        v=f(); out[l]={'outcome':'value','repr':str(v),'srepr':srepr(v) if isinstance(v,Basic) else None,'type':type(v).__name__}
    except Exception as e:
        out[l]={'outcome':'exception','exc':type(e).__name__,'msg':str(e)[:200]}
t('Integer(1)/Integer(0)', lambda: Integer(1)/Integer(0))
t('S(1)/S(0)', lambda: S(1)/S(0))
t('Rational(1,0)', lambda: Rational(1,0))
t('S(0)/S(0)', lambda: S(0)/S(0))
t('x/0', lambda: x/0)
t('sqrt(-1)', lambda: sqrt(-1))
t('sqrt(-4)', lambda: sqrt(-4))
t('log(0)', lambda: log(0))
t('log(-1)', lambda: log(-1))
t('oo - oo', lambda: oo-oo)
t('0*oo', lambda: S(0)*oo)
t('zoo+1', lambda: zoo+1)
t('zoo*0', lambda: zoo*S(0))
t('nan == nan', lambda: nan==nan)
t('Eq(nan,nan)', lambda: Eq(nan,nan))
t('0**0', lambda: S(0)**0)
t('oo/oo', lambda: oo/oo)
t('limit(sin(x)/x, x, 0)', lambda: limit(sin(x)/x,x,0))
t('(sin(x)/x).subs(x,0)  -- naive substitution', lambda: (sin(x)/x).subs(x,0))
t('Matrix([[1,2],[2,4]]).inv()  singular', lambda: Matrix([[1,2],[2,4]]).inv())
t('Matrix([[1,2],[2,4]]).det()', lambda: Matrix([[1,2],[2,4]]).det())
t('Matrix([[1,2]])*Matrix([[1,2]])  shape mismatch', lambda: Matrix([[1,2]])*Matrix([[1,2]]))
t('Matrix([[1,2]])+Matrix([[1],[2]])  shape mismatch', lambda: Matrix([[1,2]])+Matrix([[1],[2]]))
t('solve(x**2+1, x)', lambda: solve(x**2+1,x))
t('solve(exp(x)+x, x)  -- no closed form', lambda: solve(exp(x)+x,x))
t('integrate(exp(-x**2),(x,-oo,oo))', lambda: integrate(exp(-x**2),(x,-oo,oo)))
t('integrate(exp(exp(x)),x)  -- nonelementary', lambda: str(integrate(exp(exp(x)),x))[:120])
t('Eq(x,y) truth value', lambda: bool(Eq(x,y)))
t('x == y  (structural, not mathematical)', lambda: (x==y))
t('Eq(x**2-1,(x-1)*(x+1))  unevaluated', lambda: Eq(x**2-1,(x-1)*(x+1)))
t('simplify(Eq(x**2-1,(x-1)*(x+1)))', lambda: simplify(Eq(x**2-1,(x-1)*(x+1))))
# rewrite machinery
t("sin(x).rewrite(exp)", lambda: sin(x).rewrite(exp))
t("tan(x).rewrite(sin)", lambda: tan(x).rewrite(sin))
t("gamma(x).rewrite(factorial)", lambda: gamma(x).rewrite(factorial))
# number of rewrite targets discoverable: _eval_rewrite_as_* methods across Function subclasses
import sympy.functions
from sympy.core.function import Function
def allsub(c):
    s=set(); st=[c]
    while st:
        k=st.pop()
        for sub in k.__subclasses__():
            if sub not in s: s.add(sub); st.append(sub)
    return s
rw=0; rwset=set()
for c in allsub(Function):
    for n in dir(c):
        if n.startswith('_eval_rewrite_as_'):
            rw+=1; rwset.add(n[len('_eval_rewrite_as_'):])
out['rewrite_rule_methods_total']=rw
out['distinct_rewrite_targets']=sorted(rwset)
out['distinct_rewrite_targets_count']=len(rwset)
# simplify family
import sympy.simplify as sim
out['sympy_simplify_public_callables']=sorted(n for n in dir(sim) if not n.startswith('_') and callable(getattr(sim,n)))
print(json.dumps(out,indent=1,default=str))
