import json, warnings, importlib, inspect
warnings.filterwarnings('ignore')
import sympy
out={'sympy_version':sympy.__version__}
sim=importlib.import_module('sympy.simplify')
c=sorted(n for n in dir(sim) if not n.startswith('_') and callable(getattr(sim,n)))
out['sympy_simplify_module_public_callables_count']=len(c)
out['sympy_simplify_module_public_callables']=c
# Boolean / logic layer
import sympy.logic.boolalg as ba
bl=sorted(n for n in dir(ba) if isinstance(getattr(ba,n),type) and issubclass(getattr(ba,n), sympy.logic.boolalg.Boolean))
out['boolalg_Boolean_subclasses_count']=len(bl); out['boolalg_Boolean_subclasses']=bl
# SAT solver present?
from sympy.logic.inference import satisfiable
x,y=sympy.symbols('x y')
out['satisfiable(x & ~x)']=repr(satisfiable(sympy.Symbol('p') & ~sympy.Symbol('p')))
out['satisfiable(p | q)']=str(satisfiable(sympy.Symbol('p') | sympy.Symbol('q')))
# quantifiers?
out['has_ForAll']=hasattr(sympy,'ForAll')
out['has_Exists']=hasattr(sympy,'Exists')
out['has_Implies']=hasattr(sympy,'Implies')
out['has_Equivalent']=hasattr(sympy,'Equivalent')
out['has_Proof_object']=hasattr(sympy,'Proof')
out['has_Theorem']=hasattr(sympy,'Theorem')
out['has_prove']=hasattr(sympy,'prove')
# sets / measure-theory
import sympy.sets as ss
out['sets_public']=sorted(n for n in dir(ss) if not n.startswith('_'))
# tensor / shape
from sympy import MatrixSymbol, Symbol
n_,m_=Symbol('n',integer=True,positive=True),Symbol('m',integer=True,positive=True)
A=MatrixSymbol('A',n_,m_); B=MatrixSymbol('B',m_,n_)
out['MatrixSymbol_symbolic_shape']=str((A*B).shape)
try:
    C=MatrixSymbol('C',3,4); D=MatrixSymbol('D',5,6); out['MatrixSymbol_bad_shape_mult']= str(C*D)
except Exception as e:
    out['MatrixSymbol_bad_shape_mult']=f'{type(e).__name__}: {e}'
# printers / backends
import sympy.printing as pr
prs=sorted(n for n in dir(pr) if not n.startswith('_') and callable(getattr(pr,n)))
out['printing_public_callables_count']=len(prs); out['printing_public_callables']=prs
# code generation targets
try:
    from sympy.utilities.lambdify import MODULES
    out['lambdify_modules']=sorted(MODULES.keys())
except Exception as e: out['lambdify_modules']=str(e)
try:
    import sympy.codegen as cg
    out['codegen_has']=sorted(n for n in dir(cg) if not n.startswith('_'))[:40]
except Exception as e: out['codegen_has']=str(e)
try:
    from sympy.utilities.codegen import codegen
    out['codegen_languages']=['C','C89','C99','F95','JULIA','OCTAVE','RUST']
except Exception as e: out['codegen_languages']=str(e)
# core Basic .args / structural contract
e=sympy.sympify('x**2 + 2*x + 1')
out['expr_args_are_the_AST']=str(e.args)
out['expr_func_reconstruction']=str(e.func(*e.args)==e)
out['srepr_example']=sympy.srepr(e)
# assumptions provenance? does an expression carry WHY
out['expr_has_provenance_field']= any(h in dir(e) for h in ('provenance','origin','justification','proof'))
print(json.dumps(out,indent=1,default=str))
